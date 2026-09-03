"""The runnable Kingdom runtime core."""

from __future__ import annotations

from typing import Any

from backend.events.event_bus import EventBus
from backend.intelligence.ai_map import AIMap
from backend.memory.service import MemoryService
from backend.models.service import ModelService
from backend.runtime.modes import MODES
from backend.runtime.scheduler import Scheduler
from backend.runtime.tasks import TaskManager
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

    async def initialize(self) -> dict[str, Any]:
        return await self.start()

    async def start(self) -> dict[str, Any]:
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
        return {**STATE, "scheduler_running": self.scheduler.running, "tasks": self.tasks.counts()}

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
        self.events.publish("task.cancelled", task)
        return task

    async def _process_next_task(self) -> None:
        task = self.tasks.claim_next()
        if task is None:
            return
        self.events.publish("task.running", task)
        try:
            actor = task["metadata"].get("actor", "system")
            capability = task["metadata"].get("capability", "node.execute")
            approval_id = task["metadata"].get("approval_id")

            # Zero-trust policy check before executing task
            auth_res = self.security.authorize(
                actor_id=actor,
                capability=capability,
                operation=f"Execute task {task['id']}",
                prompt=task["prompt"],
                approval_id=approval_id,
                parameters=task["metadata"],
            )
            if not auth_res["authorized"]:
                raise PermissionError(f"Security policy denied task execution: {auth_res['reason']}")

            result = await self.swarm.execute(task)
            provider = task["metadata"].get("model_provider")
            if provider:
                model_result = await self.models.generate(task["prompt"], task["metadata"].get("model"), provider)
                result["model"] = model_result
                self.events.publish("model.completed", {"task_id": task["id"], **model_result})
            completed = self.tasks.complete(task["id"], result)
            self.memory.record_task(completed)
            self.events.publish("task.completed", completed)
        except Exception as exc:
            recovered = self.tasks.retry_or_fail(task["id"], str(exc))
            if recovered["status"] == "failed":
                self.memory.record_task(recovered)
            event_type = "task.requeued" if recovered["status"] == "queued" else "task.failed"
            self.events.publish(event_type, recovered)
