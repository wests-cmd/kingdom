"""Authenticated advice and curated local training candidates, never authority."""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/assistance', dependencies=[Depends(require_owner)])
_service = None


def service():
    global _service
    if _service is None:
        from backend.storage.db import db
        from backend.api import engine
        from backend.runtime.work_programme_api import service as programmes
        from backend.models.chatgpt_plan_api import service as connection
        from backend.runtime.consultation_coordinator import ConsultationCoordinator
        _service = ConsultationCoordinator(db, engine, programmes(), connection())
    return _service


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    enabled: bool
    max_daily_calls: int = Field(ge=1, le=32)
    expected_revision: int = Field(ge=1)


class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    evidence_id: str = Field(min_length=1, max_length=160)


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    selected: bool


def boundary(call):
    try:
        return call()
    except KeyError:
        raise HTTPException(404, 'Advice record not found') from None
    except PermissionError:
        raise HTTPException(403, 'Current bound acceptance evidence is required') from None
    except (ValueError, StopIteration):
        raise HTTPException(409, 'Advice or its original work changed or requires review') from None


@router.get('')
def status():
    return boundary(lambda: service().status())


@router.post('/settings')
def settings(body: Settings):
    return boundary(lambda: service().configure(**body.model_dump()))


@router.post('/programmes/{ident}/items/{key}')
async def request(ident: str, key: str):
    try:
        return await service().request_programme(ident, key)
    except (KeyError, ValueError, StopIteration):
        raise HTTPException(409, 'Select current held work that needs advice') from None


@router.post('/requests/{ident}/apply')
def apply(ident: str):
    return boundary(lambda: service().apply(ident))


@router.post('/requests/{ident}/cancel')
def cancel(ident: str):
    return boundary(lambda: service().store.cancel(ident))


@router.post('/requests/{ident}/verify')
def verify(ident: str, body: Evidence):
    return boundary(lambda: service().store.record_verification(ident, body.evidence_id))


@router.post('/requests/{ident}/training')
def select(ident: str, body: Selection):
    return boundary(lambda: service().store.select_for_training(ident, body.selected))


@router.get('/training/{project}')
def export(project: str):
    data = boundary(lambda: service().store.export_training(project=project))
    return Response(data, media_type='application/x-ndjson',
                    headers={'Content-Disposition': 'attachment; filename="verified-lessons.jsonl"', 'Cache-Control': 'no-store'})
