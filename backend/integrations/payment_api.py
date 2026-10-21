"""Owner-only optional payment provider setup and exact payment records."""
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/payments', dependencies=[Depends(require_owner)])


def service():
    from backend.api import engine
    from backend.storage.db import db
    from backend.integrations.payments import PaymentService
    return PaymentService(db, engine)


class Configuration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    mode: Literal['test', 'live'] = 'test'
    currency: str = Field(default='usd', pattern='^[a-z]{3}$')
    max_amount_minor: int = Field(default=1000, strict=True, ge=1, le=100000000)
    api_key: str | None = Field(default=None, max_length=500)


class Payment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: str = Field(min_length=8, max_length=100)
    amount_minor: int = Field(strict=True, ge=1)
    currency: str = Field(default='usd', pattern='^[a-z]{3}$')
    purpose: str = Field(min_length=1, max_length=300)
    payment_method: str | None = Field(default=None, max_length=220)
    confirm: bool = False


@router.get('/settings')
def settings():
    return service().settings()


@router.put('/settings')
def configure(request: Configuration):
    try:
        return service().configure(**request.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get('')
def inventory():
    return service().list()


@router.post('')
def prepare(request: Payment):
    try:
        return service().prepare(**request.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post('/{ident}/execute')
async def execute(ident: str):
    try:
        # SQL and approval checks stay off the API event loop; provider I/O is async.
        return await asyncio.to_thread(lambda: asyncio.run(service().execute(ident)))
    except KeyError as error:
        raise HTTPException(404, 'Payment request not found') from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
