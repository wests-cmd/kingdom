from types import SimpleNamespace
from fastapi.testclient import TestClient
from backend.main import app
from backend import recovery
from backend.storage.db import Database
from backend.storage.integration_repository import IntegrationRepository
from tests.auth_support import owner_client


class Runtime:
    def __init__(self):
        self.scheduler = SimpleNamespace(running=True)
        self.actions = []
        self.fail = False

    async def stop(self):
        self.actions.append('stop')
        self.scheduler.running = False

    async def start(self):
        self.actions.append('start')
        if self.fail:
            raise RuntimeError('private diagnostic')
        self.scheduler.running = True


def setup_recovery(tmp_path, monkeypatch):
    runtime = Runtime()
    repository = IntegrationRepository(Database(tmp_path/'recovery.sqlite3'))
    monkeypatch.setattr(recovery, 'repository', repository)
    monkeypatch.setattr(recovery, 'services', lambda: (runtime, lambda: {'status':'ready'}))
    return owner_client(app), runtime, repository


def test_owner_approval_executes_once_and_preserves_preferences(tmp_path, monkeypatch):
    client, runtime, repository = setup_recovery(tmp_path, monkeypatch)
    assert TestClient(app).get('/recovery/status').status_code == 401
    assert TestClient(app).post('/recovery/plans', json={'action':'restart_runtime'}).status_code in (401,403)
    repository.put('presentation_preferences', 'owner', {'scale':200})
    assert client.post('/recovery/plans', json={'action':'modify_policy'}).status_code == 422
    plan = client.post('/recovery/plans', json={'action':'restart_runtime'}).json()
    assert runtime.actions == []
    url = '/recovery/plans/'+plan['plan_id']+'/execute'
    assert client.post(url, json={'approved':False}).status_code == 422
    assert runtime.actions == []
    result = client.post(url, json={'approved':True})
    assert result.status_code == 200
    assert result.json()['state'] == 'verified'
    assert runtime.actions == ['stop','start']
    assert client.post(url, json={'approved':True}).status_code == 409
    assert runtime.actions == ['stop','start']
    assert repository.get('presentation_preferences','owner') == {'scale':200}


def test_expired_competing_and_failed_repairs_are_not_success(tmp_path, monkeypatch):
    client, runtime, repository = setup_recovery(tmp_path, monkeypatch)
    plan = client.post('/recovery/plans', json={'action':'restart_runtime'}).json()
    url = '/recovery/plans/'+plan['plan_id']+'/execute'
    plan['expires_at'] = 0
    repository.put('operational_repair', plan['plan_id'], plan)
    assert client.post(url, json={'approved':True}).status_code == 409
    assert runtime.actions == []
    assert client.get('/recovery/status').json()['repairs'][0]['state'] == 'expired'
    plan['expires_at'] = 10**12
    repository.put('operational_repair', plan['plan_id'], plan)
    competing = dict(plan, plan_id='other', state='running')
    repository.put('operational_repair','other',competing)
    assert client.post(url, json={'approved':True}).status_code == 409
    assert runtime.actions == []
    repository.put('operational_repair','other',dict(competing,state='failed'))
    runtime.fail = True
    result = client.post(url, json={'approved':True}).json()
    assert result['state'] == 'failed' and result['after_running'] is False
    assert 'private diagnostic' not in result['error']
    assert client.get('/recovery/status').json()['runtime_running'] is False


def test_legacy_stubs_do_not_claim_repairs():
    from backend.failure.partial_repair import PartialRepair
    from backend.failure.recovery_engine import RecoveryEngine
    assert PartialRepair().repair('runtime')['repaired'] is False
    assert RecoveryEngine().recover('failure')['recovered'] is False
