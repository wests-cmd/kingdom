import time
from typing import Dict, Any, List
from backend.cluster.node_registry import node_registry

class TopologySync:
    def sync(self) -> Dict[str, Any]:
        nodes = node_registry.list_nodes()
        topology = {
            "commander": "KG-MASTER-01",
            "knights": [
                {
                    "id": n["id"],
                    "state": n.get("node_state"),
                    "role": n.get("role"),
                    "capabilities": n.get("granted_capabilities", [])
                }
                for n in nodes
            ],
            "timestamp": time.time()
        }
        return topology
