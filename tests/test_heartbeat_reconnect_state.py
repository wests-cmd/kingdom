import time
from types import SimpleNamespace

import pytest

from backend.cluster.heartbeat import HeartbeatManager


@pytest.mark.parametrize('state', ['REVOKED', 'REJECTED', 'QUARANTINED'])
def test_restricted_idle_node_cannot_refresh_heartbeat(monkeypatch, state):
    from backend.cluster.node_registry import node_registry
    node = SimpleNamespace(node_state=state, status='idle', last_heartbeat=1, health='old')
    monkeypatch.setattr(node_registry, 'get_node', lambda ident: node)
    assert HeartbeatManager().ping('worker')['success'] is False
    assert node.last_heartbeat == 1


def test_disconnected_idle_node_reconnects_using_trust_state(monkeypatch):
    from backend.cluster.node_registry import node_registry
    updates = []
    node = SimpleNamespace(node_state='DISCONNECTED', status='idle', last_heartbeat=1, health='old')
    node.to_dict = lambda: {'last_heartbeat': node.last_heartbeat}
    monkeypatch.setattr(node_registry.repo, 'save', lambda data: None)
    monkeypatch.setattr(node_registry, 'get_node', lambda ident: node)
    monkeypatch.setattr(node_registry, 'update_node_state', lambda ident, state: updates.append((ident, state.value)))
    assert HeartbeatManager().ping('worker')['success'] is True
    assert updates == [('worker', 'CONNECTED')]


def test_health_timeout_uses_connection_state_not_task_status(monkeypatch):
    from backend.cluster.node_registry import node_registry
    updates = []
    node = SimpleNamespace(node_id='worker', node_state='CONNECTED', status='idle', last_heartbeat=time.time()-100)
    monkeypatch.setattr(node_registry, 'list_nodes', lambda: [node])
    monkeypatch.setattr(node_registry, 'update_node_state', lambda *args, **kwargs: updates.append(args))
    assert HeartbeatManager().evaluate_cluster_health()['disconnected'] == 1
    assert updates[0][0] == 'worker'


@pytest.mark.parametrize('state', ['DISCONNECTED', 'RECONNECTING', 'APPROVED'])
def test_reconnect_persists_fresh_ping_before_state_reload(monkeypatch, state):
    from backend.cluster.node_registry import node_registry, NodeInfo
    persisted = NodeInfo(node_id='worker', node_state_val=state, last_heartbeat=1).to_dict()
    monkeypatch.setattr(node_registry.repo, 'get', lambda ident: dict(persisted))
    monkeypatch.setattr(node_registry.repo, 'save', lambda data: persisted.update(data))
    monkeypatch.setattr('backend.cluster.heartbeat.time.time', lambda: 1000)
    result = HeartbeatManager().ping('worker', load_metrics={'cpu': 0.25})
    assert result['success']
    assert persisted['last_heartbeat'] == 1000
    assert persisted['connection_metadata']['load_metrics'] == {'cpu': 0.25}
    assert persisted['node_state'] == 'CONNECTED'
    assert HeartbeatManager().evaluate_cluster_health()['disconnected'] == 0


def test_offline_membership_survives_reload_and_reconnect_without_repairing(monkeypatch):
    """A liveness timeout cannot expire the owner's permanent trust decision."""
    from backend.cluster.node_registry import NodeRegistry, NodeInfo
    from backend.cluster import heartbeat
    import copy

    class Repository:
        def __init__(self): self.rows = {}
        def get(self, ident): return copy.deepcopy(self.rows.get(ident))
        def save(self, row): self.rows[row['id']] = copy.deepcopy(row)
        def list_all(self): return copy.deepcopy(list(self.rows.values()))

    repo = Repository()
    registry = NodeRegistry(repository=repo)
    original = NodeInfo(node_id='permanent-peer', node_state_val='CONNECTED',
        fingerprint='pinned-fingerprint', public_identity={'node_id':'permanent-peer', 'public_key_hex':'pinned-key'},
        granted_capabilities=['compute'], capabilities=['compute'], last_heartbeat=1,
        connection_metadata={'kingdom_endpoint':'http://127.0.0.1:18014'}).to_dict()
    repo.save(original)
    monkeypatch.setattr(heartbeat.time, 'time', lambda: 1000)
    registry.check_stale_heartbeats()
    offline = repo.get('permanent-peer')
    assert offline['node_state'] == 'DISCONNECTED'
    for key in ('fingerprint','public_identity','granted_capabilities','connection_metadata'):
        assert offline[key] == original[key]

    # Rebuild from persisted records, as on restart. No invitation or approval.
    restarted = NodeRegistry(repository=repo)
    monkeypatch.setattr(heartbeat, 'node_registry', restarted)
    assert heartbeat.HeartbeatManager().ping('permanent-peer')['success']
    online = repo.get('permanent-peer')
    assert online['node_state'] == 'CONNECTED'
    for key in ('fingerprint','public_identity','granted_capabilities','connection_metadata'):
        assert online[key] == original[key]
