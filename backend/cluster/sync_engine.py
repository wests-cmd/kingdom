import time
from typing import Dict, Any, List
from backend.cluster.node_registry import node_registry, NodeState

class SyncEngine:
    def synchronize(self) -> Dict[str, Any]:
        nodes = node_registry.list_nodes()
        connected_nodes = [n for n in nodes if n.get("node_state") in [NodeState.CONNECTED.value, NodeState.APPROVED.value]]
        return {
            "status": "synced",
            "active_node_count": len(connected_nodes),
            "total_nodes": len(nodes),
            "timestamp": time.time()
        }
