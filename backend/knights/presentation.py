"""Allowlisted worker presentation. Runtime metadata is never a display label."""
from typing import Literal
from pydantic import BaseModel

ROLES = {"planner": "Planning", "coder": "Code analysis", "researcher": "Research",
         "memory": "Knowledge", "security": "Security"}
CAPABILITIES = {"model.inference": "Generate text", "memory.read": "Read knowledge",
                "compute": "Analyze supplied text"}


class KnightSummary(BaseModel):
    id: str
    name: str
    display_name: str
    role: str
    is_local: bool
    status: Literal["ready", "working", "offline", "unknown"]
    health: Literal["healthy", "degraded", "unhealthy", "unknown"]
    current_task: None = None
    activity: str
    capabilities: list[str]
    active: int
    completed: int


def knight_summary(role, knight, active, completed):
    # Built-in registry keys are established by code, never peer-supplied labels.
    if role not in ROLES:
        raise ValueError("Unknown built-in worker role")
    state = "working" if active else "ready"
    health = knight.health if isinstance(knight.health, str) and knight.health in {"healthy", "degraded", "unhealthy"} else "unknown"
    caps = [key for key in CAPABILITIES if key in knight.capabilities]
    return KnightSummary(id=f"knight-{role}", name=role, display_name=ROLES[role], role=role,
                         is_local=True, status=state, health=health,
                         activity="Processing a task" if active else "Available for tasks",
                         capabilities=caps, active=max(0, active),
                         completed=max(0, completed)).model_dump()
