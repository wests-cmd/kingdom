"""Real SQLite heartbeat, reconnection and revocation concurrency checks."""
import threading
import time

import pytest

from backend.cluster.heartbeat import HeartbeatManager
from backend.cluster.node_registry import NodeInfo, NodeRegistry, NodeState
from backend.storage.db import Database
from backend.storage.repository import KnightRepository


def registry_for(tmp_path):
    repo = KnightRepository(Database(tmp_path / "heartbeats.db"))
    return repo, NodeRegistry(repository=repo)


def register(repo, node_id, *, state="CONNECTED", last_heartbeat=None):
    value = NodeInfo(
        node_id=node_id, node_state_val=state,
        last_heartbeat=time.time() if last_heartbeat is None else last_heartbeat,
        role="commander", fingerprint="pinned-fingerprint",
        capabilities=["compute"], granted_capabilities=["compute"],
        public_identity={"node_id": node_id, "public_key_hex": "pinned-key"},
        connection_metadata={"kingdom_endpoint": "http://127.0.0.1:18014"},
    ).to_dict()
    repo.save(value)
    return value


@pytest.mark.parametrize("state", ["REVOKED", "REJECTED", "QUARANTINED", "PENDING_APPROVAL"])
def test_unapproved_node_cannot_refresh_signed_heartbeat(tmp_path, monkeypatch, state):
    from backend.cluster import heartbeat
    repo, registry = registry_for(tmp_path)
    register(repo, "peer", state=state, last_heartbeat=1)
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    before = repo.get("peer")
    assert HeartbeatManager().ping("peer")["success"] is False
    after = repo.get("peer")
    assert after["node_state"] == state
    assert after["last_heartbeat"] == before["last_heartbeat"]
    assert after["granted_capabilities"] == before["granted_capabilities"]


@pytest.mark.parametrize("state", ["APPROVED", "DISCONNECTED", "RECONNECTING"])
def test_approved_reconnect_preserves_grants_and_metadata(tmp_path, monkeypatch, state):
    from backend.cluster import heartbeat
    repo, registry = registry_for(tmp_path)
    original = register(repo, "peer", state=state, last_heartbeat=1)
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    started = time.time()
    result = HeartbeatManager().ping("peer", load_metrics={"cpu": 0.25},
                                     native_analysis_return=True)
    after = repo.get("peer")
    assert result["success"] and result["node_state"] == "CONNECTED"
    assert after["last_heartbeat"] >= started
    assert after["connection_metadata"]["load_metrics"] == {"cpu": 0.25}
    assert after["connection_metadata"]["native_analysis_return"] is True
    for name in ("fingerprint", "public_identity", "granted_capabilities"):
        assert after[name] == original[name]
    assert HeartbeatManager().evaluate_cluster_health()["disconnected"] == 0


def test_reconnect_keeps_permanent_owner_trust_through_restart(tmp_path, monkeypatch):
    from backend.cluster import heartbeat
    repo, registry = registry_for(tmp_path)
    original = register(repo, "peer", last_heartbeat=time.time()-100)
    registry.check_stale_heartbeats()
    assert repo.get("peer")["node_state"] == "DISCONNECTED"
    restarted = NodeRegistry(repository=KnightRepository(Database(repo.db.db_path)))
    monkeypatch.setattr(heartbeat, "node_registry", restarted)
    assert HeartbeatManager().ping("peer")["success"]
    after = repo.get("peer")
    assert after["node_state"] == "CONNECTED"
    for key in ("fingerprint", "public_identity", "granted_capabilities"):
        assert after[key] == original[key]


def test_ping_cannot_restore_owner_revocation_during_prepared_request(tmp_path, monkeypatch):
    from backend.cluster import heartbeat
    repo, registry = registry_for(tmp_path)
    register(repo, "peer")
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    entered, release = threading.Event(), threading.Event()
    original = repo.refresh_heartbeat
    output = []

    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(8), "test synchronization timed out"
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "refresh_heartbeat", delayed)
    thread = threading.Thread(target=lambda: output.append(HeartbeatManager().ping("peer")))
    thread.start()
    try:
        assert entered.wait(5), "heartbeat did not reach persisted-state barrier"
        registry.update_node_state("peer", NodeState.REVOKED, reason="Owner revoked")
    finally:
        release.set()
        thread.join(timeout=10)
    assert not thread.is_alive()
    assert output and output[0]["success"] is False
    after = repo.get("peer")
    assert after["node_state"] == "REVOKED"
    assert after["status"] == "REVOKED"
    assert after["granted_capabilities"] == ["compute"]


def test_health_timeout_uses_current_sqlite_state_not_stale_snapshot(tmp_path, monkeypatch):
    from backend.cluster import heartbeat
    repo, registry = registry_for(tmp_path)
    register(repo, "peer", last_heartbeat=time.time()-50)
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    status = HeartbeatManager(timeout_seconds=45).evaluate_cluster_health()
    assert status["disconnected"] >= 1
    assert repo.get("peer")["node_state"] == "DISCONNECTED"
    assert repo.get("peer")["granted_capabilities"] == ["compute"]


def test_timeout_cannot_undo_revocation_or_fresh_heartbeat(tmp_path, monkeypatch):
    from backend.cluster import heartbeat
    repo, registry = registry_for(tmp_path)
    register(repo, "peer", last_heartbeat=time.time()-50)
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    stale = repo.list_all()
    repo.list_all = lambda: stale
    registry.update_node_state("peer", NodeState.REVOKED, reason="Owner revoked")
    HeartbeatManager(timeout_seconds=45).evaluate_cluster_health()
    assert repo.get("peer")["node_state"] == "REVOKED"


def test_degraded_heartbeat_only_updates_health_of_still_approved_peer(tmp_path, monkeypatch):
    from backend.cluster import heartbeat
    repo, registry = registry_for(tmp_path)
    register(repo, "peer", last_heartbeat=time.time()-30)
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    result = HeartbeatManager(timeout_seconds=45).evaluate_cluster_health()
    assert result["degraded"] >= 1
    assert repo.get("peer")["health"] == "degraded"
    assert repo.get("peer")["granted_capabilities"] == ["compute"]
    registry.update_node_state("peer", NodeState.REVOKED, reason="Owner revoked")
    assert repo.mark_degraded_heartbeat("peer", older_than=time.time(),
                                        newer_than=time.time()-45,
                                        observed_at=time.time()) is False
    assert repo.get("peer")["node_state"] == "REVOKED"


def test_invalid_inventory_cannot_change_peer_state(tmp_path, monkeypatch):
    from backend.cluster import heartbeat
    repo, registry = registry_for(tmp_path)
    register(repo, "peer")
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    before = repo.get("peer")
    with pytest.raises((TypeError, ValueError, KeyError)):
        HeartbeatManager().ping("peer", apprentice_inventory={"untrusted": "invalid"})
    after = repo.get("peer")
    assert after["last_heartbeat"] == before["last_heartbeat"]
