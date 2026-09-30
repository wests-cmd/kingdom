"""Human-in-the-loop approval management engine for high-risk Kingdom operations."""

from __future__ import annotations

import uuid
import json
import time
from copy import deepcopy
from backend.storage.db import db
from datetime import datetime, timezone, timedelta
from typing import Any, Literal

from backend.security.risk import RiskLevel

ApprovalStatus = Literal["pending", "approved", "denied", "expired", "cancelled"]


class ApprovalEngine:
    def __init__(self, default_ttl_seconds: int = 3600, database=None) -> None:
        self.db = database or db
        self.default_ttl_seconds = default_ttl_seconds
        self._requests: dict[str, dict[str, Any]] = {}
        self._reload()

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
        *args: Any,
        capability: str | None = None,
        operation: str | None = None,
        reason: str = "",
        requesting_actor: str = "system",
        requesting_node: str | None = None,
        requesting_tool: str | None = None,
        requested_capability: str | None = None,
        action: str | None = None,
        risk_level: RiskLevel | str = RiskLevel.HIGH,
        parameters: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        req_node = requesting_node
        req_actor = requesting_actor
        cap = capability or requested_capability
        op = operation or action
        reas = reason

        if args:
            if len(args) == 5:
                # Signature: create_request(requesting_node, component, requested_capability, action, reason)
                req_node = args[0]
                req_actor = args[1]
                cap = args[2]
                op = args[3]
                reas = args[4]
            elif len(args) == 4:
                # Signature: create_request(capability, operation, reason, requesting_actor)
                cap = args[0]
                op = args[1]
                reas = args[2]
                req_actor = args[3]
            elif len(args) == 3:
                # Signature: create_request(capability, operation, reason)
                cap = args[0]
                op = args[1]
                reas = args[2]
            elif len(args) == 2:
                # Signature: create_request(capability, operation)
                cap = args[0]
                op = args[1]
            elif len(args) == 1:
                # Signature: create_request(capability)
                cap = args[0]

        cap = cap or "system.default"
        op = op or "execute"

        now = datetime.now(timezone.utc)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = now + timedelta(seconds=ttl)

        request_id = f"appr_{uuid.uuid4().hex[:12]}"
        request_record = {
            "id": request_id,
            "approval_id": request_id,
            "requesting_actor": req_actor,
            "requesting_node": req_node or req_actor,
            "requesting_tool": requesting_tool or "core",
            "capability": cap,
            "operation": op,
            "reason": reas,
            "risk_level": str(risk_level),
            "parameters": parameters or {},
            "status": "pending",
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "approved_by": None,
            "approved_at": None,
            "denial_reason": None,
        }

        self._save(request_record)
        self._requests[request_id] = request_record
        return deepcopy(request_record)

    def get_request(self, approval_id: str) -> dict[str, Any] | None:
        self._expire_stale()
        return deepcopy(self._requests.get(approval_id))

    def list_requests(self, status: str | None = None) -> list[dict[str, Any]]:
        self._expire_stale()
        requests = deepcopy(list(self._requests.values()))
        if status:
            requests = [r for r in requests if r["status"] == status]
        return sorted(requests, key=lambda x: x["created_at"], reverse=True)

    def _decide(self, approval_id, status, approver, reason=None):
        with self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT value_json FROM runtime_state WHERE key=?", ("approval:" + approval_id,)).fetchone()
            if row is None:
                raise KeyError(f"Approval request '{approval_id}' not found")
            req = json.loads(row[0])
            if req["status"] != "pending" or datetime.now(timezone.utc) >= datetime.fromisoformat(req["expires_at"]):
                raise ValueError("Only an unexpired pending approval can be decided")
            req.update(status=status, approved_by=approver, approved_at=datetime.now(timezone.utc).isoformat(), denial_reason=reason)
            conn.execute("UPDATE runtime_state SET value_json=?,updated_at=? WHERE key=?", (json.dumps(req, sort_keys=True), time.time(), "approval:" + approval_id))
            conn.commit()
        self._requests[approval_id] = req
        return deepcopy(req)

    def approve(self, approval_id: str, approver: str = "admin"):
        return self._decide(approval_id, "approved", approver)

    def deny(self, approval_id: str, reason: str = "Denied by administrator", denier: str = "admin"):
        return self._decide(approval_id, "denied", denier, reason)

    def is_approved(self, approval_id: str) -> bool:
        req = self.get_request(approval_id)
        return req is not None and req["status"] == "approved"

    def _expire_stale(self) -> None:
        self._reload()
        now = datetime.now(timezone.utc)
        for req in self._requests.values():
            if req["status"] in {"pending", "approved"}:
                exp = datetime.fromisoformat(req["expires_at"])
                if now >= exp:
                    req["status"] = "expired"
                    self._save(req)

    def _reload(self):
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT value_json FROM runtime_state WHERE key LIKE 'approval:%'").fetchall()
        self._requests = {r["id"]: r for r in (json.loads(row[0]) for row in rows)}

    def _save(self, request):
        with self.db.get_connection() as conn:
            conn.execute("INSERT INTO runtime_state(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
                         ("approval:" + request["id"], json.dumps(request, sort_keys=True), time.time()))
            conn.commit()

    def consume(self, approval_id, *, actor_id, capability, operation, parameters):
        """Atomically spend one unexpired approval for its exact actor and operation."""
        with self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT value_json FROM runtime_state WHERE key=?", ("approval:" + approval_id,)).fetchone()
            if row is None:
                return False
            req = json.loads(row[0])
            if req["status"] != "approved" or datetime.now(timezone.utc) >= datetime.fromisoformat(req["expires_at"]):
                return False
            if req["requesting_actor"] != actor_id or req["capability"] != capability or req["operation"] != operation or req["parameters"] != (parameters or {}):
                return False
            req["status"] = "consumed"
            req["consumed_at"] = datetime.now(timezone.utc).isoformat()
            conn.execute("UPDATE runtime_state SET value_json=?,updated_at=? WHERE key=?", (json.dumps(req, sort_keys=True), time.time(), "approval:" + approval_id))
            conn.commit()
        self._requests[approval_id] = req
        return True


approval_engine = ApprovalEngine()
