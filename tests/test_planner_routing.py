import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.models.planner_routing import deliberate, hosting
from backend.models.profiles import ModelProfiles
from backend.runtime.work_programmes import WorkProgrammes
from test_project_test_missions import runtime, plan


@pytest.fixture
def profiles(monkeypatch):
    configured = [
        {'id': 'local', 'provider': 'ollama', 'model': 'small', 'endpoint': 'http://127.0.0.1:11434', 'context_characters': 100000},
        {'id': 'cloud_a', 'provider': 'openai_compatible', 'model': 'chat', 'endpoint': 'https://a.example', 'context_characters': 100000},
        {'id': 'cloud_b', 'provider': 'openai_compatible', 'model': 'chat', 'endpoint': 'https://b.example', 'context_characters': 100000},
    ]
    monkeypatch.setattr(ModelProfiles, 'list', lambda self: configured)
    return configured


def test_local_default_two_independent_plans_critique_and_synthesis(profiles):
    models = SimpleNamespace(plan_chat=AsyncMock(side_effect=[{'text': 'A'}, {'text': 'B'}, {'text': 'critique'}, {'text': '{"question":"Which target?"}'}]))
    record = AsyncMock()
    result = asyncio.run(deliberate(models, 'outcome', 'local', record))
    assert result['text'] == '{"question":"Which target?"}'
    calls = models.plan_chat.await_args_list
    assert len(calls) == 4 and all(c.kwargs == {'profile': 'local', 'hosting': 'local'} for c in calls)
    assert 'candidate plan B independently' in calls[1].args[0] and '"plan_a"' not in calls[1].args[0]
    assert '"plan_a": "A"' in calls[2].args[0] and '"plan_b": "B"' in calls[2].args[0]
    assert 'critique' in calls[3].args[0]
    assert [c.args[0] for c in record.await_args_list] == ['plan_a', 'plan_b', 'critique', 'synthesis']


def test_cloud_quota_falls_back_once_to_another_available_model(profiles):
    async def respond(prompt, profile, hosting):
        if profile == 'cloud_a':
            raise httpx.HTTPStatusError('private provider body', request=httpx.Request('POST', 'https://a.example'), response=httpx.Response(429))
        return {'text': '{}'}
    models = SimpleNamespace(plan_chat=AsyncMock(side_effect=respond))
    record = AsyncMock()
    asyncio.run(deliberate(models, 'outcome', 'cloud', record))
    ids = [c.kwargs['profile'] for c in models.plan_chat.await_args_list]
    assert ids == ['cloud_a', 'cloud_b', 'cloud_b', 'cloud_b', 'cloud_b']
    first = record.await_args_list[0].args[1]
    assert first['fallbacks'] == [{'profile': 'cloud_a', 'reason': 'quota or service unavailable'}]
    assert 'private provider body' not in str(record.await_args_list)


def test_cloud_exhaustion_can_fall_back_local_but_local_never_escalates(profiles):
    async def respond(prompt, profile, hosting):
        if hosting == 'cloud':
            raise TimeoutError()
        return {'text': '{}'}
    models = SimpleNamespace(plan_chat=AsyncMock(side_effect=respond))
    asyncio.run(deliberate(models, 'outcome', 'cloud', AsyncMock()))
    assert models.plan_chat.await_args_list[-1].kwargs['profile'] == 'local'
    profiles[:] = [p for p in profiles if p['id'] != 'local']
    models.plan_chat.reset_mock()
    with pytest.raises(ValueError, match='No eligible'):
        asyncio.run(deliberate(models, 'private outcome', 'local', AsyncMock()))
    models.plan_chat.assert_not_awaited()


def test_mixed_assigns_local_draft_and_synthesis_cloud_alternative_and_critique(profiles):
    models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': '{}'}))
    asyncio.run(deliberate(models, 'outcome', 'mixed', AsyncMock()))
    assert [c.kwargs['hosting'] for c in models.plan_chat.await_args_list] == ['local', 'cloud', 'cloud', 'local']


def test_deliberation_checkpoint_stays_proposal_and_does_not_approve(runtime, profiles):
    engine, backlog, _ = runtime
    engine.models = SimpleNamespace(plan_chat=AsyncMock(side_effect=[{'text': 'A'}, {'text': 'B'}, {'text': 'gaps'}, {'text': json.dumps({'plan': plan().model_dump(), 'acceptance_step': 'suite'})}]))
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'two-plans', '- Check recovery', source_revision='a'*40)
    assert state['planner_mode'] == 'deliberative' and state['planner_routing'] == 'local'
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    row = state['sections'][0]['items'][0]
    assert row['planning'] == 'needs_review' and len(row['planning_stages']) == 4
    assert row['planning_stages']['critique']['text'] == 'gaps'
    assert WorkProgrammes(backlog.db, engine, backlog).get(state['id'])['sections'][0]['items'][0]['planning_stages'] == row['planning_stages']
    assert engine.missions.list() == [] and engine.tasks.list() == []


def test_unknown_remote_host_is_not_silently_local():
    assert hosting({'provider': 'openai_compatible', 'endpoint': 'http://127.0.0.1:1234'}) == 'cloud'
    assert hosting({'provider': 'ollama', 'endpoint': 'https://worker.example'}) == 'cloud'
    assert hosting({'provider': 'ollama', 'endpoint': 'https://worker.example', 'hosting': 'local'}) == 'local'


def test_invalid_synthesis_gets_one_contract_repair_without_execution(runtime, profiles):
    engine, backlog, _ = runtime
    engine.models = SimpleNamespace(plan_chat=AsyncMock(side_effect=[
        {'text': 'A'}, {'text': 'B'}, {'text': 'gaps'}, {'text': '**Ready**.'},
        {'text': json.dumps({'question': 'Which reviewed source revision should be used?'})}]))
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'repair-synthesis', '- Check recovery', source_revision='a'*40)
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    row = state['sections'][0]['items'][0]
    assert row['planning'] == 'awaiting_answer'
    assert row['question'] == 'Which reviewed source revision should be used?'
    assert len(engine.models.plan_chat.await_args_list) == 5
    assert row['planning_stages']['synthesis_rejection']['reason'] == 'invalid_planning_contract'
    assert row['planning_stages']['synthesis_repair']['hosting'] == 'local'
    assert engine.missions.list() == [] and engine.tasks.list() == []


def test_synthesis_repair_budget_exhaustion_stays_blocked(runtime, profiles):
    engine, backlog, _ = runtime
    engine.models = SimpleNamespace(plan_chat=AsyncMock(side_effect=[
        {'text': 'A'}, {'text': 'B'}, {'text': 'gaps'}, {'text': 'Ready'}, {'text': 'Done'}]))
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'exhaust-synthesis', '- Check recovery', source_revision='a'*40)
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    row = state['sections'][0]['items'][0]
    assert row['planning'] == 'blocked'
    assert len(engine.models.plan_chat.await_args_list) == 5
    assert row['planning_stages']['synthesis_repair_rejection']['reason'] == 'invalid_planning_contract'
    assert engine.missions.list() == [] and engine.tasks.list() == []


def test_many_cloud_connections_cannot_push_local_fallback_out_of_budget(profiles):
    profiles.append({**profiles[-1], 'id': 'cloud_c', 'endpoint': 'https://c.example'})
    async def respond(prompt, profile, hosting):
        if hosting == 'cloud':
            raise TimeoutError()
        return {'text': '{}'}
    models = SimpleNamespace(plan_chat=AsyncMock(side_effect=respond))
    asyncio.run(deliberate(models, 'outcome', 'cloud', AsyncMock()))
    assert [c.kwargs['profile'] for c in models.plan_chat.await_args_list][:3] == ['cloud_a', 'cloud_b', 'local']


def test_available_local_model_is_preferred_to_busy_local_model(profiles, monkeypatch):
    from backend.models.capacity import capacity
    profiles.append({**profiles[0], 'id': 'local_b', 'endpoint': 'http://127.0.0.1:11435'})
    monkeypatch.setattr(capacity, 'status', lambda rows: [
        {'profile': p['id'], 'active': int(p['id'] == 'local'), 'max_parallel': 1} for p in rows])
    models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': '{}'}))
    asyncio.run(deliberate(models, 'outcome', 'local', AsyncMock()))
    assert all(c.kwargs['profile'] == 'local_b' for c in models.plan_chat.await_args_list)


def test_owner_selected_local_model_is_not_starved_by_three_dead_profiles(profiles):
    profiles[:] = [{**profiles[0], 'id': 'a-dead'}, {**profiles[0], 'id': 'b-dead'},
                  {**profiles[0], 'id': 'c-dead'}, {**profiles[0], 'id': 'z-working'}]
    models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': '{}'}))
    asyncio.run(deliberate(models, 'outcome', 'local', AsyncMock(), preferred_profile='z-working'))
    assert all(c.kwargs['profile'] == 'z-working' for c in models.plan_chat.await_args_list)


def test_preferred_cloud_profile_cannot_override_local_only_routing(profiles):
    models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': '{}'}))
    asyncio.run(deliberate(models, 'outcome', 'local', AsyncMock(), preferred_profile='cloud_a'))
    assert all(c.kwargs['profile'] == 'local' for c in models.plan_chat.await_args_list)


@pytest.mark.parametrize('configured,expected', [(600,600), (120,120), (3600,600), (1,15)])
def test_slow_model_uses_its_bounded_configured_budget(profiles,monkeypatch,configured,expected):
    profiles[0]['timeout_seconds'] = configured
    budgets=[]
    async def wait(awaitable,timeout):
        budgets.append(timeout)
        return await awaitable
    monkeypatch.setattr('backend.models.planner_routing.asyncio.wait_for', wait)
    models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text':'{}'}))
    asyncio.run(deliberate(models,'outcome','local',AsyncMock()))
    assert budgets == [expected]*4
