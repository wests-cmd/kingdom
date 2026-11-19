"""The one owner of Kingdom's background-service startup and shutdown.

No authority to create tasks or grant permissions lives here. Individual services
keep their existing policy enforcement and durable checkpoints. The supervisor
only manages process-local lifecycle and makes abnormal exits observable.
"""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any


class RuntimeServiceSupervisor:
    def __init__(self, engine: Any, runners: Mapping[str, Any], *, shutdown_extra=()):
        if not runners or len(set(runners)) != len(runners):
            raise ValueError("Supply distinct named runtime services")
        self.engine = engine
        self.runners = dict(runners)
        self.shutdown_extra = tuple(shutdown_extra)
        self._started: list[tuple[str, Any]] = []
        self._lock = asyncio.Lock()
        self.state = "stopped"
        self.last_error_type: str | None = None
        self.cleanup_errors: list[str] = []

    def status(self) -> dict:
        services = {}
        for name, runner in self.runners.items():
            task = getattr(runner, "task", None)
            services[name] = "running" if task is not None and not task.done() else "stopped"
        service_health = all(services[name] == "running" for name in self.runners)
        scheduler = self.engine.scheduler.health()
        healthy = (self.state == "running" and service_health and
                   scheduler["status"] != "degraded")
        state = "degraded" if self.state == "running" and not healthy else self.state
        return {
            "state": state,
            "healthy": healthy,
            "services": services,
            "scheduler": scheduler,
            "last_error_type": self.last_error_type,
            "cleanup_errors": list(self.cleanup_errors),
        }

    async def start(self) -> None:
        async with self._lock:
            if self.state == "running":
                if not self.status()["healthy"]:
                    raise RuntimeError("Kingdom background supervision is degraded")
                return
            if self._started:
                raise RuntimeError("Previous Kingdom service cleanup is incomplete")
            self.state = "starting"
            self.last_error_type = None
            self.cleanup_errors = []
            try:
                if await asyncio.to_thread(self.engine.autostart_requested):
                    await self.engine.start(persist=False)
                for name, runner in self.runners.items():
                    # Register before start: a service can spawn a task and then fail.
                    self._started.append((name, runner))
                    await runner.start()
                    task = getattr(runner, "task", None)
                    if task is None or task.done():
                        raise RuntimeError("Background service did not start: " + name)
                self.state = "running"
            except BaseException as error:
                self.last_error_type = type(error).__name__
                self.state = "failed"
                await self._cleanup()
                raise

    async def _cleanup(self) -> None:
        # Independently attempt every cleanup: a failing stop must not strand
        # later services or leave the runtime scheduler executing work.
        for runner in self.shutdown_extra:
            try:
                await runner.stop()
            except Exception as error:
                self.cleanup_errors.append(type(error).__name__)
        for _, runner in reversed(self._started):
            try:
                await runner.stop()
            except Exception as error:
                self.cleanup_errors.append(type(error).__name__)
        self._started.clear()
        try:
            await self.engine.stop(persist=False)
        except Exception as error:
            self.cleanup_errors.append(type(error).__name__)

    async def stop(self) -> None:
        async with self._lock:
            if self.state == "stopped" and not self._started:
                return
            self.state = "stopping"
            await self._cleanup()
            self.state = "failed" if self.cleanup_errors else "stopped"
