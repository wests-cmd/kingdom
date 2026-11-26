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


def test_project_references_cannot_overflow_small_model_or_drop_current_question(tmp_path):
    import json
    from backend.models.profiles import ModelProfiles
    from backend.memory.portable_vault import project_identity
    from backend.memory.tiered_vault import configured_vault
    service, models, _ = setup(tmp_path)
    ModelProfiles(service.db).save('small-local', {
        'provider':'ollama', 'endpoint':'http://127.0.0.1:11434',
        'model':'installed-model', 'variant':'standard', 'context_characters':4000})
    vault = configured_vault(service.db)
    for index in range(3):
        vault.put(project_identity('projects/a'), 'planning ' + ('reference ' * 400),
                  {'source':'test'}, [], ident='large_note_'+str(index), expected_revision=0)
    captured = []
    async def bounded_chat(profile, payload):
        captured.append(payload['messages'])
        assert len(json.dumps(payload['messages'])) <= 4000
        return {'choices':[{'message':{'content':'Scoped proposal'}}], 'kingdom_profile':profile}
    models.chat = bounded_chat
    data = body(); data.update(mode='quick', model_profile='small-local',
                               prompt='planning: critique the proposals; preserve this exact question')
    result = asyncio.run(service.run(service.create(data)['id']))
    assert result['status'] == 'completed'
    assert captured[0][-1] == {'role':'user','content':data['prompt']}
    assert any('UNTRUSTED PROJECT REFERENCES' in m['content'] for m in captured[0])


@pytest.mark.parametrize('text,finish', [('', 'stop'), ('unfinished proposal', 'length')])
def test_incomplete_quick_answer_is_not_a_completed_plan(tmp_path, text, finish):
    service, models, _ = setup(tmp_path)
    async def incomplete(*args):
        return {'choices':[{'message':{'content':text}, 'finish_reason':finish}]}
    models.chat = incomplete
    data = body(); data.update(mode='quick', prompt='Draft a proposal')
    ident = service.create(data)['id']
    with pytest.raises(ValueError):
        asyncio.run(service.run(ident))
    failed = service.get(ident)
    assert failed['status'] == 'failed'
    assert failed['error_code'] == 'model_output_incomplete'
    assert 'unfinished proposal' not in failed['error']


def test_context_keeps_recent_complete_turns_and_exact_unicode_question(tmp_path):
    import json
    from backend.models.profiles import ModelProfiles
    service, _, _ = setup(tmp_path)
    ModelProfiles(service.db).save('small-local', {
        'provider':'ollama','endpoint':'http://127.0.0.1:11434',
        'model':'installed-model','variant':'standard','context_characters':4000})
    for key, prompt, answer in [('old', 'old ' * 1000, 'old answer ' * 1000),
                                ('recent', 'Recent question', 'Recent answer')]:
        data = body(); data.update(idempotency_key=key, prompt=prompt)
        previous = service.create(data)
        service.update(previous['id'], {'status':'completed','answer':answer})
    data = body(); data.update(idempotency_key='new', model_profile='small-local', prompt='Question ☃ "\\"' * 20)
    current = service.create(data)
    messages = service.messages(current)
    assert len(json.dumps(messages)) <= 4000
    assert messages[-1]['content'] == data['prompt']
    assert messages[:2] == [{'role':'user','content':'Recent question'},
                            {'role':'assistant','content':'Recent answer'}]


def test_oversize_current_question_is_retained_without_inference(tmp_path):
    from backend.models.profiles import ModelProfiles
    service, models, _ = setup(tmp_path)
    ModelProfiles(service.db).save('small-local', {
        'provider':'ollama','endpoint':'http://127.0.0.1:11434',
        'model':'installed-model','variant':'standard','context_characters':4000})
    data=body();data.update(mode='quick',model_profile='small-local',prompt='x'*4500)
    ident=service.create(data)['id']
    with pytest.raises(ValueError):asyncio.run(service.run(ident))
    failed=service.get(ident)
    assert failed['prompt']==data['prompt']
    assert failed['error_code']=='context_budget_exceeded'
    assert models.calls==0


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


@pytest.mark.parametrize('remaining,lower,upper',[(1000,599,600),(90,88,90)])
def test_background_deadline_reaches_inner_agent_without_default_five_minute_cutoff(tmp_path,remaining,lower,upper):
    import time
    service,_,agents=setup(tmp_path);seen=[]
    original=agents.run
    async def capture(*args):seen.append(args[2]);return await original(*args)
    agents.run=capture
    data=body();data['mode']='agent'
    ident=service.create(data)['id']
    service.update(ident,{'background_deadline_at':time.time()+remaining})
    asyncio.run(service.run(ident))
    assert lower<=seen[0]<=upper


def test_expired_background_deadline_cannot_dispatch_an_agent_turn(tmp_path):
    import time
    service,_,agents=setup(tmp_path)
    data=body();data['mode']='agent'
    ident=service.create(data)['id']
    service.update(ident,{'background_deadline_at':time.time()-1})
    with pytest.raises(TimeoutError):asyncio.run(service.run(ident))
    assert agents.runs==0


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


def test_agent_receives_only_prior_completed_turns_in_exact_scope(tmp_path):
    import json
    service, _, agents = setup(tmp_path)
    def saved(key, prompt, project='projects/a', session='chat', completed=True):
        data = body()
        data.update(idempotency_key=key, prompt=prompt, project_scope=project,
                    session_scope=session, mode='quick')
        state = service.create(data)
        if completed:
            service.update(state['id'], {'status':'completed', 'answer':'answer '+prompt})
        return state
    prior = saved('prior', 'prior architecture')
    saved('other-project', 'private project', project='projects/b')
    saved('other-chat', 'private chat', session='other')
    saved('pending', 'unfinished turn', completed=False)
    data = body()
    data.update(idempotency_key='agent', prompt='implement the previous design', mode='agent')
    current = service.create(data)
    saved('later', 'future turn')
    received = []
    original = agents.create
    def capture(objective, profile, **kwargs):
        received.append((objective, profile, kwargs))
        return original(objective, profile, **kwargs)
    agents.create = capture
    asyncio.run(service.run(current['id']))
    objective, profile, options = received[0]
    assert objective == data['prompt']
    assert profile == data['model_profile']
    assert options['allow_process'] is False
    assert options['use_owner_memory'] is False
    assert json.loads(options['conversation_context']) == [
        {'request_id':prior['id'], 'question':'prior architecture', 'answer':'answer prior architecture'}]


def test_agent_history_is_bounded_and_chronological(tmp_path):
    import json
    service, _, _ = setup(tmp_path)
    for index in range(8):
        data = body()
        data.update(idempotency_key=str(index), prompt='prompt '+str(index)+'雪'*800)
        state = service.create(data)
        service.update(state['id'], {'status':'completed','answer':'answer '+str(index)+'a'*1000})
    data = body()
    data.update(idempotency_key='current', prompt='next task')
    current = service.create(data)
    context = service.agent_conversation_context(current)
    assert context is None or len(context) <= 4000
    # A smaller newest completed turn must be included without crossing scope.
    service.update(current['id'], {'status':'completed','answer':'short answer'})
    data.update(idempotency_key='next')
    next_state = service.create(data)
    turns = json.loads(service.agent_conversation_context(next_state))
    assert turns[-1]['request_id'] == current['id']
    assert len(service.agent_conversation_context(next_state)) <= 4000


@pytest.mark.parametrize("command,route", [("/help","help"),("/work","work"),("/harnesses","harnesses"),
    ("/time","time"),("/status","status"),("/priorities","priorities")])
def test_instant_commands_use_existing_request_bridge_without_model(tmp_path, command, route):
    service, models, agents = setup(tmp_path)
    data = body()
    data["prompt"] = command
    request = service.create(data)
    assert request["route"] == route
    result = asyncio.run(service.run(request["id"]))
    assert result["status"] == "completed" and result["evidence"]
    assert models.calls == agents.created == 0
    if route == "help":
        assert "\n/status" in result["answer"]


def test_shortcut_is_scoped_and_request_identity_survives_edit_and_removal(tmp_path):
    service, models, agents = setup(tmp_path)
    service.shortcuts.save("projects/a","focus","status")
    data = body()
    data["prompt"] = "/focus"
    saved = service.create(data)
    assert saved["route"] == "status"
    service.shortcuts.save("projects/a","focus","time")
    service.shortcuts.remove("projects/a","focus")
    restarted = RequestService(service.db, service.engine, models, agents)
    assert restarted.create(data)["id"] == saved["id"]
    assert asyncio.run(restarted.run(saved["id"]))["route"] == "status"
    other = dict(data, project_scope="projects/b")
    with pytest.raises(ValueError, match="Unknown instant"):
        restarted.create(other)
    assert models.calls == agents.created == 0


@pytest.mark.parametrize("name,command", [("status","time"),("hello;rm","status"),("a","process.run"),
    ("a","/status"),("a","status; shutdown")])
def test_shortcut_refuses_reserved_names_and_executable_payloads(tmp_path,name,command):
    service, _, _ = setup(tmp_path)
    with pytest.raises(ValueError):
        service.shortcuts.save("projects/a",name,command)


def test_recent_work_never_crosses_project_or_conversation(tmp_path):
    service, models, agents = setup(tmp_path)
    for key, session, project, prompt in [
        ("one","chat","projects/a","visible task"),
        ("two","elsewhere","projects/a","secret chat"),
        ("three","chat","projects/b","secret project")]:
        service.create(dict(body(),idempotency_key=key,session_scope=session,project_scope=project,prompt=prompt))
    saved = service.create(dict(body(),prompt="/work"))
    result = asyncio.run(service.run(saved["id"]))
    assert "visible task" in result["answer"]
    assert "secret" not in result["answer"]
    assert len(result["evidence"][0]["request_ids"]) == 1
    assert models.calls == agents.created == 0


def test_harness_catalog_does_not_expose_configured_arguments_or_credentials(tmp_path):
    service, models, agents = setup(tmp_path)
    with service.db.get_connection() as conn:
        conn.execute("CREATE TABLE harness_profiles(id TEXT PRIMARY KEY,config_json TEXT NOT NULL)")
        conn.execute("INSERT INTO harness_profiles VALUES(?,?)",("configured-cli",'{"argv":["private-arg"]}'))
        conn.commit()
    result = asyncio.run(service.run(service.create(dict(body(),prompt="/harnesses"))["id"]))
    assert "configured-cli" in result["answer"]
    assert "private-arg" not in str(result)
    assert result["evidence"][0]["verified_execution"] is False
    assert models.calls == agents.created == 0


def test_unknown_slash_does_not_reach_agent_or_model(tmp_path):
    service, models, agents = setup(tmp_path)
    with pytest.raises(ValueError,match="Unknown instant"):
        service.create(dict(body(),prompt="/delete everything"))
    assert models.calls == agents.created == 0


def test_learn_only_completed_instant_request_in_exact_scope(tmp_path):
    service, models, agents = setup(tmp_path)
    saved=service.create(dict(body(),prompt='/status'))
    with pytest.raises(ValueError):
        service.learn_shortcut(saved['id'],'chat','projects/a','focus')
    asyncio.run(service.run(saved['id']))
    with pytest.raises(ValueError):
        service.learn_shortcut(saved['id'],'other','projects/a','focus')
    assert service.learn_shortcut(saved['id'],'chat','projects/a','focus')['command']=='status'
    next_request=service.create(dict(body(),idempotency_key='next',prompt='/focus'))
    assert asyncio.run(service.run(next_request['id']))['status']=='completed'
    assert models.calls==agents.created==0


def _chat_profiles(service):
    from backend.models.profiles import ModelProfiles
    profiles=ModelProfiles(service.db)
    for ident in ('primary','fallback'):
        profiles.save(ident,{'provider':'ollama','endpoint':'http://127.0.0.1:11434',
            'model':ident,'variant':'standard','vision':ident=='primary'})
    return profiles


def test_opt_in_incomplete_text_escalates_once(tmp_path):
    service, models, agents=setup(tmp_path)
    _chat_profiles(service)
    calls=[]
    async def chat(profile,request):
        calls.append(profile)
        assert not request.get('tools')
        return {'choices':[{'message':{'content':'partial' if profile=='primary' else 'complete'},'finish_reason':'length' if profile=='primary' else 'stop'}]}
    models.chat=chat
    saved=service.create(dict(body(),mode='quick',model_profile='primary',fallback_profile='fallback',prompt='Explain a concept'))
    result=asyncio.run(service.run(saved['id']))
    assert calls==['primary','fallback'] and agents.created==0
    assert result['answer']=='complete'
    assert result['evidence'][0]['type']=='model_escalation'
    assert result['evidence'][1]['profile']=='fallback'


def test_transport_failure_never_escalates(tmp_path):
    service,models,_=setup(tmp_path)
    _chat_profiles(service)
    calls=[]
    async def chat(profile,request):
        calls.append(profile)
        raise PermissionError('not authorized')
    models.chat=chat
    saved=service.create(dict(body(),mode='quick',model_profile='primary',fallback_profile='fallback'))
    with pytest.raises(PermissionError):asyncio.run(service.run(saved['id']))
    assert calls==['primary']


def test_explicit_screen_region_is_not_sent_to_other_provider(tmp_path):
    import base64,io
    from PIL import Image
    service,models,agents=setup(tmp_path)
    _chat_profiles(service)
    raw=io.BytesIO()
    Image.new('RGB',(80,80),'red').save(raw,format='JPEG')
    crop='data:image/jpeg;base64,'+base64.b64encode(raw.getvalue()).decode()
    calls=[]
    async def chat(profile,request):
        calls.append((profile,request))
        return {'choices':[{'message':{'content':'Red area'},'finish_reason':'stop'}]}
    models.chat=chat
    data=dict(body(),mode='quick',model_profile='primary',screen_region=crop)
    for changed in ({'model_profile':'fallback'},{'mode':'agent'},{'fallback_profile':'fallback'},
                    {'screen_region':'https://example.com/private.jpg'}):
        with pytest.raises(ValueError):service.create({**data,**changed})
    result=asyncio.run(service.run(service.create(data)['id']))
    assert result['answer']=='Red area' and agents.created==0
    assert calls[0][0]=='primary'
    assert calls[0][1]['messages'][0]['content'][1]['image_url']['url']==crop
    assert 'tools' not in calls[0][1]


def _harness_fixture(tmp_path,monkeypatch):
    import sys
    from backend.runtime.harnesses import HarnessService,HarnessConfig
    service,models,agents=setup(tmp_path)
    monkeypatch.setenv('KINGDOM_WORKSPACE',str(tmp_path/'workspace'))
    service.engine.events=SimpleNamespace(publish=lambda *args:None)
    from backend.runtime.tasks import TaskManager
    from backend.storage.repository import TaskRepository
    service.engine.tasks=TaskManager(TaskRepository(service.db))
    service.engine.submit_task=service.engine.tasks.create
    service.engine.cancel_task=service.engine.tasks.cancel
    harness=HarnessService(service.engine,service.db)
    harness.save('example',HarnessConfig(name='Example',argv=[sys.executable,'-c','print("ok")','{prompt}']))
    return service,harness,models,agents


def test_harness_chat_links_one_approved_task_and_collects_verified_exit(tmp_path,monkeypatch):
    service,harness,models,agents=_harness_fixture(tmp_path,monkeypatch)
    data=dict(body(),mode='harness',harness_id='example',allow_process=True,prompt='literal request')
    saved=service.create(data)
    result=asyncio.run(service.run(saved['id']))
    ident=result['governed_task_id']
    assert result['status']=='waiting_review'
    assert asyncio.run(service.run(saved['id']))['governed_task_id']==ident
    assert len(service.engine.tasks.list())==1
    task=service.engine.tasks.repo.get(ident)
    assert task['metadata']['tool']=='harness.run@1.0.0'
    assert task['metadata']['conversation_request_id']==saved['id']
    service.engine.tasks.transition_task(ident,'running')
    service.engine.tasks.transition_task(ident,'completed',{'result':{'results':[{
        'verification':{'state':'VERIFIED'},'outcome':{'tool':'harness.run@1.0.0','output':{'exit_code':0,'output':'fixture output'}}}]}})
    completed=asyncio.run(service.run(saved['id']))
    assert completed['status']=='completed' and completed['evidence'][0]['verified_execution']
    assert models.calls==agents.created==0


def test_harness_revision_drift_or_interrupted_admission_never_submits(tmp_path,monkeypatch):
    import sys
    from backend.runtime.harnesses import HarnessConfig
    service,harness,_,_=_harness_fixture(tmp_path,monkeypatch)
    data=dict(body(),mode='harness',harness_id='example',allow_process=True,prompt='literal')
    saved=service.create(data)
    harness.save('example',HarnessConfig(name='Changed',argv=[sys.executable,'-c','print("changed")','{prompt}']))
    with pytest.raises(ValueError,match='changed'):
        asyncio.run(service.run(saved['id']))
    saved=service.create(dict(data,idempotency_key='new'))
    service.update(saved['id'],{'status':'waiting_review','governed_submission_started':True})
    result=asyncio.run(service.run(saved['id']))
    assert result['status']=='waiting_review' and 'interrupted' in result['answer']
    assert service.engine.tasks.list()==[]
