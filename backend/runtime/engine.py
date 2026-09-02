import asyncio
import time
import uuid
from typing import Optional, Dict, Any, List
from backend.state import STATE
from backend.storage.repository import task_repo, knight_repo, event_repo
from backend.events.event_bus import event_bus

VALID_STATES = {"queued", "assigned", "running", "completed", "failed", "cancelled"}

class RuntimeEngine:

    def __init__(self):
        self._supervisor_task: Optional[asyncio.Task] = None

    def initialize(self):
        STATE["running"] = True

    def start(self):
        STATE["running"] = True
        event_bus.publish("runtime.started", {"mode": STATE["mode"]}, source="runtime")
        return {"status": "started"}

    def stop(self):
        STATE["running"] = False
        event_bus.publish("runtime.stopped", {"mode": STATE["mode"]}, source="runtime")
        return {"status": "stopped"}

    def status(self):
        return {
            "running": STATE["running"],
            "mode": STATE["mode"],
            "version": STATE["version"]
        }

    def get_mode(self):
        return STATE["mode"]

    # --- TASK API METHODS ---

    def create_task(self, task_type: str, input_data: Any, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        task_id = str(uuid.uuid4())
        now = time.time()

        task = {
            "id": task_id,
            "type": task_type or "generic",
            "status": "queued",
            "input": input_data or {},
            "assigned_knight": None,
            "result": None,
            "error": None,
            "cancellation_requested": False,
            "created_at": now,
            "updated_at": now
        }

        task_repo.save(task)
        event_bus.publish("task.created", task, source="task_api", task_id=task_id)
        return task

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return task_repo.get(task_id)

    def list_tasks(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return task_repo.list_all(status=status, limit=limit)

    def cancel_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = task_repo.get(task_id)
        if not task:
            return None

        if task["status"] in ["completed", "failed", "cancelled"]:
            return task

        task["cancellation_requested"] = True
        task["status"] = "cancelled"
        task["updated_at"] = time.time()
        task_repo.save(task)

        event_bus.publish("task.cancelled", task, source="task_api", task_id=task_id)
        return task

# Global runtime engine instance
runtime_engine = RuntimeEngine()
