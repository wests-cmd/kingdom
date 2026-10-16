"""Owner-only native agent conversations, using the existing task approval system."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/agent-sessions', dependencies=[Depends(require_owner)])
_service = None


def service():
    global _service
    if _service is None:
        from backend.api import engine
        from backend.storage.db import db
        from backend.runtime.agent_sessions import AgentSessionService
        _service = AgentSessionService(engine, db)
    return _service


class CreateSession(BaseModel):
    model_config = ConfigDict(extra='forbid')
    objective: str = Field(min_length=1, max_length=24000)
    model_profile: str = Field(default='auto', min_length=1, max_length=100)
    max_turns: int = Field(default=12, ge=1, le=32)
    allow_process: bool = False
    skill_ids: list[str] = Field(default_factory=list,max_length=8)
    workspace: str = Field(default='.',max_length=300)
    knowledge_scope: str | None = Field(default=None,max_length=100)
    embedding_profile: str | None = Field(default=None,max_length=64)
    use_owner_memory: bool = False

class RunSession(BaseModel):
    model_config = ConfigDict(extra='forbid')
    max_turns: int = Field(default=2,ge=1,le=4)
    max_seconds: int = Field(default=300,ge=5,le=600)


@router.get('')
def sessions():
    return service().list()


@router.post('', status_code=201)
def create(request: CreateSession):
    try:
        return service().create(**request.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get('/{ident}')
def get(ident: str):
    try:
        return service().get(ident)
    except KeyError as error:
        raise HTTPException(404, 'Agent session not found') from error


@router.post('/{ident}/advance')
async def advance(ident: str):
    try:
        return await service().advance(ident)
    except KeyError as error:
        raise HTTPException(404, 'Agent session not found') from error


@router.post('/{ident}/cancel')
def cancel(ident: str):
    try:
        return service().cancel(ident)
    except KeyError as error:
        raise HTTPException(404, 'Agent session not found') from error

@router.post('/{ident}/run')
async def run(ident: str, request: RunSession):
    try: return await service().run(ident,request.max_turns,request.max_seconds)
    except KeyError as error: raise HTTPException(404,'Agent session not found') from error
