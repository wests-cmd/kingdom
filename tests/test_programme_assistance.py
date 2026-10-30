import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from backend.runtime.work_programmes import WorkProgrammes
from test_project_test_missions import runtime, plan


def test_help_preserves_failed_attempts_and_cannot_approve(runtime):
    engine, backlog, _ = runtime
    engine.models = SimpleNamespace(plan_chat=AsyncMock(side_effect=TimeoutError))
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'help', 'Run the reviewed suite', source_revision='a'*40,
                           planner_mode='configured_chat')
    for _ in range(3):
        if state['sections'][0]['items'][0]['planning'] == 'blocked':
            state = service.retry_planning(state['id'], 's1-t1', state['revision'])
        state = asyncio.run(service.plan_next(state['id'], state['revision']))
    before = state['sections'][0]['items'][0]['planning_attempts']
    request = asyncio.run(service.planning_help_request(state['id'], 's1-t1'))
    assert request['parent_work_id'] == state['sections'][0]['items'][0]['work_id']
    assert 'No action is authorized' in request['question']
    response = json.dumps({'plan': plan().model_dump(), 'acceptance_step': 'suite'})
    state = service.apply_help_response(state['id'], 's1-t1', response,
                                       request['context_revision'], 'question-a')
    row = state['sections'][0]['items'][0]
    assert before == row['planning_attempts'] == 3
    assert row['planning'] == 'needs_review' and row['mission_id'] is None
    assert engine.missions.list() == [] and engine.tasks.list() == []


def test_advice_for_an_old_question_cannot_replace_owner_clarification(runtime):
    engine, backlog, _ = runtime
    engine.models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': '{"question":"Which suite?"}'}))
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'clarify', 'Run suite', source_revision='a'*40,
                           planner_mode='configured_chat')
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    request = asyncio.run(service.planning_help_request(state['id'], 's1-t1'))
    state = service.answer(state['id'], 's1-t1', 'Use the section suite', state['revision'])
    with pytest.raises(ValueError):
        service.apply_help_response(state['id'], 's1-t1', '{"blocked_reasons":["missing"]}',
                                    request['context_revision'], 'question-a')


def test_independent_adopted_work_can_plan_while_another_item_waits_for_answer(runtime):
    engine, backlog, _ = runtime
    engine.models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': '{"question":"Which suite?"}'}))
    service = WorkProgrammes(backlog.db, engine, backlog)
    notes = [backlog.register('kingdom', 'independent-'+str(i), title='Outcome'+str(i)) for i in range(2)]
    state = service.adopt('kingdom', 'independent-help',
        [{'work_id': n['id'], 'expected_revision': n['revision']} for n in notes],
        title='Independent outcomes', source_revision='a'*40, planner_mode='configured_chat')
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    assert [r['planning'] for r in state['sections'][0]['items']] == ['awaiting_answer', 'awaiting_answer']
