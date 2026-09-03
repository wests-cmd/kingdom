from typing import Dict, List, Optional
from backend.learning.models import (
    ImprovementProposal,
    Experiment,
    ExperimentStatus,
    PromotionRecord,
    RollbackRecord,
    ProposalStatus,
    SkillMetrics
)
from backend.learning.collector import LearningCollector


class LearningDefenseError(Exception):
    pass


class LearningPoisoningDefense:

    @staticmethod
    def validate_outcome_provenance(provenance: str, actor_verified: bool = True) -> bool:
        if not actor_verified:
            return False
        allowed = ["execution_engine", "system_test", "verified_agent", "human_supervisor"]
        return provenance in allowed

    @staticmethod
    def check_poisoning_risk(outcomes: List) -> bool:
        if not outcomes:
            return False
        timestamps = [o.timestamp for o in outcomes]
        if len(timestamps) > 10 and len(set(timestamps)) == 1:
            return True
        return False


class LearningExperimentRunner:

    def __init__(self, collector: LearningCollector):
        self.collector = collector
        self.experiments: Dict[str, Experiment] = {}
        self.promotions: List[PromotionRecord] = []
        self.rollbacks: List[RollbackRecord] = []

    def create_experiment(self, proposal: ImprovementProposal) -> Experiment:
        exp = Experiment(
            proposal_id=proposal.id,
            skill_id=proposal.skill_id,
            baseline_version=proposal.current_version,
            candidate_version=proposal.proposed_version,
            status=ExperimentStatus.PENDING
        )
        self.experiments[exp.id] = exp
        proposal.status = ProposalStatus.EXPERIMENTING
        return exp

    def run_sandbox_eval(self, experiment_id: str, candidate_outcomes: List) -> Experiment:
        exp = self.experiments.get(experiment_id)
        if not exp:
            raise KeyError(f"Experiment '{experiment_id}' not found.")

        exp.status = ExperimentStatus.RUNNING

        baseline_metrics = self.collector.compute_metrics(exp.skill_id, exp.baseline_version)
        exp.baseline_metrics = baseline_metrics

        for outcome in candidate_outcomes:
            self.collector.record_outcome(outcome)

        candidate_metrics = self.collector.compute_metrics(exp.skill_id, exp.candidate_version)
        exp.candidate_metrics = candidate_metrics

        success_pass = candidate_metrics.success_rate >= baseline_metrics.success_rate
        latency_pass = candidate_metrics.avg_latency_sec <= (baseline_metrics.avg_latency_sec * 1.2) if baseline_metrics.avg_latency_sec > 0 else True

        if success_pass and latency_pass:
            exp.pass_criteria_met = True
            exp.status = ExperimentStatus.PASSED
            exp.logs.append("Sandbox evaluation PASSED. Performance criteria met.")
        else:
            exp.pass_criteria_met = False
            exp.status = ExperimentStatus.FAILED
            exp.logs.append("Sandbox evaluation FAILED. Performance regressed.")

        return exp

    def promote_candidate(
        self,
        experiment_id: str,
        proposal: ImprovementProposal,
        promoter: str = "admin",
        governance_level: int = 3
    ) -> PromotionRecord:
        exp = self.experiments.get(experiment_id)
        if not exp or not exp.pass_criteria_met:
            raise ValueError("Cannot promote: Sandbox experiment has not passed.")

        outcomes = self.collector.get_outcomes(exp.skill_id, exp.candidate_version)
        if LearningPoisoningDefense.check_poisoning_risk(outcomes):
            raise LearningDefenseError("Promotion blocked by Learning Poisoning Defense: Anomaly detected.")

        if governance_level < 2:
            raise ValueError("Governance Level 0/1 cannot promote skill improvements.")

        rec = PromotionRecord(
            proposal_id=proposal.id,
            skill_id=proposal.skill_id,
            old_version=proposal.current_version,
            promoted_version=proposal.proposed_version,
            promoter=promoter,
            reason="Sandbox evaluation passed and governance approved."
        )
        self.promotions.append(rec)
        proposal.status = ProposalStatus.PROMOTED
        return rec

    def trigger_rollback(
        self,
        skill_id: str,
        from_version: str,
        to_version: str,
        reason: str
    ) -> RollbackRecord:
        metrics = self.collector.compute_metrics(skill_id, from_version)
        rec = RollbackRecord(
            skill_id=skill_id,
            from_version=from_version,
            to_version=to_version,
            trigger_reason=reason,
            metrics_at_rollback=metrics
        )
        self.rollbacks.append(rec)
        return rec
