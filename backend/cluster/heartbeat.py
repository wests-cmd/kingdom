import time
from typing import Dict, Any, Optional
from backend.cluster.node_registry import node_registry, NodeState
from backend.events.event_bus import event_bus

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15.0
DEFAULT_TIMEOUT_THRESHOLD_SECONDS = 45.0

class HeartbeatManager:
    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_THRESHOLD_SECONDS):
        self.timeout_seconds = timeout_seconds

    def ping(self, node_id: str, health: str = "healthy", load_metrics: Optional[Dict[str, Any]] = None, apprentice_inventory=None, native_analysis_return=None) -> Dict[str, Any]:
        if native_analysis_return is not None and type(native_analysis_return) is not bool:
            raise ValueError('Native analysis return support must be an explicit boolean')
        report = None
        if apprentice_inventory is not None:
            from backend.cluster.apprentice_inventory import validate_inventory
            report = validate_inventory(apprentice_inventory)
        now = time.time()

        # The database, not a node snapshot taken before an HTTP await,
        # decides whether the identity is still approved. This one transaction
        # updates liveness fields only: it cannot overwrite grants, fingerprint
        # or a concurrent owner revocation with stale NodeInfo data.
        result = node_registry.repo.refresh_heartbeat(
            node_id, now=now, health=health, load_metrics=load_metrics,
            apprentice_inventory=report,
            native_analysis_return=native_analysis_return,
        )
        if result is None:
            return {"success": False, "error": f"Node {node_id} not found in cluster registry."}
        if not result["accepted"]:
            return {"success": False,
                    "error": f"Node {node_id} is not approved for heartbeat in state {result['node_state']}."}

        if result["transitioned"]:
            event_bus.publish("cluster.node_state_changed", {
                "node_id": node_id, "old_state": result["previous_state"],
                "new_state": result["node_state"], "reason": "",
                "admin_override": False, "actor": "system",
            }, source="node_registry")
        event_bus.publish("cluster.heartbeat_received", {
            "node_id": node_id, "health": health, "timestamp": now,
        }, source="heartbeat_manager")
        return {
            "success": True, "node_id": node_id,
            "node_state": result["node_state"], "timestamp": now,
        }

    def evaluate_cluster_health(self) -> Dict[str, Any]:
        now = time.time()
        all_nodes = node_registry.list_nodes()
        degraded_count = 0
        disconnected_count = 0
        healthy_count = 0

        for node in all_nodes:
            state_val = node.node_state
            if state_val in [NodeState.CONNECTED.value, NodeState.APPROVED.value]:
                elapsed = now - (node.last_heartbeat or 0)
                if elapsed > self.timeout_seconds:
                    node_registry.update_node_state(node.node_id, NodeState.DISCONNECTED, reason="Heartbeat timeout")
                    disconnected_count += 1
                elif elapsed > (self.timeout_seconds / 2):
                    node.health = "degraded"
                    node_registry.repo.save(node.to_dict())
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
