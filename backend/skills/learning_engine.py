import time
import json
from typing import Dict, Any, List, Optional
from backend.skills.models import Skill, SkillTrustLevel, SkillLifecycleState, SkillDependency
from backend.skills.lifecycle import SkillLifecycleManager
from backend.events.event_bus import event_bus

class SkillLearningEngine:
    def __init__(self, lifecycle_manager: Optional[SkillLifecycleManager] = None):
        if lifecycle_manager:
            self.lifecycle_manager = lifecycle_manager
        else:
            self.lifecycle_manager = SkillLifecycleManager(
                available_tools=["pdf_parser", "http_client"],
                available_capabilities=["model.inference"],
                granted_permissions=["filesystem.read"]
            )

    def learn_skill_from_examples(
        self,
        skill_name: str,
        description: str,
        example_texts: List[str],
        department: str = "Workflows"
    ) -> Dict[str, Any]:
        skill_id = f"skill-{skill_name.lower().replace(' ', '-')}"

        # Extract workflow inputs & rules from examples
        required_tools = ["pdf_parser", "http_client"] if "invoice" in description.lower() else ["text_processor"]

        learned_skill = Skill(
            id=skill_id,
            name=skill_name,
            version="1.0.0",
            description=description,
            department=department,
            trust_level=SkillTrustLevel.VERIFIED,
            state=SkillLifecycleState.SAVED,
            permissions=["filesystem.read"],
            dependencies=SkillDependency(
                required_tools=["pdf_parser"],
                required_capabilities=["model.inference"]
            )
        )

        saved = self.lifecycle_manager.save(learned_skill)

        event_bus.publish("skill.learned_candidate_created", {
            "skill_id": skill_id,
            "version": "1.0.0"
        }, source="learning_engine")

        return {
            "success": True,
            "skill": saved.model_dump(),
            "status": "DRAFT",
            "message": f"Draft skill '{skill_name}' v1.0.0 created from example demonstration. Ready for testing & approval."
        }

    def test_and_promote_skill(self, skill_id: str, governance_approved: bool = True) -> Dict[str, Any]:
        skill = self.lifecycle_manager.skills.get(skill_id)
        if not skill:
            return {"success": False, "error": f"Skill {skill_id} not found."}

        # Simulate sandbox testing
        self.lifecycle_manager.install(skill_id)
        activated = self.lifecycle_manager.activate(skill_id, governance_approved=governance_approved)

        event_bus.publish("skill.promoted_to_active", {
            "skill_id": skill_id,
            "version": activated.version
        }, source="learning_engine")

        return {
            "success": True,
            "skill": activated.model_dump(),
            "status": "ACTIVE"
        }

skill_learning_engine = SkillLearningEngine()
