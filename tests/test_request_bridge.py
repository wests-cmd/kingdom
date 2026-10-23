import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from backend.storage.db import Database
from backend.runtime.request_service import RequestService

class Models:
    def __init__(self):self.calls=0
    async def chat(self, profile, body):
        self.calls+=1
        await asyncio.sleep(0.01)
        return {'choices':[{'message':{'content':'Real adapter boundary exercised'}}],'kingdom_profile':profile}

class Agents:
    def __init__(self):self.created=0;self.runs=0;self.cancelled=[]
    def create(self,*args,**kwargs):self.created+=1;return {'id':'saved-agent'}
    async def run(self,*args):self.runs+=1;return {'id':'saved-agent','status':'completed','turns':1,'messages':[{'role':'assistant','content':'Done'}]}
    def cancel(self,ident):self.cancelled.append(ident)


def test_empty_timeout_exception_retains_safe_failure_class(tmp_path):
    service,models,_=setup(tmp_path)
    async def timeout(*args):raise TimeoutError()
    models.chat=timeout
    data=body();data['mode']='quick'
    ident=service.create(data)['id']
    with pytest.raises(TimeoutError):asyncio.run(service.run(ident))
    failed=service.get(ident)
    assert failed['error_class']=='TimeoutError'
    assert failed['error'] and 'timed out' in failed['error'].lower()
    assert failed['status']=='failed'


@pytest.mark.parametrize('failure',[TimeoutError('api_key=private-provider-key'),
                                    ValueError('Authorization: Bearer private-provider-key')])
def test_failed_request_diagnostic_excludes_exception_secrets(tmp_path,failure):
    service,models,_=setup(tmp_path)
    async def fail(*args):raise failure
    models.chat=fail
    data=body();data['mode']='quick'
    ident=service.create(data)['id']
    with pytest.raises(type(failure)):asyncio.run(service.run(ident))
    failed=service.get(ident)
    assert failed['error_class']==type(failure).__name__
    assert failed['error']
    assert 'private-provider-key' not in str(failed)


def test_desktop_request_uses_agent_and_preserves_owner_window(tmp_path):
    service, models, agents=setup(tmp_path)
    options=[]
    original=agents.create
    def capture(*args,**kwargs):
        options.append(kwargs)
        return original(*args,**kwargs)
    agents.create=capture
    data=body(desktop_window_title='Kingdom Test')
    request=service.create(data)
    assert request['route']=='agent'
    asyncio.run(service.run(request['id']))
    assert options[0]['desktop_window_title']=='Kingdom Test'
    assert options[0]['required_tools']==['desktop_observe']
    assert models.calls==0


def test_text_only_route_cannot_silently_accept_a_desktop_request(tmp_path):
    service, _, _=setup(tmp_path)
    data=body(desktop_window_title='Kingdom Test');data['mode']='quick'
    with pytest.raises(ValueError,match='agent route'):
        service.create(data)


def setup(tmp_path):
    db=Database(tmp_path/'state.db');models=Models();agents=Agents()
    engine=SimpleNamespace(status=lambda:{'running':True,'mode':'adaptive'},tasks=SimpleNamespace(list=lambda:[]))
    return RequestService(db,engine,models,agents),models,agents


def body(**extra):
    return dict(idempotency_key='key',session_scope='chat',project_scope='projects/a',prompt='what time is it?',mode='auto',model_profile='explicit-model',allow_process=False,**extra)

@pytest.mark.parametrize('prompt',['what time is it?','status','what are my priorities?', 'What is the runtime status?', 'runtime status', 'What is the system status?'])
def test_deterministic_requests_never_call_provider(tmp_path,prompt):
    service,models,agents=setup(tmp_path)
    data=body();data['prompt']=prompt
    result=asyncio.run(service.run(service.create(data)['id']))
    assert result['status']=='completed' and result['answer'] and result['evidence']
    assert models.calls==agents.created==0


def test_duplicate_frontdoors_and_restart_share_id(tmp_path):
    service,models,agents=setup(tmp_path)
    other=RequestService(service.db,service.engine,models,agents)
    with ThreadPoolExecutor(2) as pool:
        records=list(pool.map(lambda instance:instance.create(body()),[service,other]))
    assert records[0]['id']==records[1]['id']
    asyncio.run(service.run(records[0]['id']))
    assert other.get(records[0]['id'])['status']=='completed'
    assert len(other.list('chat','projects/a'))==1
    changed=body();changed['prompt']='different question'
    with pytest.raises(ValueError):other.create(changed)


def test_explicit_model_and_route_preserved_no_duplicate_inference(tmp_path):
    service,models,agents=setup(tmp_path)
    data=body();data['mode']='quick'
    ident=service.create(data)['id']
    async def race():return await asyncio.gather(service.run(ident),service.run(ident))
    asyncio.run(race())
    assert models.calls==1
    assert service.get(ident)['evidence'][0]['profile']=='explicit-model'
    assert service.get(ident)['route']=='quick'


def test_agent_delegation_and_cancel_checkpoint(tmp_path):
    service,models,agents=setup(tmp_path)
    data=body();data['mode']='agent'
    ident=service.create(data)['id']
    result=asyncio.run(service.run(ident))
    assert result['agent_session_id']=='saved-agent'
    asyncio.run(service.run(ident))
    assert agents.created==agents.runs==1 and models.calls==0
    data['idempotency_key']='cancel'
    queued=service.create(data)
    service.cancel(queued['id'])
    assert asyncio.run(service.run(queued['id']))['status']=='cancelled'
    assert agents.created==1


def test_restart_running_checkpoint_does_not_replay(tmp_path):
    service,models,agents=setup(tmp_path)
    data=body();data['mode']='agent'
    ident=service.create(data)['id']
    service.update(ident,{'status':'running'})
    restarted=RequestService(service.db,service.engine,models,agents)
    assert asyncio.run(restarted.run(ident))['status']=='running'
    assert agents.created==models.calls==0


def test_project_priorities_do_not_leak_other_scope(tmp_path):
    service,models,agents=setup(tmp_path)
    service.engine.tasks.list=lambda:[{'id':'secret','prompt':'private elsewhere','status':'queued','metadata':{'project_scope':'projects/b'}}]
    data=body();data['prompt']='priorities'
    result=asyncio.run(service.run(service.create(data)['id']))
    assert 'private elsewhere' not in result['answer']
    assert result['evidence'][0]['task_ids']==[]


def test_natural_work_list_question_reads_real_scoped_backlog_without_model(tmp_path):
    service, models, agents = setup(tmp_path)
    from backend.runtime.work_backlog import WorkBacklog
    service.engine.events = SimpleNamespace(publish=lambda *args, **kwargs: None)
    backlog = WorkBacklog(service.db, service.engine)
    lower = backlog.register('kingdom', 'later', title='Later real work', priority=10)
    first = backlog.register('kingdom', 'first', title='First real security work', priority=100)
    backlog.register('private', 'hidden', title='Private other project', priority=100)
    data = body()
    data.update(project_scope='kingdom', prompt='What should we do next on the project work list? Show the highest-priority unfinished work and its blockers. Do not claim the updates are complete.')
    result = asyncio.run(service.run(service.create(data)['id']))
    assert result['route'] == 'priorities'
    assert models.calls == agents.created == 0
    assert result['answer'].index(first['title']) < result['answer'].index(lower['title'])
    assert first['reason'] in result['answer']
    assert 'Private other project' not in result['answer']
    assert result['evidence'][1]['work_ids'] == [first['id'], lower['id']]


@pytest.mark.parametrize('prompt', ['How should a priority queue work?',
                                   'What are priorities in project management?'])
def test_priority_explanation_questions_keep_model_route(tmp_path, prompt):
    service, _, _ = setup(tmp_path)
    data = body(); data['prompt'] = prompt
    assert service.create(data)['route'] == 'quick'

@pytest.mark.parametrize('prompt,route',[('fix the workspace bug','agent'),('How do I fix a bug?','quick'),('please inspect the project','agent'),('Tell me the history of clocks','quick')])
def test_automatic_action_vs_question_routing(tmp_path,prompt,route):
    service,models,agents=setup(tmp_path)
    data=body();data['prompt']=prompt
    assert service.create(data)['route']==route
    assert models.calls==agents.created==0


def test_slow_status_read_does_not_block_event_loop(tmp_path):
    import time
    service,models,agents=setup(tmp_path)
    def slow_status():
        time.sleep(0.15)
        return {'running':True,'mode':'adaptive'}
    service.engine.status=slow_status
    data=body();data['prompt']='status'
    ident=service.create(data)['id']
    async def check():
        task=asyncio.create_task(service.run(ident))
        await asyncio.sleep(0.04)
        assert not task.done()
        await task
    asyncio.run(check())


def test_automatic_agent_preserves_explicit_model_without_inference(tmp_path):
    service,models,agents=setup(tmp_path)
    original=agents.create
    profiles=[]
    def create(objective,profile,**kwargs):
        profiles.append(profile)
        return original(objective,profile,**kwargs)
    agents.create=create
    data=body();data['prompt']='implement a small change'
    result=asyncio.run(service.run(service.create(data)['id']))
    assert result['route']=='agent'
    assert profiles==['explicit-model'] and models.calls==0

@pytest.mark.parametrize('desktop_title', [None, 'Kingdom Test'])
def test_request_preserves_required_coding_evidence_in_native_session(tmp_path, monkeypatch, desktop_title):
    from backend.runtime.agent_sessions import AgentSessionService
    db = Database(tmp_path / 'coding-evidence.db')
    models = Models()
    engine = SimpleNamespace(models=models, events=SimpleNamespace(publish=lambda *args: None),
                             execution_policy=SimpleNamespace(get=lambda: {'level': 3}))
    monkeypatch.setenv('KINGDOM_WORKSPACE', str(tmp_path / 'workspace'))
    agents = AgentSessionService(engine, db)
    service = RequestService(db, engine, models, agents)
    data = body(required_tools=['workspace_read', 'workspace_write'], desktop_window_title=desktop_title)
    data['mode'] = 'agent'
    saved = service.create(data)
    restarted = RequestService(db, engine, models, agents)
    result = asyncio.run(restarted.run(saved['id']))
    assert result['status'] == 'waiting_review'
    native = agents.get(result['agent_session_id'])
    assert native['required_tools'] == (['workspace_read', 'workspace_write', 'desktop_observe']
                                        if desktop_title else ['workspace_read', 'workspace_write'])
    assert native['status'] == 'needs_review'
    assert 'workspace_write' in native['error']
    assert native['model_profile'] == 'explicit-model'
    assert native['allow_process'] is False
    assert native['workspace'] == 'projects/a'
    assert native['tool_count'] == 0

def test_request_input_accepts_only_known_required_tools():
    from pydantic import ValidationError
    from backend.runtime.request_api import RequestInput
    data = body(required_tools=['workspace_read', 'workspace_write'])
    parsed = RequestInput.model_validate(data)
    assert parsed.model_dump()['required_tools'] == ['workspace_read', 'workspace_write']
    data['required_tools'] = ['unrestricted_shell']
    with pytest.raises(ValidationError):
        RequestInput.model_validate(data)


@pytest.mark.parametrize('prompt', ['what time is it?', 'runtime status', 'Please repair the saved project'])
def test_required_tools_force_agent_before_auto_routing(tmp_path, prompt):
    service, models, agents = setup(tmp_path)
    data = body(required_tools=['workspace_read', 'workspace_write'])
    data['prompt'] = prompt
    saved = service.create(data)
    assert saved['route'] == 'agent'
    asyncio.run(service.run(saved['id']))
    assert agents.created == 1
    assert models.calls == 0


@pytest.mark.parametrize('options, expected', [
    ({'mode': 'quick', 'required_tools': ['workspace_write']}, 'agent route'),
    ({'required_tools': ['process_run']}, 'process option'),
    ({'required_tools': ['desktop_observe']}, 'owner-selected window'),
    ({'required_tools': ['desktop_input']}, 'owner-selected window'),
])
def test_invalid_required_tool_route_or_options_rejected_before_insertion(tmp_path, options, expected):
    service, models, agents = setup(tmp_path)
    data = body()
    data.update(options)
    with pytest.raises(ValueError, match=expected):
        service.create(data)
    assert service.list(data['session_scope'], data['project_scope']) == []
    assert models.calls == agents.created == 0
