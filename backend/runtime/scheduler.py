"""Cooperative background scheduler for Kingdom runtime work."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class Scheduler:
    def __init__(self, tick_handler: Callable[[], Awaitable[None]], interval_seconds: float = 0.1) -> None:
        self._tick_handler = tick_handler
        self._interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> bool:
        if self.running:
            return False
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="kingdom-scheduler")
        return True

    async def stop(self) -> bool:
        if not self.running:
            return False
        self._stop_event.set()
        assert self._task is not None
        await self._task
        self._task = None
        return True

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self._tick_handler()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_seconds)
            except asyncio.TimeoutError:
                continue
