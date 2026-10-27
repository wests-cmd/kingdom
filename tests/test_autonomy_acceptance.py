"""Real task/lease/RPC acceptance: stale-worker fencing and owner stop."""
import asyncio
import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import backend.api as api
from backend.cluster.task_leasing import TaskLeaseManager
from backend.runtime.tasks import TaskManager
from backend.storage.db import Database
from backend.storage.repository import TaskRepository

REMOTE = {'tool': 'text.analyze@1.0.0', 'execution_target': 'remote', 'capability': 'compute'}


def _runtime(tmp_path, monkeypatch):
    database = Database(tmp_path / 'acceptance.db')
    tasks = TaskManager(TaskRepository(database))
    leases = TaskLeaseManager(database=database)
    monkeypatch.setattr(api.engine, 'tasks', tasks)
    monkeypatch.setattr(api.engine, 'lease_manager', leases, raising=False)
    monkeypatch.setattr(api, 'task_lease_manager', leases)
    monkeypatch.setattr(api.capability_authorizer, 'is_capability_granted', lambda *a: True)
    monkeypatch.setattr('backend.cluster.node_registry.node_registry.get_node',
                        lambda ident: SimpleNamespace(node_state='CONNECTED'))
    return tasks, leases


def _submit_result(monkeypatch, sender, task_id, lease_id, token):
    monkeypatch.setattr(api.RPCSecureTransport, 'verify_and_unwrap_message', lambda *a, **kw: {
        'valid': True, 'sender_id': sender, 'msg_type': 'task_result',
        'payload': {'task_id': task_id, 'executed_by': sender, 'lease_id': lease_id,
                    'fencing_token': token, 'status': 'completed', 'output': {}}})
    return api.handle_cluster_rpc(SimpleNamespace(model_dump=lambda: {}))


def test_stale_worker_result_is_rejected_after_reassignment(tmp_path, monkeypatch):
    tasks, leases = _runtime(tmp_path, monkeypatch)
    task = tasks.create('analyse', {**REMOTE, 'assigned_knight': 'worker-a'})
    first = tasks.claim_remote_atomically(task['id'], 'worker-a', 'compute', leases)
    assert first and first['status'] == 'leased'
    old_lease, old_token = first['lease_id'], first['fencing_token']
    leases.revoke_lease(task['id'])
    tasks.transition_task(task['id'], 'RECOVERY_REQUIRED', {'error': 'worker-a disconnected'})
    tasks.transition_task(task['id'], 'queued', {'assigned_knight': None, 'lease_id': None})
    second = tasks.claim_remote_atomically(task['id'], 'worker-b', 'compute', leases)
    assert second and second['assigned_knight'] == 'worker-b'
    assert second['fencing_token'] > old_token and second['lease_id'] != old_lease
    for lease_id in (old_lease, second['lease_id']):
        with pytest.raises(HTTPException) as rejected:
            _submit_result(monkeypatch, 'worker-a', task['id'], lease_id, old_token)
        assert rejected.value.status_code == 403
    # Even the current assignee cannot reuse the previous fencing generation.
    with pytest.raises(HTTPException) as stale_generation:
        _submit_result(monkeypatch, 'worker-b', task['id'], second['lease_id'], old_token)
    assert stale_generation.value.status_code == 403
    current = tasks.get(task['id'])
    assert current['status'] == 'leased' and current['assigned_knight'] == 'worker-b'
    assert current['result'] is None


class _Policy:
    """Isolate policy persistence from the global installation."""
    def __init__(self, level=5): self.level = level
    def get(self):
        return {'level': self.level, 'revision': 'acceptance',
                'mission_budget': {'max_steps': 100, 'max_retries': 3, 'max_parallel': 3,
                                   'auto_advance': True, 'cross_computer': True}}
    def set(self, level): self.level = level; return self.get()
    def requires_approval(self, task): return False


def test_emergency_stop_is_exposed_by_the_runtime():
    assert callable(getattr(api.engine, 'emergency_stop', None))


@pytest.mark.parametrize('tool', ['text.analyze@1.0.0', 'process.run@1.0.0'])
def test_emergency_stop_revokes_leases_and_rejects_late_results(tmp_path, monkeypatch, tool):
    assert callable(getattr(api.engine, 'emergency_stop', None))
    tasks, leases = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(api.engine, 'execution_policy', _Policy(level=5))
    task = tasks.create('in-flight work', {**REMOTE, 'tool': tool, 'assigned_knight': 'worker-a'})
    leased = tasks.claim_remote_atomically(task['id'], 'worker-a', 'compute', leases)
    assert leased and leased['status'] == 'leased'
    waiting = tasks.create('queued work', {**REMOTE, 'assigned_knight': 'worker-a'})
    outcome = api.engine.emergency_stop('owner', 'acceptance drill')
    if inspect.isawaitable(outcome): asyncio.run(outcome)
    assert api.engine.execution_policy.get()['level'] == 0
    with pytest.raises(PermissionError):
        leases.validate_lease_execution(task['id'], 'worker-a', leased['fencing_token'])
    after = tasks.get(task['id'])
    assert after['status'] not in ('leased', 'completed'), after['status']
    with pytest.raises(HTTPException) as late:
        _submit_result(monkeypatch, 'worker-a', task['id'], leased['lease_id'], leased['fencing_token'])
    assert late.value.status_code == 403
    assert api.engine.dispatch_remote_task(waiting['id'], 'worker-b', 'compute', leases) is None
    assert tasks.get(waiting['id'])['status'] == 'queued'


def test_emergency_stop_survives_new_managers_and_stale_policy(tmp_path, monkeypatch):
    from backend.runtime.policy import ExecutionPolicy
    tasks, leases = _runtime(tmp_path, monkeypatch)
    policy = ExecutionPolicy(tasks.repo.db)
    policy.set(5)
    monkeypatch.setattr(api.engine, 'execution_policy', policy)
    task = tasks.create('leased work', REMOTE)
    leased = tasks.claim_remote_atomically(task['id'], 'worker-a', 'compute', leases)
    stale = TaskManager(TaskRepository(tasks.repo.db))
    waiting = tasks.create('waiting', REMOTE)
    api.engine.emergency_stop('owner', 'restart drill')
    restored = TaskLeaseManager(database=tasks.repo.db)
    assert restored.issue_and_claim(waiting['id'], 'worker-b', 'compute', waiting['version']) is None
    with pytest.raises(PermissionError): restored.issue_lease(waiting['id'], 'worker-b', 'compute')
    with pytest.raises((ValueError, PermissionError)):
        stale.complete(task['id'], {'untrusted': 'late completion'})
    assert TaskManager(TaskRepository(tasks.repo.db)).get(task['id'])['status'] == 'RECOVERY_REQUIRED'
    with pytest.raises(PermissionError): ExecutionPolicy(tasks.repo.db).set(5)
    assert ExecutionPolicy(tasks.repo.db).get()['level'] == 0
    with pytest.raises(PermissionError):
        restored.validate_lease_execution(task['id'], 'worker-a', leased['fencing_token'])
    local = tasks.create('local waiting work')
    assert TaskManager(TaskRepository(tasks.repo.db)).claim_next() is None
    assert tasks.repo.get(local['id'])['status'] == 'queued'


def test_only_owner_can_stop_or_reset_and_reset_never_restarts_held_work(tmp_path, monkeypatch):
    from backend.runtime.policy import ExecutionPolicy
    tasks, leases = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(api.engine, 'execution_policy', ExecutionPolicy(tasks.repo.db))
    task = tasks.create('side effect', {**REMOTE, 'tool': 'process.run@1.0.0'})
    tasks.claim_remote_atomically(task['id'], 'worker-a', 'compute', leases)
    with pytest.raises(PermissionError): api.engine.emergency_stop('model', 'untrusted')
    first = api.engine.emergency_stop('owner', 'first stop')
    second = api.engine.emergency_stop('owner', 'second stop')
    with pytest.raises(ValueError): api.engine.reset_emergency_stop('owner', first['stop_id'])
    assert leases.emergency_status()['stop_id'] == second['stop_id']
    with pytest.raises(PermissionError): api.engine.reset_emergency_stop('model', second['stop_id'])
    api.engine.reset_emergency_stop('owner', second['stop_id'])
    assert api.engine.execution_policy.get()['level'] == 0
    assert tasks.get(task['id'])['status'] == 'RECOVERY_REQUIRED'
    assert leases.emergency_status() is None
    with pytest.raises(PermissionError):
        leases.validate_lease_execution(task['id'], 'worker-a', task['fencing_token'])


def test_emergency_endpoint_is_owner_only_and_strict(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.security.http_auth import owner_auth
    tasks, leases = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(api.engine, 'execution_policy', _Policy())
    app = FastAPI(); app.include_router(api.router)
    client = TestClient(app)
    assert client.post('/runtime/emergency-stop', headers={'X-Kingdom-Request':'1'}, json={'reason': 'drill'}).status_code == 401
    headers = {'Authorization': 'Bearer '+owner_auth.token}
    assert client.post('/runtime/emergency-stop', headers=headers, json={'reason': ' ', 'operator':'owner'}).status_code == 422
    response = client.post('/runtime/emergency-stop', headers=headers, json={'reason': 'drill'})
    assert response.status_code == 200
    stop_id = response.json()['stop_id']
    assert client.get('/runtime/emergency-stop', headers=headers).json()['stop']['stop_id'] == stop_id
    assert client.post('/runtime/emergency-stop/reset', headers={'X-Kingdom-Request':'1'}, json={'stop_id': stop_id}).status_code == 401
    assert client.post('/runtime/emergency-stop/reset', headers=headers, json={'stop_id': '0'*32}).status_code == 409
    assert client.post('/runtime/emergency-stop/reset', headers=headers, json={'stop_id': stop_id}).status_code == 200


@pytest.mark.parametrize('iteration', range(5))
def test_stop_and_independent_dispatch_cannot_leave_an_active_lease(tmp_path, monkeypatch, iteration):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    tasks, leases = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(api.engine, 'execution_policy', _Policy())
    queued = tasks.create('racing dispatch', REMOTE)
    other = TaskLeaseManager(database=tasks.repo.db)
    ready = Barrier(2)
    def claim():
        ready.wait(timeout=3)
        return other.issue_and_claim(queued['id'], 'worker-a', 'compute', queued['version'])
    def stop():
        ready.wait(timeout=3)
        return api.engine.emergency_stop('owner', 'concurrent dispatch drill')
    with ThreadPoolExecutor(max_workers=2) as pool:
        claiming, stopping = pool.submit(claim), pool.submit(stop)
        claimed, stopped = claiming.result(timeout=5), stopping.result(timeout=5)
    assert stopped['autonomy_level'] == 0
    current = TaskManager(TaskRepository(tasks.repo.db)).get(queued['id'])
    assert current['status'] == ('RECOVERY_REQUIRED' if claimed else 'queued')
    assert TaskLeaseManager(database=tasks.repo.db).busy_node_ids() == set()
    assert other.issue_and_claim(queued['id'], 'worker-b', 'compute', current['version']) is None


def test_prepared_local_execution_is_rechecked_when_its_thread_enters(tmp_path, monkeypatch):
    from functools import partial
    from backend.runtime.execution import execute_request
    tasks, _ = _runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(api.engine, 'execution_policy', _Policy())
    tasks.create('hello world', {'tool': 'text.analyze@1.0.0'})
    prepared = tasks.claim_next()
    guard = partial(api.engine.assert_execution_allowed, prepared['id'], prepared['version'])
    # Same real operation succeeds before stop; no fake tool/authorization path.
    assert execute_request(prepared, ['compute'], execution_guard=guard)['output']['words'] == 2
    apprentice = api.engine.swarm.registry.get('coder')
    assert apprentice.execute(prepared)['status'] == 'completed'
    stopped = api.engine.emergency_stop('owner', 'stop before prepared thread starts')
    with pytest.raises(PermissionError, match='emergency stop'):
        execute_request(prepared, ['compute'], execution_guard=guard)
    with pytest.raises(PermissionError, match='emergency stop'):
        apprentice.execute(prepared)
    api.engine.reset_emergency_stop('owner', stopped['stop_id'])
    with pytest.raises(PermissionError, match='stopped, stale'):
        apprentice.execute(prepared)
    with pytest.raises(PermissionError, match='stopped, stale'):
        execute_request(prepared, ['compute'], execution_guard=guard)
