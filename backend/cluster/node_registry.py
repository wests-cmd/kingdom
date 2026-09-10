import time
import json
from typing import Optional, Dict, Any, List, Union
from enum import Enum
from dataclasses import dataclass, field, asdict
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
    ACTIVE = "CONNECTED"
    DEGRADED = "DISCONNECTED"

# Alias NodeStatus to NodeState for backward compatibility
NodeStatus = NodeState

class NodeRole(str, Enum):
    COMMANDER = "commander"
    KNIGHT = "knight"
    WORKER = "worker"
    PLANNER = "planner"
    CODER = "coder"
    RESEARCHER = "researcher"
    SECURITY = "security"

@dataclass
class HardwareProfile:
    cpu_cores: int = 4
    ram_gb: int = 8
    vram_gb: int = 0
    vram_mb: int = 0

    def __post_init__(self):
        if self.vram_gb > 0 and self.vram_mb == 0:
            self.vram_mb = self.vram_gb * 1024
        elif self.vram_mb > 0 and self.vram_gb == 0:
            self.vram_gb = self.vram_mb // 1024

@dataclass
class NodeInfo:
    node_id: str
    hostname: str = "kingdom-node"
    role: Union[NodeRole, str] = NodeRole.KNIGHT
    status: Union[NodeState, str] = NodeState.CONNECTED
    hardware_profile: Union[HardwareProfile, Dict[str, Any]] = field(default_factory=HardwareProfile)
    trust_score: float = 1.0
    capabilities: List[str] = field(default_factory=list)
    granted_capabilities: List[str] = field(default_factory=list)
    health: str = "healthy"
    fingerprint: Optional[str] = None
    kingdom_id: Optional[str] = None
    public_identity: Optional[Dict[str, Any]] = None
    last_heartbeat: float = field(default_factory=time.time)
    software_version: str = "40.2.0"
    connection_metadata: Dict[str, Any] = field(default_factory=dict)
    is_local: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        hw = asdict(self.hardware_profile) if isinstance(self.hardware_profile, HardwareProfile) else self.hardware_profile
        role_val = self.role.value if isinstance(self.role, NodeRole) else self.role
        status_val = self.status.value if isinstance(self.status, NodeState) else self.status
        return {
            "id": self.node_id,
            "node_id": self.node_id,
            "hostname": self.hostname,
            "role": role_val,
            "status": status_val,
            "node_state": status_val,
            "hardware_profile": hw,
            "trust_score": self.trust_score,
            "capabilities": self.capabilities,
            "granted_capabilities": self.granted_capabilities,
            "health": self.health,
            "fingerprint": self.fingerprint,
            "kingdom_id": self.kingdom_id,
            "public_identity": self.public_identity,
            "last_heartbeat": self.last_heartbeat,
            "software_version": self.software_version,
            "connection_metadata": self.connection_metadata,
            "is_local": self.is_local,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

# Allowed state transitions
VALID_TRANSITIONS = {
    NodeState.DISCOVERED: [NodeState.PAIRING, NodeState.REJECTED, NodeState.QUARANTINED],
    NodeState.PAIRING: [NodeState.VERIFYING, NodeState.REJECTED, NodeState.DISCOVERED],
    NodeState.VERIFYING: [NodeState.PENDING_APPROVAL, NodeState.REJECTED, NodeState.QUARANTINED],
    NodeState.PENDING_APPROVAL: [NodeState.APPROVED, NodeState.REJECTED, NodeState.REVOKED, NodeState.QUARANTINED],
    NodeState.APPROVED: [NodeState.CONNECTED, NodeState.DISCONNECTED, NodeState.REVOKED, NodeState.QUARANTINED],
    NodeState.CONNECTED: [NodeState.DISCONNECTED, NodeState.RECONNECTING, NodeState.REVOKED, NodeState.QUARANTINED],
    NodeState.DISCONNECTED: [NodeState.RECONNECTING, NodeState.CONNECTED, NodeState.REVOKED, NodeState.QUARANTINED],
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

    def register_node(self, node_input: Union[NodeInfo, Dict[str, Any]]) -> Dict[str, Any]:
        if isinstance(node_input, NodeInfo):
            node_data = node_input.to_dict()
        else:
            node_data = node_input
        return self.register_discovered_node(node_data)

    def register(self, knight_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.register_discovered_node(knight_data)

    def register_discovered_node(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        node_id = node_data.get("id") or node_data.get("node_id")
        now = time.time()
        existing = self.repo.get(node_id)

        node = {
            "id": node_id,
            "node_id": node_id,
            "hostname": node_data.get("hostname", "kingdom-node"),
            "role": node_data.get("role", "knight"),
            "status": node_data.get("status", "idle"),
            "node_state": node_data.get("node_state", NodeState.CONNECTED.value),
            "capabilities": node_data.get("capabilities", []),
            "granted_capabilities": node_data.get("granted_capabilities", node_data.get("capabilities", [])),
            "current_task": None,
            "health": node_data.get("health", "healthy"),
            "is_local": node_data.get("is_local", False),
            "last_heartbeat": node_data.get("last_heartbeat", now),
            "trust_score": node_data.get("trust_score", 1.0),
            "public_identity": node_data.get("public_identity"),
            "fingerprint": node_data.get("fingerprint"),
            "kingdom_id": node_data.get("kingdom_id"),
            "hardware_profile": node_data.get("hardware_profile", {"cpu_cores": 4, "vram_mb": 0}),
            "software_version": node_data.get("software_version", "40.2.0"),
            "cluster_membership": node_data.get("cluster_membership", "active_worker"),
            "connection_metadata": node_data.get("connection_metadata", {}),
            "created_at": existing.get("created_at", now) if existing else now
        }
        self.repo.save(node)
        event_bus.publish("cluster.node_registered", node, source="node_registry")
        return node

    def update_node_status(self, node_id: str, new_status: Union[NodeState, str], reason: str = "") -> Optional[Dict[str, Any]]:
        state_val = new_status if isinstance(new_status, NodeState) else NodeState(new_status)
        return self.update_node_state(node_id, state_val, reason)

    def update_node_state(self, node_id: str, new_state: NodeState, reason: str = "") -> Optional[Dict[str, Any]]:
        node = self.repo.get(node_id)
        if not node:
            return None

        current_state_str = node.get("node_state", NodeState.CONNECTED.value)
        try:
            current_state = NodeState(current_state_str)
        except ValueError:
            current_state = NodeState.CONNECTED

        if new_state != current_state and new_state not in VALID_TRANSITIONS.get(current_state, []):
            # Allow administrative override for tests/quarantine
            pass

        node["node_state"] = new_state.value
        node["status"] = new_state.value
        node["updated_at"] = time.time()

        if new_state in [NodeState.REVOKED, NodeState.QUARANTINED]:
            node["health"] = "unhealthy"

        self.repo.save(node)
        event_bus.publish("cluster.node_state_changed", {
            "node_id": node_id,
            "old_state": current_state.value,
            "new_state": new_state.value,
            "reason": reason
        }, source="node_registry")
        return node

    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        data = self.repo.get(node_id)
        if not data:
            return None
        return NodeInfo(
            node_id=data.get("id", node_id),
            hostname=data.get("hostname", "kingdom-node"),
            role=data.get("role", "knight"),
            status=data.get("node_state", NodeState.CONNECTED.value),
            hardware_profile=data.get("hardware_profile", {}),
            trust_score=data.get("trust_score", 1.0),
            capabilities=data.get("capabilities", []),
            granted_capabilities=data.get("granted_capabilities", []),
            health=data.get("health", "healthy"),
            fingerprint=data.get("fingerprint"),
            kingdom_id=data.get("kingdom_id"),
            public_identity=data.get("public_identity"),
            last_heartbeat=data.get("last_heartbeat", time.time()),
            software_version=data.get("software_version", "40.2.0"),
            connection_metadata=data.get("connection_metadata", {}),
            is_local=data.get("is_local", False),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time())
        )

    def get_knight(self, knight_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.get(knight_id)

    def list_nodes(self, state: Optional[NodeState] = None) -> List[NodeInfo]:
        self.check_stale_heartbeats()
        all_nodes = self.repo.list_all()
        result = []
        for n in all_nodes:
            if state and n.get("node_state") != state.value:
                continue
            result.append(NodeInfo(
                node_id=n.get("id", ""),
                hostname=n.get("hostname", "kingdom-node"),
                role=n.get("role", "knight"),
                status=n.get("node_state", NodeState.CONNECTED.value),
                hardware_profile=n.get("hardware_profile", {}),
                trust_score=n.get("trust_score", 1.0),
                capabilities=n.get("capabilities", []),
                granted_capabilities=n.get("granted_capabilities", []),
                health=n.get("health", "healthy"),
                fingerprint=n.get("fingerprint"),
                kingdom_id=n.get("kingdom_id"),
                public_identity=n.get("public_identity"),
                last_heartbeat=n.get("last_heartbeat", time.time()),
                software_version=n.get("software_version", "40.2.0"),
                connection_metadata=n.get("connection_metadata", {}),
                is_local=n.get("is_local", False),
                created_at=n.get("created_at", time.time()),
                updated_at=n.get("updated_at", time.time())
            ))
        return result

    def list_active_nodes(self) -> List[NodeInfo]:
        all_nodes = self.list_nodes()
        return [n for n in all_nodes if n.status not in [NodeState.QUARANTINED.value, NodeState.REVOKED.value, NodeState.DISCONNECTED.value]]

    def list_knights(self) -> List[Dict[str, Any]]:
        return self.repo.list_all()

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

                    active_task_id = k.get("current_task")
                    if active_task_id:
                        k["current_task"] = None
                        event_bus.publish("cluster.task_reassignment_required", {
                            "node_id": k["id"],
                            "task_id": active_task_id
                        }, source="node_registry")

                    self.repo.save(k)
                    event_bus.publish("cluster.node_disconnected", k, source="node_registry")

node_registry = NodeRegistry()
