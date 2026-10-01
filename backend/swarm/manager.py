"""Working in-process swarm coordinator built on the existing knight modules."""

from __future__ import annotations

import asyncio
import hashlib

from backend.knights.registry import KnightRegistry
from backend.routing.complexity_router import ComplexityRouter
from backend.security.zero_trust import ZeroTrust
from backend.swarm.workload_balancer import WorkloadBalancer


class SwarmManager:
    def __init__(self, event_publisher, security: ZeroTrust | None = None):
        self._publish = event_publisher
        self.security = security or ZeroTrust()
        self.registry = KnightRegistry(security=self.security)
        self._balancer = WorkloadBalancer()
        self._complexity = ComplexityRouter()

    def status(self):
        knights = self.registry.status()
        return {"knights": knights, "active_knights": sum(knight["status"] == "working" for knight in knights)}

    async def execute(self, task):
        subtasks = self._decompose(task["prompt"], task["metadata"].get("subtasks")) if task["metadata"].get("subtasks") else [task["prompt"]]
        assignments = [self._balancer.select_knight(subtask, list(self.registry._knights)) for subtask in subtasks]
        requested = task["metadata"].get("requested_knight")
        if requested:
            if requested not in self.registry._knights:
                raise ValueError("Requested worker is not available")
            assignments = [requested] * len(subtasks)
        plan = {
            "task_id": task["id"],
            "complexity": self._complexity.classify(task["prompt"]),
            "subtasks": [{"prompt": subtask, "knight": knight} for subtask, knight in zip(subtasks, assignments)],
        }
        self._publish("swarm.planned", plan)
        results = await asyncio.gather(*(self._run(knight, subtask, task) for subtask, knight in zip(subtasks, assignments)))
        return {"plan": plan, "results": results}

    def _decompose(self, prompt, requested):
        if requested:
            if not isinstance(requested, list) or not all(isinstance(item, str) and item.strip() for item in requested):
                raise ValueError("subtasks must be a list of non-empty strings")
            return requested
        parts = [part.strip(" -\t") for part in prompt.splitlines() if part.strip()]
        return parts or [prompt]

    async def _run(self, knight_name, prompt, task):
        task_id = task["id"]
        knight = self.registry.get(knight_name)
        if knight is None:
            raise RuntimeError(f"No registered knight named {knight_name}")

        # Zero-trust knight execution permission check
        auth_res = self.security.authorize(
            actor_id=knight_name,
            token=(self.security.nodes.get_node(knight_name) or {}).get("token"),
            capability="node.execute",
            operation=f"Knight '{knight_name}' execution for task '{task_id}'",
            prompt=prompt,
        )
        if not auth_res["authorized"]:
            raise PermissionError(f"Security policy denied knight execution: {auth_res['reason']}")

        self.registry.begin(knight_name)
        self._publish("knight.started", {"task_id": task_id, "knight": knight_name})
        try:
            request = {**task, "prompt": prompt, "id": task_id + ":" + hashlib.sha256(prompt.encode()).hexdigest()}
            result = await asyncio.to_thread(knight.execute, request)
            from backend.runtime.execution import verify_request_result
            if result.get("status") != "completed":
                raise RuntimeError("Knight did not complete a verified operation")
            result["verification"] = verify_request_result(request, result["outcome"])
            self._publish("knight.completed", {"task_id": task_id, "knight": knight_name})
            return result
        finally:
            self.registry.finish(knight_name)
