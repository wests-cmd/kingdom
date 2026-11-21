import time
from typing import Dict, Any
from pydantic import BaseModel, Field
from backend.security.identity_fabric import IdentityFabric
from backend.security.risk import RiskClassifier, RiskLevel
from backend.security.approval_engine import ApprovalEngine


class AuthorizationRequest(BaseModel):
    actor_identity_id: str
    capability: str
    operation: str
    resource: str
    context: Dict[str, Any] = Field(default_factory=dict)
    data_scope: str = "general"
    requested_at: float = Field(default_factory=time.time)


class AuthorizationDecision(BaseModel):
    allowed: bool
    actor_identity_id: str
    capability: str
    resource: str
    risk_level: RiskLevel
    requires_human_approval: bool = False
    reason: str
    decision_id: str = Field(default_factory=lambda: f"dec_{time.time_ns()}")


class ScopedAuthorizationEngine:

    def __init__(self, identity_fabric: IdentityFabric,
                 approval_engine: ApprovalEngine | None = None):
        self.identity_fabric = identity_fabric
        # Only the host-supplied, existing durable approval store is authoritative.
        # No store means high-risk operations fail closed.
        self._approvals = approval_engine

    def evaluate_authorization(
        self,
        request: AuthorizationRequest,
        required_governance_level: int = 3
    ) -> AuthorizationDecision:
        # 1. Verify active identity
        try:
            actor = self.identity_fabric.verify_active_identity(request.actor_identity_id)
        except PermissionError as pe:
            return AuthorizationDecision(
                allowed=False,
                actor_identity_id=request.actor_identity_id,
                capability=request.capability,
                resource=request.resource,
                risk_level=RiskLevel.HIGH,
                reason=str(pe)
            )

        # 2. Check capability grant
        if request.capability not in actor.capabilities and "admin" not in actor.capabilities and "*" not in actor.capabilities:
            return AuthorizationDecision(
                allowed=False,
                actor_identity_id=request.actor_identity_id,
                capability=request.capability,
                resource=request.resource,
                risk_level=RiskLevel.MEDIUM,
                reason=f"Identity '{actor.display_name}' lacks required capability '{request.capability}'."
            )

        # 3. Classify Risk
        risk_level = RiskClassifier.classify_operation(request.capability, request.context)

        # 4. Restrict data scopes before consuming a one-time approval.
        restricted_scopes = request.context.get("restricted_data_scopes", [])
        if request.data_scope in restricted_scopes and actor.trust_level != "TRUSTED":
            return AuthorizationDecision(
                allowed=False,
                actor_identity_id=request.actor_identity_id,
                capability=request.capability,
                resource=request.resource,
                risk_level=risk_level,
                reason=f"Data scope '{request.data_scope}' is restricted to TRUSTED identities."
            )

        # 5. High-risk actions require an atomic, exact, unexpired approval.
        # Neither caller-provided governance level nor a boolean context flag
        # establishes authority. The normal ZeroTrust owner-policy path handles
        # separate authenticated level-5 standing authorization.
        requires_approval = (risk_level == RiskLevel.HIGH)
        if requires_approval:
            approval_id = request.context.get("approval_id")
            approved = False
            if isinstance(approval_id, str) and approval_id and self._approvals is not None:
                try:
                    approved = self._approvals.consume(
                        approval_id,
                        actor_id=request.actor_identity_id,
                        capability=request.capability,
                        operation=request.operation,
                        parameters={
                            "resource": request.resource,
                            "data_scope": request.data_scope,
                        },
                    ) is True
                except Exception:
                    approved = False
            if not approved:
                return AuthorizationDecision(
                    allowed=False,
                    actor_identity_id=request.actor_identity_id,
                    capability=request.capability,
                    resource=request.resource,
                    risk_level=risk_level,
                    requires_human_approval=True,
                    reason="High risk operation lacks an exact, unexpired, single-use owner approval."
                )

        return AuthorizationDecision(
            allowed=True,
            actor_identity_id=request.actor_identity_id,
            capability=request.capability,
            resource=request.resource,
            risk_level=risk_level,
            requires_human_approval=requires_approval,
            reason="Authorization granted."
        )
