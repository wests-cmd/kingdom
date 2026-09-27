"""Lifecycle-aware registry for Kingdom's built-in knight roles."""

import json
import os
from backend.knights.coder import CoderKnight
from backend.knights.memory_knight import MemoryKnight
from backend.knights.planner import PlannerKnight
from backend.knights.researcher import ResearchKnight
from backend.knights.security_knight import SecurityKnight

_KNIGHT_CLASSES = {
    "planner": PlannerKnight,
    "coder": CoderKnight,
    "researcher": ResearchKnight,
    "memory": MemoryKnight,
    "security": SecurityKnight,
}

ALL_KNOWN_ROLES = ["planner", "coder", "researcher", "memory", "security"]


def _default_profile_path():
    return os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )
        ),
        "configs",
        "local_profile.json",
    )


def load_enabled_knight_roles():
    profile_path = os.getenv("KINGDOM_LOCAL_PROFILE") or _default_profile_path()
    if not os.path.exists(profile_path):
        return list(ALL_KNOWN_ROLES)

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        knights = data.get("knights")
        if not isinstance(knights, list):
            return list(ALL_KNOWN_ROLES)

        seen = set()
        enabled = []
        for r in knights:
            if isinstance(r, str) and r in _KNIGHT_CLASSES and r not in seen:
                seen.add(r)
                enabled.append(r)

        return enabled if enabled else list(ALL_KNOWN_ROLES)

    except Exception:
        return list(ALL_KNOWN_ROLES)


class KnightRegistry:
    def __init__(self, enabled_roles=None):
        if enabled_roles is None:
            roles = load_enabled_knight_roles()
        else:
            roles = enabled_roles

        seen = set()
        unique_roles = []
        for r in roles:
            if isinstance(r, str) and r in _KNIGHT_CLASSES and r not in seen:
                seen.add(r)
                unique_roles.append(r)

        self._knights = {
            name: _KNIGHT_CLASSES[name]()
            for name in unique_roles
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
        if name in self._knights:
            self._active[name] = max(0, self._active[name] - 1)
            self._completed[name] += 1

    def status(self):
        return [
            {
                "name": name,
                "status": "working" if self._active[name] else "ready",
                "active": self._active[name],
                "completed": self._completed[name]
            }
            for name in self._knights
        ]
