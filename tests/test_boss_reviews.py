"""Boss observes real process receipts; no generated success or remote worker."""
import asyncio
from pathlib import Path
from backend.runtime.boss_reviews import BossReviews
from backend.runtime.work_programmes import WorkProgrammes
from test_project_test_missions import runtime, plan, execute


def setup(runtime, text='Section:\n- Verify component'):
    engine, backlog, _ = runtime
    programmes = WorkProgrammes(backlog.db, engine, backlog)
    programme = programmes.create('kingdom', 'boss-test', text, source_revision='a'*40)
    boss = BossReviews(backlog.db, programmes, backlog, engine)
    return engine, backlog, programmes, programme, boss


def bind(programmes, programme, integration=False, index=0):
    state = programmes.get(programme['id'])
    row = state['sections'][0]['integration' if integration else 'items']
    row = row if integration else row[index]
    command = plan()
    if integration:
        # Distinct fixed integration invocation, still the same real suite.
        command.steps[0].argv += ['-v']
    row.update(planning='needs_review', proposal=command.model_dump(), acceptance_step='suite')
    programmes._save(state, state['revision'])
    return programmes.approve(state['id'], row['key'], state['revision'])


def advance(engine, backlog):
    backlog.settings(True, backlog.snapshot()['revision'])
    backlog.tick()
    task = execute(engine)
    backlog.tick()
    return task


def test_real_local_suites_never_become_independent_environment_or_release(runtime):
    engine, backlog, programmes, programme, boss = setup(runtime)
    first = boss.review(programme['id'])
    assert first['status'] == 'needs_plan_or_execution'
    assert first == boss.review(programme['id'])  # No revision/event churn.
    programme = bind(programmes, programme)
    component = advance(engine, backlog)
    programme = bind(programmes, programme, integration=True)
    integration = advance(engine, backlog)
    result = boss.review(programme['id'])
    assert result['status'] == 'needs_independent_test'
    assert result['independent_reviewer'] is None
    assert not result['release_allowed']
    assert {r['evidence']['task_id'] for r in result['rows']} == {component['id'], integration['id']}
    assert len(engine.tasks.list()) == 2  # Boss neither submits nor repeats work.
    assert BossReviews(backlog.db, programmes, backlog, engine).review(programme['id']) == result


def test_receipt_loss_invalidates_boss_and_creates_only_one_disabled_repair_note(runtime):
    engine, backlog, programmes, programme, boss = setup(runtime)
    bind(programmes, programme)
    task = advance(engine, backlog)
    boss.review(programme['id'])
    Path(task['result']['results'][0]['outcome']['artifact']).unlink()
    result = boss.review(programme['id'])
    assert result['status'] == 'needs_repair_plan'
    notes = [r for r in backlog.list('kingdom') if r['intent'].get('task_type') == 'repair']
    assert len(notes) == 1 and not notes[0]['enabled']
    assert notes[0]['intent']['mission_id'] is None
    for _ in range(3):
        boss.review(programme['id'])
    assert len([r for r in backlog.list('kingdom') if r['intent'].get('task_type') == 'repair']) == 1
    assert len(engine.tasks.list()) == 1
    assert not result['release_allowed']


def test_browser_independent_review_tick_persists_current_plan_responsibility(runtime):
    engine, backlog, programmes, programme, boss = setup(runtime)
    bind(programmes, programme)
    asyncio.run(boss.tick())
    row = boss.list()[0]['rows'][0]
    assert row['planning_model_profile'] == 'auto'
    assert row['tools'] == ['project_test']
    assert row['requested_computers'] == []
    assert row['evidence'] is None
    assert len(engine.tasks.list()) == 0


def test_repair_notes_are_bounded_across_real_failed_receipts_and_restart(runtime):
    engine, backlog, programmes, programme, boss = setup(runtime, 'Section:\n- One\n- Two\n- Three\n- Four')
    tasks = []
    for index in range(4):
        bind(programmes, programme, index=index)
        tasks.append(advance(engine, backlog))
    for task in tasks:
        Path(task['result']['results'][0]['outcome']['artifact']).unlink()
    result = boss.review(programme['id'])
    assert result['status'] == 'repair_budget_exhausted'
    assert len(result['repair_bindings']) == 3
    assert len([r for r in backlog.list('kingdom') if r['intent'].get('task_type') == 'repair']) == 3
    fresh = BossReviews(backlog.db, programmes, backlog, engine)
    fresh.recover_startup()
    fresh.review(programme['id'])
    assert len(backlog.list('kingdom')) == 8  # Four components, integration, three notes.
    assert len(engine.tasks.list()) == 4


def test_crash_after_reservation_reconciles_disabled_note_without_reexecution(runtime, monkeypatch):
    import pytest
    engine, backlog, programmes, programme, boss = setup(runtime)
    bind(programmes, programme)
    task = advance(engine, backlog)
    Path(task['result']['results'][0]['outcome']['artifact']).unlink()
    register = backlog.register

    def unavailable(*args, **kwargs):
        raise OSError('Simulated interrupted note persistence')

    monkeypatch.setattr(backlog, 'register', unavailable)
    with pytest.raises(OSError):
        boss.review(programme['id'])
    assert len(boss.list()[0]['repair_bindings']) == 1
    monkeypatch.setattr(backlog, 'register', register)
    BossReviews(backlog.db, programmes, backlog, engine).review(programme['id'])
    assert len([r for r in backlog.list('kingdom') if r['intent'].get('task_type') == 'repair']) == 1
    assert len(engine.tasks.list()) == 1


def test_owner_boundary_blocks_initialization_and_lists_retained_review(runtime, monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from backend.security.http_auth import require_owner
    from backend.runtime import boss_review_api as api
    _, _, _, programme, boss = setup(runtime)
    app = FastAPI()
    app.include_router(api.router)
    calls = []
    monkeypatch.setattr(api, 'service', lambda: calls.append('must not initialize'))

    def denied():
        raise HTTPException(403, 'Owner required')

    app.dependency_overrides[require_owner] = denied
    client = TestClient(app)
    assert client.get('/boss-reviews').status_code == 403
    assert not calls
    monkeypatch.setattr(api, 'service', lambda: boss)
    app.dependency_overrides[require_owner] = lambda: True
    boss.review(programme['id'])
    assert client.get('/boss-reviews').json()[0]['controller'] == 'Boss'
