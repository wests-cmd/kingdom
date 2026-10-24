import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from test_project_test_missions import runtime, plan
from backend.runtime.work_programmes import WorkProgrammes


def test_question_survives_restart_and_answer_replans_without_execution(runtime):
    engine, backlog, _ = runtime
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'question', '- Check recovery', source_revision='a'*40, planner_mode='configured_chat')
    engine.models = SimpleNamespace(plan_chat=AsyncMock(side_effect=[
        {'text': json.dumps({'question': 'Which recovery behavior should be checked?'})},
        {'text': json.dumps({'plan': plan().model_dump(), 'acceptance_step': 'suite'})}]))
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    assert state['sections'][0]['items'][0]['planning'] == 'awaiting_answer'
    service = WorkProgrammes(backlog.db, engine, backlog)
    asyncio.run(service.plan_next(state['id'], state['revision']))
    assert engine.models.plan_chat.await_count == 1
    with pytest.raises(ValueError):
        service.approve(state['id'], 's1-t1', state['revision'])
    state = service.answer(state['id'], 's1-t1', 'Retain queued conversations after restart.', state['revision'])
    with pytest.raises(ValueError):
        service.answer(state['id'], 's1-t1', 'Duplicate answer', state['revision'])
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    assert 'Retain queued conversations' in engine.models.plan_chat.await_args.args[0]
    assert state['sections'][0]['items'][0]['planning'] == 'needs_review'
    assert engine.missions.list() == [] and engine.tasks.list() == []


def test_chatgpt_handoff_never_calls_local_planner_and_preserves_validation(runtime):
    engine, backlog, _ = runtime
    service = WorkProgrammes(backlog.db, engine, backlog)
    engine.models = SimpleNamespace(plan_chat=AsyncMock(side_effect=AssertionError('No model fallback')))
    state = service.create('kingdom', 'external', '- Check recovery', source_revision='a'*40,
                           planner_mode='chatgpt')
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    row = state['sections'][0]['items'][0]
    assert row['planning'] == 'awaiting_chatgpt' and 'OWNER OUTCOME DATA' in row['planning_request']
    service = WorkProgrammes(backlog.db, engine, backlog)
    service.recover_startup()
    assert service.get(state['id'])['sections'][0]['items'][0]['planning'] == 'awaiting_chatgpt'
    assert asyncio.run(service.plan_next(state['id'], state['revision']))['revision'] == state['revision']
    with pytest.raises(ValueError):
        service.chatgpt_response(state['id'], row['key'], '{"approve":true}', state['revision'])
    assert service.get(state['id'])['revision'] == state['revision']
    state = service.chatgpt_response(state['id'], row['key'], '{"question":"Which target?"}', state['revision'])
    state = service.answer(state['id'], row['key'], 'Queued conversations', state['revision'])
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    assert 'Queued conversations' in state['sections'][0]['items'][0]['planning_request']
    reply = json.dumps({'plan': plan().model_dump(), 'acceptance_step': 'suite'})
    with pytest.raises(ValueError):
        service.chatgpt_response(state['id'], row['key'], reply, state['revision']-1)
    state = service.chatgpt_response(state['id'], row['key'], reply, state['revision'])
    assert state['sections'][0]['items'][0]['planning'] == 'needs_review'
    with pytest.raises(ValueError):
        service.chatgpt_response(state['id'], row['key'], reply, state['revision'])
    engine.models.plan_chat.assert_not_awaited()
    assert engine.missions.list() == [] and engine.tasks.list() == []


def test_planner_mode_is_part_of_programme_identity(runtime):
    engine, backlog, _ = runtime
    service = WorkProgrammes(backlog.db, engine, backlog)
    service.create('kingdom', 'mode', '- Check recovery', planner_mode='chatgpt')
    with pytest.raises(ValueError, match='another list'):
        service.create('kingdom', 'mode', '- Check recovery')


def test_repeated_questions_are_bounded_and_stale_answers_rejected(runtime):
    engine, backlog, _ = runtime
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'bounded', '- Check recovery', planner_mode='configured_chat')
    engine.models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': '{"question":"Which target?"}'}))
    for _ in range(3):
        state = asyncio.run(service.plan_next(state['id'], state['revision']))
        with pytest.raises(ValueError):
            service.answer(state['id'], 's1-t1', 'target', state['revision']-1)
        state = service.answer(state['id'], 's1-t1', 'target', state['revision'])
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    assert state['sections'][0]['items'][0]['planning'] == 'blocked'
    assert len(state['sections'][0]['items'][0]['clarifications']) == 3
    assert engine.missions.list() == []


def test_chat_planner_uses_chat_messages_and_rejects_truncated_output():
    from backend.models.service import ModelService
    service = ModelService()
    service.chat = AsyncMock(return_value={'kingdom_profile': 'chat', 'choices': [
        {'finish_reason': 'stop', 'message': {'content': '{"question":"Which target?"}'}}]})
    result = asyncio.run(service.plan_chat('outcome', 'chat'))
    assert result['profile'] == 'chat'
    assert service.chat.await_args.kwargs == {'planner': True}
    assert service.chat.await_args.args[1]['messages'][0]['role'] == 'system'
    service.chat.return_value['choices'][0]['finish_reason'] = 'length'
    with pytest.raises(RuntimeError):
        asyncio.run(service.plan_chat('outcome', 'chat'))


@pytest.mark.parametrize('selection', ['coding', 'pool:chat', 'auto'])
def test_codex_is_rejected_before_chat_transport(monkeypatch, selection):
    from backend.models.service import ModelService
    from backend.models.profiles import ModelProfiles
    from backend.models.capacity import capacity
    profile = {'id': 'coding', 'model': 'gpt-codex', 'pool_group': 'chat'}
    monkeypatch.setattr(ModelProfiles, 'list', lambda self: [profile])
    monkeypatch.setattr(ModelProfiles, 'get', lambda self, ident, **kwargs: profile)
    monkeypatch.setattr('backend.models.selection.eligible_profiles', AsyncMock(return_value=[profile]))
    def forbidden(*args, **kwargs):
        pytest.fail('Codex must not acquire a planner connection')
    monkeypatch.setattr(capacity, 'acquire', forbidden)
    with pytest.raises(ValueError, match='non-Codex'):
        asyncio.run(ModelService().plan_chat('Plan this', selection))


def test_model_changed_during_reservation_cannot_become_codex(monkeypatch):
    from contextlib import asynccontextmanager
    from backend.models.service import ModelService
    from backend.models.profiles import ModelProfiles
    from backend.models.capacity import capacity
    profile = {'id': 'chat', 'model': 'chat-model'}
    monkeypatch.setattr(ModelProfiles, 'list', lambda self: [profile])
    monkeypatch.setattr(ModelProfiles, 'get', lambda self, ident, **kwargs:
                        {**profile, 'model': 'codex'} if kwargs.get('credential') else profile)
    @asynccontextmanager
    async def reserve(*args, **kwargs):
        yield profile
    monkeypatch.setattr(capacity, 'acquire', reserve)
    with pytest.raises(ValueError, match='changed'):
        asyncio.run(ModelService().plan_chat('Plan this', 'chat'))
