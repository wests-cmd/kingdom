"""Authenticated human boundary for the local/server control plane."""
import hmac
import os
from pathlib import Path
import re
import secrets

from fastapi import HTTPException, Request
from backend.security.identity_fabric import IdentityFabric, IdentityType


class OwnerAuthentication:
    def __init__(self):
        token = os.environ.get("KINGDOM_OWNER_TOKEN")
        if token is None:
            path = Path("data/owner-token")
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w") as handle:
                    handle.write(secrets.token_urlsafe(48))
            token = path.read_text().strip()
            path.chmod(0o600)
        if len(token) < 32 or any(c.isspace() for c in token):
            raise RuntimeError("KINGDOM_OWNER_TOKEN must be an unpredictable access code of at least 32 characters")
        self.token = token
        self.fabric = IdentityFabric()
        identity = self.fabric.register_identity(IdentityType.HUMAN_USER, "Kingdom owner",
                                                 capabilities=["system.admin"], trust_level="TRUSTED")
        del self.fabric.identities[identity.identity_id]
        identity.identity_id = "owner"
        self.fabric.identities["owner"] = identity
        self.fabric.activate_identity("owner")

    def authenticate(self, token):
        if not isinstance(token, str) or not hmac.compare_digest(token, self.token):
            raise HTTPException(status_code=401, detail="A valid owner access code is required")
        return self.fabric.verify_active_identity("owner")


owner_auth = OwnerAuthentication()

PUBLIC_GET = {"/health/live", "/health/ready", "/api/system/version", "/api/system/compatibility", "/nodes/identity"}
PUBLIC_POST = {"/nodes/pair", "/nodes/rpc", "/mobile/pair", "/mobile/session/status"}


def require_owner(request: Request):
    path = request.url.path
    if request.method == "GET" and (path in PUBLIC_GET or re.fullmatch(r"/nodes/[^/]+/status", path)):
        return None
    if request.method == "POST" and path in PUBLIC_POST:
        return None  # Invitation proof or signed RPC authenticates these independently.
    bearer = request.headers.get("Authorization", "")
    if bearer.startswith("Bearer "):
        token = bearer[7:]
    else:
        token = request.cookies.get("kingdom_session")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("X-Kingdom-Request") != "1":
            raise HTTPException(status_code=403, detail="Authenticated control-plane request header is required")
    identity = owner_auth.authenticate(token)
    origin = request.headers.get("origin")
    allowed = {request.url.scheme + "://" + request.url.netloc} | set(os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","))
    if origin and origin not in allowed:
        raise HTTPException(status_code=403, detail="Untrusted request origin")
    request.state.principal = identity
    return identity
