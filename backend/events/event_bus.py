"""A small in-process event bus used by the runtime and WebSocket API."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class EventBus:
    """Publish runtime events to connected consumers and retain recent history."""

    def __init__(self, history_size: int = 200) -> None:
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {"id": str(uuid4()), "type": event_type, "timestamp": datetime.now(timezone.utc).isoformat(), "data": data or {}}
        self._history.append(event)
        for queue in tuple(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
        return event

    def subscribe(self, max_queue_size: int = 100) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._history)[-limit:] if limit > 0 else []
