"""Actual local registration/enablement, not provider execution or acceptance."""
import copy
import pytest
from backend.runtime.work_programmes import WorkProgrammes, JulesPlacement
from backend.runtime.missions import MissionPlan
from backend.integrations.jules import JulesService
from test_project_test_missions import runtime


SCOPE = dict(enabled=True, repository='wests-cmd/kingdom', source='sources/github/wests-cmd/kingdom',
             branch='main', max_jobs=1, max_repair_budget=2, deadline_seconds=600)


def setup(runtime):
    engine, backlog, workspace = runtime
    engine.jules = JulesService(backlog.db, engine, secrets_root=workspace/'secrets')
    engine.jules.configure(enabled=True, api_key='fixture-not-a-provider-key',
        allowed_repositories=['wests-cmd/kingdom'], allowed_sources=[SCOPE['source']])
    service = WorkProgrammes(backlog.db, engine, backlog)
    state = service.create('kingdom', 'external-programme', 'Build:\n- Fix a reviewed bug', source_revision='a'*40)
    proposal = MissionPlan.model_validate(dict(title='External patch', objective='Fix bug with independent test',
        deliverables=['Candidate patch'], steps=[dict(id='review', title='Verify returned patch',
            kind='independent_review', acceptance='Exact external contract passes', independent_review=dict(
                project='kingdom', source=SCOPE['source'], base_revision='a'*40,
                contract_id='fixture-contract', contract_sha256='b'*64))]))
    row = state['sections'][0]['items'][0]
    row.update(planning='needs_review', proposal=proposal.model_dump(), acceptance_step='review')
    service._save(state, state['revision'])
    return engine, backlog, service, service.get(state['id'])


def configure(service, state):
    return service.configure_jules_placement(state['id'], SCOPE, state['revision'])


def test_disabled_default_keeps_external_slot_disabled_and_unregistered(runtime):
    engine, backlog, service, state = setup(runtime)
    result = service.approve(state['id'], 's1-t1', state['revision'])
    row = result['sections'][0]['items'][0]
    assert row['dispatch_status'] == 'awaiting_external_job_registration'
    assert not backlog.get('kingdom', row['work_id'])['enabled']
    assert engine.jules.list_jobs() == []
    assert engine.tasks.list() == []


def test_exact_owner_placement_registers_one_job_and_enables_existing_mission(runtime):
    engine, backlog, service, state = setup(runtime)
    state = configure(service, state)
    result = service.approve(state['id'], 's1-t1', state['revision'])
    row = result['sections'][0]['items'][0]
    jobs = engine.jules.list_jobs()
    assert len(jobs) == 1 and jobs[0]['id'] == row['jules_job_id']
    assert jobs[0]['phase'] == 'queued' and not jobs[0]['accepted']
    assert jobs[0]['revision'] == 'a'*40 and jobs[0]['max_repair_budget'] == 2
    assert row['planning'] == 'reviewed' and row['dispatch_status'] == 'jules_registered'
    assert backlog.get('kingdom', row['work_id'])['enabled']
    service.recover_startup()
    assert len(engine.jules.list_jobs()) == 1 and engine.tasks.list() == []
    assert service.get(state['id'])['jules_placement']['used_jobs'] == 1
    assert engine.execution_policy.get()['level'] == 5


@pytest.mark.parametrize('crash_stage', ['jules_registered_pending_enable', 'jules_registered'])
def test_crash_after_register_or_enable_recovers_without_duplicate_or_submission(runtime, monkeypatch, crash_stage):
    engine, backlog, service, state = setup(runtime)
    state = configure(service, state)
    save = service._save

    class ProcessLost(BaseException):
        pass

    def interrupted(saved, expected=None):
        if saved['sections'][0]['items'][0].get('dispatch_status') == crash_stage:
            raise ProcessLost()
        return save(saved, expected)

    monkeypatch.setattr(service, '_save', interrupted)
    with pytest.raises(ProcessLost):
        service.approve(state['id'], 's1-t1', state['revision'])
    assert len(engine.jules.list_jobs()) == 1
    fresh = WorkProgrammes(backlog.db, engine, backlog)
    fresh.recover_startup()
    row = fresh.get(state['id'])['sections'][0]['items'][0]
    assert row['planning'] == 'reviewed' and row['dispatch_status'] == 'jules_registered'
    assert backlog.get('kingdom', row['work_id'])['enabled']
    assert len(engine.jules.list_jobs()) == 1
    assert engine.jules.list_jobs()[0]['phase'] == 'queued'
    assert engine.tasks.list() == []


def test_current_policy_allowlist_budget_and_source_are_checked_before_new_mission(runtime):
    engine, backlog, service, state = setup(runtime)
    state = configure(service, state)
    before = len(engine.missions.list())
    engine.execution_policy.get()['level'] = 4
    with pytest.raises(ValueError):
        service.approve(state['id'], 's1-t1', state['revision'])
    assert len(engine.missions.list()) == before and not engine.jules.list_jobs()
    engine.execution_policy.get()['level'] = 5
    engine.jules.configure(allowed_sources=['sources/github/wests-cmd/other'])
    with pytest.raises(ValueError):
        service.approve(state['id'], 's1-t1', state['revision'])
    assert len(engine.missions.list()) == before


def test_owner_job_budget_cannot_reset_and_unrelated_source_cannot_register(runtime):
    engine, backlog, service, state = setup(runtime)
    state = configure(service, state)
    broken = service.get(state['id'])
    broken['sections'][0]['items'][0]['proposal']['steps'][0]['independent_review']['source'] = 'sources/github/wests-cmd/other'
    service._save(broken, broken['revision'])
    with pytest.raises(ValueError):
        service.approve(broken['id'], 's1-t1', broken['revision'])
    assert not engine.jules.list_jobs() and not engine.missions.list()
    saved = service.get(state['id'])
    saved['sections'][0]['items'][0]['proposal']['steps'][0]['independent_review']['source'] = SCOPE['source']
    saved['jules_placement']['used_jobs'] = 1  # Retained reservation, not execution proof.
    service._save(saved, saved['revision'])
    with pytest.raises(ValueError, match='budget'):
        service.approve(saved['id'], 's1-t1', saved['revision'])
    assert not engine.jules.list_jobs() and not engine.missions.list()


def test_recovery_respects_owner_placement_pause_and_holds_committed_job(runtime, monkeypatch):
    engine, backlog, service, state = setup(runtime)
    state = configure(service, state)
    save = service._save

    class ProcessLost(BaseException):
        pass

    def interrupted(saved, expected=None):
        if saved['sections'][0]['items'][0].get('dispatch_status') == 'jules_registered_pending_enable':
            raise ProcessLost()
        return save(saved, expected)

    monkeypatch.setattr(service, '_save', interrupted)
    with pytest.raises(ProcessLost):
        service.approve(state['id'], 's1-t1', state['revision'])
    fresh = WorkProgrammes(backlog.db, engine, backlog)
    checkpoint = fresh.get(state['id'])
    fresh.configure_jules_placement(state['id'], {**SCOPE, 'enabled': False}, checkpoint['revision'])
    fresh.recover_startup()
    row = fresh.get(state['id'])['sections'][0]['items'][0]
    assert row['planning'] == 'blocked' and row['dispatch_status'] == 'external_binding_held'
    assert not backlog.get('kingdom', row['work_id'])['enabled']
    assert len(engine.jules.list_jobs()) == 1 and engine.jules.list_jobs()[0]['phase'] == 'queued'


def test_placement_is_strict_owner_only_and_cas_guarded(runtime, monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from pydantic import ValidationError
    from backend.runtime import work_programme_api as api
    from backend.security.http_auth import require_owner
    _, _, service, state = setup(runtime)
    with pytest.raises(ValidationError):
        JulesPlacement(**{**SCOPE, 'grants': ['process.execute']})
    app = FastAPI(); app.include_router(api.router)

    def denied():
        raise HTTPException(403, 'Owner required')

    app.dependency_overrides[require_owner] = denied
    monkeypatch.setattr(api, 'service', lambda: service)
    client = TestClient(app)
    path = f"/work-programmes/{state['id']}/jules-placement"
    body = {'scope': copy.deepcopy(SCOPE), 'expected_revision': state['revision']}
    assert client.post(path, json=body).status_code == 403
    app.dependency_overrides[require_owner] = lambda: True
    assert client.post(path, json=body).status_code == 200
    assert client.post(path, json=body).status_code == 409
