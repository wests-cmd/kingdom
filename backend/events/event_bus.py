import time
import uuid
from typing import Callable, List, Dict, Any, Optional
from backend.storage.repository import event_repo
from backend.security.audit_log import sanitize_data

class EventBus:

    def __init__(self, repository=None):
        self.repo = repository or event_repo
        self.subscribers: List[Callable[[Dict[str, Any]], None]] = []

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]):
        if callback not in self.subscribers:
            self.subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]):
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        source: str = "system",
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": time.time(),
            "source": source,
            "task_id": task_id,
            "payload": sanitize_data(payload) if isinstance(payload, dict) else {"data": sanitize_data(payload)}
        }

        # Persist event
        self.repo.save(event)

        # Notify active in-process subscribers
        for sub in list(self.subscribers):
            try:
                sub(event)
            except Exception:
                pass

        return event

    def get_events(self, task_id: Optional[str] = None, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self.repo.query(task_id=task_id, event_type=event_type, limit=limit)

# Global EventBus instance
event_bus = EventBus()
