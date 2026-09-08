import time
import math
from typing import Dict, List, Optional
from backend.learning.models import SkillOutcome, SkillMetrics, SOURCE_AUTHORITY_WEIGHTS


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

        # Assign source authority weight if explicitly known
        if outcome.source_authority in SOURCE_AUTHORITY_WEIGHTS:
            outcome.authority_weight = SOURCE_AUTHORITY_WEIGHTS[outcome.source_authority]

        self.outcomes[key].append(outcome)
        if len(self.outcomes[key]) > self.max_history:
            self.outcomes[key] = self.outcomes[key][-self.max_history:]

        return outcome

    def get_outcomes(
        self,
        skill_id: str,
        skill_version: str,
        limit: int = 100,
        ignore_expired: bool = True
    ) -> List[SkillOutcome]:
        key = self._key(skill_id, skill_version)
        history = self.outcomes.get(key, [])
        now = time.time()

        valid_history = []
        for o in history:
            if ignore_expired and o.valid_until and o.valid_until < now:
                continue
            valid_history.append(o)

        return valid_history[-limit:]

    def compute_metrics(
        self,
        skill_id: str,
        skill_version: str,
        decay_half_life_sec: float = 604800.0  # 7 days half-life
    ) -> SkillMetrics:
        outcomes = self.get_outcomes(skill_id, skill_version, limit=self.max_history)
        if not outcomes:
            return SkillMetrics(skill_id=skill_id, skill_version=skill_version)

        now = time.time()
        sample_count = len(outcomes)
        total_weight = 0.0
        weighted_success = 0.0
        total_latency = 0.0
        total_cost = 0.0
        approvals = 0.0
        rejections = 0.0
        corrections = 0.0
        retries = 0.0

        for o in outcomes:
            # Decay weight calculation
            age_sec = max(0.0, now - o.timestamp)
            decay = math.exp(-0.693147 * (age_sec / decay_half_life_sec)) if decay_half_life_sec > 0 else 1.0
            o.decay_weight = round(decay, 4)

            effective_weight = o.authority_weight * o.decay_weight
            total_weight += effective_weight

            if o.success:
                weighted_success += effective_weight

            total_latency += o.latency_sec * effective_weight
            total_cost += o.cost_usd * effective_weight

            if o.user_feedback == "approved":
                approvals += effective_weight
            elif o.user_feedback == "rejected":
                rejections += effective_weight
            if o.user_feedback == "corrected" or o.user_correction is not None:
                corrections += effective_weight

            retries += o.retries * effective_weight

        if total_weight <= 0:
            total_weight = 1.0

        success_count = sum(1 for o in outcomes if o.success)
        failure_count = sample_count - success_count

        return SkillMetrics(
            skill_id=skill_id,
            skill_version=skill_version,
            sample_count=sample_count,
            success_count=success_count,
            failure_count=failure_count,
            success_rate=round(weighted_success / total_weight, 4),
            avg_latency_sec=round(total_latency / total_weight, 4),
            avg_cost_usd=round(total_cost / total_weight, 4),
            user_approval_rate=round(approvals / total_weight, 4),
            user_rejection_rate=round(rejections / total_weight, 4),
            user_correction_rate=round(corrections / total_weight, 4),
            retry_rate=round(retries / total_weight, 4)
        )
