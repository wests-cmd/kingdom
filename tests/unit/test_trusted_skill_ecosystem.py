import pytest
from backend.skills.trust_model import SkillTrustRegistry, SkillTrustLevel


@pytest.fixture
def sample_skill_manifest_dict():
    return {
        "skill_id": "skill_pdf_parser",
        "name": "PDF Document Parser",
        "version": "1.0.0",
        "publisher_id": "pub_official_kingdom",
        "capabilities_requested": ["filesystem.read", "memory.write"],
        "permissions_requested": ["filesystem.read"],
        "risk_classification": "LOW"
    }


def test_skill_trust_registry_manifest_validation(sample_skill_manifest_dict):
    registry = SkillTrustRegistry()

    # 1. Register valid skill
    manifest = registry.register_skill_manifest(sample_skill_manifest_dict)
    assert manifest.skill_id == "skill_pdf_parser"
    assert manifest.trust_level == SkillTrustLevel.UNVERIFIED

    # 2. Reject prohibited permission
    bad_manifest = sample_skill_manifest_dict.copy()
    bad_manifest["skill_id"] = "skill_bad_kernel"
    bad_manifest["permissions_requested"] = ["kernel.bypass_security"]

    with pytest.raises(PermissionError, match="prohibited kernel permission"):
        registry.register_skill_manifest(bad_manifest)


def test_skill_trust_level_transitions(sample_skill_manifest_dict):
    registry = SkillTrustRegistry()
    registry.register_skill_manifest(sample_skill_manifest_dict)

    # Promote to VERIFIED then TRUSTED
    registry.promote_trust_level("skill_pdf_parser", SkillTrustLevel.VERIFIED, promoter="admin")
    assert registry.skills["skill_pdf_parser"].trust_level == SkillTrustLevel.VERIFIED

    registry.promote_trust_level("skill_pdf_parser", SkillTrustLevel.TRUSTED, promoter="admin")
    assert registry.skills["skill_pdf_parser"].trust_level == SkillTrustLevel.TRUSTED

    # Quarantine skill
    registry.quarantine_skill("skill_pdf_parser", reason="Anomaly detected in output")
    assert registry.skills["skill_pdf_parser"].trust_level == SkillTrustLevel.QUARANTINED

    # Revoke skill
    registry.revoke_skill("skill_pdf_parser", reason="Security vulnerability")
    assert registry.skills["skill_pdf_parser"].trust_level == SkillTrustLevel.REVOKED

    # Cannot promote revoked skill
    with pytest.raises(ValueError, match="is REVOKED and cannot be promoted"):
        registry.promote_trust_level("skill_pdf_parser", SkillTrustLevel.TRUSTED, promoter="admin")


def test_skill_capability_boundary_and_revocation_blocking(sample_skill_manifest_dict):
    registry = SkillTrustRegistry()
    registry.register_skill_manifest(sample_skill_manifest_dict)

    # 1. Valid execution authority check
    authorized = registry.verify_execution_authority(
        skill_id="skill_pdf_parser",
        requested_capability="filesystem.read",
        caller_permissions=["filesystem.read"]
    )
    assert authorized is True

    # 2. Capability boundary error (undeclared capability)
    with pytest.raises(PermissionError, match="capability boundary error"):
        registry.verify_execution_authority(
            skill_id="skill_pdf_parser",
            requested_capability="filesystem.delete",  # Undeclared!
            caller_permissions=["filesystem.delete"]
        )

    # 3. Caller missing required permission
    with pytest.raises(PermissionError, match="Caller lacking permission"):
        registry.verify_execution_authority(
            skill_id="skill_pdf_parser",
            requested_capability="filesystem.read",
            caller_permissions=[]  # Empty permissions!
        )

    # 4. Revocation blocks execution
    registry.revoke_skill("skill_pdf_parser", reason="Compromised")
    with pytest.raises(PermissionError, match="Trust level is 'REVOKED'"):
        registry.verify_execution_authority(
            skill_id="skill_pdf_parser",
            requested_capability="filesystem.read",
            caller_permissions=["filesystem.read"]
        )
