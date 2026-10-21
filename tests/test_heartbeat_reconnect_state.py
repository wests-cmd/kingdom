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
