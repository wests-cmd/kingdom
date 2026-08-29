"""In-memory task lifecycle management for the first runnable Kingdom core."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


TERMINAL_STATUSES = ("completed", "failed", "cancelled")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._queue: deque[str] = deque()

    def create(self, prompt: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = metadata or {}
        max_attempts = metadata.get("max_attempts", 1)
        if not isinstance(max_attempts, int) or max_attempts < 1 or max_attempts > 5:
            raise ValueError("max_attempts must be an integer from 1 through 5")
        task = {"id": str(uuid4()), "execution_id": str(uuid4()), "prompt": prompt, "metadata": metadata, "status": "queued", "created_at": _timestamp(), "started_at": None, "completed_at": None, "result": None, "error": None, "attempt": 0, "max_attempts": max_attempts}
        self._tasks[task["id"]] = task
        self._queue.append(task["id"])
        return task.copy()

    def get(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        return task.copy() if task else None

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        tasks = self._tasks.values() if status is None else (task for task in self._tasks.values() if task["status"] == status)
        return [task.copy() for task in tasks]

    def claim_next(self) -> dict[str, Any] | None:
        while self._queue:
            task = self._tasks[self._queue.popleft()]
            if task["status"] == "queued":
                task.update(status="running", started_at=_timestamp(), attempt=task["attempt"] + 1)
                return task.copy()
        return None

    def complete(self, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
        task = self._require_running(task_id)
        task.update(status="completed", result=result, completed_at=_timestamp())
        return task.copy()

    def fail(self, task_id: str, error: str) -> dict[str, Any]:
        task = self._require_running(task_id)
        task.update(status="failed", error=error, completed_at=_timestamp())
        return task.copy()

    def retry_or_fail(self, task_id: str, error: str) -> dict[str, Any]:
        task = self._require_running(task_id)
        if task["attempt"] < task["max_attempts"]:
            task.update(status="queued", error=error, started_at=None)
            self._queue.append(task_id)
        else:
            task.update(status="failed", error=error, completed_at=_timestamp())
        return task.copy()

    def cancel(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task["status"] != "queued":
            raise ValueError("Only queued tasks can be cancelled")
        task.update(status="cancelled", completed_at=_timestamp())
        return task.copy()

    def counts(self) -> dict[str, int]:
        return {status: sum(task["status"] == status for task in self._tasks.values()) for status in ("queued", "running", *TERMINAL_STATUSES)}

    def _require_running(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task["status"] != "running":
            raise ValueError("Only running tasks can change to a terminal state")
        return task
