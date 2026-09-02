import time
from typing import Optional, Dict, Any
from backend.security.zero_trust import ZeroTrust
from backend.security.audit_log import audit_logger
from backend.storage.repository import knight_repo
from backend.events.event_bus import event_bus

class BaseKnight:

    def __init__(self, name: str, role: Optional[str] = None, is_local: bool = True):
        self.name = name
        self.id = f"knight-{name}"
        self.role = role or name
        self.is_local = is_local
        self.status = "idle"
        self.health = "healthy"
        self.current_task: Optional[str] = None
        self.capabilities = [f"{self.role}.execute", "model.inference", "memory.read"]
        self.zero_trust = ZeroTrust()
        self._sync_to_repo()

    def _sync_to_repo(self):
        knight_data = {
            "id": self.id,
            "role": self.role,
            "status": self.status,
            "capabilities": self.capabilities,
            "current_task": self.current_task,
            "health": self.health,
            "is_local": self.is_local,
            "last_heartbeat": time.time()
        }
        knight_repo.save(knight_data)

    def execute(self, task: Any) -> Dict[str, Any]:
        actor = None
        capability = f"{self.role}.execute"
        task_id = None

        if isinstance(task, dict):
            actor = task.get("actor")
            capability = task.get("capability", capability)
            task_id = task.get("id")

        # Zero trust authorization check
        if actor:
            validation = self.zero_trust.validate(actor, required_capability=capability)
            if not validation.get("authorized"):
                audit_logger.log_event(
                    actor=str(actor),
                    node=self.id,
                    operation="knight_execute",
                    capability=capability,
                    decision="denied",
                    reason=validation.get("reason", "Knight execution unauthorized")
                )
                self.status = "failed"
                self._sync_to_repo()
                return {
                    "knight": self.id,
                    "task": task,
                    "status": "unauthorized",
                    "reason": validation.get("reason")
                }

        # Lifecycle state transitions
        self.status = "running"
        self.current_task = task_id
        self._sync_to_repo()
        event_bus.publish("task.started", {"task_id": task_id, "knight_id": self.id}, source="knight", task_id=task_id)

        # Simulate execution
        result = {
            "knight": self.id,
            "task": task,
            "status": "completed",
            "executed_at": time.time()
        }

        self.status = "idle"
        self.current_task = None
        self._sync_to_repo()
        event_bus.publish("task.completed", result, source="knight", task_id=task_id)

        return result

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        if self.current_task == task_id:
            self.status = "idle"
            self.current_task = None
            self._sync_to_repo()
            event_bus.publish("task.cancelled", {"task_id": task_id, "knight_id": self.id}, source="knight", task_id=task_id)
            return {"status": "cancelled", "knight_id": self.id, "task_id": task_id}
        return {"status": "not_running", "knight_id": self.id, "task_id": task_id}
