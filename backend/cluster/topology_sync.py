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
                    "id": n.node_id,
                    "state": n.node_state,
                    "role": n.role.value if hasattr(n.role, "value") else str(n.role),
                    "capabilities": n.granted_capabilities
                }
                for n in nodes
            ],
            "timestamp": time.time()
        }
        return topology
