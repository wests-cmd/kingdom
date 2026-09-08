import time
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class SkillTrustLevel(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    TRUSTED = "TRUSTED"
    QUARANTINED = "QUARANTINED"
    REVOKED = "REVOKED"


class CanonicalSkillManifest(BaseModel):
    skill_id: str
    name: str
    version: str
    publisher_id: str
    source: str = "official_repository"
    kingdom_compatibility: str = ">=40.0.0"
    capabilities_requested: List[str] = Field(default_factory=list)
    permissions_requested: List[str] = Field(default_factory=list)
    dependencies: Dict[str, str] = Field(default_factory=dict)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    risk_classification: str = "MEDIUM"
    trust_level: SkillTrustLevel = SkillTrustLevel.UNVERIFIED
    publisher_signature: Optional[str] = None
    created_at: float = Field(default_factory=time.time)


class SkillTrustRegistry:

    PROHIBITED_SKILL_PERMISSIONS = {
        "kernel.bypass_security",
        "system.disable_audit",
        "governance.auto_approve",
        "root.escalate"
    }

    def __init__(self):
        self.skills: Dict[str, CanonicalSkillManifest] = {}

    def register_skill_manifest(self, manifest_data: dict) -> CanonicalSkillManifest:
        manifest = CanonicalSkillManifest(**manifest_data)

        # Prohibited permission check
        for perm in manifest.permissions_requested:
            if perm in self.PROHIBITED_SKILL_PERMISSIONS:
                raise PermissionError(f"Skill '{manifest.skill_id}' requested prohibited kernel permission '{perm}'.")

        self.skills[manifest.skill_id] = manifest
        return manifest

    def promote_trust_level(self, skill_id: str, new_trust_level: SkillTrustLevel, promoter: str) -> CanonicalSkillManifest:
        manifest = self.skills.get(skill_id)
        if not manifest:
            raise KeyError(f"Skill '{skill_id}' not found in trust registry.")

        if manifest.trust_level == SkillTrustLevel.REVOKED:
            raise ValueError(f"Skill '{skill_id}' is REVOKED and cannot be promoted.")

        manifest.trust_level = new_trust_level
        return manifest

    def quarantine_skill(self, skill_id: str, reason: str) -> CanonicalSkillManifest:
        manifest = self.skills.get(skill_id)
        if not manifest:
            raise KeyError(f"Skill '{skill_id}' not found in trust registry.")

        manifest.trust_level = SkillTrustLevel.QUARANTINED
        return manifest

    def revoke_skill(self, skill_id: str, reason: str) -> CanonicalSkillManifest:
        manifest = self.skills.get(skill_id)
        if not manifest:
            raise KeyError(f"Skill '{skill_id}' not found in trust registry.")

        manifest.trust_level = SkillTrustLevel.REVOKED
        return manifest

    def verify_execution_authority(
        self,
        skill_id: str,
        requested_capability: str,
        caller_permissions: List[str]
    ) -> bool:
        manifest = self.skills.get(skill_id)
        if not manifest:
            raise PermissionError(f"Skill '{skill_id}' is not registered in Trust Registry.")

        if manifest.trust_level in [SkillTrustLevel.REVOKED, SkillTrustLevel.QUARANTINED]:
            raise PermissionError(f"Skill '{skill_id}' execution blocked: Trust level is '{manifest.trust_level.value}'.")

        if requested_capability not in manifest.capabilities_requested:
            raise PermissionError(f"Skill '{skill_id}' capability boundary error: Capability '{requested_capability}' was not declared in manifest.")

        # Check caller permissions
        if requested_capability not in caller_permissions and "admin" not in caller_permissions and "*" not in caller_permissions:
            raise PermissionError(f"Caller lacking permission for capability '{requested_capability}' requested by skill '{skill_id}'.")

        return True
