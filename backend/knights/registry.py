"""Lifecycle-aware registry for Kingdom's built-in knight roles."""

import json
import os
from pathlib import Path

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


def _default_profile_path():
    return Path(__file__).resolve().parents[2] / "configs" / "local_profile.json"


def load_enabled_knight_roles():
    profile_path = os.getenv("KINGDOM_LOCAL_PROFILE") or str(_default_profile_path())
    try:
        with open(profile_path, "r", encoding="utf-8") as handle:
            profile = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return list(_KNIGHT_CLASSES.keys())

    if not isinstance(profile, dict):
        return list(_KNIGHT_CLASSES.keys())

    roles = profile.get("knights")
    if not isinstance(roles, list):
        return list(_KNIGHT_CLASSES.keys())

    valid = list(dict.fromkeys(role for role in roles if role in _KNIGHT_CLASSES))
    return valid or list(_KNIGHT_CLASSES.keys())


class KnightRegistry:
    def __init__(self, enabled_roles=None):
        if enabled_roles is None:
            enabled_roles = load_enabled_knight_roles()
        valid_roles = list(dict.fromkeys(
            role for role in (enabled_roles if isinstance(enabled_roles, list) else [])
            if role in _KNIGHT_CLASSES
        ))
        if not valid_roles:
            valid_roles = list(_KNIGHT_CLASSES.keys())

        self._knights = {name: _KNIGHT_CLASSES[name]() for name in valid_roles}
        self._active = {name: 0 for name in self._knights}
        self._completed = {name: 0 for name in self._knights}

    def get(self, name):
        return self._knights.get(name)

    def begin(self, name):
        if name not in self._knights:
            raise KeyError(name)
        self._active[name] += 1

    def finish(self, name):
        if name not in self._knights:
            raise KeyError(name)
        self._active[name] = max(0, self._active[name] - 1)
        self._completed[name] += 1

    def status(self):
        return [
            {"name": name, "status": "working" if self._active[name] else "ready",
             "active": self._active[name], "completed": self._completed[name]}
            for name in self._knights
        ]
