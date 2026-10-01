"""Allowlisted worker presentation. Runtime metadata is never a display label."""
from typing import Literal
from pydantic import BaseModel

ROLES = {"planner": "Planning", "coder": "Code analysis", "researcher": "Research",
         "memory": "Knowledge", "security": "Security"}
CAPABILITIES = {"model.inference": "Model text permission", "memory.read": "Read knowledge permission",
                "compute": "Built-in text and syntax analysis", "providers.test": "Reviewed provider-test permission"}


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


def knight_summary(role, knight, active, completed, security=None):
    # Built-in registry keys are established by code, never peer-supplied labels.
    if role not in ROLES:
        raise ValueError("Unknown built-in worker role")
    health = knight.health if isinstance(knight.health, str) and knight.health in {"healthy", "degraded", "unhealthy"} else "unknown"
    layers = [knight.zero_trust] + ([security] if security is not None else [])
    available = all((layer.nodes.get_node(role) or {}).get("active") for layer in layers)
    from backend.security.capabilities import CapabilityEvaluator
    caps = [key for key in CAPABILITIES if available and all(
        CapabilityEvaluator.evaluate(layer.nodes.get_node_capabilities(role), key) for layer in layers)]
    state = "offline" if not available or health == "unhealthy" else "unknown" if health == "unknown" else "working" if active else "ready"
    return KnightSummary(id=f"knight-{role}", name=role, display_name=ROLES[role], role=role,
                         is_local=True, status=state, health=health,
                         activity="Worker unavailable" if state == "offline" else "Health unavailable" if state == "unknown" else "Processing a task" if active else "Available for tasks",
                         capabilities=caps, active=max(0, active),
                         completed=max(0, completed)).model_dump()
