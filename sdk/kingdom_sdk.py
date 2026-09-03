import httpx
from typing import Any, Dict, List, Optional


class KingdomSDK:

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def get_status(self) -> Dict[str, Any]:
        res = self.client.get("/status")
        res.raise_for_status()
        return res.json()

    def submit_task(self, prompt: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"prompt": prompt, "metadata": metadata or {}}
        res = self.client.post("/tasks", json=payload)
        res.raise_for_status()
        return res.json()

    def get_task(self, task_id: str) -> Dict[str, Any]:
        res = self.client.get(f"/tasks/{task_id}")
        res.raise_for_status()
        return res.json()

    def list_skills(self) -> List[Dict[str, Any]]:
        res = self.client.get("/skills")
        res.raise_for_status()
        return res.json()

    def check_skill_readiness(self, skill_id: str) -> Dict[str, Any]:
        res = self.client.get(f"/skills/{skill_id}/readiness")
        res.raise_for_status()
        return res.json()

    def record_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"content": content, "metadata": metadata or {}}
        res = self.client.post("/memory", json=payload)
        res.raise_for_status()
        return res.json()

    def get_learning_activity(self) -> Dict[str, Any]:
        res = self.client.get("/learning/activity")
        res.raise_for_status()
        return res.json()
