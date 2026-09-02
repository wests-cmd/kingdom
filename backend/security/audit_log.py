import logging
import json
import time
from pathlib import Path

AUDIT_LOG_PATH = Path("data/logs/audit.jsonl")

logger = logging.getLogger("kingdom.audit")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

SENSITIVE_KEYS = {"password", "secret", "token", "api_key", "auth_token", "private_key", "bearer"}

def sanitize_data(data):
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data

class AuditLogger:

    def __init__(self, log_file=AUDIT_LOG_PATH):
        self.log_file = Path(log_file)

    def log_event(
        self,
        actor,
        node,
        operation,
        capability,
        decision,
        reason,
        target=None,
        approval_id=None,
        correlation_id=None,
        extra=None
    ):
        event = {
            "timestamp": time.time(),
            "actor": sanitize_data(str(actor)),
            "node": sanitize_data(str(node)),
            "operation": operation,
            "capability": capability,
            "decision": decision,
            "reason": reason,
            "target": target,
            "approval_id": approval_id,
            "correlation_id": correlation_id,
            "extra": sanitize_data(extra) if extra else None
        }

        logger.info(f"AUDIT | {decision.upper()} | op={operation} cap={capability} actor={actor} reason={reason}")

        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log to file: {e}")

        return event

    def get_events(self, limit=100, decision=None, actor=None):
        if not self.log_file.exists():
            return []

        events = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        if decision and record.get("decision") != decision:
                            continue
                        if actor and record.get("actor") != actor:
                            continue
                        events.append(record)
                    except Exception:
                        pass
        except Exception:
            return []

        return events[-limit:]

# Global instance
audit_logger = AuditLogger()
