import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    EVALUATING = "EVALUATING"
    EXPERIMENTING = "EXPERIMENTING"
    APPROVED = "APPROVED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"


class ExperimentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class SkillOutcome(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    skill_id: str
    skill_version: str
    task_id: str
    success: bool
    latency_sec: float
    cost_usd: float = 0.0
    retries: int = 0
    errors: List[str] = Field(default_factory=list)
    user_feedback: Optional[str] = None
    user_correction: Optional[str] = None
    resource_usage: Dict[str, float] = Field(default_factory=dict)
    model_used: Optional[str] = None
    provider_used: Optional[str] = None
    knight_id: Optional[str] = None
    provenance: str = "execution_engine"
    audit_id: Optional[str] = None


class SkillMetrics(BaseModel):
    skill_id: str
    skill_version: str
    sample_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_latency_sec: float = 0.0
    avg_cost_usd: float = 0.0
    user_approval_rate: float = 0.0
    user_rejection_rate: float = 0.0
    user_correction_rate: float = 0.0
    retry_rate: float = 0.0


class LearningEpisode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    skill_id: str
    skill_version: str
    outcomes: List[SkillOutcome] = Field(default_factory=list)
    summary_pattern: str = ""


class SkillEvaluation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    skill_id: str
    old_version: str
    new_version: str
    metrics_before: SkillMetrics
    metrics_after: SkillMetrics
    confidence_score: float = 0.0
    risk_score: float = 0.0


class ImprovementProposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    skill_id: str
    current_version: str
    proposed_version: str
    what_was_wrong: str
    what_kingdom_learned: str
    proposed_change: str
    evidence_references: List[str] = Field(default_factory=list)
    sample_size: int = 0
    confidence: float = 0.0
    expected_benefit: str = ""
    regression_risk: str = "LOW"
    security_impact: str = "NONE"
    compatibility_impact: str = "NONE"
    resource_impact: str = "NONE"
    status: ProposalStatus = ProposalStatus.PROPOSED
    governance_approval_required: bool = True
    approved_by: Optional[str] = None


class Experiment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: str
    skill_id: str
    baseline_version: str
    candidate_version: str
    status: ExperimentStatus = ExperimentStatus.PENDING
    baseline_metrics: Optional[SkillMetrics] = None
    candidate_metrics: Optional[SkillMetrics] = None
    pass_criteria_met: bool = False
    logs: List[str] = Field(default_factory=list)


class Benchmark(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    test_cases: List[Dict[str, Any]] = Field(default_factory=list)


class PromotionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    proposal_id: str
    skill_id: str
    old_version: str
    promoted_version: str
    promoter: str
    reason: str


class RollbackRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    skill_id: str
    from_version: str
    to_version: str
    trigger_reason: str
    metrics_at_rollback: SkillMetrics
