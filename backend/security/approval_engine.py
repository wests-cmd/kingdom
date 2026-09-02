import json
import uuid
import time
from pathlib import Path

DATA_PATH = Path("data/approvals.json")

HIGH_RISK_CAPABILITIES = {
    "filesystem.delete",
    "process.execute",
    "docker.execute",
    "system.admin"
}

MEDIUM_RISK_CAPABILITIES = {
    "filesystem.write",
    "memory.write",
    "ai_map.write"
}

class ApprovalEngine:

    def __init__(self, storage_path=DATA_PATH):
        self.storage_path = Path(storage_path)
        self.requests = {}
        self._load()

    def _load(self):
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self.requests = json.load(f)
            except Exception:
                self.requests = {}

    def _save(self):
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.requests, f, indent=2)
        except Exception:
            pass

    def classify_risk(self, capability=None, action=None, severity=None):
        if severity in ["critical", "destructive", "high"]:
            return "HIGH"
        if severity in ["medium", "moderate"]:
            return "MEDIUM"

        if capability in HIGH_RISK_CAPABILITIES:
            return "HIGH"
        if capability in MEDIUM_RISK_CAPABILITIES:
            return "MEDIUM"

        if action and any(kw in str(action).lower() for kw in ["delete", "rm", "exec", "shell", "sudo", "admin", "format"]):
            return "HIGH"

        return "LOW"

    def requires_approval(self, severity_or_risk=None, capability=None, action=None):
        risk = self.classify_risk(capability=capability, action=action, severity=severity_or_risk)
        return risk == "HIGH" or severity_or_risk in ["critical", "destructive"]

    def create_request(
        self,
        requesting_node,
        component,
        requested_capability,
        action,
        reason="Operation requires elevated authorization",
        risk_level=None,
        parameters=None,
        ttl_seconds=3600
    ):
        self.clean_expired()
        approval_id = str(uuid.uuid4())
        now = time.time()

        if not risk_level:
            risk_level = self.classify_risk(capability=requested_capability, action=action)

        req = {
            "approval_id": approval_id,
            "requesting_node": requesting_node or "unknown",
            "component": component or "unknown",
            "requested_capability": requested_capability,
            "action": action,
            "reason": reason,
            "risk_level": risk_level,
            "parameters": parameters or {},
            "created_at": now,
            "expires_at": now + ttl_seconds,
            "status": "pending",
            "approving_identity": None,
            "approval_timestamp": None,
            "denial_reason": None
        }

        self.requests[approval_id] = req
        self._save()
        return req

    def get_request(self, approval_id):
        self.clean_expired()
        return self.requests.get(approval_id)

    def list_requests(self, status=None):
        self.clean_expired()
        reqs = list(self.requests.values())
        if status:
            return [r for r in reqs if r.get("status") == status]
        return reqs

    def approve(self, approval_id, approving_identity="admin"):
        req = self.get_request(approval_id)
        if not req:
            return {"error": "Approval request not found"}
        if req["status"] != "pending":
            return {"error": f"Request cannot be approved in state '{req['status']}'"}

        req["status"] = "approved"
        req["approving_identity"] = approving_identity
        req["approval_timestamp"] = time.time()
        self._save()
        return req

    def deny(self, approval_id, denying_identity="admin", reason="Denied by policy administrator"):
        req = self.get_request(approval_id)
        if not req:
            return {"error": "Approval request not found"}
        if req["status"] != "pending":
            return {"error": f"Request cannot be denied in state '{req['status']}'"}

        req["status"] = "denied"
        req["approving_identity"] = denying_identity
        req["denial_reason"] = reason
        req["approval_timestamp"] = time.time()
        self._save()
        return req

    def clean_expired(self):
        now = time.time()
        modified = False
        for req in self.requests.values():
            if req.get("status") == "pending" and req.get("expires_at", 0) < now:
                req["status"] = "expired"
                modified = True
        if modified:
            self._save()

# Global instance
approval_engine = ApprovalEngine()
