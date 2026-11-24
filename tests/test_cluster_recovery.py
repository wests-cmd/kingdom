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


@pytest.mark.parametrize("group_id", [None, "group-1"])
def test_pre_dispatch_offload_fallback_clears_both_targets_without_escaping_group(tmp_path, monkeypatch, group_id):
    database = Database(tmp_path / "fallback.db")
    tasks = TaskManager(TaskRepository(database))
    task = tasks.create("analysis", {"tool":"text.analyze@1.0.0", "offload":True,
        "assigned_knight":"offline-peer", "execution_target":"remote", "group_id":group_id})
    events = []
    runtime = SimpleNamespace(tasks=tasks, lease_manager=TaskLeaseManager(database=database),
        dispatch_lock=RLock(), events=SimpleNamespace(publish=lambda *args:events.append(args)))
    monkeypatch.setattr("backend.cluster.heartbeat.heartbeat_manager.evaluate_cluster_health", lambda:None)
    monkeypatch.setattr("backend.cluster.node_registry.node_registry.get_node", lambda _:None)
    RuntimeEngine.recover_remote_tasks(runtime)
    saved = tasks.get(task["id"])
    if group_id:
        assert saved == task
        assert tasks.claim_next() is None
        assert not events
    else:
        assert saved["assigned_knight"] is None
        assert saved["metadata"]["assigned_knight"] is None
        assert saved["metadata"]["execution_target"] == "local"
        assert tasks.claim_next()["id"] == task["id"]
        assert events[-1][0] == "task.offload_fallback"


def test_group_assignment_keeps_exact_durable_version_and_routing(tmp_path):
    db = Database(tmp_path / "assignment.db")
    tasks = TaskManager(TaskRepository(db))
    task = tasks.create("analysis", {"tool":"text.analyze@1.0.0", "group_id":"team-a"})
    assigned = tasks.assign_queued_group_task(task["id"], task["version"], "team-a", "worker")
    assert assigned["assigned_knight"] == assigned["metadata"]["assigned_knight"] == "worker"
    assert assigned["metadata"]["execution_target"] == "remote"
    assert assigned["version"] == task["version"] + 1
    assert tasks.repo.get(task["id"]) == assigned
    assert tasks.claim_next() is None
    with pytest.raises(ValueError):
        tasks.assign_queued_group_task(task["id"], task["version"], "team-a", "other")
    with pytest.raises(ValueError):
        tasks.assign_queued_group_task(task["id"], assigned["version"], "team-b", "other")


def test_group_assignment_cannot_rewind_independently_claimed_work(tmp_path):
    db = Database(tmp_path / "race.db")
    first = TaskManager(TaskRepository(db))
    task = first.create("analysis", {"tool":"text.analyze@1.0.0", "group_id":"team-a"})
    second = TaskManager(TaskRepository(db))
    claimed = second.claim_next()
    assert claimed["status"] == "running"
    with pytest.raises(ValueError):
        first.assign_queued_group_task(task["id"], task["version"], "team-a", "worker")
    assert first.repo.get(task["id"])["status"] == "running"
