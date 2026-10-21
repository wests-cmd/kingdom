"""Node slots are durable SQLite reservations, even across managers."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import time

import pytest

from backend.cluster.task_leasing import TaskLeaseManager
from backend.storage.db import Database


def queued(database, task_id):
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO tasks(id,type,status,created_at,updated_at) VALUES(?,'tool','queued',?,?)",
            (task_id, time.time(), time.time()),
        )
        conn.commit()


def test_two_managers_cannot_claim_different_tasks_on_one_node(tmp_path):
    path = tmp_path / "capacity.db"
    database = Database(path)
    for task in ("a", "b"):
        queued(database, task)
    managers = [TaskLeaseManager(database=Database(path)) for _ in range(2)]
    barrier = Barrier(2)

    def claim(index):
        barrier.wait()
        return managers[index].issue_and_claim(("a", "b")[index], "worker", "compute", 1)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(claim, range(2)))
    assert sum(result is not None for result in results) == 1
    with database.get_connection() as conn:
        assert conn.execute("SELECT count(*) FROM leases WHERE revoked=0").fetchone()[0] == 1
        rows = conn.execute("SELECT status,attempt,version FROM tasks ORDER BY status").fetchall()
    assert [(row["status"], row["attempt"], row["version"]) for row in rows] == [
        ("leased", 1, 2), ("queued", 0, 1)
    ]


@pytest.mark.parametrize("release", ["expired", "revoked"])
def test_capacity_recovers_from_persisted_release(tmp_path, release):
    database = Database(tmp_path / "capacity.db")
    first = TaskLeaseManager(database=database)
    lease = first.issue_lease("a", "worker", "compute")
    second = TaskLeaseManager(database=database)
    queued(database, "b")
    assert second.issue_and_claim("b", "worker", "compute", 1) is None
    assert second.busy_node_ids() == {"worker"}
    if release == "revoked":
        first.revoke_lease("a")
    else:
        with database.get_connection() as conn:
            conn.execute("UPDATE leases SET expires_at=? WHERE lease_id=?", (time.time() - 1, lease.lease_id))
            conn.commit()
    assert second.busy_node_ids() == set()
    assert second.issue_and_claim("b", "worker", "compute", 1) is not None
    with pytest.raises(PermissionError):
        second.validate_lease_execution("a", "worker", lease.fencing_token)


def test_direct_issue_respects_capacity_and_same_task_reissue_fences(tmp_path):
    database = Database(tmp_path / "capacity.db")
    manager = TaskLeaseManager(database=database)
    first = manager.issue_lease("a", "worker", "compute")
    restarted = TaskLeaseManager(database=database)
    with pytest.raises(ValueError, match="active task lease"):
        restarted.issue_lease("b", "worker", "compute")
    replacement = restarted.issue_lease("a", "worker", "compute")
    assert replacement.fencing_token == first.fencing_token + 1
    with pytest.raises(PermissionError, match="Fencing"):
        manager.validate_lease_execution("a", "worker", first.fencing_token)
    assert manager.validate_lease_execution("a", "worker", replacement.fencing_token)
    assert manager.issue_lease("b", "other-worker", "compute") is not None


def test_failed_claim_does_not_reserve_capacity(tmp_path):
    database = Database(tmp_path / "capacity.db")
    manager = TaskLeaseManager(database=database)
    queued(database, "a")
    assert manager.issue_and_claim("a", "worker", "compute", 99) is None
    assert manager.issue_and_claim("a", "worker", "compute", 1) is not None


@pytest.mark.parametrize("ttl", [0, -1, float("inf"), float("nan")])
def test_invalid_lifetime_cannot_reserve_node(tmp_path, ttl):
    database = Database(tmp_path / "capacity.db")
    manager = TaskLeaseManager(default_lease_ttl_sec=ttl, database=database)
    queued(database, "a")
    with pytest.raises(ValueError):
        manager.issue_and_claim("a", "worker", "compute", 1)
    with pytest.raises(ValueError):
        manager.issue_lease("a", "worker", "compute")
