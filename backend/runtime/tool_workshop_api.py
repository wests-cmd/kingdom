from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner
from backend.runtime.tool_workshop import ToolProposal, ToolWorkshop

router = APIRouter(prefix='/tool-workshop', dependencies=[Depends(require_owner)])


def service():
    from backend.api import engine
    from backend.storage.db import db
    return ToolWorkshop(engine, db)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    checksum: str = Field(pattern=r'^[0-9a-f]{64}$')


class RegisterRequest(ReviewRequest):
    connection_id: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,63}$')


def call(method, *args):
    try:
        return getattr(service(), method)(*args)
    except KeyError as error:
        raise HTTPException(404, 'Tool proposal not found') from error
    except (ValueError, OSError) as error:
        raise HTTPException(400, str(error)) from error


@router.get('')
def proposals():
    return call('list')


@router.get('/discover')
def discover(query: str = Query(default='', max_length=200)):
    return call('discover', query)


@router.post('', status_code=201)
def propose(request: ToolProposal):
    return call('propose', request)


@router.get('/{ident}')
def get(ident: str):
    return call('get', ident)


@router.post('/{ident}/review')
def review(ident: str, request: ReviewRequest):
    return call('review', ident, request.checksum)


@router.post('/{ident}/advance')
def advance(ident: str):
    return call('advance', ident)


@router.post('/{ident}/register')
def register(ident: str, request: RegisterRequest):
    return call('register', ident, request.checksum, request.connection_id)


@router.post('/{ident}/disable')
def disable(ident: str):
    return call('disable', ident)
