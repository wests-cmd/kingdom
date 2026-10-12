"""Structured, secret-sanitized audit logging for Kingdom security events."""

from __future__ import annotations

import logging
import json
from pathlib import Path
from threading import RLock
import re
from datetime import datetime, timezone
from typing import Any

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger("kingdom.audit")

SECRET_KEY_RE = re.compile(
    r"(?i)(api[_-]?key|secret|password|token|bearer|auth|credentials)\s*[:=]\s*['\"]?([^'\"\s,#]+)['\"]?"
)
SK_KEY_RE = re.compile(r"sk-[a-zA-Z0-9]{32,}")


class AuditLogger:
    def __init__(self, max_history: int = 1000) -> None:
        self.max_history = max_history
        self._records: list[dict[str, Any]] = []
        self._lock = RLock()

    def record(
        self,
        actor: str,
        operation: str,
        capability: str,
        decision: str,  # "ALLOWED", "DENIED", "PENDING_APPROVAL", "EXPIRED", "ERROR"
        reason: str,
        node: str | None = None,
        target: str | None = None,
        approval_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        record = {
            "timestamp": now.isoformat(),
            "actor": self._sanitize_value(actor),
            "node": self._sanitize_value(node or actor),
            "operation": self._sanitize_value(operation),
            "capability": capability,
            "target": self._sanitize_value(target or "system"),
            "decision": decision,
            "reason": self._sanitize_value(reason),
            "approval_id": approval_id,
            "request_id": request_id,
            "metadata": self._sanitize_dict(metadata or {}),
        }

        with self._lock:
            path = Path("data/logs/audit.jsonl")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record, sort_keys=True) + "\n")
            self._records.append(record)
        if len(self._records) > self.max_history:
            self._records.pop(0)

        log_msg = f"[AUDIT] decision={decision} actor={record['actor']} cap={capability} op={record['operation']} reason={record['reason']}"
        if decision == "DENIED":
            _logger.warning(log_msg)
        else:
            _logger.info(log_msg)

        return record

    def log_event(
        self,
        actor: str,
        operation: str,
        capability: str,
        decision: str,
        reason: str,
        node: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.record(
            actor=actor,
            operation=operation,
            capability=capability,
            decision=decision.upper(),
            reason=reason,
            node=node,
            **kwargs,
        )

    def history(
        self,
        limit: int = 100,
        actor: str | None = None,
        decision: str | None = None,
        capability: str | None = None,
    ) -> list[dict[str, Any]]:
        filtered = self._records
        if actor:
            filtered = [r for r in filtered if r["actor"] == actor]
        if decision:
            filtered = [r for r in filtered if r["decision"] == decision]
        if capability:
            filtered = [r for r in filtered if r["capability"] == capability]

        return list(reversed(filtered[-limit:]))

    def _sanitize_any(self, val: Any) -> Any:
        if isinstance(val, str):
            return self._sanitize_value(val)
        elif isinstance(val, dict):
            return self._sanitize_dict(val)
        elif isinstance(val, (list, tuple, set)):
            items = [self._sanitize_any(item) for item in val]
            return items if isinstance(val, set) else type(val)(items)
        return val

    def _sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        sanitized = {}
        for key, value in data.items():
            key_str = str(key)
            if any(term in key_str.lower() for term in ("key", "secret", "password", "token", "auth")):
                sanitized[key_str] = "******"
            else:
                sanitized[key_str] = self._sanitize_any(value)
        return sanitized

    def _sanitize_value(self, val: str) -> str:
        if not isinstance(val, str):
            return str(val)
        result = SECRET_KEY_RE.sub(r"\1=******", val)
        result = SK_KEY_RE.sub("sk-******", result)
        return result


# Global singleton instance for system audit logging
audit_log = AuditLogger()
audit_logger = audit_log
