"""One cooperative scheduler with bounded retry, owner-visible health and clean stop.

Scheduling never grants tool authority. The task handler owns the durable state
machine, approvals and fencing; this layer retries tick *polling* only.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class Scheduler:
    def __init__(self, tick_handler: Callable[[], Awaitable[None]],
                 interval_seconds: float = 0.1,
                 on_error: Callable[[str, int], None] | None = None) -> None:
        self._tick_handler = tick_handler
        self._interval_seconds = interval_seconds
        self._on_error = on_error
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._consecutive_failures = 0
        self._total_failures = 0
        self._last_error_type: str | None = None
        self._last_success_at: float | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def health(self) -> dict:
        return {
            "status": ("degraded" if self._consecutive_failures >= 3 or
                       (self._task is not None and self._task.done())
                       else "running" if self.running else "stopped"),
            "running": self.running,
            "consecutive_failures": self._consecutive_failures,
            "total_failures": self._total_failures,
            "last_error_type": self._last_error_type,
            "last_success_at": self._last_success_at,
        }

    async def start(self) -> bool:
        if self.running:
            return False
        if self._task is not None and self._task.done():
            # Consume a previous exception before creating the replacement.
            try:
                self._task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                self._last_error_type = "TaskTerminated"
        self._consecutive_failures = 0
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="kingdom-scheduler")
        return True

    async def stop(self) -> bool:
        task = self._task
        if task is None:
            return False
        self._stop_event.set()
        try:
            await task
        finally:
            self._task = None
        return True

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            delay = self._interval_seconds
            try:
                await self._tick_handler()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._total_failures += 1
                self._consecutive_failures += 1
                # Avoid accidental disclosure of prompts, paths, or credentials.
                self._last_error_type = type(error).__name__
                # Bounded exponential backoff protects low-RAM/slow machines.
                delay = min(30.0, 0.25 * 2 ** min(self._consecutive_failures - 1, 7))
                if self._on_error and self._consecutive_failures in {1, 3, 10}:
                    try:
                        self._on_error(self._last_error_type, self._consecutive_failures)
                    except Exception:
                        pass
            else:
                self._consecutive_failures = 0
                self._last_error_type = None
                self._last_success_at = time.time()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=max(0.001, delay))
            except asyncio.TimeoutError:
                pass
