"""Durable task lifecycle management backed by persistent storage."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.storage.repository import task_repo

TERMINAL_STATUSES = ("completed", "failed", "cancelled", "succeeded", "SUCCEEDED", "COMPLETED", "FAILED", "CANCELLED")

VALID_TASK_TRANSITIONS = {
    "CREATED": ["VALIDATING", "WAITING_AUTHORIZATION", "WAITING_APPROVAL", "QUEUED", "BLOCKED", "CANCELLED"],
    "VALIDATING": ["WAITING_AUTHORIZATION", "WAITING_APPROVAL", "QUEUED", "BLOCKED", "CANCELLED"],
    "WAITING_AUTHORIZATION": ["AUTHORIZED", "BLOCKED", "CANCELLED"],
    "WAITING_APPROVAL": ["APPROVED", "DENIED", "QUEUED", "BLOCKED", "CANCELLED"],
    "AUTHORIZED": ["QUEUED", "LEASED", "RUNNING", "CANCELLED"],
    "QUEUED": ["LEASED", "RUNNING", "CANCELLED", "EXPIRED"],
    "LEASED": ["RUNNING", "CANCELLED", "EXPIRED", "RECOVERY_REQUIRED"],
    "RUNNING": ["VERIFYING", "SUCCEEDED", "COMPLETED", "FAILED", "QUEUED", "RECOVERY_REQUIRED", "CANCELLED"],
    "VERIFYING": ["SUCCEEDED", "COMPLETED", "FAILED", "RECOVERY_REQUIRED"],
    "SUCCEEDED": [],
    "COMPLETED": [],
    "FAILED": ["QUEUED", "RECOVERY_REQUIRED"],
    "CANCEL_REQUESTED": ["CANCELLED"],
    "CANCELLED": [],
    "EXPIRED": ["QUEUED", "RECOVERY_REQUIRED"],
    "BLOCKED": ["QUEUED", "CANCELLED"],
    "RECOVERY_REQUIRED": ["QUEUED", "FAILED", "CANCELLED", "UNKNOWN"],
    "UNKNOWN": ["QUEUED", "FAILED", "CANCELLED"]
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskManager:
    def __init__(self, repository=None) -> None:
        self.repo = repository or task_repo
        self._tasks: dict[str, dict[str, Any]] = {}
        self._queue: deque[str] = deque()
        self.load_persisted_tasks()

    def clear(self) -> None:
        self._tasks.clear()
        self._queue.clear()

    def load_persisted_tasks(self) -> None:
        try:
            db_tasks = self.repo.list_all(limit=500)
            for t in db_tasks:
                self._tasks[t["id"]] = t
                if t.get("status") in ["queued", "QUEUED"]:
                    if t["id"] not in self._queue:
                        self._queue.append(t["id"])
        except Exception:
            pass

    def create(self, prompt: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = metadata or {}
        max_attempts = metadata.get("max_attempts", 1)
        if not isinstance(max_attempts, int) or max_attempts < 1 or max_attempts > 5:
            raise ValueError("max_attempts must be an integer from 1 through 5")

        task_id = str(uuid4())
        task = {
            "id": task_id,
            "execution_id": str(uuid4()),
            "prompt": prompt,
            "input": {"prompt": prompt},
            "metadata": metadata,
            "type": metadata.get("type", "generic"),
            "status": "queued",
            "assigned_knight": metadata.get("assigned_knight"),
            "cancellation_requested": False,
            "created_at": _timestamp(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "attempt": 0,
            "max_attempts": max_attempts,
            "version": 1,
            "fencing_token": 0
        }
        self._tasks[task_id] = task
        self._queue.append(task_id)
        self.repo.save(task)
        return task.copy()

    def get(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        if not task:
            task = self.repo.get(task_id)
            if task:
                self._tasks[task_id] = task
        return task.copy() if task else None

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            return [t.copy() for t in self._tasks.values()]
        return [t.copy() for t in self._tasks.values() if t["status"] == status or t["status"].upper() == status.upper()]

    def transition_task(self, task_id: str, new_status: str, updates: dict[str, Any] | None = None) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if not task:
            task = self.repo.get(task_id)
            if not task:
                raise KeyError(f"Task '{task_id}' not found.")
            self._tasks[task_id] = task

        cur_status_upper = task["status"].upper()
        new_status_upper = new_status.upper()

        if cur_status_upper != new_status_upper:
            allowed = VALID_TASK_TRANSITIONS.get(cur_status_upper, [])
            if new_status_upper not in allowed:
                raise ValueError(f"Invalid task state transition from '{cur_status_upper}' to '{new_status_upper}'.")

        task["status"] = new_status.lower() if new_status.lower() in ["queued", "leased", "running", "completed", "failed", "cancelled"] else new_status
        task["version"] = task.get("version", 1) + 1
        if updates:
            task.update(updates)

        self.repo.save(task)
        return task.copy()

    def claim_next(self) -> dict[str, Any] | None:
        while self._queue:
            task_id = self._queue.popleft()
            task = self._tasks.get(task_id)
            if task and task["status"] in ["queued", "QUEUED"]:
                task.update(status="running", started_at=_timestamp(), attempt=task["attempt"] + 1)
                task["version"] = task.get("version", 1) + 1
                self.repo.save(task)
                return task.copy()
        return None

    def complete(self, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
        task = self._require_running(task_id)
        task.update(status="completed", result=result, completed_at=_timestamp())
        task["version"] = task.get("version", 1) + 1
        self.repo.save(task)
        return task.copy()

    def fail(self, task_id: str, error: str) -> dict[str, Any]:
        task = self._require_running(task_id)
        task.update(status="failed", error=error, completed_at=_timestamp())
        task["version"] = task.get("version", 1) + 1
        self.repo.save(task)
        return task.copy()

    def retry_or_fail(self, task_id: str, error: str) -> dict[str, Any]:
        task = self._require_running(task_id)
        if task["attempt"] < task["max_attempts"]:
            task.update(status="queued", error=error, started_at=None)
            task["version"] = task.get("version", 1) + 1
            self._queue.append(task_id)
        else:
            task.update(status="failed", error=error, completed_at=_timestamp())
            task["version"] = task.get("version", 1) + 1
        self.repo.save(task)
        return task.copy()

    def cancel(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task["status"] not in ["queued", "QUEUED"]:
            raise ValueError("Only queued tasks can be cancelled")
        task.update(status="cancelled", cancellation_requested=True, completed_at=_timestamp())
        task["version"] = task.get("version", 1) + 1
        self.repo.save(task)
        return task.copy()

    def counts(self) -> dict[str, int]:
        return {status: sum(task["status"] == status for task in self._tasks.values()) for status in ("queued", "running", "completed", "failed", "cancelled")}

    def _require_running(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task["status"] not in ["running", "RUNNING", "leased", "LEASED"]:
            raise ValueError("Only running or leased tasks can change to a terminal state")
        return task
