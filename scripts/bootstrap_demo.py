"""
Kingdom Demo Bootstrap Script.
Explicitly installs sample skills and demo fixtures for demo environment evaluation.
"""

from backend.skills.models import Skill, SkillTrustLevel, SkillLifecycleState, SkillDependency
from backend.skills.lifecycle import SkillLifecycleManager

def bootstrap_demo_fixtures():
    sample_skill = Skill(
        id="skill-web-research",
        name="Web Research",
        version="1.0.0",
        description="Automated web research and document analysis (Demo)",
        department="Research",
        trust_level=SkillTrustLevel.VERIFIED,
        state=SkillLifecycleState.ACTIVE,
        permissions=["network.outbound"],
        dependencies=SkillDependency(
            required_tools=["http_client"],
            required_capabilities=["model.inference"],
            required_models=["gpt-4o"]
        )
    )

    mgr = SkillLifecycleManager(
        available_tools=["http_client", "pdf_parser"],
        available_capabilities=["model.inference", "python.exec"],
        available_models=["gpt-4o"],
        granted_permissions=["network.outbound", "filesystem.read"]
    )
    mgr.save(sample_skill)
    mgr.install(sample_skill.id)
    mgr.activate(sample_skill.id, governance_approved=True)
    print("Demo skill 'skill-web-research' successfully bootstrapped.")

if __name__ == "__main__":
    bootstrap_demo_fixtures()
