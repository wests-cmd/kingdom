"""
Tests for SkillInstaller and SkillTestHarness.
"""

from backend.skills.installer import SkillInstaller
from backend.skills.test_harness import SkillTestHarness
from backend.skills.models import Skill, SkillLifecycleState, SkillTrustLevel
from backend.skills.dependency import SkillDependencyEngine

def test_skill_installer_pipeline():
    dep_engine = SkillDependencyEngine()
    installer = SkillInstaller(dep_engine)

    skill = Skill(
        id="org.kingdom.skill.research",
        name="Research Skill",
        version="1.0.0",
        description="Web and document research",
        author="Kingdom",
        provenance="official",
        department="Research",
        category="Intelligence",
        capability="research",
        required_capabilities=["python.exec"],
        trust_level=SkillTrustLevel.VERIFIED
    )

    # Missing capability
    res_blocked = installer.install_skill(skill, [], [])
    assert res_blocked["status"] == "BLOCKED"

    # Valid installation
    res_installed = installer.install_skill(skill, ["python.exec"], [])
    assert res_installed["status"] == "SUCCESS"
    assert skill.lifecycle_state == SkillLifecycleState.INSTALLED

    # Activation
    res_act = installer.activate_skill("org.kingdom.skill.research")
    assert res_act["status"] == "SUCCESS"
    assert skill.lifecycle_state == SkillLifecycleState.ACTIVE

def test_skill_test_harness_prohibited_permissions():
    harness = SkillTestHarness()
    bad_skill = Skill(
        id="org.kingdom.badskill",
        name="Bad Skill",
        version="1.0.0",
        description="Malicious permission skill",
        author="Unknown",
        provenance="untrusted",
        department="Unknown",
        category="Unknown",
        capability="unrestricted",
        permissions=["admin:all"]
    )

    res = harness.run_skill_tests(bad_skill)
    assert res["passed"] is False
    assert res["security_pass"] is False
