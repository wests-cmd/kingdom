"""Durable task lifecycle management backed by persistent storage."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from threading import RLock
from functools import wraps
from copy import deepcopy

from backend.storage.repository import task_repo

def synchronized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call

TERMINAL_STATUSES = ("completed", "failed", "cancelled", "succeeded", "SUCCEEDED", "COMPLETED", "FAILED", "CANCELLED")

VALID_TASK_TRANSITIONS = {
    "CREATED": ["VALIDATING", "WAITING_AUTHORIZATION", "WAITING_APPROVAL", "QUEUED", "BLOCKED", "CANCELLED"],
    "VALIDATING": ["WAITING_AUTHORIZATION", "WAITING_APPROVAL", "QUEUED", "BLOCKED", "CANCELLED"],
    "WAITING_AUTHORIZATION": ["AUTHORIZED", "BLOCKED", "CANCELLED"],
    "WAITING_APPROVAL": ["APPROVED", "DENIED", "QUEUED", "BLOCKED", "CANCELLED"],
    "AUTHORIZED": ["QUEUED", "LEASED", "RUNNING", "CANCELLED"],
    "QUEUED": ["LEASED", "RUNNING", "CANCELLED", "EXPIRED"],
    "LEASED": ["RUNNING", "CANCELLED", "EXPIRED", "RECOVERY_REQUIRED"],
    "RUNNING": ["WAITING_APPROVAL", "VERIFYING", "SUCCEEDED", "COMPLETED", "FAILED", "QUEUED", "RECOVERY_REQUIRED", "CANCELLED"],
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
        self._lock = RLock()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._queue: deque[str] = deque()
        self.load_persisted_tasks()

    @synchronized
    def clear(self) -> None:
        self._tasks.clear()
        self._queue.clear()

    def load_persisted_tasks(self) -> None:
        try:
            db_tasks = self.repo.list_all(limit=None)
            for t in db_tasks:
                self._tasks[t["id"]] = t
                if t.get("status") in ["queued", "QUEUED"]:
                    if t["id"] not in self._queue:
                        self._queue.append(t["id"])
        except Exception as exc:
            raise RuntimeError("Cannot load durable task state safely") from exc

    @synchronized
    def create(self, prompt: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = deepcopy(metadata or {})
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
        self.repo.save(task)
        self._tasks[task_id] = task
        self._queue.append(task_id)
        return deepcopy(task)

    @synchronized
    def get(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        if not task:
            task = self.repo.get(task_id)
            if task:
                self._tasks[task_id] = task
        if task["status"] == "queued" and task_id not in self._queue:
            self._queue.append(task_id)
        return deepcopy(task) if task else None

    @synchronized
    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            return [deepcopy(t) for t in self._tasks.values()]
        return [deepcopy(t) for t in self._tasks.values() if t["status"] == status or t["status"].upper() == status.upper()]

    @synchronized
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

        changed = deepcopy(task)
        changed["status"] = new_status.lower() if new_status.lower() in ["queued", "leased", "running", "completed", "failed", "cancelled"] else new_status
        changed["version"] = task.get("version", 1) + 1
        if updates:
            changed.update(updates)

        self.repo.save(changed, expected_version=task["version"])
        self._tasks[task_id] = changed
        if changed["status"].lower() == "queued" and task_id not in self._queue:
            self._queue.append(task_id)
        return deepcopy(changed)

    @synchronized
    def claim_next(self) -> dict[str, Any] | None:
        for _ in range(len(self._queue)):
            task_id = self._queue.popleft()
            task = self._tasks.get(task_id)
            if task and task["status"] in ["queued", "QUEUED"]:
                assigned = task.get("assigned_knight") or task.get("metadata", {}).get("assigned_knight")
                if task.get("metadata", {}).get("execution_target") == "remote" or (assigned and assigned not in {"planner", "coder", "researcher", "memory", "security"}):
                    self._queue.append(task_id)
                    continue
                claimed = self.repo.claim(task_id, task["version"], assigned_knight=assigned)
                if claimed:
                    self._tasks[task_id] = claimed
                    return deepcopy(claimed)
                current = self.repo.get(task_id)
                if current:
                    self._tasks[task_id] = current
        return None

    @synchronized
    def claim_remote(self, task_id, node_id, lease):
        task = self.get(task_id)
        if not task or task["status"].lower() != "queued":
            return None
        claimed = self.repo.claim(task_id, task["version"], status="leased", assigned_knight=node_id,
                                  lease_id=lease.lease_id, fencing_token=lease.fencing_token)
        if claimed:
            self._tasks[task_id] = claimed
        return deepcopy(claimed)

    @synchronized
    def claim_remote_atomically(self, task_id, node_id, capability, leases):
        task = self.repo.get(task_id)
        if not task:
            return None
        lease = leases.issue_and_claim(task_id, node_id, capability, task["version"])
        if not lease:
            return None
        claimed = self.repo.get(task_id)
        self._tasks[task_id] = claimed
        return deepcopy(claimed)

    @synchronized
    def complete(self, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
        task = deepcopy(self._require_running(task_id))
        task.update(status="completed", result=result, completed_at=_timestamp())
        task["version"] = task.get("version", 1) + 1
        self.repo.save(task, expected_version=task["version"] - 1)
        self._tasks[task_id] = task
        if task["status"] == "queued" and task_id not in self._queue:
            self._queue.append(task_id)
        return deepcopy(task)

    @synchronized
    def fail(self, task_id: str, error: str) -> dict[str, Any]:
        task = deepcopy(self._require_running(task_id))
        task.update(status="failed", error=error, completed_at=_timestamp())
        task["version"] = task.get("version", 1) + 1
        self.repo.save(task, expected_version=task["version"] - 1)
        self._tasks[task_id] = task
        if task["status"] == "queued" and task_id not in self._queue:
            self._queue.append(task_id)
        return deepcopy(task)

    @synchronized
    def retry_or_fail(self, task_id: str, error: str) -> dict[str, Any]:
        task = deepcopy(self._require_running(task_id))
        if task["attempt"] < task["max_attempts"]:
            task.update(status="queued", error=error, started_at=None)
            task["version"] = task.get("version", 1) + 1
        else:
            task.update(status="failed", error=error, completed_at=_timestamp())
            task["version"] = task.get("version", 1) + 1
        self.repo.save(task, expected_version=task["version"] - 1)
        self._tasks[task_id] = task
        if task["status"] == "queued" and task_id not in self._queue:
            self._queue.append(task_id)
        return deepcopy(task)

    @synchronized
    def cancel(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task["status"] not in ["queued", "QUEUED"]:
            raise ValueError("Only queued tasks can be cancelled")
        task = deepcopy(task)
        task.update(status="cancelled", cancellation_requested=True, completed_at=_timestamp())
        task["version"] = task.get("version", 1) + 1
        self.repo.save(task, expected_version=task["version"] - 1)
        self._tasks[task_id] = task
        if task["status"] == "queued" and task_id not in self._queue:
            self._queue.append(task_id)
        return deepcopy(task)

    @synchronized
    def counts(self) -> dict[str, int]:
        return {status: sum(task["status"] == status for task in self._tasks.values()) for status in ("queued", "running", "completed", "failed", "cancelled")}

    def _require_running(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task["status"] not in ["running", "RUNNING", "leased", "LEASED"]:
            raise ValueError("Only running or leased tasks can change to a terminal state")
        return task
