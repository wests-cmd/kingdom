from typing import Dict, Any, Optional
from backend.cluster.node_registry import node_registry, NodeState
from backend.cluster.heartbeat import heartbeat_manager

class AutoConnector:
    def connect(self, node_id: Optional[str] = None) -> Dict[str, Any]:
        if not node_id:
            nodes = node_registry.list_nodes(state=NodeState.APPROVED)
            if not nodes:
                return {"connected": False, "message": "No approved nodes available for auto-connect"}
            node_id = nodes[0]["id"]

        res = heartbeat_manager.ping(node_id)
        return res
