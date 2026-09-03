"""A small in-process event bus used by the runtime and WebSocket API."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from backend.storage.repository import event_repo


class EventBus:
    """Publish runtime events to connected consumers and retain recent history."""

    def __init__(self, history_size: int = 200) -> None:
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._callbacks: set[Callable[[dict[str, Any]], None]] = set()

    def publish(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        source: str = "system",
        task_id: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        event_id = str(uuid4())
        payload = data or {}
        if isinstance(data, dict) and "payload" in data and len(data) == 1:
            payload = data["payload"]

        event = {
            "id": event_id,
            "event_id": event_id,
            "type": event_type,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "task_id": task_id,
            "data": payload,
            "payload": payload,
            **extra,
        }
        self._history.append(event)
        try:
            event_repo.save(event)
        except Exception:
            pass

        for callback in tuple(self._callbacks):
            try:
                callback(event)
            except Exception:
                pass

        for queue in tuple(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
        return event

    def subscribe(
        self,
        consumer_or_max_size: Callable[[dict[str, Any]], None] | int = 100,
    ) -> asyncio.Queue[dict[str, Any]] | None:
        if callable(consumer_or_max_size):
            self._callbacks.add(consumer_or_max_size)
            return None
        max_size = consumer_or_max_size if isinstance(consumer_or_max_size, int) else 100
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, consumer_or_queue: Any) -> None:
        if callable(consumer_or_queue):
            self._callbacks.discard(consumer_or_queue)
        else:
            self._subscribers.discard(consumer_or_queue)

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._history)[-limit:] if limit > 0 else []

    def get_events(self, task_id: str | None = None, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        try:
            db_events = event_repo.query(task_id=task_id, event_type=event_type, limit=limit)
            if db_events:
                return db_events
        except Exception:
            pass

        filtered = []
        for evt in reversed(self._history):
            if task_id and evt.get("task_id") != task_id:
                continue
            if event_type and evt.get("event_type") != event_type and evt.get("type") != event_type:
                continue
            filtered.append(evt)
            if len(filtered) >= limit:
                break
        return filtered


event_bus = EventBus()
