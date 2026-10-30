"""Owner-controlled connection; OAuth consent remains on the owning Knight."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner
from backend.models.chatgpt_plan import ChatGPTPlanConnection, ChatGPTPlanError

router = APIRouter(prefix='/chatgpt-plan', dependencies=[Depends(require_owner)])
_service = None


def service():
    global _service
    if _service is None:
        from backend.storage.db import db
        from backend.api import engine
        _service = ChatGPTPlanConnection(db, publish=engine.events.publish)
    return _service


class Account(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    account_id: str | None = Field(default=None, max_length=160)


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    enabled: bool
    model: str | None = Field(default=None, max_length=200)


def boundary(call):
    try:
        return call()
    except ChatGPTPlanError as error:
        raise HTTPException(409, error.code) from None


@router.get('')
def status():
    return boundary(lambda: service().status())


@router.get('/models')
def models():
    return boundary(lambda: service().models())


@router.post('/begin')
def begin(body: Account):
    return boundary(lambda: service().begin(body.account_id))


@router.post('/settings')
def settings(body: Settings):
    return boundary(lambda: service().configure(**body.model_dump()))


@router.post('/cancel')
def cancel():
    return boundary(lambda: service().cancel())


@router.post('/sign-out')
def sign_out(body: Account):
    return boundary(lambda: service().sign_out(body.account_id))
