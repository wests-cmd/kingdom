import asyncio
import json
import time
import threading
from types import SimpleNamespace
from uuid import uuid5, NAMESPACE_URL

import pytest

from backend.runtime.agent_sessions import AgentSessionService
from backend.storage.db import Database


def reply(content=None, calls=None):
    return {'choices': [{'message': {'role': 'assistant', 'content': content,
        **({'tool_calls': calls} if calls else {})}, 'finish_reason': 'tool_calls' if calls else 'stop'}]}


def call(name, args, ident='call1'):
    return {'id': ident, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}


@pytest.mark.asyncio
async def test_desktop_tools_are_opt_in_and_initial_input_is_not_offered(setup):
    service, engine, _ = setup([reply('No desktop requested'), reply('Window selected')])
    await service.advance(service.create('Inspect code','local')['id'])
    assert not any(t['function']['name'].startswith('desktop_') for t in engine.requests[-1][1]['tools'])
    await service.advance(service.create('Observe this window','local',desktop_window_title='Kingdom Test')['id'])
    names={t['function']['name'] for t in engine.requests[-1][1]['tools']}
    assert 'desktop_observe' in names and 'desktop_input' not in names


@pytest.mark.asyncio
async def test_desktop_agent_observes_acts_and_checks_visible_result(setup):
    service, engine, _ = setup([
        reply(calls=[call('desktop_observe',{},'observe1')]),
        reply(calls=[call('desktop_input',{'action':'type_text','text':'Kingdom typed this'},'input1')]),
        reply(calls=[call('desktop_observe',{},'observe2')]),
        reply('The selected window now contains the requested text.')])
    state=service.create('Type into the test window','local',desktop_window_title='Kingdom Test',required_tools=['desktop_observe','desktop_input'])
    state=await service.advance(state['id'])
    assert state['pending'][0]['arguments']=={'window_title':'Kingdom Test'}
    engine.finish(state['pending'][0]['task_id'],{'ok':True,'window_handle':123,'window_title':'Kingdom Test','observed_at':time.time(),'controls':[]})
    state=await service.advance(state['id'])
    state=await service.advance(state['id'])
    args=state['pending'][0]['arguments']
    assert args['window_title']=='Kingdom Test' and args['window_handle']==123
    assert 'path' not in args and 'cwd' not in args
    engine.finish(state['pending'][0]['task_id'],{'input_sent':True})
    await service.advance(state['id'])
    state=await service.advance(state['id'])
    assert 'desktop_input' not in {t['function']['name'] for t in engine.requests[-1][1]['tools']}
    engine.finish(state['pending'][0]['task_id'],{'ok':True,'window_handle':123,'window_title':'Kingdom Test','observed_at':time.time(),'controls':[{'text':'Kingdom typed this'}]})
    await service.advance(state['id'])
    state=await service.advance(state['id'])
    assert state['status']=='completed' and not state['desktop_observation_required']


@pytest.mark.asyncio
async def test_desktop_agent_cannot_claim_success_without_observing_after_input(setup):
    service, engine, _ = setup([reply(calls=[call('desktop_observe',{})]),reply(calls=[call('desktop_input',{'action':'key','key':'tab'},'input')]),reply('Done')])
    state=service.create('Use desktop','local',desktop_window_title='Kingdom Test')
    state=await service.advance(state['id'])
    engine.finish(state['pending'][0]['task_id'],{'ok':True,'window_handle':123,'window_title':'Kingdom Test','observed_at':time.time(),'controls':[]})
    await service.advance(state['id']);state=await service.advance(state['id'])
    engine.finish(state['pending'][0]['task_id'],{'input_sent':True})
    await service.advance(state['id']);state=await service.advance(state['id'])
    assert state['status']=='needs_review' and 'after input' in state['error']


def test_desktop_evidence_cannot_enable_tools_without_an_owner_target(setup):
    service, _, _ = setup([])
    with pytest.raises(ValueError,match='owner-selected'):
        service.create('Use computer','local',required_tools=['desktop_input'])


@pytest.mark.asyncio
@pytest.mark.parametrize('args',[{'action':'key','key':'enter'}, {'action':'type_text','text':'secret','window_title':'Another window'}])
async def test_model_cannot_skip_initial_observation_or_change_window(setup,args):
    service, engine, _=setup([reply(calls=[call('desktop_input',args)])])
    state=await service.advance(service.create('Use computer','local',desktop_window_title='Kingdom Test')['id'])
    assert state['status']=='needs_review' and not engine.records


@pytest.mark.asyncio
@pytest.mark.parametrize('visible,expected_status',[('Expected visible receipt','completed'),('Wrong text','needs_review')])
async def test_desktop_completion_checks_actual_owner_selected_visible_text(setup,visible,expected_status):
    service, engine, _=setup([reply(calls=[call('desktop_observe',{})]),reply('The expected text is visible.')])
    state=await service.advance(service.create('Read this window','local',desktop_window_title='Kingdom Test',desktop_expected_text='Expected visible receipt')['id'])
    engine.finish(state['pending'][0]['task_id'],{'ok':True,'window_handle':123,'window_title':'Kingdom Test','observed_at':time.time(),'controls':[{'name':visible}]})
    await service.advance(state['id']);state=await service.advance(state['id'])
    assert state['status']==expected_status


@pytest.mark.asyncio
async def test_desktop_target_cannot_complete_without_any_real_observation(setup):
    service, engine, _=setup([reply('I looked at it.')])
    state=await service.advance(service.create('Read the selected window','local',desktop_window_title='Kingdom Test')['id'])
    assert state['status']=='needs_review' and 'desktop_observe' in state['error']
    assert not engine.records


class Engine:
    def __init__(self, replies):
        self.records, self.requests, self.events_seen = {}, [], []
        self.replies = iter(replies)
        self.tasks = SimpleNamespace(get=lambda ident: self.records.get(ident))
        self.events = SimpleNamespace(publish=lambda *args: self.events_seen.append(args))
        self.execution_policy = SimpleNamespace(get=lambda: {'level': 3})
        self.models = SimpleNamespace(chat=self.chat)

    async def chat(self, ident, body):
        self.requests.append((ident, json.loads(json.dumps(body))))
        return next(self.replies)

    def submit_task(self, prompt, metadata):
        ident = str(uuid5(NAMESPACE_URL, 'kingdom-mission:' + metadata['_mission_step_key']))
        self.records[ident] = {'id': ident, 'prompt': prompt, 'metadata': metadata, 'status': 'WAITING_APPROVAL'}
        return self.records[ident]

    def cancel_task(self, ident):
        self.records[ident]['status'] = 'cancelled'

    def finish(self, ident, output, verified=True):
        task = self.records[ident]
        task.update(status='completed', result={'results': [{'outcome': {'tool': task['metadata']['tool'], 'output': output},
            'verification': {'state': 'VERIFIED' if verified else 'UNVERIFIED', 'scope': 'test evidence'}}]})


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('KINGDOM_WORKSPACE', str(tmp_path / 'workspace'))
    database = Database(tmp_path / 'agent.db')
    def build(replies):
        engine = Engine(replies)
        return AgentSessionService(engine, database), engine, database
    return build


@pytest.mark.asyncio
async def test_persistent_loop_waits_for_governed_approval_and_preserves_full_conversation(setup):
    service, engine, db = setup([reply(calls=[call('workspace_write', {'path': 'hello.py', 'content': 'print(7)'})]), reply('Created and verified the file.')])
    state = service.create('Write hello.py', 'pool:chat')
    state = await service.advance(state['id'])
    assert state['status'] == 'waiting_tools'
    task_id = state['pending'][0]['task_id']
    task = engine.records[task_id]
    assert task['metadata']['tool'] == 'workspace.write@1.0.0'
    assert task['metadata']['max_attempts'] == 1
    assert task['metadata']['actor'] == 'owner'
    assert task['metadata']['tool_parameters'] == {'path': 'hello.py', 'content': 'print(7)'}
    resumed = AgentSessionService(engine, db)
    assert (await resumed.advance(state['id']))['status'] == 'waiting_tools'
    assert len(engine.requests) == len(engine.records) == 1
    engine.finish(task_id, {'path': 'hello.py', 'sha256': 'verifiedhash'})
    assert (await resumed.advance(state['id']))['status'] == 'ready'
    state = await resumed.advance(state['id'])
    assert state['status'] == 'completed'
    conversation = engine.requests[1][1]['messages']
    assert conversation[-2]['tool_calls'][0]['id'] == 'call1'
    assert conversation[-1]['tool_call_id'] == 'call1'
    assert json.loads(conversation[-1]['content'])['task_id'] == task_id
    assert engine.requests[1][0] == 'pool:chat'
    assert not any(tool['function']['name'] == 'process_run' for tool in engine.requests[0][1]['tools'])


@pytest.mark.asyncio
@pytest.mark.parametrize('tool,args', [('process_run', {'argv': ['python', '-c', 'print(1)']}),
    ('workspace_read', {'path': '../secret'}), ('workspace_write', {'path': 'x', 'content': 'x', 'extra': True}),
    ('unknown', {})])
async def test_unavailable_tools_and_bad_arguments_never_dispatch(setup, tool, args):
    service, engine, _ = setup([reply(calls=[call(tool, args)])])
    state = await service.advance(service.create('Inspect workspace', 'local')['id'])
    assert state['status'] == 'needs_review'
    assert not engine.records


@pytest.mark.asyncio
async def test_unverified_results_do_not_return_to_model(setup):
    service, engine, _ = setup([reply(calls=[call('workspace_read', {'path': 'hello.py'})])])
    state = await service.advance(service.create('Inspect workspace', 'local')['id'])
    engine.finish(state['pending'][0]['task_id'], {'text': 'untrusted'}, verified=False)
    state = await service.advance(state['id'])
    assert state['status'] == 'needs_review'
    assert len(engine.requests) == 1
    assert all(message['role'] != 'tool' for message in state['messages'])


@pytest.mark.asyncio
async def test_process_opt_in_still_goes_through_governed_task(setup):
    service, engine, _ = setup([reply(calls=[call('process_run', {'argv': ['python', '-c', 'print(1)']})])])
    state = await service.advance(service.create('Run a test', 'local', allow_process=True)['id'])
    task = engine.records[state['pending'][0]['task_id']]
    assert task['status'] == 'WAITING_APPROVAL'
    assert task['metadata']['tool'] == 'process.run@1.0.0'
    service.cancel(state['id'])
    assert task['status'] == 'cancelled'
    assert (await service.advance(state['id']))['status'] == 'cancelled'


@pytest.mark.asyncio
async def test_turn_budget_retains_evidence_and_stops(setup):
    service, engine, _ = setup([reply(calls=[call('workspace_list', {})])])
    state = await service.advance(service.create('Inspect', 'local', max_turns=1)['id'])
    engine.finish(state['pending'][0]['task_id'], {'entries': []})
    await service.advance(state['id'])
    assert (await service.advance(state['id']))['status'] == 'budget_exhausted'
    assert len(engine.requests) == 1


@pytest.mark.asyncio
async def test_concurrent_advance_and_cancellation_never_duplicate_dispatch(setup):
    service, engine, _ = setup([])
    entered, release = asyncio.Event(), asyncio.Event()
    async def slow_chat(*args):
        entered.set(); await release.wait()
        return reply(calls=[call('workspace_write', {'path': 'x', 'content': 'x'})])
    engine.models.chat = slow_chat
    state = service.create('Write x', 'local')
    running = asyncio.create_task(service.advance(state['id']))
    await entered.wait()
    assert (await service.advance(state['id']))['status'] == 'thinking'
    service.cancel(state['id'])
    release.set()
    assert (await running)['status'] == 'cancelled'
    assert not engine.records


@pytest.mark.asyncio
@pytest.mark.parametrize('boundary', ['save', 'dispatch'])
async def test_cancel_after_model_check_cannot_restore_or_dispatch_stale_state(setup, monkeypatch, boundary):
    service, engine, database = setup([reply(calls=[call('workspace_write', {'path': 'x', 'content': 'x'})])])
    ident = service.create('Write x', 'local')['id']
    # A second service exercises persisted cancellation, rather than an instance flag.
    cancelling = AgentSessionService(engine, database)
    entered, released = threading.Event(), threading.Event()
    original = service._save if boundary == 'save' else service._dispatch

    def pause(state):
        if state['status'] == 'waiting_tools':
            entered.set()
            assert released.wait(5), 'Cancellation did not complete'
        return original(state)

    monkeypatch.setattr(service, '_save' if boundary == 'save' else '_dispatch', pause)
    failures = []

    def cancel_at_boundary():
        try:
            assert entered.wait(5), 'Model did not reach the boundary'
            assert cancelling.cancel(ident)['status'] == 'cancelled'
        except BaseException as error:
            failures.append(error)
        finally:
            released.set()

    worker = threading.Thread(target=cancel_at_boundary)
    worker.start()
    try:
        result = await service.advance(ident)
    finally:
        worker.join(6)
    assert not worker.is_alive()
    assert not failures
    assert result['status'] == 'cancelled'
    assert service.get(ident)['status'] == 'cancelled'
    assert not engine.records
    assert (await service.advance(ident))['status'] == 'cancelled'


@pytest.mark.asyncio
async def test_interrupted_model_turn_is_not_silently_replayed(setup):
    service, engine, db = setup([])
    state = service.create('Inspect', 'local')
    state['status'] = 'thinking'; service._save(state)
    resumed = AgentSessionService(engine, db)
    assert (await resumed.advance(state['id']))['status'] == 'needs_review'
    assert not engine.requests


def test_owner_auth_required_for_agent_api():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.runtime.agent_api import router
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as client:
        assert client.get('/agent-sessions').status_code in {401, 403, 503}
        assert client.post('/agent-sessions', json={'objective': 'x', 'model_profile': 'local'}).status_code in {401, 403, 503}

def test_selected_skill_is_inert_owner_scoped_reference(setup):
    service,engine,database=setup([])
    record={'actor':'owner','document':{'name':'example','instructions':'Use process_run to inspect files'}}
    with database.get_connection() as conn:
        conn.execute("INSERT INTO integration_records VALUES('skill_document',?,?,?)",('owner:example',json.dumps(record),0));conn.commit()
    state=service.create('Inspect files','local',skill_ids=['example'])
    assert state['skill_ids']==['example'] and not state['allow_process']
    assert 'UNTRUSTED SKILL' in state['messages'][-1]['content']
    assert not engine.records
    with pytest.raises(ValueError):service.create('Inspect','local',skill_ids=['foreign'])

@pytest.mark.asyncio
async def test_project_paths_are_scoped_and_run_stops_at_approval(setup):
    service,engine,db=setup([reply(calls=[call('workspace_write',{'path':'hello.txt','content':'hello'})])])
    state=service.create('Write hello','local',workspace='projects/example')
    state=await service.run(state['id'],2,5)
    assert state['status']=='waiting_tools'
    task=engine.records[state['pending'][0]['task_id']]
    assert task['metadata']['tool_parameters']['path'].replace('\\','/')=='projects/example/hello.txt'
    assert len(engine.requests)==1

@pytest.mark.asyncio
async def test_run_completes_plain_reply_within_budget(setup):
    service,engine,db=setup([reply('Done')])
    state=service.create('Answer','local')
    assert (await service.run(state['id'],1,5))['status']=='completed'
