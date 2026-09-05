from typing import List, Dict, Any, Optional
from backend.cluster.node_registry import node_registry, NodeState
from backend.events.event_bus import event_bus

SUPPORTED_CAPABILITIES = [
    "compute",
    "gpu",
    "storage_read",
    "storage_write",
    "network",
    "tool_execution",
    "memory_access",
    "ai_map_access"
]

class CapabilityAuthorizer:
    @staticmethod
    def approve_node_and_capabilities(node_id: str, granted_capabilities: List[str]) -> Optional[Dict[str, Any]]:
        node = node_registry.get_node(node_id)
        if not node:
            return None

        valid_granted = [cap for cap in granted_capabilities if cap in SUPPORTED_CAPABILITIES or cap.endswith(".execute")]

        node["granted_capabilities"] = valid_granted
        node_registry.repo.save(node)
        updated = node_registry.update_node_state(node_id, NodeState.APPROVED)

        event_bus.publish("cluster.node_approved", {
            "node_id": node_id,
            "granted_capabilities": valid_granted
        }, source="capability_authorizer")
        return updated

    @staticmethod
    def is_capability_granted(node_id: str, capability: str) -> bool:
        node = node_registry.get_node(node_id)
        if not node:
            return False

        state = node.get("node_state")
        if state not in [NodeState.APPROVED.value, NodeState.CONNECTED.value]:
            return False

        granted = node.get("granted_capabilities", [])
        return capability in granted

    @staticmethod
    def revoke_node(node_id: str, reason: str = "Admin revocation") -> Optional[Dict[str, Any]]:
        node = node_registry.get_node(node_id)
        if not node:
            return None

        node["granted_capabilities"] = []
        node_registry.repo.save(node)
        updated = node_registry.update_node_state(node_id, NodeState.REVOKED, reason=reason)

        event_bus.publish("cluster.node_revoked", {
            "node_id": node_id,
            "reason": reason
        }, source="capability_authorizer")
        return updated

    @staticmethod
    def update_capabilities(node_id: str, granted_capabilities: List[str]) -> Optional[Dict[str, Any]]:
        node = node_registry.get_node(node_id)
        if not node:
            return None

        valid_granted = [cap for cap in granted_capabilities if cap in SUPPORTED_CAPABILITIES or cap.endswith(".execute")]
        node["granted_capabilities"] = valid_granted
        node_registry.repo.save(node)

        event_bus.publish("cluster.capabilities_updated", {
            "node_id": node_id,
            "granted_capabilities": valid_granted
        }, source="capability_authorizer")
        return node

capability_authorizer = CapabilityAuthorizer()
