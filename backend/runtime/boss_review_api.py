"""Owner-visible accountability for the service-owned Boss receipt reviewer."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from typing import Literal
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/boss-reviews', dependencies=[Depends(require_owner)])
_service = None


class BossReviewRow(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    key: str
    work_id: str
    title: str
    status: str
    reason: str | None
    mission_id: str | None
    mission_version: int | None
    planning_model_profile: str
    execution_model_profile: str | None
    requested_computers: list[str]
    reviewer: Literal['Boss receipt controller']
    tools: list[str]
    evidence: dict[str, JsonValue] | None
    assignment_scope: str
    failed_acceptance: dict[str, JsonValue] | None


class BossRepairNote(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=12000)


class BossReview(BaseModel):
    """This controller can report observations, never publication authority."""
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str
    project: str
    status: Literal['repair_budget_exhausted', 'needs_repair_plan', 'needs_independent_test',
                    'needs_owner_review', 'working', 'needs_plan_or_execution']
    controller: Literal['Boss']
    controller_kind: Literal['Kingdom-owned deterministic receipt review']
    rows: list[BossReviewRow]
    repair_bindings: dict[str, int]
    repair_notes: dict[str, BossRepairNote] = Field(default_factory=dict)
    repair_limit: Literal[3]
    independent_reviewer: None
    release_allowed: Literal[False]
    blockers: list[str]
    scope: str
    digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    revision: int = Field(ge=1)
    reviewed_at: float


def service():
    global _service
    if _service is None:
        from backend.storage.db import db
        from backend.api import engine
        from backend.runtime.work_programme_api import service as programmes
        from backend.runtime.work_backlog_api import service as backlog
        from backend.runtime.boss_reviews import BossReviews
        _service = BossReviews(db, programmes(), backlog(), engine)
    return _service


@router.get('', response_model=list[BossReview])
def listing() -> list[BossReview]:
    return service().list()
