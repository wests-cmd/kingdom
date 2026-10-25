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
    required_tools: list[str] = Field(default_factory=list,max_length=4)
    tool_sequence:list[str]=Field(default_factory=list,max_length=8)
    desktop_window_title: str | None = Field(default=None,min_length=1,max_length=500)
    desktop_expected_text: str | None = Field(default=None,min_length=1,max_length=2000)

class RunSession(BaseModel):
    model_config = ConfigDict(extra='forbid')
    max_turns: int = Field(default=2,ge=1,le=4)
    max_seconds: int = Field(default=300,ge=5,le=600)

class ReviewFeedback(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1,max_length=4000)
    expected_updated_at: float

@router.get('/readiness')
async def readiness():
    from backend.models.profiles import ModelProfiles
    from backend.models.selection import eligible_profiles
    from backend.storage.db import db
    from backend.api import engine
    from backend.runtime.computer_tools import TOOL_CAPABILITIES
    catalog=ModelProfiles(db)
    profiles=catalog.list()
    ready=await eligible_profiles([catalog.get(p['id'],credential=True) for p in profiles],characters=2000,tools=True)
    grants=[{'role':role,'capabilities':sorted(engine.security.nodes.get_node_capabilities(role) & set(TOOL_CAPABILITIES.values()))} for role in engine.swarm.registry._knights]
    blockers=[]
    if not ready: blockers.append('No reachable installed tool-capable model fits the minimum context budget. Verify tool support and model connection in Settings.')
    if not any('filesystem.read' in item['capabilities'] and 'filesystem.write' in item['capabilities'] for item in grants): blockers.append('No Apprentice has both workspace read and write grants. Review the intended worker in Governance.')
    if not engine.status().get('running'): blockers.append('Start the Kingdom runtime.')
    return {'ready_for_scoped_file_work':not blockers,'blockers':blockers,'models':[{'id':p['id'],'model':p['model'],'computer':p.get('computer_id')} for p in ready], 'grants':grants,'scope':'Connection and setup checks only; coding correctness and independent tests remain required.'}


@router.get('/desktop-readiness')
def desktop_readiness():
    import sys
    import importlib.util
    from backend.api import engine
    grants=[{'role':role,'can_observe':'computer.observe' in engine.security.nodes.get_node_capabilities(role),
             'can_control':'computer.control' in engine.security.nodes.get_node_capabilities(role)} for role in engine.swarm.registry._knights]
    foreground=None
    if sys.platform=='win32':
        try:
            from backend.runtime.desktop_observation import _foreground_window
            handle,title=_foreground_window()
            foreground={'window_handle':handle,'window_title':title}
        except Exception:
            pass
    return {'platform_supported':sys.platform=='win32',
            'adapter_installed':importlib.util.find_spec('pywinauto') is not None,
            'foreground_window':foreground,
            'foreground_available':foreground is not None,
            'apprentices':grants,'scope':'Interactive Windows desktop only. Select the exact foreground window; actual observation/action/read-back must still be verified. No tools or privileges were granted by this check.'}

@router.post('/{ident}/review-feedback')
def review_feedback(ident: str, request: ReviewFeedback):
    try:return service().review_feedback(ident,request.message,request.expected_updated_at)
    except KeyError:raise HTTPException(404,'Agent session not found')
    except ValueError as error:raise HTTPException(409,str(error)) from error


@router.get('')
def sessions():
    return service().list()


@router.post('', status_code=201)
def create(request: CreateSession):
    try:
        return service().create(**request.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get('/{ident}/activity')
def activity(ident: str):
    try: return service().activity(ident)
    except KeyError: raise HTTPException(404, 'Agent session not found')


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
