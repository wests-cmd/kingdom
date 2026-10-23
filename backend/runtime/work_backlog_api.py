"""Owner-only backlog registration and review. No model planning or new grants."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/work-backlog', dependencies=[Depends(require_owner)])
_service = None


def service():
    global _service
    if _service is None:
        from backend.storage.db import db
        from backend.api import engine
        from backend.runtime.work_backlog import WorkBacklog
        _service = WorkBacklog(db, engine)
    return _service


class Item(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    project: str = Field(default='kingdom', pattern=r'^[A-Za-z0-9_-]{1,80}$')
    idempotency_key: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=12000)
    priority: int = Field(default=50, ge=0, le=100)
    task_type: str = Field(default='generic', pattern=r'^[A-Za-z0-9_-]{1,80}$')
    mission_id: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_-]{1,80}$')
    mission_version: int | None = Field(default=None, ge=1)
    acceptance_step: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_-]{1,80}$')
    depends_on: list[str] = Field(default_factory=list, max_length=30)
    enabled: bool = False


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    enabled: bool
    expected_revision: int = Field(ge=1)


class TypePriorities(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    priorities: dict[str, int] = Field(max_length=20)
    expected_revision: int = Field(ge=1)


class Attachment(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    mission_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    mission_version: int = Field(ge=1)
    acceptance_step: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    expected_revision: int = Field(ge=1)


class Recovery(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_revision: int = Field(ge=1)
    lease: str = Field(pattern=r'^[a-f0-9]{32}$')


def boundary(operation):
    try:
        return operation()
    except KeyError as error:
        raise HTTPException(404, 'Backlog item or mission not found') from error
    except (ValueError, TypeError) as error:
        raise HTTPException(409, 'Invalid or changed backlog checkpoint; inspect the mission and reload') from error


@router.get('')
def listing():
    return boundary(lambda: service().snapshot())


@router.get('/type-priorities')
def type_priorities():
    return boundary(lambda: service().type_priorities())


@router.put('/type-priorities')
def set_type_priorities(request: TypePriorities):
    return boundary(lambda: service().set_type_priorities(**request.model_dump()))


@router.post('/settings')
def settings(request: Settings):
    return boundary(lambda: service().settings(**request.model_dump()))


@router.post('/review')
def review():
    return boundary(lambda: service().review())


@router.post('/items', status_code=201)
def register(request: Item):
    return boundary(lambda: service().register(**request.model_dump()))


@router.post('/items/{project}/{ident}/settings')
def configure(project: str, ident: str, request: Settings):
    return boundary(lambda: service().configure(project, ident, **request.model_dump()))


@router.post('/items/{project}/{ident}/mission')
def attach(project: str, ident: str, request: Attachment):
    return boundary(lambda: service().attach(project, ident, **request.model_dump()))


@router.post('/items/{project}/{ident}/reconcile')
def reconcile(project: str, ident: str, request: Recovery):
    return boundary(lambda: service().reconcile(project, ident, **request.model_dump()))
