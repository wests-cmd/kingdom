import asyncio
import json
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
