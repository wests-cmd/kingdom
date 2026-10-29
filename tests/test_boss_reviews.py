"""Boss observes real process receipts; no generated success or remote worker."""
import asyncio
from pathlib import Path
import pytest
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


def test_owner_api_cannot_serialize_release_authority_as_a_receipt_review(runtime, monkeypatch):
    import pytest
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.exceptions import ResponseValidationError
    from fastapi.testclient import TestClient
    from backend.security.http_auth import require_owner
    from backend.runtime import boss_review_api as api
    _, _, _, programme, boss = setup(runtime)
    review = boss.review(programme['id'])
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[require_owner] = lambda: True
    monkeypatch.setattr(api, 'service', lambda: SimpleNamespace(list=lambda: [{**review, 'release_allowed': True}]))
    with pytest.raises(ResponseValidationError):
        TestClient(app).get('/boss-reviews')


def external_failure(runtime, monkeypatch):
    """Real native ledger/signature gate; only provider/OS trust plumbing is a fixture.

    This signed unit-test fixture is not evidence of an external test execution.
    """
    import base64
    import hashlib
    import io
    import json
    import time
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from backend.runtime.patch_acceptance import canonical
    import backend.runtime.patch_acceptance as acceptance
    import test_programme_jules_placement as placement

    engine, backlog, programmes, state = placement.setup(runtime)
    state = programmes.configure_jules_placement(state['id'],
        {**placement.SCOPE, 'max_repair_budget': 0}, state['revision'])
    state = programmes.approve(state['id'], 's1-t1', state['revision'])
    backlog.settings(True, backlog.snapshot()['revision'])
    job, = engine.jules.list_jobs()

    class ProviderReply:
        def __init__(self, data):
            self.data = data

        def open(self, *args, **kwargs):
            return io.BytesIO(json.dumps(self.data).encode())

    engine.jules.submit_job(job['id'], opener=ProviderReply({'name': 'sessions/boss-failure'}))
    engine.jules.poll_job(job['id'], opener=ProviderReply({'name': 'sessions/boss-failure', 'state': 'COMPLETED'}))
    patch = 'diff --git a/example.py b/example.py\n'
    job = engine.jules.fetch_candidate(job['id'], opener=ProviderReply({'activities': [
        {'createTime': '2026-10-28', 'artifacts': [{'changeSet': {
            'source': job['source'], 'gitPatch': {'baseCommitId': job['revision'], 'unidiffPatch': patch}}}]}]}))
    backlog.tick()
    row = programmes.get(state['id'])['sections'][0]['items'][0]
    key = Ed25519PrivateKey.generate()
    registry = {'boss-fixture-reviewer': dict(enabled=True, projects=['kingdom'],
        sources=[job['source']], contracts=['b'*64], public_key=base64.b64encode(
            key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())}
    monkeypatch.setattr(acceptance, 'reviewer_registry', lambda: registry)
    now = time.time()
    binding = dict(job_id=job['id'], project='kingdom', backlog_id=row['work_id'],
        mission_id=row['mission_id'], mission_version=row['mission_version'], step_id='review',
        source=job['source'], base_revision=job['revision'], patch_sha256=hashlib.sha256(patch.encode()).hexdigest(),
        contract_sha256='b'*64)
    payload = dict(format='kingdom.patch-test.v2', receipt_id='boss-failed-receipt',
        reviewer_id='boss-fixture-reviewer', issued_at=now, expires_at=now+120, binding=binding,
        execution=dict(run_id='boss-fixture-run', image_sha256='c'*64, source_archive_sha256='d'*64,
            candidate_tree_sha256='e'*64, argv=['fixed-fixture-controller'], test_count=2,
            failed_count=1, exit_code=1, network_isolated=True, read_only_source=True,
            verdict_origin='external_controller', diagnostics=[dict(test_id='owner_auth',
                error_code='assertion_failed', status_code=403)]))
    envelope = {'payload': payload, 'signature': base64.b64encode(key.sign(canonical(payload))).decode()}
    job = engine.jules.verify_job_failure(job['id'], {'attestation': envelope})
    assert job['phase'] == 'review_required' and not job['accepted']
    return engine, backlog, programmes, state, BossReviews(backlog.db, programmes, backlog, engine), job, payload, registry, key


def test_native_failed_patch_keeps_consumed_exact_binding_and_bounded_diagnostics(runtime, monkeypatch):
    engine, backlog, programmes, state, boss, job, payload, _, _ = external_failure(runtime, monkeypatch)
    result = boss.review(state['id'])
    failed = result['rows'][0]['failed_acceptance']
    assert failed is not None and failed['state'] == 'external_test_failed'
    assert failed['tests_passed'] is False
    assert failed['binding'] == payload['binding']
    assert failed['job_id'] == job['id'] and failed['receipt_id'] == 'boss-failed-receipt'
    assert failed['execution']['diagnostics'] == [{'test_id': 'owner_auth', 'error_code': 'assertion_failed', 'status_code': 403}]
    assert 'argv' not in failed['execution']  # No candidate output/commands copied to planning notes.
    assert result['status'] == 'needs_repair_plan' and result['release_allowed'] is False
    notes = [r for r in backlog.list('kingdom') if r['intent'].get('task_type') == 'repair']
    assert len(notes) == 1 and not notes[0]['enabled'] and notes[0]['intent']['mission_id'] is None
    boss.review(state['id'])
    assert len([r for r in backlog.list('kingdom') if r['intent'].get('task_type') == 'repair']) == 1
    assert len(engine.jules.list_jobs()) == 1 and engine.tasks.list() == []


def test_new_verdict_for_same_failed_patch_updates_review_without_rewriting_reserved_note(runtime, monkeypatch):
    import base64
    import copy
    from backend.runtime.patch_acceptance import canonical
    engine, backlog, _, state, boss, job, payload, _, key = external_failure(runtime, monkeypatch)
    first = boss.review(state['id'])
    note, = [r for r in backlog.list('kingdom') if r['intent'].get('task_type') == 'repair']
    new_payload = copy.deepcopy(payload)
    new_payload['receipt_id'] = 'boss-new-failed-receipt'
    new_payload['execution']['diagnostics'][0]['test_id'] = 'another_failure'
    envelope = {'payload': new_payload, 'signature': base64.b64encode(key.sign(canonical(new_payload))).decode()}
    engine.jules.verify_job_failure(job['id'], {'attestation': envelope})
    result = boss.review(state['id'])
    assert result['rows'][0]['failed_acceptance']['receipt_id'] == 'boss-new-failed-receipt'
    assert result['repair_bindings'] == first['repair_bindings'] and result['release_allowed'] is False
    current, = [r for r in backlog.list('kingdom') if r['intent'].get('task_type') == 'repair']
    assert current == note and not current['enabled']
    assert engine.tasks.list() == []


@pytest.mark.parametrize('fault', ['patch_changed', 'receipt_not_consumed', 'reviewer_revoked', 'receipt_expired', 'mission_cancelled'])
def test_native_failure_feedback_rechecks_current_exact_patch_receipt_and_authority(runtime, monkeypatch, fault):
    engine, backlog, _, _, _, job, payload, registry, _ = external_failure(runtime, monkeypatch)
    if fault == 'patch_changed':
        # Inject storage damage; observe rejection through the public adapter seam.
        with backlog.db.get_connection() as conn:
            conn.execute('UPDATE jules_candidate_patches SET patch=? WHERE job_id=?', ('changed bytes', job['id']))
            conn.commit()
    elif fault == 'receipt_not_consumed':
        with backlog.db.get_connection() as conn:
            conn.execute('DELETE FROM jules_failed_receipts WHERE receipt_id=?', (payload['receipt_id'],))
            conn.commit()
    elif fault == 'reviewer_revoked':
        registry[payload['reviewer_id']]['enabled'] = False
    elif fault == 'receipt_expired':
        monkeypatch.setattr(engine.jules, 'clock', lambda: payload['expires_at'] + 1)
    else:
        engine.missions.cancel(payload['binding']['mission_id'])
    with pytest.raises(ValueError):
        engine.jules.failure_feedback(job['id'])
    assert not engine.jules.get_job(job['id'])['accepted']
    assert engine.tasks.list() == []
