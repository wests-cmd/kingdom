import time
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from backend.security.identity_fabric import IdentityFabric, SystemIdentity, IdentityState
from backend.security.risk import RiskClassifier, RiskLevel


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

    def __init__(self, identity_fabric: IdentityFabric):
        self.identity_fabric = identity_fabric

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

        # 4. Check Risk vs Approval
        requires_approval = (risk_level == RiskLevel.HIGH)

        if requires_approval and required_governance_level < 4 and request.context.get("approved_by_commander") is not True:
            return AuthorizationDecision(
                allowed=False,
                actor_identity_id=request.actor_identity_id,
                capability=request.capability,
                resource=request.resource,
                risk_level=risk_level,
                requires_human_approval=True,
                reason=f"High risk capability '{request.capability}' requires L4+ Commander human approval."
            )

        # 5. Data Scope Isolation
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

        return AuthorizationDecision(
            allowed=True,
            actor_identity_id=request.actor_identity_id,
            capability=request.capability,
            resource=request.resource,
            risk_level=risk_level,
            requires_human_approval=requires_approval,
            reason="Authorization granted."
        )
