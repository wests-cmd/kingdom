import time
from typing import Dict, Any, List
from backend.cluster.node_registry import node_registry, NodeState

class SyncEngine:
    def synchronize(self, remote_state: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        nodes = node_registry.list_nodes()
        connected_nodes = [n for n in nodes if n.node_state in [NodeState.CONNECTED.value, NodeState.APPROVED.value]]

        reconciled_count = 0
        if remote_state:
            for r_node in remote_state:
                node_id = r_node.get("id") or r_node.get("node_id")
                local_node_info = node_registry.get_node(node_id)
                if local_node_info:
                    # Deterministic timestamp-based conflict resolution (newer update wins)
                    r_updated = r_node.get("updated_at", 0)
                    l_updated = local_node_info.updated_at
                    if r_updated > l_updated:
                        raw_dict = node_registry.repo.get(node_id)
                        if raw_dict:
                            raw_dict["status"] = r_node.get("status", raw_dict.get("status"))
                            raw_dict["health"] = r_node.get("health", raw_dict.get("health"))
                            raw_dict["node_state"] = r_node.get("node_state", raw_dict.get("node_state"))
                            raw_dict["updated_at"] = r_updated
                            node_registry.repo.save(raw_dict)
                            reconciled_count += 1

        return {
            "status": "synced",
            "reconciled_nodes": reconciled_count,
            "active_node_count": len(connected_nodes),
            "total_nodes": len(nodes),
            "timestamp": time.time()
        }

sync_engine = SyncEngine()
