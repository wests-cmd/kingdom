"""Owner-authenticated request bridge; clients share scope and idempotency keys."""
import asyncio
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    mode:Literal['auto','quick','agent','harness','delegate','commander']='auto'
    model_profile:str=Field(default='auto',min_length=1,max_length=100)
    allow_process:bool=False
    prefer_benchmarked:bool=False
    screen_region:str|None=Field(default=None,max_length=18000)
    guide_region:bool=False
    group_id:str|None=Field(default=None,min_length=1,max_length=128)
    target_knight:str|None=Field(default=None,min_length=1,max_length=128)
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


class LearnShortcutInput(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    name:str=Field(min_length=1,max_length=40)
    request_id:str=Field(min_length=1,max_length=100)
    session_scope:str=Field(min_length=1,max_length=100)
    project_scope:str=Field(min_length=1,max_length=200)


@router.post('/shortcuts/learn')
def learn_shortcut(body:LearnShortcutInput):
    try:return service().learn_shortcut(body.request_id,body.session_scope,body.project_scope,body.name)
    except (KeyError,ValueError) as error:raise HTTPException(409,'Choose a completed, verified instant request in this conversation') from error


@router.get('/voice/local')
def local_voice_status():
    from backend.runtime.local_transcription import configured
    return {'configured':configured() is not None,'format':'16 kHz mono 16-bit PCM WAV','max_seconds':60}


@router.post('/voice/local')
async def local_voice(request:Request):
    from backend.runtime.local_transcription import MAX_WAV,transcribe
    if request.headers.get('content-type','').split(';')[0] not in {'audio/wav','audio/x-wav','application/octet-stream'}:
        raise HTTPException(415,'Choose a WAV recording')
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>MAX_WAV:
            raise HTTPException(413,'Recording exceeds 2 MiB')
        data.extend(chunk)
    try:return await asyncio.to_thread(transcribe,bytes(data))
    except ValueError as error:raise HTTPException(400,str(error)) from error
    except Exception as error:raise HTTPException(503,'Local transcription unavailable; check the configured engine and model') from error


class BenchmarkInput(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    profile:str=Field(min_length=1,max_length=64)


@router.get('/benchmarks')
def benchmarks():
    from backend.models.assistant_benchmark import AssistantBenchmarks
    return AssistantBenchmarks(service().db).list()


@router.post('/benchmarks')
async def benchmark(body:BenchmarkInput):
    from backend.models.assistant_benchmark import AssistantBenchmarks
    current=service()
    try:return await AssistantBenchmarks(current.db).run(body.profile,current.models)
    except Exception as error:raise HTTPException(502,'Benchmark did not complete; previous evidence is retained') from error


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


@router.get('/{ident}/progress')
def governed_progress(ident:str):
    from backend.events.event_bus import event_bus
    try:state=service().get(ident)
    except KeyError as error:raise HTTPException(404,'Request not found') from error
    task_id=state.get('governed_task_id')
    if not task_id:return {'task_id':None,'status':state['status'],'progress':[]}
    task=service().engine.tasks.repo.get(task_id)
    events=event_bus.get_events(task_id=task_id,event_type='task.harness_progress',limit=12)
    progress=[]
    for event in events:
        data=event.get('data') or event.get('payload') or {}
        if type(data.get('bytes')) is int and type(data.get('elapsed_seconds')) in (int,float):
            progress.append({'bytes':data['bytes'],'elapsed_seconds':data['elapsed_seconds'],'timestamp':event.get('timestamp')})
    return {'task_id':task_id,'status':task['status'] if task else 'missing','progress':progress}


@router.post('/{ident}/review-harness-proposals',status_code=201)
def review_harness_proposals(ident:str):
    from backend.runtime.harness_protocol import proposal_plan
    current=service()
    try:
        state=current.get(ident)
        if state['status']!='completed' or state['route']!='harness':raise ValueError('No completed harness')
        task=current.engine.tasks.repo.get(state['governed_task_id'])
        if not task or task.get('status')!='completed' or task.get('metadata',{}).get('conversation_request_id')!=ident:
            raise ValueError('Harness task changed')
        items=(task.get('result') or {}).get('results',[])
        if len(items)!=1 or items[0].get('verification',{}).get('state')!='VERIFIED':raise ValueError('Missing receipt')
        outcome=items[0]['outcome']
        if outcome.get('tool')!='harness.run@1.0.0' or outcome['output'].get('exit_code')!=0:raise ValueError('Missing successful harness result')
        plan=proposal_plan(outcome['output']['structured']['proposals'])
        return current.engine.missions.create(plan)
    except (KeyError,TypeError,ValueError) as error:raise HTTPException(409,'No verified supported harness proposal; no work was dispatched') from error
