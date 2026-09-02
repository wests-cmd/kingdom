"""Zero-Trust Security Coordinator for Kingdom."""

from __future__ import annotations

from typing import Any

from backend.security.approval_engine import ApprovalEngine
from backend.security.audit_log import audit_log
from backend.security.capabilities import CapabilityEvaluator
from backend.security.node_security import NodeSecurityManager
from backend.security.prompt_firewall import PromptFirewall
from backend.security.risk import RiskClassifier, RiskLevel


class ZeroTrust:
    """Unified zero-trust policy engine enforcing authentication, permissions, approvals, and injection checks."""

    def __init__(self) -> None:
        self.approvals = ApprovalEngine()
        self.nodes = NodeSecurityManager()
        self.firewall = PromptFirewall()
        self.evaluator = CapabilityEvaluator()
        self.risk_classifier = RiskClassifier()
        self.audit = audit_log

    def validate(self, actor: str) -> dict[str, Any]:
        """Backward compatible validator method."""
        node = self.nodes.get_node(actor)
        trusted = node is not None and node.get("active", False)
        return {"actor": actor, "trusted": trusted}

    def authorize(
        self,
        actor_id: str,
        capability: str,
        operation: str,
        prompt: str | None = None,
        token: str | None = None,
        parameters: dict[str, Any] | None = None,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Policy enforcement point:
        1. Prompt firewall & injection check (if prompt provided)
        2. Node / actor token authentication check
        3. Capability check (deny-by-default)
        4. Risk classification & human approval check (for HIGH risk)
        5. Audit event logging
        """
        # 1. Prompt Firewall Inspection
        if prompt:
            try:
                self.firewall.inspect(prompt)
            except Exception as exc:
                reason = f"Prompt firewall block: {exc}"
                self.audit.record(
                    actor=actor_id,
                    operation=operation,
                    capability=capability,
                    decision="DENIED",
                    reason=reason,
                    metadata={"prompt_snippet": prompt[:100]},
                )
                return {
                    "authorized": False,
                    "reason": reason,
                    "risk_level": RiskLevel.HIGH.value,
                    "approval_id": None,
                }

        # 2. Token Authentication (if token provided)
        if token:
            authenticated_node = self.nodes.authenticate_token(token)
            if not authenticated_node:
                reason = "Invalid or expired node authentication token"
                self.audit.record(
                    actor=actor_id,
                    operation=operation,
                    capability=capability,
                    decision="DENIED",
                    reason=reason,
                )
                return {
                    "authorized": False,
                    "reason": reason,
                    "risk_level": RiskLevel.HIGH.value,
                    "approval_id": None,
                }
            actor_id = authenticated_node

        # 3. Capability Check
        actor_caps = self.nodes.get_node_capabilities(actor_id)
        if not self.evaluator.evaluate(actor_caps, capability):
            reason = f"Actor '{actor_id}' lacks required capability '{capability}'"
            self.audit.record(
                actor=actor_id,
                operation=operation,
                capability=capability,
                decision="DENIED",
                reason=reason,
            )
            return {
                "authorized": False,
                "reason": reason,
                "risk_level": RiskLevel.HIGH.value,
                "approval_id": None,
            }

        # 4. Risk Classification & Approval check
        risk = self.risk_classifier.classify_operation(capability, parameters)

        if self.approvals.requires_approval(capability, risk):
            # Verify explicit approval_id capability scope
            if approval_id:
                appr_req = self.approvals.get_request(approval_id)
                if (
                    appr_req
                    and appr_req["status"] == "approved"
                    and appr_req["capability"] == capability
                ):
                    self.audit.record(
                        actor=actor_id,
                        operation=operation,
                        capability=capability,
                        decision="ALLOWED",
                        reason="Approved via human authorization",
                        approval_id=approval_id,
                    )
                    return {
                        "authorized": True,
                        "reason": "Authorized with explicit approval",
                        "risk_level": risk.value,
                        "approval_id": approval_id,
                    }

            # Otherwise, request approval and deny current execution
            appr_req = self.approvals.create_request(
                capability=capability,
                operation=operation,
                reason=f"High risk action requires approval: {operation}",
                requesting_actor=actor_id,
                risk_level=risk,
                parameters=parameters,
            )
            reason = f"Operation is HIGH risk and pending human approval (Approval ID: {appr_req['id']})"
            self.audit.record(
                actor=actor_id,
                operation=operation,
                capability=capability,
                decision="PENDING_APPROVAL",
                reason=reason,
                approval_id=appr_req["id"],
            )
            return {
                "authorized": False,
                "reason": reason,
                "risk_level": risk.value,
                "approval_id": appr_req["id"],
            }

        # 5. Authorization Granted
        self.audit.record(
            actor=actor_id,
            operation=operation,
            capability=capability,
            decision="ALLOWED",
            reason="Authorized by zero-trust policy",
        )
        return {
            "authorized": True,
            "reason": "Authorized",
            "risk_level": risk.value,
            "approval_id": None,
        }
