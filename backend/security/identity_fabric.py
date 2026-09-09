import time
import secrets
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from backend.cluster.identity import BaseNodeIdentity


class IdentityType(str, Enum):
    HUMAN_USER = "human_user"
    COMMANDER = "commander"
    KNIGHT = "knight"
    MOBILE_CLIENT = "mobile_client"
    INTELLIGENCE_MODEL = "intelligence_model"
    SKILL = "skill"
    EXTENSION = "extension"
    TOOL = "tool"
    WORKFLOW = "workflow"
    SERVICE_ACCOUNT = "service_account"


class IdentityState(str, Enum):
    DISCOVERED = "DISCOVERED"
    AUTHENTICATED = "AUTHENTICATED"
    AUTHORIZED = "AUTHORIZED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    QUARANTINED = "QUARANTINED"
    REVOKED = "REVOKED"


class SystemIdentity(BaseModel):
    identity_id: str = Field(default_factory=lambda: f"id_{secrets.token_hex(8)}")
    identity_type: IdentityType
    display_name: str
    issuer: str = "KG-MASTER-AUTHORITY"
    public_key_hex: Optional[str] = None
    fingerprint: Optional[str] = None
    state: IdentityState = IdentityState.DISCOVERED
    created_at: float = Field(default_factory=time.time)
    expires_at: Optional[float] = None
    capabilities: List[str] = Field(default_factory=list)
    trust_level: str = "UNVERIFIED"
    revocation_reason: Optional[str] = None


class IdentityFabric:

    def __init__(self):
        self.identities: Dict[str, SystemIdentity] = {}

    def register_identity(
        self,
        identity_type: IdentityType,
        display_name: str,
        public_key_hex: Optional[str] = None,
        fingerprint: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        trust_level: str = "UNVERIFIED",
        expires_in_sec: Optional[float] = None
    ) -> SystemIdentity:
        now = time.time()
        expires_at = (now + expires_in_sec) if expires_in_sec else None

        ident = SystemIdentity(
            identity_type=identity_type,
            display_name=display_name,
            public_key_hex=public_key_hex,
            fingerprint=fingerprint,
            state=IdentityState.AUTHENTICATED,
            capabilities=capabilities or [],
            trust_level=trust_level,
            expires_at=expires_at
        )
        self.identities[ident.identity_id] = ident
        return ident

    def activate_identity(self, identity_id: str) -> SystemIdentity:
        ident = self.identities.get(identity_id)
        if not ident:
            raise KeyError(f"Identity '{identity_id}' not found.")

        if ident.state in [IdentityState.REVOKED, IdentityState.QUARANTINED]:
            raise ValueError(f"Identity '{identity_id}' is in terminal state '{ident.state}' and cannot be activated.")

        ident.state = IdentityState.ACTIVE
        return ident

    def suspend_identity(self, identity_id: str, reason: str) -> SystemIdentity:
        ident = self.identities.get(identity_id)
        if not ident:
            raise KeyError(f"Identity '{identity_id}' not found.")

        ident.state = IdentityState.SUSPENDED
        ident.revocation_reason = reason
        return ident

    def quarantine_identity(self, identity_id: str, reason: str) -> SystemIdentity:
        ident = self.identities.get(identity_id)
        if not ident:
            raise KeyError(f"Identity '{identity_id}' not found.")

        ident.state = IdentityState.QUARANTINED
        ident.revocation_reason = reason
        return ident

    def revoke_identity(self, identity_id: str, reason: str) -> SystemIdentity:
        ident = self.identities.get(identity_id)
        if not ident:
            raise KeyError(f"Identity '{identity_id}' not found.")

        ident.state = IdentityState.REVOKED
        ident.revocation_reason = reason
        return ident

    def get_identity(self, identity_id: str) -> Optional[SystemIdentity]:
        ident = self.identities.get(identity_id)
        if not ident:
            return None

        # Check expiration
        if ident.expires_at and time.time() > ident.expires_at and ident.state == IdentityState.ACTIVE:
            ident.state = IdentityState.SUSPENDED
            ident.revocation_reason = "Expired identity token"

        return ident

    def verify_active_identity(self, identity_id: str) -> SystemIdentity:
        ident = self.get_identity(identity_id)
        if not ident:
            raise PermissionError(f"Identity '{identity_id}' is unknown/unregistered.")

        if ident.state != IdentityState.ACTIVE:
            raise PermissionError(f"Identity '{identity_id}' is not ACTIVE. Current state: '{ident.state}' (Reason: {ident.revocation_reason})")

        return ident
