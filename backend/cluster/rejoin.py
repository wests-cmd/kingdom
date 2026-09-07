from typing import Dict, Any
from backend.cluster.node_registry import node_registry, NodeState
from backend.cluster.heartbeat import heartbeat_manager

class RejoinManager:
    def rejoin(self, node_id: str) -> Dict[str, Any]:
        node = node_registry.get_node(node_id)
        if not node:
            return {"rejoined": False, "error": f"Node {node_id} not registered"}

        state = node.get("node_state")
        if state in [NodeState.REVOKED.value, NodeState.REJECTED.value, NodeState.QUARANTINED.value]:
            return {"rejoined": False, "error": f"Cannot rejoin node in state {state}"}

        res = heartbeat_manager.ping(node_id)
        return {"rejoined": res.get("success", False), "node_state": res.get("node_state")}
