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
    mode:Literal['auto','quick','agent','harness']='auto'
    model_profile:str=Field(default='auto',min_length=1,max_length=100)
    allow_process:bool=False
    harness_id:str|None=Field(default=None,max_length=64,pattern=r'^[a-z][a-z0-9_-]{0,63}$')
    fallback_profile:str|None=Field(default=None,max_length=64,pattern=r'^[a-z][a-z0-9_-]{0,63}$')
    required_tools:list[Literal['workspace_read','workspace_list','workspace_write','process_run','desktop_observe','desktop_input']]=Field(default_factory=list,max_length=4)
    tool_sequence:list[Literal['workspace_read','workspace_list','workspace_write','process_run','desktop_observe','desktop_input']]=Field(default_factory=list,max_length=8)
    tool_protocol:Literal['native','structured']='native'
    tool_paths:list[str]=Field(default_factory=list,max_length=8)
    review_instructions:str=Field(default='',max_length=2000)
    desktop_window_title:str|None=Field(default=None,min_length=1,max_length=500)
    desktop_expected_text:str|None=Field(default=None,min_length=1,max_length=2000)

@router.post('',status_code=201)
def create(body:RequestInput):
    try:return service().create(body.model_dump())
    except ValueError as error:raise HTTPException(409,str(error)) from error

@router.get('')
def listing(session_scope:str=Query(min_length=1,max_length=100),project_scope:str=Query(min_length=1,max_length=200)):
    return service().list(session_scope,project_scope)

class ShortcutInput(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    project_scope:str=Field(min_length=1,max_length=200)
    name:str=Field(min_length=1,max_length=40)
    command:str=Field(min_length=1,max_length=40)


# Static routes must precede the generic request identity route.
@router.get('/shortcuts')
def shortcuts(project_scope:str=Query(min_length=1,max_length=200)):
    from backend.runtime.intent_router import COMMANDS
    return {'commands':COMMANDS,'shortcuts':service().shortcuts.list(project_scope)}


@router.put('/shortcuts')
def save_shortcut(body:ShortcutInput):
    try:return service().shortcuts.save(body.project_scope,body.name,body.command)
    except ValueError as error:raise HTTPException(400,str(error)) from error


@router.delete('/shortcuts/{name}')
def remove_shortcut(name:str,project_scope:str=Query(min_length=1,max_length=200)):
    return {'removed':service().shortcuts.remove(project_scope,name)}


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

from backend.runtime.background_requests import BackgroundRequests
background = BackgroundRequests(service)

class BackgroundOptions(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    max_seconds:int=Field(default=310,ge=30,le=1800)
    max_chunks:int=Field(default=6,ge=1,le=12)

@router.post('/{ident}/background', status_code=202)
async def start_background(ident: str,options:BackgroundOptions|None=None):
    try: return background.start(ident,**(options or BackgroundOptions()).model_dump())
    except KeyError: raise HTTPException(404, 'Request not found')
    except ValueError as error: raise HTTPException(409, str(error)) from error
