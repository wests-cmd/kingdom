# STEP 6 ARCHITECTURE: SKILL LEARNING & DEMONSTRATION

Kingdom learns new workflows from natural language demonstrations and example files without retraining base LLM weights.

## Learning Lifecycle
1. User provides skill name, description, and example demonstration.
2. `SkillLearningEngine` extracts required tools, capabilities, and business rules.
3. Skill candidate is saved in `DRAFT` / `SAVED` state.
4. Skill is tested in a sandbox environment and validated against readiness rules.
5. Upon human approval (`POST /skills/{id}/promote`), the skill transitions to `ACTIVE` and becomes discoverable by relevant Knights.
