import time
from typing import Optional, Dict, Any, List
from backend.storage.repository import knight_repo
from backend.events.event_bus import event_bus

class NodeRegistry:

    def __init__(self, repository=None):
        self.repo = repository or knight_repo
        self._init_default_knights()

    def _init_default_knights(self):
        default_roles = ["planner", "coder", "researcher", "security"]
        now = time.time()
        for role in default_roles:
            k_id = f"knight-{role}"
            if not self.repo.get(k_id):
                k = {
                    "id": k_id,
                    "role": role,
                    "status": "idle",
                    "capabilities": [f"{role}.execute", "model.inference", "memory.read"],
                    "current_task": None,
                    "health": "healthy",
                    "is_local": True,
                    "last_heartbeat": now
                }
                self.repo.save(k)

    def register(self, knight_data: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        k_id = knight_data.get("id") or f"knight-{knight_data.get('role', 'generic')}-{int(now)}"

        knight = {
            "id": k_id,
            "role": knight_data.get("role", "knight"),
            "status": knight_data.get("status", "idle"),
            "capabilities": knight_data.get("capabilities", []),
            "current_task": knight_data.get("current_task"),
            "health": knight_data.get("health", "healthy"),
            "is_local": knight_data.get("is_local", True),
            "last_heartbeat": now
        }

        self.repo.save(knight)
        event_bus.publish("knight.registered", knight, source="node_registry", task_id=None)
        return knight

    def get_knight(self, knight_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.get(knight_id)

    def list_knights(self) -> List[Dict[str, Any]]:
        self.check_stale_heartbeats()
        return self.repo.list_all()

    def heartbeat(self, knight_id: str, health: str = "healthy") -> Optional[Dict[str, Any]]:
        knight = self.repo.get(knight_id)
        if not knight:
            return None

        knight["last_heartbeat"] = time.time()
        knight["health"] = health
        if knight["status"] == "offline":
            knight["status"] = "idle"

        self.repo.save(knight)
        event_bus.publish("knight.heartbeat", knight, source="node_registry")
        return knight

    def check_stale_heartbeats(self, timeout_seconds: float = 60.0):
        now = time.time()
        knights = self.repo.list_all()
        for k in knights:
            if k["status"] != "offline" and (now - k.get("last_heartbeat", 0)) > timeout_seconds:
                k["status"] = "offline"
                k["health"] = "unhealthy"
                self.repo.save(k)
                event_bus.publish("knight.offline", k, source="node_registry")

# Global node registry instance
node_registry = NodeRegistry()
