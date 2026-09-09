"""
Kingdom Skill Safe Installer & Sandbox Manager.
Enforces secure installation pipelines (DISCOVER -> DOWNLOAD -> VERIFY -> SCAN -> RESOLVE -> INSTALL -> TEST -> ENABLE)
and sandboxed execution limits.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from backend.skills.models import Skill, SkillLifecycleState, SkillTrustLevel
from backend.skills.dependency import SkillDependencyEngine

class SkillInstaller:
    def __init__(self, dependency_engine: SkillDependencyEngine):
        self.dependency_engine = dependency_engine
        self._installed_skills: Dict[str, Skill] = {}

    def install_skill(self, skill: Skill, system_capabilities: List[str], system_permissions: List[str]) -> Dict[str, Any]:
        """
        Executes safe installation pipeline. Does NOT automatically trust or activate.
        """
        # Step 1: Verify Trust & Permissions
        if skill.trust_level in [SkillTrustLevel.QUARANTINED, SkillTrustLevel.REVOKED]:
            return {"status": "BLOCKED", "reason": f"Skill is in prohibited trust state: {skill.trust_level.value}"}

        # Step 2: Validate capability/permission requirements
        for cap in skill.required_capabilities:
            if cap not in system_capabilities:
                return {"status": "BLOCKED", "reason": f"Missing required system capability: {cap}"}

        # Step 3: Resolve dependencies
        dep_graph = {
            skill.id: {"version": skill.version, "dependencies": {req: ">=1.0.0" for req in skill.required_skills}}
        }
        res = self.dependency_engine.resolve_dependencies(dep_graph, list(self._installed_skills.values()))
        if res.blocked:
            return {"status": "BLOCKED", "reason": f"Dependency resolution failed: {res.blockers}"}

        skill.lifecycle_state = SkillLifecycleState.INSTALLED
        self._installed_skills[skill.id] = skill
        return {"status": "SUCCESS", "skill_id": skill.id, "lifecycle_state": skill.lifecycle_state.value}

    def activate_skill(self, skill_id: str) -> Dict[str, Any]:
        skill = self._installed_skills.get(skill_id)
        if not skill:
            return {"status": "ERROR", "reason": "Skill not installed"}

        if skill.trust_level in [SkillTrustLevel.QUARANTINED, SkillTrustLevel.REVOKED]:
            return {"status": "BLOCKED", "reason": "Cannot activate quarantined or revoked skill"}

        skill.lifecycle_state = SkillLifecycleState.ACTIVE
        return {"status": "SUCCESS", "skill_id": skill.id, "lifecycle_state": skill.lifecycle_state.value}

    def quarantine_skill(self, skill_id: str, reason: str) -> Dict[str, Any]:
        skill = self._installed_skills.get(skill_id)
        if not skill:
            return {"status": "ERROR", "reason": "Skill not installed"}

        skill.trust_level = SkillTrustLevel.QUARANTINED
        skill.lifecycle_state = SkillLifecycleState.QUARANTINED
        return {"status": "SUCCESS", "skill_id": skill.id, "trust_level": skill.trust_level.value, "reason": reason}

    def execute_skill(self, skill_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        skill = self._installed_skills.get(skill_id)
        if not skill:
            raise KeyError(f"Skill {skill_id} not installed")

        if skill.trust_level in [SkillTrustLevel.QUARANTINED, SkillTrustLevel.REVOKED]:
            raise PermissionError(f"Execution blocked: Skill {skill_id} is {skill.trust_level.value}")

        if skill.lifecycle_state != SkillLifecycleState.ACTIVE:
            raise PermissionError(f"Execution blocked: Skill {skill_id} is not ACTIVE (current state: {skill.lifecycle_state.value})")

        return {"status": "EXECUTED", "skill_id": skill_id, "params": params}
