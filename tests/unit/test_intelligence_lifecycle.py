import time
import pytest
from backend.learning.models import (
    SkillOutcome,
    ImprovementProposal,
    ProposalStatus,
    ExperimentStatus
)
from backend.learning.collector import LearningCollector
from backend.learning.evaluator import LearningEvaluator
from backend.learning.experiment import LearningExperimentRunner
from backend.learning.hypothesis import HypothesisEngine
from backend.skills.models import Skill, SkillLifecycleState
from backend.skills.lifecycle import SkillLifecycleManager


def test_end_to_end_knowledge_and_learning_lifecycle():
    # 1. Setup collector and managers
    collector = LearningCollector()
    evaluator = LearningEvaluator(collector=collector, min_sample_size=3)
    lifecycle_mgr = SkillLifecycleManager()
    runner = LearningExperimentRunner(collector=collector, lifecycle_manager=lifecycle_mgr)
    hyp_engine = HypothesisEngine()

    # Register initial skill v1.0
    skill = Skill(
        id="skill_doc_extractor",
        name="Document Extraction Skill",
        version="1.0.0",
        state=SkillLifecycleState.ACTIVE
    )
    lifecycle_mgr.skills[skill.id] = skill

    # 2. Record initial outcomes with explicit user feedback and source authority
    for i in range(4):
        outcome = SkillOutcome(
            skill_id="skill_doc_extractor",
            skill_version="1.0.0",
            task_id=f"task_{i}",
            success=(i < 2),  # 2 success, 2 failures
            latency_sec=6.2,
            cost_usd=0.01,
            user_feedback="rejected" if i >= 2 else "approved",
            source_authority="execution_engine"
        )
        collector.record_outcome(outcome)

    # 3. Evaluate skill metrics and generate improvement proposal
    proposal = evaluator.evaluate_skill(
        skill_id="skill_doc_extractor",
        current_version="1.0.0",
        proposed_version="1.1.0",
        proposed_change="Optimize PDF parsing chunk size to reduce latency and errors."
    )
    assert proposal is not None
    assert proposal.skill_id == "skill_doc_extractor"
    assert proposal.status == ProposalStatus.PROPOSED

    # 4. Create sandbox experiment
    exp = runner.create_experiment(proposal)
    assert exp.status == ExperimentStatus.PENDING

    # 5. Run sandbox evaluation with candidate v1.1.0 outcomes
    candidate_outcomes = [
        SkillOutcome(
            skill_id="skill_doc_extractor",
            skill_version="1.1.0",
            task_id=f"cand_task_{j}",
            success=True,
            latency_sec=1.8,
            cost_usd=0.005,
            user_feedback="approved",
            source_authority="human_supervisor"
        ) for j in range(5)
    ]
    exp_res = runner.run_sandbox_eval(exp.id, candidate_outcomes)
    assert exp_res.status == ExperimentStatus.PASSED
    assert exp_res.pass_criteria_met is True

    # 6. Evaluate via HypothesisEngine multi-metric benchmark
    hyp = hyp_engine.generate_hypothesis(
        subsystem="skills",
        observation="v1.0.0 high latency and failure rate",
        proposed_optimization="Use optimized streaming parser in v1.1.0"
    )
    sandbox_eval = hyp_engine.evaluate_hypothesis_in_sandbox(
        hypothesis_id=hyp.id,
        benchmark_results={"latency_delta_pct": -45.0, "accuracy_delta_pct": 2.5, "security_violations": 0}
    )
    assert sandbox_eval["success"] is True
    assert sandbox_eval["status"] == "VALIDATED"

    # 7. Test Governance Level promotion restriction (Level 1 should fail)
    with pytest.raises(ValueError, match="Governance Level 0/1 cannot promote"):
        runner.promote_candidate(
            experiment_id=exp.id,
            proposal=proposal,
            promoter="assistant_bot",
            governance_level=1
        )

    # 8. Test Governance boundary protection (Permission escalation should fail without Level 4+)
    proposal.requested_permissions = ["filesystem.write_root"]
    with pytest.raises(PermissionError, match="High-risk governance boundary"):
        runner.promote_candidate(
            experiment_id=exp.id,
            proposal=proposal,
            promoter="analyst",
            governance_level=3
        )

    # 9. Successful promotion with Commander (Level 4)
    rec = runner.promote_candidate(
        experiment_id=exp.id,
        proposal=proposal,
        promoter="commander",
        governance_level=4
    )
    assert rec.promoted_version == "1.1.0"
    assert lifecycle_mgr.skills["skill_doc_extractor"].version == "1.1.0"

    # 10. Trigger rollback recovery
    rollback_rec = runner.trigger_rollback(
        skill_id="skill_doc_extractor",
        from_version="1.1.0",
        to_version="1.0.0",
        reason="Observed edge-case regression in production node."
    )
    assert rollback_rec.to_version == "1.0.0"
    assert lifecycle_mgr.skills["skill_doc_extractor"].version == "1.0.0"


def test_user_correction_driven_learning():
    collector = LearningCollector()

    # High authority user instruction
    user_outcome = SkillOutcome(
        skill_id="skill_sql_query",
        skill_version="1.0.0",
        task_id="sql_task_1",
        success=True,
        latency_sec=0.5,
        user_feedback="corrected",
        user_correction="SELECT * FROM table WHERE active=1",
        source_authority="explicit_user_instruction"
    )
    collector.record_outcome(user_outcome)

    # Model inference low authority outcome
    model_outcome = SkillOutcome(
        skill_id="skill_sql_query",
        skill_version="1.0.0",
        task_id="sql_task_2",
        success=False,
        latency_sec=4.2,
        source_authority="model_inference"
    )
    collector.record_outcome(model_outcome)

    metrics = collector.compute_metrics("skill_sql_query", "1.0.0")
    assert metrics.sample_count == 2
    # User outcome has 1.0 weight vs 0.5 for model outcome
    assert metrics.user_correction_rate > 0.0
