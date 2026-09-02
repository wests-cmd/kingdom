"""Lifecycle-aware registry for Kingdom's built-in knight roles."""

from backend.knights.coder import CoderKnight
from backend.knights.memory_knight import MemoryKnight
from backend.knights.planner import PlannerKnight
from backend.knights.researcher import ResearchKnight
from backend.knights.security_knight import SecurityKnight


class KnightRegistry:
    def __init__(self):
        self._knights = {
            "planner": PlannerKnight(),
            "coder": CoderKnight(),
            "researcher": ResearchKnight(),
            "memory": MemoryKnight(),
            "security": SecurityKnight(),
        }
        self._active = {name: 0 for name in self._knights}
        self._completed = {name: 0 for name in self._knights}

    def get(self, name):
        return self._knights.get(name)

    def begin(self, name):
        if name not in self._knights:
            raise KeyError(name)
        self._active[name] += 1

    def finish(self, name):
        self._active[name] = max(0, self._active[name] - 1)
        self._completed[name] += 1

    def status(self):
        return [{"name": name, "status": "working" if self._active[name] else "ready", "active": self._active[name], "completed": self._completed[name]} for name in self._knights]
