"""Atomic heartbeat/revocation regression for real SQLite membership rows."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from backend.cluster.node_registry import NodeRegistry
from backend.storage.db import Database
from backend.storage.repository import KnightRepository


def setup_remote(tmp_path):
    repo = KnightRepository(Database(tmp_path / "mesh-test.db"))
    registry = NodeRegistry(repo)
    now = time.time()
    repo.save({
        "id": "remote-kingdom", "role": "commander", "status": "CONNECTED",
        "node_state": "CONNECTED", "health": "healthy", "is_local": False,
        "current_task": "leased-task", "last_heartbeat": now - 120,
        "granted_capabilities": ["compute"], "capabilities": ["compute"],
        "public_identity": {"node_id": "remote-kingdom", "node_type": "commander"},
        "fingerprint": "pinned-fingerprint", "connection_metadata": {"mesh_authority": "authority"}
    })
    return repo, registry


def revoke_directly(repo):
    with repo.db.get_connection() as conn:
        conn.execute("""UPDATE knights SET node_state='REVOKED',status='REVOKED',
                        health='unhealthy' WHERE id='remote-kingdom'""")
        conn.commit()


def test_revoked_peer_cannot_be_revived_by_late_heartbeat(tmp_path):
    repo, registry = setup_remote(tmp_path)
    stale_copy = repo.get("remote-kingdom")
    revoke_directly(repo)
    assert registry.heartbeat("remote-kingdom") is None
    after = repo.get("remote-kingdom")
    assert after["node_state"] == "REVOKED"
    assert after["status"] == "REVOKED"
    assert after["health"] == "unhealthy"
    assert after["granted_capabilities"] == stale_copy["granted_capabilities"]
    assert after["public_identity"] == stale_copy["public_identity"]


def test_revocation_wins_over_stale_node_inventory(tmp_path):
    repo, registry = setup_remote(tmp_path)
    snapshot = repo.list_all()
    # Simulate the exact old read-modify-write race: roster revocation occurs
    # after list_all returns, before check_stale_heartbeats acts on it.
    repo.list_all = lambda: snapshot
    revoke_directly(repo)
    registry.check_stale_heartbeats(timeout_seconds=30)
    after = repo.get("remote-kingdom")
    assert after["node_state"] == "REVOKED"
    assert after["status"] == "REVOKED"
    assert after["current_task"] == "leased-task"
    assert after["granted_capabilities"] == ["compute"]


def test_recent_heartbeat_prevents_stale_timeout(tmp_path):
    repo, registry = setup_remote(tmp_path)
    assert registry.heartbeat("remote-kingdom") is not None
    assert repo.mark_stale_heartbeat("remote-kingdom", time.time()-30, time.time()) is None
    assert repo.get("remote-kingdom")["node_state"] == "CONNECTED"


def test_disconnected_node_can_reconnect_without_grant_changes(tmp_path):
    repo, registry = setup_remote(tmp_path)
    with repo.db.get_connection() as conn:
        conn.execute("UPDATE knights SET node_state='DISCONNECTED' WHERE id='remote-kingdom'")
        conn.commit()
    result = registry.heartbeat("remote-kingdom")
    assert result["node_state"] == "CONNECTED"
    assert result["granted_capabilities"] == ["compute"]
    assert result["fingerprint"] == "pinned-fingerprint"


def test_concurrent_revocation_and_heartbeat_leave_node_revoked(tmp_path):
    repo, registry = setup_remote(tmp_path)
    # A write may win first, but the final persisted security state must be
    # revoked. This test exercises separate SQLite connections and threads.
    for _ in range(12):
        with repo.db.get_connection() as conn:
            conn.execute("""UPDATE knights SET node_state='CONNECTED',status='CONNECTED',
                            health='healthy' WHERE id='remote-kingdom'""")
            conn.commit()
        barrier = threading.Barrier(2)
        def beat():
            barrier.wait()
            return registry.heartbeat("remote-kingdom")
        def revoke():
            barrier.wait()
            revoke_directly(repo)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(beat), pool.submit(revoke)]
            for result in results:
                result.result(timeout=10)
        assert repo.get("remote-kingdom")["node_state"] == "REVOKED"
