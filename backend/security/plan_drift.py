import hashlib
import json
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ApprovedPlanBinding(BaseModel):
    plan_id: str
    actor_identity_id: str
    tool_id: str
    operation: str
    resource: str
    parameter_hash: str
    risk_level: str
    approved_at: float = Field(default_factory=time.time)
    expires_at: float
    invalidated: bool = False
    invalidation_reason: Optional[str] = None


class PlanDriftEngine:

    @staticmethod
    def compute_param_hash(params: Dict[str, Any]) -> str:
        serialized = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def __init__(self):
        self.bindings: Dict[str, ApprovedPlanBinding] = {}

    def bind_approved_plan(
        self,
        plan_id: str,
        actor_identity_id: str,
        tool_id: str,
        operation: str,
        resource: str,
        params: Dict[str, Any],
        risk_level: str = "LOW",
        ttl_sec: float = 300.0
    ) -> ApprovedPlanBinding:
        now = time.time()
        param_hash = self.compute_param_hash(params)

        binding = ApprovedPlanBinding(
            plan_id=plan_id,
            actor_identity_id=actor_identity_id,
            tool_id=tool_id,
            operation=operation,
            resource=resource,
            parameter_hash=param_hash,
            risk_level=risk_level,
            approved_at=now,
            expires_at=now + ttl_sec
        )
        self.bindings[plan_id] = binding
        return binding

    def validate_plan_execution(
        self,
        plan_id: str,
        actor_identity_id: str,
        tool_id: str,
        operation: str,
        resource: str,
        params: Dict[str, Any]
    ) -> bool:
        binding = self.bindings.get(plan_id)
        if not binding:
            raise PermissionError(f"No approved binding found for plan '{plan_id}'.")

        if binding.invalidated:
            raise PermissionError(f"Approved plan '{plan_id}' was invalidated: {binding.invalidation_reason}")

        if time.time() > binding.expires_at:
            binding.invalidated = True
            binding.invalidation_reason = "Approval binding expired."
            raise PermissionError(f"Approved plan '{plan_id}' has expired.")

        # Drift Checks
        if binding.actor_identity_id != actor_identity_id:
            binding.invalidated = True
            binding.invalidation_reason = f"Actor drift detected: Expected {binding.actor_identity_id}, got {actor_identity_id}"
            raise PermissionError(binding.invalidation_reason)

        if binding.tool_id != tool_id or binding.operation != operation or binding.resource != resource:
            binding.invalidated = True
            binding.invalidation_reason = f"Plan scope drift detected: Tool/operation/resource substitution attempt."
            raise PermissionError(binding.invalidation_reason)

        current_param_hash = self.compute_param_hash(params)
        if binding.parameter_hash != current_param_hash:
            binding.invalidated = True
            binding.invalidation_reason = "Parameter drift detected: Execution arguments modified post-approval."
            raise PermissionError(binding.invalidation_reason)

        return True
