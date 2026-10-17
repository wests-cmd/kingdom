"""Recovery must use durable fencing and never repeat unknown side effects."""
from threading import RLock
from types import SimpleNamespace
import time

import pytest

from backend.cluster.task_leasing import TaskLeaseManager
from backend.runtime.engine import RuntimeEngine
from backend.runtime.tasks import TaskManager
from backend.storage.db import Database
from backend.storage.repository import TaskRepository


@pytest.mark.parametrize('tool,expected', [
    ('text.analyze@1.0.0', 'queued'),
    ('code.python.analyze@1.0.0', 'queued'),
    ('process.run@1.0.0', 'RECOVERY_REQUIRED'),
    (None, 'RECOVERY_REQUIRED'),
])
@pytest.mark.parametrize('release', ['revoked', 'expired'])
def test_remote_revocation_is_seen_across_controllers(tmp_path, monkeypatch, tool, expected, release):
    database = Database(tmp_path/'recovery.db')
    tasks = TaskManager(TaskRepository(database))
    task = tasks.create('interrupted work', {'tool': tool})
    leases = TaskLeaseManager(database=database)
    tasks.claim_remote_atomically(task['id'], 'worker', 'compute', leases)
    independent = TaskLeaseManager(database=database)
    if release == 'revoked':
        independent.revoke_lease(task['id'])
    else:
        with database.get_connection() as conn:
            conn.execute('UPDATE leases SET expires_at=? WHERE task_id=?', (time.time()-1, task['id']))
            conn.commit()
    assert not leases.leases[task['id']].revoked  # deliberately stale cache
    events = []
    runtime = SimpleNamespace(tasks=tasks, lease_manager=leases, dispatch_lock=RLock(),
                              events=SimpleNamespace(publish=lambda *args: events.append(args)))
    monkeypatch.setattr('backend.cluster.heartbeat.heartbeat_manager.evaluate_cluster_health', lambda: None)
    monkeypatch.setattr('backend.cluster.node_registry.node_registry.get_node',
                        lambda ident: SimpleNamespace(node_state='CONNECTED'))
    RuntimeEngine.recover_remote_tasks(runtime)
    recovered = tasks.get(task['id'])
    assert recovered['status'] == expected
    assert events[-1][0] == ('task.requeued' if expected == 'queued' else 'task.recovery_required')
    with pytest.raises(PermissionError):
        leases.validate_lease_execution(task['id'], 'worker', recovered['fencing_token'])


def test_healthy_remote_lease_is_not_requeued(tmp_path, monkeypatch):
    database = Database(tmp_path/'healthy.db')
    tasks = TaskManager(TaskRepository(database))
    task = tasks.create('active work', {'tool': 'text.analyze@1.0.0'})
    leases = TaskLeaseManager(database=database)
    claimed = tasks.claim_remote_atomically(task['id'], 'worker', 'compute', leases)
    events = []
    runtime = SimpleNamespace(tasks=tasks, lease_manager=leases, dispatch_lock=RLock(),
                              events=SimpleNamespace(publish=lambda *args: events.append(args)))
    monkeypatch.setattr('backend.cluster.heartbeat.heartbeat_manager.evaluate_cluster_health', lambda: None)
    monkeypatch.setattr('backend.cluster.node_registry.node_registry.get_node',
                        lambda ident: SimpleNamespace(node_state='CONNECTED'))
    RuntimeEngine.recover_remote_tasks(runtime)
    assert tasks.get(task['id']) == claimed
    assert not events
