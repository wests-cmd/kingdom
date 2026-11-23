"""Owner stop fences the live browser task/lease atomically and never replays effects."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.api import engine as api_engine
from backend.main import app
from backend.cluster.task_leasing import TaskLeaseManager
from backend.runtime.engine import RuntimeEngine
from backend.runtime.tasks import TaskManager
from backend.storage.db import Database
from backend.storage.repository import TaskRepository
from tests.auth_support import owner_client

TOOL = 'computer.browser.run@1.0.0'


@pytest.fixture
def runtime(tmp_path):
    database = Database(tmp_path / 'browser-stop.db')
    instance = RuntimeEngine()
    instance.tasks = TaskManager(TaskRepository(database))
    instance.lease_manager = TaskLeaseManager(database=database)
    return instance


def test_stop_running_browser_fences_local_task_and_survives_database_reload(runtime):
    task = runtime.tasks.create('test', {'actor': 'owner', 'tool': TOOL})
    running = runtime.tasks.claim_next()
    runtime.assert_execution_allowed(task['id'], running['version'])
    stopped = runtime.stop_browser_task(task['id'])
    assert stopped['status'] == 'RECOVERY_REQUIRED'
    assert stopped['cancellation_requested'] is True
    assert stopped['version'] > running['version']
    with pytest.raises(PermissionError, match='stopped, stale'):
        runtime.assert_execution_allowed(task['id'], running['version'])
    with pytest.raises(ValueError, match='Only running or leased'):
        runtime.tasks.complete(task['id'], {'claimed': 'should not complete'})
    assert TaskRepository(runtime.tasks.repo.db).get(task['id'])['status'] == 'RECOVERY_REQUIRED'
    with pytest.raises(ValueError, match='current state'):
        runtime.stop_browser_task(task['id'])


def test_stop_leased_browser_revokes_real_lease_in_same_database(runtime):
    task = runtime.tasks.create('test', {'actor': 'owner', 'tool': TOOL})
    lease = runtime.lease_manager.issue_and_claim(task['id'], 'node-test', 'computer.control', task['version'])
    assert lease is not None
    runtime.tasks.load_persisted_tasks()
    assert runtime.lease_manager.validate_lease_execution(task['id'], 'node-test', lease.fencing_token)
    stopped = runtime.stop_browser_task(task['id'])
    assert stopped['status'] == 'RECOVERY_REQUIRED'
    with pytest.raises(PermissionError, match='revoked'):
        runtime.lease_manager.validate_lease_execution(task['id'], 'node-test', lease.fencing_token)
    with runtime.tasks.repo.db.get_connection() as connection:
        state = connection.execute('SELECT status,cancellation_requested FROM tasks WHERE id=?', (task['id'],)).fetchone()
        lease_state = connection.execute('SELECT revoked FROM leases WHERE task_id=?', (task['id'],)).fetchone()
    assert state['status'] == 'RECOVERY_REQUIRED'
    assert state['cancellation_requested'] == 1
    assert lease_state['revoked'] == 1


def test_targeted_stop_refuses_other_tools_and_does_not_change_them(runtime):
    task = runtime.tasks.create('safe analysis', {'actor': 'owner', 'tool': 'text.analyze@1.0.0'})
    runtime.tasks.claim_next()
    with pytest.raises(ValueError, match='limited to private browser'):
        runtime.stop_browser_task(task['id'])
    assert runtime.tasks.repo.get(task['id'])['status'] == 'running'


def test_queued_browser_can_be_cancelled_without_started_effects(runtime):
    task = runtime.tasks.create('safe preview', {'actor': 'owner', 'tool': TOOL})
    stopped = runtime.stop_browser_task(task['id'])
    assert stopped['status'] == 'cancelled'
    assert stopped['cancellation_requested'] is True
    assert runtime.tasks.claim_next() is None


def test_stop_endpoint_requires_owner_and_cannot_stop_arbitrary_task(monkeypatch):
    calls = []
    def do_stop(task_id):
        calls.append(task_id)
        raise ValueError('Targeted browser stop is limited to private browser tasks')
    monkeypatch.setattr(api_engine, 'stop_browser_task', do_stop)
    assert TestClient(app).post('/tasks/not-browser/stop-private-browser').status_code in {401, 403}
    assert calls == []
    response = owner_client(app).post('/tasks/not-browser/stop-private-browser')
    assert response.status_code == 409
    assert calls == ['not-browser']
