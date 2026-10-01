"""The runnable Kingdom runtime core."""

from __future__ import annotations

from typing import Any
from threading import RLock

from backend.events.event_bus import EventBus
from backend.intelligence.ai_map import AIMap
from backend.memory.service import MemoryService
from backend.models.service import ModelService
from backend.runtime.modes import MODES
from backend.runtime.policy import ExecutionPolicy
from backend.runtime.scheduler import Scheduler
from backend.runtime.tasks import TaskManager
from backend.runtime.resilience import (
    IdempotencyManager,
    CircuitBreakerEngine,
    DeadLetterQueue,
    ReconciliationEngine,
    RateLimiterEngine,
    CircuitState,
)
from backend.security.zero_trust import ZeroTrust
from backend.state import STATE
from backend.swarm.manager import SwarmManager


class RuntimeEngine:
    def __init__(self) -> None:
        self.events = EventBus()
        self.security = ZeroTrust()
        self.tasks = TaskManager()
        self.swarm = SwarmManager(self.events.publish, security=self.security)
        self.models = ModelService()
        self.memory = MemoryService()
        self.maps = AIMap()
        self.scheduler = Scheduler(self._process_next_task)
        self.idempotency = IdempotencyManager()
        self.circuit_breaker = CircuitBreakerEngine()
        self.dlq = DeadLetterQueue()
        self.rate_limiter = RateLimiterEngine()
        self.execution_policy = ExecutionPolicy()
        self.dispatch_lock = RLock()

    async def initialize(self) -> dict[str, Any]:
        return await self.start()

    def reconcile_startup_tasks(self) -> list[dict[str, Any]]:
        running_tasks = self.tasks.list("running")
        recovered = []
        for task in running_tasks:
            rec_task = self.tasks.transition_task(
                task["id"],
                new_status="RECOVERY_REQUIRED",
                updates={"error": "Process restarted while task was running. Reconciled to RECOVERY_REQUIRED."}
            )
            self.events.publish("task.recovery_required", rec_task)
            if task.get("metadata", {}).get("tool") in {"text.analyze@1.0.0", "code.python.analyze@1.0.0"}:
                rec_task = self.tasks.transition_task(task["id"], "queued", {"error": "Restarted idempotent analysis safely requeued"})
                self.events.publish("task.requeued", rec_task)
            recovered.append(rec_task)
        return recovered

    async def start(self) -> dict[str, Any]:
        self.reconcile_startup_tasks()
        started = await self.scheduler.start()
        STATE["running"] = self.scheduler.running
        if started:
            self.events.publish("runtime.started", {"mode": STATE["mode"]})
        return {"status": "started" if started else "already_running", **self.status()}

    async def stop(self) -> dict[str, Any]:
        stopped = await self.scheduler.stop()
        STATE["running"] = self.scheduler.running
        if stopped:
            self.events.publish("runtime.stopped", {"mode": STATE["mode"]})
        return {"status": "stopped" if stopped else "already_stopped", **self.status()}

    def status(self) -> dict[str, Any]:
        return {**STATE, "scheduler_running": self.scheduler.running, "tasks": self.tasks.counts(),
                "autonomy_level": self.execution_policy.get()["level"]}

    def set_autonomy(self, level: int) -> dict[str, Any]:
        previous = self.execution_policy.get()["level"]
        result = self.execution_policy.set(level)
        self.events.publish("runtime.autonomy_changed", {"previous": previous, "level": level, "actor": "owner"})
        return result

    def get_mode(self) -> str:
        return STATE["mode"]

    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in MODES:
            raise ValueError(f"Unsupported runtime mode: {mode}")
        previous = STATE["mode"]
        STATE["mode"] = mode
        self.events.publish("runtime.mode_changed", {"previous": previous, "mode": mode})
        return {"mode": mode}

    def create_task(self, task_type: str = "generic", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        meta = {"type": task_type, "payload": payload or {}}
        prompt = payload.get("query") if isinstance(payload, dict) else str(payload)
        return self.submit_task(prompt or task_type, meta)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self.tasks.get(task_id)

    def submit_task(self, prompt: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        meta = metadata or {}
        actor = meta.get("actor", "system")
        cap = meta.get("capability", "node.execute")

        # Prompt firewall check on task creation
        try:
            self.security.firewall.inspect(prompt)
        except Exception as exc:
            self.security.audit.record(
                actor=actor,
                operation="submit_task",
                capability=cap,
                decision="DENIED",
                reason=f"Task rejected by security firewall: {exc}",
                metadata={"prompt_snippet": prompt[:100]},
            )
            raise ValueError(f"Task rejected by security firewall: {exc}") from exc

        task = self.tasks.create(prompt, meta)
        self.events.publish("task.queued", task)
        return task

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        task = self.tasks.cancel(task_id)
        approval = task.get("metadata", {}).get("approval_id")
        if approval:
            try:
                self.security.approvals.cancel(approval)
            except (KeyError, ValueError):
                pass  # A decided request cannot execute a cancelled task.
        self.events.publish("task.cancelled", task)
        return task

    async def _process_next_task(self) -> None:
        if self.execution_policy.get()["level"] == 0:
            return
        # Modes affect polling cadence, not authority or capability grants.
        self.scheduler._interval_seconds = {"persistent": 0.1, "burst": 0.02, "adaptive": 0.1 if self.tasks.counts().get("queued", 0) else 0.5}.get(STATE["mode"], 0.1)
        self.recover_remote_tasks()
        task = self.tasks.claim_next()
        if task is None:
            return
        self.events.publish("task.running", task)
        try:
            # Zero-trust policy check before executing task
            auth_res = self.authorize_task(task)
            if not auth_res["authorized"] and auth_res.get("approval_id"):
                waiting = self.tasks.transition_task(task["id"], "WAITING_APPROVAL",
                    {"metadata": {**task["metadata"], "approval_id": auth_res["approval_id"]}})
                self.events.publish("task.waiting_approval", waiting)
                return
            if not auth_res["authorized"]:
                raise PermissionError(f"Security policy denied task execution: {auth_res['reason']}")

            result = await self.swarm.execute(task)
            if not result.get("results") or any(r.get("verification", {}).get("state") != "VERIFIED" for r in result["results"]):
                raise RuntimeError("Independent execution evidence is required for completion")
            completed = self.tasks.complete(task["id"], result)
            self.memory.record_task(completed)
            self.events.publish("task.completed", completed)
        except Exception as exc:
            recovered = self.tasks.retry_or_fail(task["id"], str(exc))
            if recovered["status"] == "failed":
                self.memory.record_task(recovered)
                actor_id = task.get("metadata", {}).get("actor", "system")
                self.dlq.push(task_id=task["id"], actor=actor_id, operation=f"Execute task {task['id']}",
                              failure_reason=str(exc), retry_count=recovered.get("retries", 0), metadata=task.get("metadata", {}))
            event_type = "task.requeued" if recovered["status"] == "queued" else "task.failed"
            self.events.publish(event_type, recovered)

    def authorize_task(self, task):
        """Same exact owner approval boundary for local execution and remote dispatch."""
        actor = task["metadata"].get("actor", "system")
        capability = task["metadata"].get("capability", "node.execute")
        approval_id = task["metadata"].get("approval_id")
        return self.security.authorize(
                actor_id=actor,
                token=(self.security.nodes.get_node(actor) or {}).get("token"),
                capability=capability,
                operation=f"Execute task {task['id']}",
                prompt=task["prompt"],
                approval_id=approval_id,
                require_human_approval=self.execution_policy.requires_approval(task),
                parameters={"task_id": task["id"], "prompt": task["prompt"],
                            "metadata": {k: v for k, v in task["metadata"].items() if k != "approval_id"}},
            )

    def dispatch_remote_task(self, task_id, node_id, capability, leases):
        with self.dispatch_lock:
            task = self.tasks.get(task_id)
            if self.execution_policy.get()["level"] == 0 or not task or task["status"].lower() != "queued":
                return None
            auth = self.authorize_task(task)
            if not auth["authorized"]:
                if auth.get("approval_id"):
                    waiting = self.tasks.transition_task(task_id, "WAITING_APPROVAL",
                        {"metadata": {**task["metadata"], "approval_id": auth["approval_id"]}})
                    self.events.publish("task.waiting_approval", waiting)
                return None
            return self.tasks.claim_remote_atomically(task_id, node_id, capability, leases)

    def recover_remote_tasks(self):
        from backend.cluster.task_leasing import task_lease_manager
        from backend.cluster.node_registry import node_registry
        import time
        from backend.cluster.heartbeat import heartbeat_manager
        leases = getattr(self, "lease_manager", task_lease_manager)
        heartbeat_manager.evaluate_cluster_health()
        for task in self.tasks.list("leased"):
            lease = leases.leases.get(task["id"])
            node = node_registry.get_node(task.get("assigned_knight"))
            if not lease or lease.revoked or lease.expires_at <= time.time() or not node or node.node_state not in {"APPROVED", "CONNECTED"}:
                leases.revoke_lease(task["id"])
                self.tasks.transition_task(task["id"], "RECOVERY_REQUIRED")
                recovered = self.tasks.transition_task(task["id"], "queued", {"assigned_knight": None, "lease_id": None,
                    "error": "Remote lease or node became unavailable; safely requeued"})
                self.events.publish("task.requeued", recovered)
