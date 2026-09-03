from typing import List, Optional
from backend.learning.models import ImprovementProposal, ProposalStatus, SkillMetrics
from backend.learning.collector import LearningCollector


class LearningEvaluator:

    def __init__(self, collector: LearningCollector, min_sample_size: int = 3):
        self.collector = collector
        self.min_sample_size = min_sample_size
        self.proposals: List[ImprovementProposal] = []

    def evaluate_skill(
        self,
        skill_id: str,
        current_version: str,
        proposed_version: str,
        proposed_change: str
    ) -> Optional[ImprovementProposal]:
        outcomes = self.collector.get_outcomes(skill_id, current_version)
        if len(outcomes) < self.min_sample_size:
            return None

        metrics = self.collector.compute_metrics(skill_id, current_version)

        issues = []
        if metrics.success_rate < 0.8:
            issues.append(f"Low success rate: {metrics.success_rate * 100:.1f}%")
        if metrics.avg_latency_sec > 5.0:
            issues.append(f"High latency: {metrics.avg_latency_sec:.2f}s")
        if metrics.user_rejection_rate > 0.2:
            issues.append(f"High user rejection rate: {metrics.user_rejection_rate * 100:.1f}%")

        if not issues:
            return None

        what_was_wrong = "; ".join(issues)
        what_learned = f"Analyzed {metrics.sample_count} executions. Failures/rejections indicate need for skill optimization."

        evidence_ids = [o.id for o in outcomes if not o.success or o.user_feedback == "rejected"]
        confidence = min(0.95, 0.5 + (metrics.sample_count * 0.05))

        proposal = ImprovementProposal(
            skill_id=skill_id,
            current_version=current_version,
            proposed_version=proposed_version,
            what_was_wrong=what_was_wrong,
            what_kingdom_learned=what_learned,
            proposed_change=proposed_change,
            evidence_references=evidence_ids,
            sample_size=metrics.sample_count,
            confidence=round(confidence, 2),
            expected_benefit="Improve success rate and reduce latency",
            regression_risk="LOW",
            security_impact="NONE",
            status=ProposalStatus.PROPOSED,
            governance_approval_required=True
        )

        self.proposals.append(proposal)
        return proposal
