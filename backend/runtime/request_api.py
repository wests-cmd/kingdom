"""Owner-authenticated request bridge; clients share scope and idempotency keys."""
import asyncio
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from backend.security.http_auth import require_owner
router=APIRouter(prefix='/requests',dependencies=[Depends(require_owner)])
_service=None

def service():
    global _service
    if _service is None:
        from backend.storage.db import db
        from backend.api import engine
        from backend.models.service import ModelService
        from backend.runtime.agent_api import service as agents
        from backend.runtime.request_service import RequestService
        _service=RequestService(db,engine,ModelService(),agents())
    return _service

class RequestInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    idempotency_key:str=Field(min_length=1,max_length=100)
    session_scope:str=Field(min_length=1,max_length=100)
    project_scope:str=Field(default='projects/default',min_length=1,max_length=200)
    prompt:str=Field(min_length=1,max_length=24000)
    mode:Literal['auto','quick','agent']='auto'
    model_profile:str=Field(default='auto',min_length=1,max_length=100)
    allow_process:bool=False

@router.post('',status_code=201)
def create(body:RequestInput):
    try:return service().create(body.model_dump())
    except ValueError as error:raise HTTPException(409,str(error)) from error

@router.get('')
def listing(session_scope:str=Query(min_length=1,max_length=100),project_scope:str=Query(min_length=1,max_length=200)):
    return service().list(session_scope,project_scope)

@router.get('/{ident}')
def get(ident:str):
    try:return service().get(ident)
    except KeyError as error:raise HTTPException(404,'Request not found') from error

@router.post('/{ident}/run')
async def run(ident:str):
    try:
        current=await asyncio.to_thread(service)
        return await current.run(ident)
    except KeyError as error:raise HTTPException(404,'Request or model not found') from error
    except Exception as error:raise HTTPException(502,'Request failed; inspect its saved checkpoint') from error

@router.post('/{ident}/cancel')
def cancel(ident:str):
    try:return service().cancel(ident)
    except KeyError as error:raise HTTPException(404,'Request not found') from error
