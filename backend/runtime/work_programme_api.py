"""Owner-reviewed plain-language programmes; planning never grants execution."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/work-programmes', dependencies=[Depends(require_owner)])
_service = None


def service():
    global _service
    if _service is None:
        from backend.storage.db import db
        from backend.api import engine
        from backend.runtime.work_backlog_api import service as backlog
        from backend.runtime.work_programmes import WorkProgrammes
        _service = WorkProgrammes(db, engine, backlog())
    return _service


class NewProgramme(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    project: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    idempotency_key: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    text: str = Field(min_length=1, max_length=24000)
    model_profile: str = Field(default='auto', min_length=1, max_length=100)
    source_revision: str | None = Field(default=None, pattern=r'^[a-fA-F0-9]{40}$')


class Revision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_revision: int = Field(ge=1)


class Settings(Revision):
    enabled: bool


class Answer(Revision):
    answer: str = Field(min_length=1, max_length=4000)


def boundary(operation):
    try:
        return operation()
    except KeyError as error:
        raise HTTPException(404, 'Saved programme not found') from error
    except (ValueError, TypeError) as error:
        raise HTTPException(409, 'Programme changed or requires review; reload its checkpoint') from error


@router.get('')
def listing():
    return boundary(lambda: [service().snapshot(s['id']) for s in service().list()])


@router.post('', status_code=201)
def create(request: NewProgramme):
    return boundary(lambda: service().create(**request.model_dump()))


@router.post('/{ident}/settings')
def configure(ident: str, request: Settings):
    return boundary(lambda: service().configure(ident, **request.model_dump()))


@router.post('/{ident}/plan-next')
async def plan(ident: str, request: Revision):
    try:
        return await service().plan_next(ident, request.expected_revision)
    except KeyError as error:
        raise HTTPException(404, 'Saved programme not found') from error
    except (ValueError, TypeError) as error:
        raise HTTPException(409, 'Programme changed; reload its checkpoint') from error


@router.post('/{ident}/items/{key}/approve')
def approve(ident: str, key: str, request: Revision):
    return boundary(lambda: service().approve(ident, key, request.expected_revision))


@router.post('/{ident}/items/{key}/retry-planning')
def retry(ident: str, key: str, request: Revision):
    return boundary(lambda: service().retry_planning(ident, key, request.expected_revision))


@router.post('/{ident}/items/{key}/answer')
def answer(ident: str, key: str, request: Answer):
    return boundary(lambda: service().answer(ident, key, request.answer, request.expected_revision))
