"""Working in-process swarm coordinator built on the existing knight modules."""

from __future__ import annotations

import asyncio

from backend.knights.registry import KnightRegistry
from backend.routing.complexity_router import ComplexityRouter
from backend.security.zero_trust import ZeroTrust
from backend.swarm.workload_balancer import WorkloadBalancer


class SwarmManager:
    def __init__(self, event_publisher, security: ZeroTrust | None = None):
        self._publish = event_publisher
        self.security = security or ZeroTrust()
        self.registry = KnightRegistry()
        self._balancer = WorkloadBalancer()
        self._complexity = ComplexityRouter()

    def status(self):
        knights = self.registry.status()
        return {"knights": knights, "active_knights": sum(knight["status"] == "working" for knight in knights)}

    async def execute(self, task):
        subtasks = self._decompose(task["prompt"], task["metadata"].get("subtasks"))
        assignments = [self._balancer.select_knight(subtask) for subtask in subtasks]
        plan = {
            "task_id": task["id"],
            "complexity": self._complexity.classify(task["prompt"]),
            "subtasks": [{"prompt": subtask, "knight": knight} for subtask, knight in zip(subtasks, assignments)],
        }
        self._publish("swarm.planned", plan)
        results = await asyncio.gather(*(self._run(knight, subtask, task["id"]) for subtask, knight in zip(subtasks, assignments)))
        return {"plan": plan, "results": results}

    def _decompose(self, prompt, requested):
        if requested:
            if not isinstance(requested, list) or not all(isinstance(item, str) and item.strip() for item in requested):
                raise ValueError("subtasks must be a list of non-empty strings")
            return requested
        parts = [part.strip(" -\t") for part in prompt.splitlines() if part.strip()]
        return parts or [prompt]

    async def _run(self, knight_name, prompt, task_id):
        knight = self.registry.get(knight_name)
        if knight is None:
            raise RuntimeError(f"No registered knight named {knight_name}")

        # Zero-trust knight execution permission check
        auth_res = self.security.authorize(
            actor_id=knight_name,
            capability="node.execute",
            operation=f"Knight '{knight_name}' execution for task '{task_id}'",
            prompt=prompt,
        )
        if not auth_res["authorized"]:
            raise PermissionError(f"Security policy denied knight execution: {auth_res['reason']}")

        self.registry.begin(knight_name)
        self._publish("knight.started", {"task_id": task_id, "knight": knight_name})
        try:
            result = await asyncio.to_thread(knight.execute, prompt)
            self._publish("knight.completed", {"task_id": task_id, "knight": knight_name})
            return result
        finally:
            self.registry.finish(knight_name)
