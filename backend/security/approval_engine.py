"""Human-in-the-loop approval management engine for high-risk Kingdom operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Literal

from backend.security.risk import RiskLevel

ApprovalStatus = Literal["pending", "approved", "denied", "expired", "cancelled"]


class ApprovalEngine:
    def __init__(self, default_ttl_seconds: int = 3600) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._requests: dict[str, dict[str, Any]] = {}

    def requires_approval(self, capability_or_severity: str, risk_level: RiskLevel | str | None = None) -> bool:
        """
        Determines whether an operation requires explicit approval.
        High risk operations or critical/destructive severities require approval by default.
        """
        if capability_or_severity in ("critical", "destructive"):
            return True

        if isinstance(risk_level, str):
            risk_level = risk_level.upper()

        if risk_level == RiskLevel.HIGH or risk_level == "HIGH":
            return True

        return False

    def create_request(
        self,
        capability: str,
        operation: str,
        reason: str = "",
        requesting_actor: str = "system",
        requesting_node: str | None = None,
        requesting_tool: str | None = None,
        risk_level: RiskLevel | str = RiskLevel.HIGH,
        parameters: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = now + timedelta(seconds=ttl)

        request_id = f"appr_{uuid.uuid4().hex[:12]}"
        request_record = {
            "id": request_id,
            "requesting_actor": requesting_actor,
            "requesting_node": requesting_node or requesting_actor,
            "requesting_tool": requesting_tool or "core",
            "capability": capability,
            "operation": operation,
            "reason": reason,
            "risk_level": str(risk_level),
            "parameters": parameters or {},
            "status": "pending",
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "approved_by": None,
            "approved_at": None,
            "denial_reason": None,
        }

        self._requests[request_id] = request_record
        return request_record

    def get_request(self, approval_id: str) -> dict[str, Any] | None:
        self._expire_stale()
        return self._requests.get(approval_id)

    def list_requests(self, status: str | None = None) -> list[dict[str, Any]]:
        self._expire_stale()
        requests = list(self._requests.values())
        if status:
            requests = [r for r in requests if r["status"] == status]
        return sorted(requests, key=lambda x: x["created_at"], reverse=True)

    def approve(self, approval_id: str, approver: str = "admin") -> dict[str, Any]:
        req = self.get_request(approval_id)
        if req is None:
            raise KeyError(f"Approval request '{approval_id}' not found")
        if req["status"] != "pending":
            raise ValueError(f"Cannot approve request with status '{req['status']}'")

        now = datetime.now(timezone.utc)
        req["status"] = "approved"
        req["approved_by"] = approver
        req["approved_at"] = now.isoformat()
        return req

    def deny(self, approval_id: str, reason: str = "Denied by administrator", denier: str = "admin") -> dict[str, Any]:
        req = self.get_request(approval_id)
        if req is None:
            raise KeyError(f"Approval request '{approval_id}' not found")
        if req["status"] != "pending":
            raise ValueError(f"Cannot deny request with status '{req['status']}'")

        now = datetime.now(timezone.utc)
        req["status"] = "denied"
        req["approved_by"] = denier
        req["denial_reason"] = reason
        req["approved_at"] = now.isoformat()
        return req

    def is_approved(self, approval_id: str) -> bool:
        req = self.get_request(approval_id)
        return req is not None and req["status"] == "approved"

    def _expire_stale(self) -> None:
        now = datetime.now(timezone.utc)
        for req in self._requests.values():
            if req["status"] == "pending":
                exp = datetime.fromisoformat(req["expires_at"])
                if now >= exp:
                    req["status"] = "expired"
