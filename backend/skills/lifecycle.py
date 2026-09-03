from typing import Any, Dict, List, Optional
from backend.skills.models import Skill, SkillLifecycleState, SkillTrustLevel
from backend.skills.dependency import SkillDependencyEngine, DependencyResolutionError
from backend.skills.map import SkillMap


class SkillLifecycleError(Exception):
    pass


class SkillLifecycleManager:

    def __init__(
        self,
        skill_map: Optional[SkillMap] = None,
        available_tools: Optional[List[str]] = None,
        available_capabilities: Optional[List[str]] = None,
        available_models: Optional[List[str]] = None,
        granted_permissions: Optional[List[str]] = None
    ):
        self.skill_map = skill_map or SkillMap()
        self.available_tools = available_tools or []
        self.available_capabilities = available_capabilities or []
        self.available_models = available_models or []
        self.granted_permissions = granted_permissions or []
        self.skills: Dict[str, Skill] = self.skill_map.skills

    def save(self, skill: Skill) -> Skill:
        skill.state = SkillLifecycleState.SAVED
        self.skills[skill.id] = skill
        self.skill_map.add_skill(skill)
        return skill

    def install(self, skill_id: str) -> Skill:
        skill = self.skills.get(skill_id)
        if not skill:
            raise SkillLifecycleError(f"Skill '{skill_id}' not found.")

        if skill.state not in [SkillLifecycleState.SAVED, SkillLifecycleState.DISABLED]:
            raise SkillLifecycleError(f"Cannot install skill in state '{skill.state}'. Must be SAVED or DISABLED.")

        skill.state = SkillLifecycleState.INSTALLED
        return skill

    def activate(self, skill_id: str, governance_approved: bool = True) -> Skill:
        skill = self.skills.get(skill_id)
        if not skill:
            raise SkillLifecycleError(f"Skill '{skill_id}' not found.")

        if skill.state not in [SkillLifecycleState.INSTALLED, SkillLifecycleState.DISABLED]:
            raise SkillLifecycleError(f"Cannot activate skill in state '{skill.state}'. Must be INSTALLED or DISABLED.")

        if skill.state == SkillLifecycleState.QUARANTINED or skill.security_status == "QUARANTINED":
            raise SkillLifecycleError(f"Skill '{skill_id}' is QUARANTINED and cannot be activated.")

        if skill.trust_level == SkillTrustLevel.UNTRUSTED and not governance_approved:
            raise SkillLifecycleError(f"UNTRUSTED skill '{skill_id}' requires explicit governance approval to activate.")

        engine = SkillDependencyEngine(list(self.skills.values()))
        try:
            engine.resolve([skill])
        except DependencyResolutionError as exc:
            raise SkillLifecycleError(f"Dependency check failed for '{skill_id}': {exc}") from exc

        readiness = self.skill_map.check_readiness(
            skill=skill,
            available_tools=self.available_tools,
            available_capabilities=self.available_capabilities,
            available_models=self.available_models,
            granted_permissions=self.granted_permissions
        )

        if readiness["status"] != "READY":
            blockers_str = ", ".join(readiness["blockers"])
            raise SkillLifecycleError(f"Activation readiness failed for '{skill_id}': {blockers_str}")

        if not governance_approved:
            raise SkillLifecycleError(f"Governance approval required for skill activation: '{skill_id}'.")

        skill.state = SkillLifecycleState.ACTIVE
        return skill

    def deactivate(self, skill_id: str) -> Skill:
        skill = self.skills.get(skill_id)
        if not skill:
            raise SkillLifecycleError(f"Skill '{skill_id}' not found.")

        if skill.state != SkillLifecycleState.ACTIVE:
            raise SkillLifecycleError(f"Cannot deactivate skill in state '{skill.state}'. Must be ACTIVE.")

        skill.state = SkillLifecycleState.DISABLED
        return skill

    def remove(self, skill_id: str) -> Skill:
        skill = self.skills.get(skill_id)
        if not skill:
            raise SkillLifecycleError(f"Skill '{skill_id}' not found.")

        dependent_skills = []
        for s in self.skills.values():
            if s.id != skill_id and s.state in [SkillLifecycleState.ACTIVE, SkillLifecycleState.INSTALLED]:
                for req in s.dependencies.required_skills:
                    if req.name == skill.name:
                        dependent_skills.append(s.name)

        if dependent_skills:
            raise SkillLifecycleError(
                f"Cannot remove skill '{skill.name}' because active/installed skills depend on it: {', '.join(dependent_skills)}"
            )

        removed_skill = self.skills.pop(skill_id)
        if skill_id in self.skill_map.skills:
            del self.skill_map.skills[skill_id]

        return removed_skill
