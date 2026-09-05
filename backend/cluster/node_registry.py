import time
import json
from typing import Optional, Dict, Any, List
from enum import Enum
from backend.storage.repository import knight_repo
from backend.events.event_bus import event_bus

class NodeState(str, Enum):
    DISCOVERED = "DISCOVERED"
    PAIRING = "PAIRING"
    VERIFYING = "VERIFYING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    REVOKED = "REVOKED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"

# Allowed state transitions
VALID_TRANSITIONS = {
    NodeState.DISCOVERED: [NodeState.PAIRING, NodeState.REJECTED, NodeState.QUARANTINED],
    NodeState.PAIRING: [NodeState.VERIFYING, NodeState.REJECTED, NodeState.DISCOVERED],
    NodeState.VERIFYING: [NodeState.PENDING_APPROVAL, NodeState.REJECTED, NodeState.QUARANTINED],
    NodeState.PENDING_APPROVAL: [NodeState.APPROVED, NodeState.REJECTED, NodeState.REVOKED],
    NodeState.APPROVED: [NodeState.CONNECTED, NodeState.DISCONNECTED, NodeState.REVOKED],
    NodeState.CONNECTED: [NodeState.DISCONNECTED, NodeState.RECONNECTING, NodeState.REVOKED, NodeState.QUARANTINED],
    NodeState.DISCONNECTED: [NodeState.RECONNECTING, NodeState.CONNECTED, NodeState.REVOKED],
    NodeState.RECONNECTING: [NodeState.CONNECTED, NodeState.DISCONNECTED, NodeState.REVOKED],
    NodeState.REVOKED: [NodeState.PAIRING, NodeState.PENDING_APPROVAL, NodeState.APPROVED],
    NodeState.REJECTED: [NodeState.PAIRING],
    NodeState.QUARANTINED: [NodeState.REVOKED, NodeState.REJECTED]
}

class NodeRegistry:
    def __init__(self, repository=None):
        self.repo = repository or knight_repo
        self._init_default_knights()

    def _init_default_knights(self):
        default_roles = ["planner", "coder", "researcher", "security"]
        now = time.time()
        for role in default_roles:
            k_id = f"knight-{role}"
            existing = self.repo.get(k_id)
            if not existing:
                k = {
                    "id": k_id,
                    "role": role,
                    "status": "idle",
                    "node_state": NodeState.CONNECTED.value,
                    "capabilities": [f"{role}.execute", "model.inference", "memory.read", "compute"],
                    "granted_capabilities": [f"{role}.execute", "model.inference", "memory.read", "compute"],
                    "current_task": None,
                    "health": "healthy",
                    "is_local": True,
                    "last_heartbeat": now,
                    "public_identity": None,
                    "fingerprint": f"LOCAL:{role.upper()}",
                    "kingdom_id": "KG-MASTER-01"
                }
                self.repo.save(k)

    def register(self, knight_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.register_discovered_node(knight_data)

    def register_discovered_node(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        node_id = node_data["id"]
        now = time.time()
        existing = self.repo.get(node_id)

        node = {
            "id": node_id,
            "role": node_data.get("role", "knight"),
            "status": "idle",
            "node_state": node_data.get("node_state", NodeState.DISCOVERED.value),
            "capabilities": node_data.get("capabilities", []),
            "granted_capabilities": node_data.get("granted_capabilities", []),
            "current_task": None,
            "health": "healthy",
            "is_local": node_data.get("is_local", False),
            "last_heartbeat": now,
            "public_identity": node_data.get("public_identity"),
            "fingerprint": node_data.get("fingerprint"),
            "kingdom_id": node_data.get("kingdom_id"),
            "connection_metadata": node_data.get("connection_metadata", {}),
            "created_at": existing.get("created_at", now) if existing else now
        }
        self.repo.save(node)
        event_bus.publish("cluster.node_registered", node, source="node_registry")
        return node

    def update_node_state(self, node_id: str, new_state: NodeState, reason: str = "") -> Optional[Dict[str, Any]]:
        node = self.repo.get(node_id)
        if not node:
            return None

        current_state_str = node.get("node_state", NodeState.DISCOVERED.value)
        try:
            current_state = NodeState(current_state_str)
        except ValueError:
            current_state = NodeState.DISCOVERED

        # Validate state transition if applicable
        if new_state != current_state and new_state not in VALID_TRANSITIONS.get(current_state, []):
            raise ValueError(f"Invalid state transition for node {node_id}: {current_state.value} -> {new_state.value}")

        node["node_state"] = new_state.value
        node["updated_at"] = time.time()

        if new_state == NodeState.REVOKED:
            node["status"] = "offline"
            node["health"] = "unhealthy"

        self.repo.save(node)
        event_bus.publish("cluster.node_state_changed", {
            "node_id": node_id,
            "old_state": current_state.value,
            "new_state": new_state.value,
            "reason": reason
        }, source="node_registry")
        return node

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.get(node_id)

    def get_knight(self, knight_id: str) -> Optional[Dict[str, Any]]:
        return self.get_node(knight_id)

    def list_nodes(self, state: Optional[NodeState] = None) -> List[Dict[str, Any]]:
        self.check_stale_heartbeats()
        all_nodes = self.repo.list_all()
        if state:
            return [n for n in all_nodes if n.get("node_state") == state.value]
        return all_nodes

    def list_knights(self) -> List[Dict[str, Any]]:
        return self.list_nodes()

    def heartbeat(self, node_id: str, health: str = "healthy") -> Optional[Dict[str, Any]]:
        node = self.repo.get(node_id)
        if not node:
            return None

        now = time.time()
        node["last_heartbeat"] = now
        node["health"] = health

        if node.get("node_state") in [NodeState.DISCONNECTED.value, NodeState.RECONNECTING.value]:
            node["node_state"] = NodeState.CONNECTED.value

        if node.get("status") == "offline":
            node["status"] = "idle"

        self.repo.save(node)
        event_bus.publish("cluster.heartbeat", node, source="node_registry")
        return node

    def check_stale_heartbeats(self, timeout_seconds: float = 60.0):
        now = time.time()
        nodes = self.repo.list_all()
        for k in nodes:
            state = k.get("node_state", NodeState.CONNECTED.value)
            if state in [NodeState.CONNECTED.value, NodeState.APPROVED.value]:
                if (now - k.get("last_heartbeat", 0)) > timeout_seconds:
                    k["node_state"] = NodeState.DISCONNECTED.value
                    k["health"] = "unhealthy"
                    self.repo.save(k)
                    event_bus.publish("cluster.node_disconnected", k, source="node_registry")

node_registry = NodeRegistry()
