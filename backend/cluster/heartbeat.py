import time
from typing import Dict, Any, Optional
from backend.cluster.node_registry import node_registry, NodeState
from backend.events.event_bus import event_bus

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15.0
DEFAULT_TIMEOUT_THRESHOLD_SECONDS = 45.0

class HeartbeatManager:
    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_THRESHOLD_SECONDS):
        self.timeout_seconds = timeout_seconds

    def ping(self, node_id: str, health: str = "healthy", load_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        node = node_registry.get_node(node_id)
        if not node:
            return {"success": False, "error": f"Node {node_id} not found in cluster registry."}

        state = node.get("node_state")
        if state in [NodeState.REVOKED.value, NodeState.REJECTED.value, NodeState.QUARANTINED.value]:
            return {"success": False, "error": f"Node {node_id} is in invalid state {state}."}

        now = time.time()
        node["last_heartbeat"] = now
        node["health"] = health
        if load_metrics:
            meta = node.get("connection_metadata", {})
            meta["load_metrics"] = load_metrics
            node["connection_metadata"] = meta

        # Transition from DISCONNECTED / RECONNECTING back to CONNECTED
        if state in [NodeState.DISCONNECTED.value, NodeState.RECONNECTING.value, NodeState.APPROVED.value]:
            node_registry.update_node_state(node_id, NodeState.CONNECTED)
        else:
            node_registry.repo.save(node)

        event_bus.publish("cluster.heartbeat_received", {
            "node_id": node_id,
            "health": health,
            "timestamp": now
        }, source="heartbeat_manager")

        return {
            "success": True,
            "node_id": node_id,
            "node_state": node.get("node_state"),
            "timestamp": now
        }

    def evaluate_cluster_health(self) -> Dict[str, Any]:
        now = time.time()
        all_nodes = node_registry.list_nodes()
        degraded_count = 0
        disconnected_count = 0
        healthy_count = 0

        for node in all_nodes:
            state = node.get("node_state")
            if state in [NodeState.CONNECTED.value, NodeState.APPROVED.value]:
                elapsed = now - node.get("last_heartbeat", 0)
                if elapsed > self.timeout_seconds:
                    node_registry.update_node_state(node["id"], NodeState.DISCONNECTED, reason="Heartbeat timeout")
                    disconnected_count += 1
                elif elapsed > (self.timeout_seconds / 2):
                    node["health"] = "degraded"
                    node_registry.repo.save(node)
                    degraded_count += 1
                else:
                    healthy_count += 1

        return {
            "healthy": healthy_count,
            "degraded": degraded_count,
            "disconnected": disconnected_count,
            "total": len(all_nodes)
        }

heartbeat_manager = HeartbeatManager()
