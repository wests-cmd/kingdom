from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from backend.runtime import work_programme_api as api
from backend.security.http_auth import require_owner
from test_project_test_missions import runtime, plan, execute


def test_all_programme_routes_require_owner_and_validation_hides_private_input(monkeypatch):
    app = FastAPI()
    app.include_router(api.router)
    calls = []

    def denied():
        raise HTTPException(403, 'Owner access required')

    app.dependency_overrides[require_owner] = denied
    monkeypatch.setattr(api, 'service', lambda: calls.append('must not initialize'))
    client = TestClient(app)
    for path, method in [('/work-programmes','get'),('/work-programmes','post'),
            ('/work-programmes/a/settings','post'),('/work-programmes/a/plan-next','post'),
            ('/work-programmes/a/items/s1-t1/approve','post'),
            ('/work-programmes/a/items/s1-t1/answer','post'),
            ('/work-programmes/a/items/s1-t1/chatgpt-response','post'),
            ('/work-programmes/a/items/s1-t1/retry-planning','post')]:
        response = getattr(client, method)(path, **({'json':{}} if method=='post' else {}))
        assert response.status_code == 403
    assert calls == []


def test_strict_request_has_no_implicit_execution_or_extra_grants():
    import pytest
    from pydantic import ValidationError
    for extra in [{'enabled':True}, {'grants':['process.execute']}, {'approve':True}]:
        with pytest.raises(ValidationError):
            api.NewProgramme(project='kingdom', idempotency_key='sample', text='Check recovery', **extra)
    with pytest.raises(ValidationError):
        api.Settings(enabled='true', expected_revision=1)


def test_owner_can_answer_saved_question_once_over_http(runtime, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from backend.runtime.work_programmes import WorkProgrammes
    engine, backlog, _ = runtime
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'http-question', '- Check recovery')
    engine.models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text': '{"question":"Which target?"}'}))
    state = asyncio.run(service.plan_next(state['id'], state['revision']))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[require_owner] = lambda: True
    monkeypatch.setattr(api, 'service', lambda: service)
    client = TestClient(app)
    endpoint = f"/work-programmes/{state['id']}/items/s1-t1/answer"
    body = {'answer': 'Queued conversations', 'expected_revision': state['revision']}
    assert client.post(endpoint, json={**body, 'approve': True}).status_code == 422
    assert client.post(endpoint, json={**body, 'answer': '  '}).status_code == 409
    saved = client.post(endpoint, json=body)
    assert saved.status_code == 200
    assert saved.json()['sections'][0]['items'][0]['planning'] == 'unplanned'
    assert client.post(endpoint, json=body).status_code == 409
    assert engine.missions.list() == [] and engine.tasks.list() == []


def test_http_saved_list_review_and_actual_command_receipt_keep_section_gate(runtime, monkeypatch):
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from backend.runtime.work_programmes import WorkProgrammes
    engine, backlog, _ = runtime
    service = WorkProgrammes(backlog.db, engine, backlog)
    engine.models = SimpleNamespace(plan_chat=AsyncMock(return_value={'text':json.dumps({
        'plan':plan().model_dump(), 'acceptance_step':'suite'})}))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[require_owner] = lambda: True
    monkeypatch.setattr(api, 'service', lambda: service)
    client = TestClient(app)
    response = client.post('/work-programmes', json={'project':'kingdom',
        'idempotency_key':'http-proof', 'text':'Recovery:\n- Check a component',
        'source_revision':'a'*40})
    assert response.status_code == 201
    state = response.json()
    ident = state['id']
    repeated = client.post('/work-programmes', json={'project':'kingdom',
        'idempotency_key':'http-proof', 'text':'Recovery:\n- Check a component',
        'source_revision':'a'*40})
    assert repeated.json()['id'] == ident
    response = client.post(f'/work-programmes/{ident}/plan-next', json={'expected_revision':state['revision']})
    assert response.status_code == 200
    state = response.json()
    assert state['sections'][0]['items'][0]['planning'] == 'needs_review'
    assert engine.missions.list() == [] and engine.tasks.list() == []
    response = client.post(f'/work-programmes/{ident}/items/s1-t1/approve', json={'expected_revision':state['revision']})
    assert response.status_code == 200
    assert engine.tasks.list() == []  # approval does not enable global selection
    backlog.settings(True, backlog.snapshot()['revision'])
    engine.execution_policy.get()['level'] = 3
    backlog.tick()
    assert engine.tasks.list() == []
    engine.execution_policy.get()['level'] = 5
    backlog.tick()
    execute(engine)
    backlog.tick()
    saved = client.get('/work-programmes').json()[0]
    assert saved['sections'][0]['items'][0]['work_status'] == 'completed'
    assert saved['sections'][0]['integration']['planning'] == 'unplanned'
    assert saved['sections'][0]['status'] == 'unfinished'
    assert len(engine.tasks.list()) == 1
