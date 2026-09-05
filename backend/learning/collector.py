from typing import Dict, List, Optional
from backend.learning.models import SkillOutcome, SkillMetrics


class LearningCollector:

    def __init__(self, max_history_per_skill: int = 1000):
        self.max_history = max_history_per_skill
        self.outcomes: Dict[str, List[SkillOutcome]] = {}

    def _key(self, skill_id: str, skill_version: str) -> str:
        return f"{skill_id}:{skill_version}"

    def record_outcome(self, outcome: SkillOutcome) -> SkillOutcome:
        key = self._key(outcome.skill_id, outcome.skill_version)
        if key not in self.outcomes:
            self.outcomes[key] = []

        self.outcomes[key].append(outcome)
        if len(self.outcomes[key]) > self.max_history:
            self.outcomes[key] = self.outcomes[key][-self.max_history:]

        return outcome

    def get_outcomes(self, skill_id: str, skill_version: str, limit: int = 100) -> List[SkillOutcome]:
        key = self._key(skill_id, skill_version)
        history = self.outcomes.get(key, [])
        return history[-limit:]

    def compute_metrics(self, skill_id: str, skill_version: str) -> SkillMetrics:
        outcomes = self.get_outcomes(skill_id, skill_version, limit=self.max_history)
        if not outcomes:
            return SkillMetrics(skill_id=skill_id, skill_version=skill_version)

        sample_count = len(outcomes)
        success_count = sum(1 for o in outcomes if o.success)
        failure_count = sample_count - success_count

        total_latency = sum(o.latency_sec for o in outcomes)
        total_cost = sum(o.cost_usd for o in outcomes)

        approvals = sum(1 for o in outcomes if o.user_feedback == "approved")
        rejections = sum(1 for o in outcomes if o.user_feedback == "rejected")
        corrections = sum(1 for o in outcomes if o.user_feedback == "corrected" or o.user_correction is not None)
        retries = sum(o.retries for o in outcomes)

        return SkillMetrics(
            skill_id=skill_id,
            skill_version=skill_version,
            sample_count=sample_count,
            success_count=success_count,
            failure_count=failure_count,
            success_rate=round(success_count / sample_count, 4),
            avg_latency_sec=round(total_latency / sample_count, 4),
            avg_cost_usd=round(total_cost / sample_count, 4),
            user_approval_rate=round(approvals / sample_count, 4),
            user_rejection_rate=round(rejections / sample_count, 4),
            user_correction_rate=round(corrections / sample_count, 4),
            retry_rate=round(retries / sample_count, 4)
        )
