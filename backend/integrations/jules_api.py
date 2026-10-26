"""Owner-authenticated API endpoints for Kingdom-to-Jules engineering handoff."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from typing import Any
from backend.security.http_auth import require_owner

router = APIRouter(
    prefix="/integrations/jules", dependencies=[Depends(require_owner)]
)


def service():
    from backend.api import engine
    from backend.storage.db import db
    from backend.integrations.jules import JulesService

    if not hasattr(engine, "jules") or engine.jules is None:
        engine.jules = JulesService(db, engine)
    return engine.jules


class SettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    allowed_repositories: list[str] | None = None
    allowed_sources: list[str] | None = None
    api_key: str | None = Field(default=None, max_length=500)
    expected_revision: int | None = None


class JobRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(min_length=1, max_length=80)
    backlog_id: str = Field(min_length=1, max_length=80)
    idempotency_key: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=200)
    repository: str = Field(min_length=1, max_length=200)
    revision: str = Field(min_length=40, max_length=40)
    branch: str = Field(min_length=1, max_length=150)
    prompt: str = Field(min_length=1, max_length=12000)
    max_repair_budget: int = Field(default=3, ge=0, le=10)
    deadline_seconds: int = Field(default=3600, ge=60, le=86400)


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="Cancelled by owner", max_length=300)


@router.get("/settings")
def get_settings():
    return service().settings()


@router.put("/settings")
def configure_settings(request: SettingsRequest):
    try:
        return service().configure(**request.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get("/jobs")
def list_jobs(project: str | None = None):
    try:
        return service().list_jobs(project=project)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/jobs", status_code=201)
def register_job(request: JobRegisterRequest):
    try:
        return service().register_job(**request.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return service().get_job(job_id)
    except KeyError as error:
        raise HTTPException(404, f"Job {job_id} not found") from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/jobs/{job_id}/run")
def run_job(job_id: str):
    try:
        return service().run_job(job_id)
    except KeyError as error:
        raise HTTPException(404, f"Job {job_id} not found") from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, request: CancelRequest):
    try:
        return service().cancel_job(job_id, reason=request.reason)
    except KeyError as error:
        raise HTTPException(404, f"Job {job_id} not found") from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/jobs/{job_id}/verify")
def verify_job(job_id: str, evidence: VerificationRequest):
    try:
        return service().verify_job_completion(job_id, evidence.model_dump())
    except KeyError as error:
        raise HTTPException(404, f"Job {job_id} not found") from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
