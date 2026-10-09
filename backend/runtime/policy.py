"""Persisted execution limits, independent of authentication and capability grants."""
import json
import time
import os
from pathlib import Path
from urllib.request import Request, urlopen
from threading import RLock
from backend.storage.db import db

LEVELS = [
    {"level": 0, "name": "Paused", "description": "Keep queued tasks on hold. No new task executes."},
    {"level": 1, "name": "Safe analysis", "description": "Run built-in text and syntax analysis. Other tasks need individual approval."},
    {"level": 2, "name": "Approve every task", "description": "Require one exact, single-use human approval before each task executes."},
    {"level": 3, "name": "Bounded execution", "description": "Run tasks within existing capability grants. High-risk actions still need approval."},
    {"level": 4, "name": "Adaptive missions", "description": "Plan and advance approved multi-step missions, retain context and retry failed safe steps within a budget. High-risk actions still need approval."},
    {"level": 5, "name": "Coordinated missions", "description": "Use larger mission budgets and offload supported analysis to healthy approved computers. Completion requires verified results. High-risk actions still need approval."},
]


class ExecutionPolicy:
    def __init__(self, database=None):
        self.db = database or db
        self._lock = RLock()
        # A parallel, tested handover preview must share the stable installation's
        # autonomy authority rather than silently create a second control plane.
        self.authority_token_file = os.environ.get('KINGDOM_POLICY_AUTHORITY_TOKEN_FILE')

    def _authority(self, level=None):
        token = Path(self.authority_token_file).read_text().strip()
        payload = None if level is None else json.dumps({'level': level}).encode()
        request = Request('http://127.0.0.1:8012/runtime/policy', data=payload,
                          method='GET' if level is None else 'PUT',
                          headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
        if type(result.get('level')) is not int or result['level'] not in range(6):
            raise RuntimeError('Autonomy authority returned an invalid policy')
        result['mission_budget'] = self.mission_budget(result['level'])
        return result

    def get(self):
        if self.authority_token_file:
            return self._authority()
        with self._lock, self.db.get_connection() as conn:
            row = conn.execute("SELECT value_json FROM runtime_state WHERE key='execution_policy'").fetchone()
        # Preserve the existing bounded runtime behavior on upgrade.
        level = json.loads(row[0])["level"] if row else 3
        if type(level) is not int or level not in range(6):
            level = 0  # Invalid persisted policy fails closed.
        return {"level": level, "levels": LEVELS, "mission_budget": self.mission_budget(level), "scope": "New task execution; existing capability and approval checks always apply."}

    def set(self, level):
        if type(level) is not int or level not in range(6):
            raise ValueError("Supported autonomy levels are 1 through 5, or 0 to pause")
        if self.authority_token_file:
            return self._authority(level)
        with self._lock, self.db.get_connection() as conn:
            conn.execute("INSERT INTO runtime_state(key,value_json,updated_at) VALUES('execution_policy',?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at", (json.dumps({"level": level}), time.time()))
            conn.commit()
        return self.get()

    def requires_approval(self, task):
        level = self.get()["level"]
        safe_tool = task.get("metadata", {}).get("tool") in {"text.analyze@1.0.0", "code.python.analyze@1.0.0"}
        return level == 2 or (level == 1 and not safe_tool)

    @staticmethod
    def mission_budget(level):
        return {"max_steps": 50 if level == 5 else 20 if level == 4 else 10,
                "max_retries": 3 if level == 5 else 2 if level == 4 else 0,
                "max_parallel": 3 if level == 5 else 1,
                "auto_advance": level >= 4, "cross_computer": level == 5}
