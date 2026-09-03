from typing import Any, Dict, List, Optional
from backend.skills.models import Skill, SkillLifecycleState
from backend.skills.dependency import SkillDependencyEngine


class SkillMap:

    def __init__(self, skills: Optional[List[Skill]] = None):
        self.skills: Dict[str, Skill] = {}
        if skills:
            for s in skills:
                self.add_skill(s)

    def add_skill(self, skill: Skill):
        self.skills[skill.id] = skill

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        return self.skills.get(skill_id)

    def list_skills(self) -> List[Skill]:
        return list(self.skills.values())

    def get_map_structure(self) -> Dict[str, Any]:
        nodes = []
        links = []
        departments: Dict[str, List[str]] = {}

        for skill in self.skills.values():
            dept = skill.department or "general"
            if dept not in departments:
                departments[dept] = []
            departments[dept].append(skill.id)

            skill_node = {
                "id": skill.id,
                "name": skill.name,
                "version": skill.version,
                "type": "skill",
                "department": dept,
                "category": skill.category,
                "capability": skill.capability,
                "state": skill.state.value,
                "trust_level": skill.trust_level.value,
                "required_skills": [req.name for req in skill.dependencies.required_skills],
                "required_tools": skill.dependencies.required_tools,
                "required_capabilities": skill.dependencies.required_capabilities,
                "required_models": skill.dependencies.required_models,
                "permissions": skill.permissions,
            }
            nodes.append(skill_node)

            for req in skill.dependencies.required_skills:
                target_skill = next((s for s in self.skills.values() if s.name == req.name), None)
                if target_skill:
                    links.append({
                        "source": skill.id,
                        "target": target_skill.id,
                        "relation": "requires_skill",
                        "constraint": req.version_constraint
                    })

        return {
            "departments": departments,
            "nodes": nodes,
            "links": links
        }

    def check_readiness(
        self,
        skill: Skill,
        available_tools: List[str],
        available_capabilities: List[str],
        available_models: List[str],
        granted_permissions: List[str]
    ) -> Dict[str, Any]:
        blockers = []
        missing_tools = []
        missing_capabilities = []
        missing_models = []
        missing_permissions = []
        missing_skills = []

        for tool in skill.dependencies.required_tools:
            if tool not in available_tools:
                missing_tools.append(tool)
                blockers.append(f"Missing tool: {tool}")

        for cap in skill.dependencies.required_capabilities:
            if cap not in available_capabilities:
                missing_capabilities.append(cap)
                blockers.append(f"Missing capability: {cap}")

        for model in skill.dependencies.required_models:
            if model not in available_models:
                missing_models.append(model)
                blockers.append(f"Missing model: {model}")

        for perm in skill.permissions:
            if perm not in granted_permissions:
                missing_permissions.append(perm)
                blockers.append(f"Permission required: {perm}")

        for req in skill.dependencies.required_skills:
            dep_skill = next((s for s in self.skills.values() if s.name == req.name), None)
            if not dep_skill or dep_skill.state not in [SkillLifecycleState.ACTIVE, SkillLifecycleState.INSTALLED]:
                missing_skills.append(f"{req.name} ({req.version_constraint})")
                blockers.append(f"Missing active skill dependency: {req.name} ({req.version_constraint})")

        status = "READY" if not blockers else "NOT READY"

        return {
            "skill_id": skill.id,
            "skill_name": skill.name,
            "status": status,
            "blockers": blockers,
            "details": {
                "missing_tools": missing_tools,
                "missing_capabilities": missing_capabilities,
                "missing_models": missing_models,
                "missing_permissions": missing_permissions,
                "missing_skills": missing_skills
            }
        }
