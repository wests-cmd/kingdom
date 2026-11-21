"""Persisted heartbeat/revocation contract across disconnects and restarts."""
import threading
import time

import pytest

from backend.cluster.heartbeat import HeartbeatManager
from backend.cluster.node_registry import NodeInfo, NodeRegistry
from backend.storage.db import Database
from backend.storage.repository import KnightRepository


def registry_for(tmp_path):
    database = Database(tmp_path / "heartbeats.db")
    repository = KnightRepository(database)
    return repository, NodeRegistry(repository=repository)


def register(repository, node_id, *, state="CONNECTED", last_heartbeat=None):
    row = NodeInfo(
        node_id=node_id,
        node_state_val=state,
        last_heartbeat=time.time() if last_heartbeat is None else last_heartbeat,
        fingerprint="pinned-fingerprint",
        granted_capabilities=["compute"],
        capabilities=["compute"],
        public_identity={"node_id": node_id, "public_key_hex": "pinned-key"},
        connection_metadata={"kingdom_endpoint": "http://127.0.0.1:18014"},
    ).to_dict()
    repository.save(row)
    return row


@pytest.mark.parametrize("state", ["REVOKED", "REJECTED", "QUARANTINED"])
def test_restricted_idle_node_cannot_refresh_heartbeat(tmp_path, monkeypatch, state):
    from backend.cluster import heartbeat
    repository, registry = registry_for(tmp_path)
    register(repository, "worker", state=state, last_heartbeat=1)
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    before = repository.get("worker")
    assert HeartbeatManager().ping("worker")["success"] is False
    after = repository.get("worker")
    assert after["node_state"] == state
    assert after["last_heartbeat"] == 1
    assert after["granted_capabilities"] == before["granted_capabilities"]


def test_disconnected_idle_node_reconnects_using_trust_state(tmp_path, monkeypatch):
    from backend.cluster import heartbeat
    repository, registry = registry_for(tmp_path)
    initial = register(repository, "worker", state="DISCONNECTED", last_heartbeat=1)
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    result = HeartbeatManager().ping("worker")
    after = repository.get("worker")
    assert result["success"] and result["node_state"] == "CONNECTED"
    assert after["node_state"] == "CONNECTED"
    assert after["last_heartbeat"] > 1
    assert after["granted_capabilities"] == initial["granted_capabilities"]


def test_health_timeout_uses_connection_state_not_task_status(monkeypatch):
    from types import SimpleNamespace
    from backend.cluster.node_registry import node_registry
    updates = []
    node = SimpleNamespace(node_id="worker", node_state="CONNECTED", status="idle", last_heartbeat=time.time() - 100)
    monkeypatch.setattr(node_registry, "list_nodes", lambda: [node])
    monkeypatch.setattr(node_registry, "update_node_state", lambda *args, **kwargs: updates.append(args))
    assert HeartbeatManager().evaluate_cluster_health()["disconnected"] == 1
    assert updates[0][0] == "worker"


@pytest.mark.parametrize("state", ["DISCONNECTED", "RECONNECTING", "APPROVED"])
def test_reconnect_persists_fresh_ping_before_state_reload(tmp_path, monkeypatch, state):
    from backend.cluster import heartbeat
    repository, registry = registry_for(tmp_path)
    register(repository, "worker", state=state, last_heartbeat=1)
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    before = time.time()
    result = HeartbeatManager().ping("worker", load_metrics={"cpu": 0.25})
    after = repository.get("worker")
    assert result["success"]
    assert after["last_heartbeat"] >= before
    assert after["connection_metadata"]["load_metrics"] == {"cpu": 0.25}
    assert after["node_state"] == "CONNECTED"
    assert HeartbeatManager().evaluate_cluster_health()["disconnected"] == 0


def test_offline_membership_survives_reload_and_reconnect_without_repairing(tmp_path, monkeypatch):
    """Liveness loss cannot expire permanent owner grants or require re-pairing."""
    from backend.cluster import heartbeat
    repository, registry = registry_for(tmp_path)
    original = register(repository, "permanent-peer", last_heartbeat=time.time() - 100)
    registry.check_stale_heartbeats()
    offline = repository.get("permanent-peer")
    assert offline["node_state"] == "DISCONNECTED"
    for key in ("fingerprint", "public_identity", "granted_capabilities", "connection_metadata"):
        assert offline[key] == original[key]
    restarted = NodeRegistry(repository=KnightRepository(Database(repository.db.db_path)))
    monkeypatch.setattr(heartbeat, "node_registry", restarted)
    assert HeartbeatManager().ping("permanent-peer")["success"]
    online = repository.get("permanent-peer")
    assert online["node_state"] == "CONNECTED"
    for key in ("fingerprint", "public_identity", "granted_capabilities", "connection_metadata"):
        assert online[key] == original[key]


def test_revocation_before_heartbeat_commit_cannot_restore_state_or_grants(tmp_path, monkeypatch):
    """The revocation wins even if another thread started a heartbeat first."""
    from backend.cluster import heartbeat, capabilities
    repository, registry = registry_for(tmp_path)
    register(repository, "worker")
    monkeypatch.setattr(heartbeat, "node_registry", registry)
    monkeypatch.setattr(capabilities, "node_registry", registry)
    started, release = threading.Event(), threading.Event()
    original = repository.refresh_heartbeat
    outcome = []

    def delayed_refresh(*args, **kwargs):
        started.set()
        if not release.wait(5):
            raise RuntimeError("Heartbeat test barrier not released")
        return original(*args, **kwargs)

    monkeypatch.setattr(repository, "refresh_heartbeat", delayed_refresh)
    thread = threading.Thread(target=lambda: outcome.append(HeartbeatManager().ping("worker")))
    thread.start()
    try:
        assert started.wait(3), "Heartbeat did not reach validation barrier"
        revoked = capabilities.CapabilityAuthorizer.revoke_node("worker")
        assert revoked["node_state"] == "REVOKED"
    finally:
        release.set()
        thread.join(timeout=6)
    assert not thread.is_alive()
    assert outcome == [{"success": False,
                        "error": "Node worker is not approved for heartbeat in state REVOKED."}]
    after = repository.get("worker")
    assert after["node_state"] == "REVOKED"
    assert after["granted_capabilities"] == []
    assert HeartbeatManager().ping("worker")["success"] is False
