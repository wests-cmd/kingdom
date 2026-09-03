from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.skills.models import Skill
from backend.skills.dependency import SkillDependencyEngine, DependencyResolutionError


class SkillBundle(BaseModel):
    id: str
    name: str
    description: str = ""
    department: str = "general"
    skills: List[Skill] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkillBundleManager:

    def __init__(self, available_skills: Optional[List[Skill]] = None):
        self.available_skills = available_skills or []
        self.bundles: Dict[str, SkillBundle] = {}

    def register_bundle(self, bundle: SkillBundle):
        self.bundles[bundle.id] = bundle

    def get_bundle(self, bundle_id: str) -> Optional[SkillBundle]:
        return self.bundles.get(bundle_id)

    def validate_bundle(self, bundle: SkillBundle) -> Dict[str, Any]:
        engine = SkillDependencyEngine(self.available_skills + bundle.skills)
        errors = []
        resolved_skills = {}
        explanations = []

        try:
            resolved_skills = engine.resolve(bundle.skills)
            for skill in bundle.skills:
                for req in skill.dependencies.required_skills:
                    explanations.append({
                        "skill": skill.name,
                        "requires": req.name,
                        "constraint": req.version_constraint,
                        "reason": req.reason or f"{skill.name} requires {req.name} for process execution."
                    })
        except DependencyResolutionError as exc:
            errors.append(str(exc))

        return {
            "bundle_id": bundle.id,
            "bundle_name": bundle.name,
            "valid": len(errors) == 0,
            "errors": errors,
            "unique_resolved_skills_count": len(resolved_skills),
            "resolved_skills": list(resolved_skills.keys()),
            "dependency_explanations": explanations
        }
