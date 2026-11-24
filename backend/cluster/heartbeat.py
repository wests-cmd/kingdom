"""Signed peer heartbeat and bounded liveness evaluation.

Every production state transition is conditional on current SQLite trust;
old heartbeat/inventory snapshots cannot undo owner revocation or quarantine.
"""
import time
from typing import Dict, Any, Optional
from backend.cluster.node_registry import node_registry
from backend.events.event_bus import event_bus

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15.0
DEFAULT_TIMEOUT_THRESHOLD_SECONDS = 45.0


class HeartbeatManager:
    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_THRESHOLD_SECONDS):
        self.timeout_seconds = timeout_seconds

    def ping(
        self, node_id: str, health: str = "healthy",
        load_metrics: Optional[Dict[str, Any]] = None,
        apprentice_inventory=None, native_analysis_return=None,
    ) -> Dict[str, Any]:
        if native_analysis_return is not None and type(native_analysis_return) is not bool:
            raise ValueError("Native analysis return support must be an explicit boolean")
        report = None
        if apprentice_inventory is not None:
            from backend.cluster.apprentice_inventory import validate_inventory
            report = validate_inventory(apprentice_inventory)

        now = time.time()
        # A signed RPC establishes the caller identity, but never grants
        # membership. The *current* on-disk state remains authoritative.
        refresh = getattr(node_registry.repo, "refresh_heartbeat", None)
        if not callable(refresh):
            return {"success": False, "error": "Atomic heartbeat storage unavailable"}
        result = refresh(
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
                "new_state": result["node_state"], "reason": "Approved peer reconnected",
                "admin_override": False, "actor": "system",
            }, source="node_registry")
        event_bus.publish("cluster.heartbeat_received", {
            "node_id": node_id, "health": health, "timestamp": now,
        }, source="heartbeat_manager")
        return {"success": True, "node_id": node_id,
                "node_state": result["node_state"], "timestamp": now}

    def evaluate_cluster_health(self) -> Dict[str, Any]:
        now = time.time()
        all_nodes = node_registry.list_nodes()
        degraded_count = disconnected_count = healthy_count = 0
        repo = node_registry.repo
        for node in all_nodes:
            if node.node_state not in {"CONNECTED", "APPROVED"}:
                continue
            elapsed = now - (node.last_heartbeat or 0)
            if elapsed > self.timeout_seconds:
                transition = getattr(repo, "mark_stale_heartbeat", None)
                if not callable(transition):
                    continue  # Unsupported stores cannot safely change trust state.
                record = transition(node.node_id, now - self.timeout_seconds, now)
                if record is None:
                    continue
                disconnected_count += 1
                if record.get("current_task"):
                    event_bus.publish("cluster.task_reassignment_required", {
                        "node_id": node.node_id, "task_id": record["current_task"],
                    }, source="node_registry")
                event_bus.publish("cluster.node_disconnected",
                                  repo.get(node.node_id), source="node_registry")
            elif elapsed > self.timeout_seconds / 2:
                degrade = getattr(repo, "mark_degraded_heartbeat", None)
                if callable(degrade) and degrade(
                    node.node_id,
                    older_than=now - self.timeout_seconds / 2,
                    newer_than=now - self.timeout_seconds,
                    observed_at=now,
                ):
                    degraded_count += 1
            else:
                healthy_count += 1
        return {"healthy": healthy_count, "degraded": degraded_count,
                "disconnected": disconnected_count, "total": len(all_nodes)}


heartbeat_manager = HeartbeatManager()
