import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from backend.runtime.work_programmes import WorkProgrammes
from backend.runtime.consultation_coordinator import ConsultationCoordinator
from test_project_test_missions import runtime, plan, execute


def setup(runtime, ready=True):
    engine, backlog, _ = runtime
    engine.models = SimpleNamespace(plan_chat=AsyncMock(side_effect=TimeoutError))
    programmes = WorkProgrammes(backlog.db, engine, backlog)
    state = programmes.create('kingdom', 'help-flow', 'Run reviewed suite', source_revision='a'*40,
                              planner_mode='configured_chat')
    state = asyncio.run(programmes.plan_next(state['id'], state['revision']))
    provider = SimpleNamespace(status=lambda: {'state': 'ready' if ready else 'sign_in_required'},
        advise=AsyncMock(return_value={'text': json.dumps({'plan': plan().model_dump(), 'acceptance_step': 'suite'})}))
    coordinator = ConsultationCoordinator(backlog.db, engine, programmes, provider)
    coordinator.configure(True, 8, 1)
    return engine, backlog, programmes, state, provider, coordinator


def test_retained_help_requires_sign_in_and_never_invents_a_reply(runtime):
    engine, _, programmes, state, provider, coordinator = setup(runtime, ready=False)
    row = asyncio.run(coordinator.request_programme(state['id'], 's1-t1'))
    asyncio.run(coordinator.tick())
    assert coordinator.store.get(row['id'])['status'] == 'queued'
    provider.advise.assert_not_called()
    assert engine.missions.list() == [] and engine.tasks.list() == []


def test_cancel_during_provider_refresh_prevents_question_delivery(runtime):
    _, _, programmes, state, provider, coordinator = setup(runtime)
    row = asyncio.run(coordinator.request_programme(state['id'], 's1-t1'))
    delivered = []

    async def refreshing_provider(prompt, *, authorization_check):
        # This is the provider's post-refresh boundary, before its HTTP POST.
        coordinator.store.cancel(row['id'])
        if await authorization_check():
            delivered.append(prompt)
        from backend.models.chatgpt_plan import ChatGPTPlanError
        raise ChatGPTPlanError('request_authorization_changed', outcome_unknown=False)

    provider.advise.side_effect = refreshing_provider
    asyncio.run(coordinator.tick())
    assert delivered == []
    assert coordinator.store.get(row['id'])['status'] == 'cancelled'
    assert programmes.get(state['id'])['sections'][0]['items'][0]['planning'] == state['sections'][0]['items'][0]['planning']


def test_owner_clarification_before_delivery_prevents_cloud_send(runtime):
    engine, _, programmes, state, provider, coordinator = setup(runtime)
    engine.models.plan_chat.side_effect = None
    engine.models.plan_chat.return_value = {'text': '{"question":"Which suite?"}'}
    state = programmes.retry_planning(state['id'], 's1-t1', state['revision'])
    state = asyncio.run(programmes.plan_next(state['id'], state['revision']))
    request = asyncio.run(coordinator.request_programme(state['id'], 's1-t1'))
    programmes.answer(state['id'], 's1-t1', 'Use section tests', state['revision'])
    asyncio.run(coordinator.tick())
    provider.advise.assert_not_called()
    assert coordinator.store.get(request['id'])['status'] == 'failed'


def test_changed_worker_grants_in_prompt_prevent_stale_cloud_send(runtime):
    engine, _, programmes, state, provider, coordinator = setup(runtime)
    grants = []
    engine.swarm = SimpleNamespace(registry=SimpleNamespace(_knights={'worker': object()}))
    engine.security = SimpleNamespace(nodes=SimpleNamespace(get_node_capabilities=lambda _: grants))
    request = asyncio.run(coordinator.request_programme(state['id'], 's1-t1'))
    grants.append('process.execute')
    fresh = asyncio.run(programmes.planning_help_request(state['id'], 's1-t1'))
    assert fresh['context_revision'] == request['context_revision']
    assert fresh['question'] != request['question']
    asyncio.run(coordinator.tick())
    provider.advise.assert_not_called()
    assert coordinator.store.get(request['id'])['status'] == 'failed'


def test_automatic_questions_follow_pause_but_explicit_owner_requests_do_not(runtime):
    _, _, programmes, state, provider, coordinator = setup(runtime)
    automatic = asyncio.run(coordinator.request_programme(state['id'], 's1-t1', automatic=True))
    asyncio.run(coordinator.tick())
    provider.advise.assert_not_called()
    assert coordinator.store.get(automatic['id'])['status'] == 'queued'
    assert coordinator.store.get(automatic['id'])['attempts'] == 0


@pytest.mark.parametrize('retained', [0, 100])
def test_answer_then_real_acceptance_produces_only_selected_training_data(runtime, retained):
    engine, backlog, programmes, state, provider, coordinator = setup(runtime)
    for i in range(retained):
        old = coordinator.store.request('kingdom', 'old-'+str(i), 'old-source', 'planning', 'Old question')
        coordinator.store.cancel(old['id'])
    row = asyncio.run(coordinator.request_programme(state['id'], 's1-t1'))
    asyncio.run(coordinator.tick())
    answer = coordinator.store.get(row['id'])
    assert answer['status'] == 'answered' and answer['authority'] == 'untrusted_advice'
    state = programmes.snapshot(state['id'])
    assert state['sections'][0]['items'][0]['planning'] == 'needs_review'
    assert engine.missions.list() == []
    with pytest.raises(PermissionError):
        coordinator.store.record_verification(row['id'], 'fabricated')
    state = programmes.approve(state['id'], 's1-t1', state['revision'])
    item = state['sections'][0]['items'][0]
    backlog.settings(True, backlog.snapshot()['revision'])
    backlog.tick(); execute(engine); backlog.tick()
    evidence_id = f"{item['mission_id']}:{item['mission_version']}:{item['acceptance_step']}"
    asyncio.run(coordinator.tick())
    assert coordinator.store.get(row['id'])['verification']['evidence_id'] == evidence_id
    assert coordinator.store.export_training(project='kingdom') == ''
    coordinator.store.select_for_training(row['id'], True)
    exported = json.loads(coordinator.store.export_training(project='kingdom'))
    assert exported['provenance']['question_id'] == row['id']
    assert exported['provenance']['authority'] == 'training_candidate_only'


def test_unknown_provider_outcome_is_held_after_restart_not_recalled(runtime):
    engine, backlog, programmes, state, provider, coordinator = setup(runtime)
    provider.advise.side_effect = TimeoutError('private token=secret')
    row = asyncio.run(coordinator.request_programme(state['id'], 's1-t1'))
    asyncio.run(coordinator.tick())
    assert coordinator.store.get(row['id'])['status'] == 'outcome_unknown'
    restored = ConsultationCoordinator(backlog.db, engine, programmes, provider)
    restored.store.recover_startup(); asyncio.run(restored.tick())
    assert provider.advise.call_count == 1
    assert 'secret' not in str(restored.status()['requests'])


def test_new_owner_routes_deny_before_service_initialization(monkeypatch):
    from backend.runtime import consultation_api
    from backend.models import chatgpt_plan_api
    from backend.security.http_auth import require_owner
    app = FastAPI(); app.include_router(consultation_api.router); app.include_router(chatgpt_plan_api.router)
    def denied(): raise HTTPException(403)
    app.dependency_overrides[require_owner] = denied
    calls = []
    monkeypatch.setattr(consultation_api, 'service', lambda: calls.append('bad'))
    monkeypatch.setattr(chatgpt_plan_api, 'service', lambda: calls.append('bad'))
    client = TestClient(app)
    for path in ['/assistance', '/chatgpt-plan', '/chatgpt-plan/models', '/assistance/training/kingdom']:
        assert client.get(path).status_code == 403
    for path in ['/chatgpt-plan/begin', '/assistance/programmes/a/items/b', '/assistance/requests/a/verify']:
        assert client.post(path, json={}).status_code == 403
    assert calls == []


def test_real_failed_execution_gets_error_advice_without_replay_or_training(runtime):
    import sys
    engine, backlog, programmes, state, provider, coordinator = setup(runtime)
    provider.advise.return_value = {'text': json.dumps({'plan': plan(
        [sys.executable, '-m', 'unittest', 'missing_test_module']).model_dump(), 'acceptance_step': 'suite'})}
    asyncio.run(coordinator.request_programme(state['id'], 's1-t1'))
    asyncio.run(coordinator.tick())
    state = programmes.snapshot(state['id'])
    programmes.approve(state['id'], 's1-t1', state['revision'])
    backlog.settings(True, backlog.snapshot()['revision']); backlog.tick(); execute(engine); backlog.tick()
    count = len(engine.tasks.list())
    request = asyncio.run(coordinator.request_programme(state['id'], 's1-t1'))
    assert request['kind'] == 'error' and request['context']['error_code'] == 'review_required'
    asyncio.run(coordinator.tick())
    assert coordinator.store.get(request['id'])['status'] == 'answered'
    assert coordinator.apply(request['id'])['state'] == 'repair_review_required'
    assert len(engine.tasks.list()) == count
    assert coordinator.store.export_training(project='kingdom') == ''
