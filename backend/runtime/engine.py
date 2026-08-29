"""The runnable Kingdom runtime core."""

from __future__ import annotations

from typing import Any

from backend.events.event_bus import EventBus
from backend.runtime.scheduler import Scheduler
from backend.runtime.tasks import TaskManager
from backend.runtime.modes import MODES
from backend.state import STATE
from backend.swarm.engine import SwarmEngine


class RuntimeEngine:
    def __init__(self) -> None:
        self.events = EventBus()
        self.tasks = TaskManager()
        self.swarm = SwarmEngine()
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

    def submit_task(self, prompt: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        task = self.tasks.create(prompt, metadata)
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
            self.swarm.submit_task(task["prompt"])
            completed = self.tasks.complete(task["id"], self.swarm.process() or {})
            self.events.publish("task.completed", completed)
        except Exception as exc:
            recovered = self.tasks.retry_or_fail(task["id"], str(exc))
            event_type = "task.requeued" if recovered["status"] == "queued" else "task.failed"
            self.events.publish(event_type, recovered)
