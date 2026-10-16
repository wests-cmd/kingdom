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
