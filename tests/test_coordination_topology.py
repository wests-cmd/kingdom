import pytest
from backend.storage.db import Database
from backend.cluster.topology import CoordinationTopology, TopologyConflict

NODES = [{'id': 'pc', 'default_parent': 'kingdom'}, {'id': 'pc/coder', 'default_parent': 'pc'}]


def test_saved_lines_survive_restart_and_publish(tmp_path):
    db = Database(tmp_path/'graph.db')
    events = []
    graph = CoordinationTopology(db, lambda *event: events.append(event))
    result = graph.save(0, {'pc': 'kingdom', 'pc/coder': 'kingdom'}, NODES)
    assert result['version'] == 1
    assert CoordinationTopology(db, lambda *a: None).read(NODES)['parents']['pc/coder'] == 'kingdom'
    assert events[0][0] == 'hierarchy.topology_saved'
    with pytest.raises(TopologyConflict): graph.save(0, result['parents'], NODES)


@pytest.mark.parametrize('parents', [
    {'pc': 'pc/coder', 'pc/coder': 'pc'},
    {'pc': 'pc', 'pc/coder': 'pc'},
    {'pc': 'unknown', 'pc/coder': 'pc'},
    {'pc': 'kingdom'},
    {'pc': 'kingdom', 'pc/coder': 'pc', 'injected': 'kingdom'},
])
def test_invalid_graph_never_changes_version(tmp_path, parents):
    graph = CoordinationTopology(Database(tmp_path/'graph.db'), lambda *a: None)
    with pytest.raises(ValueError): graph.save(0, parents, NODES)
    assert graph.read(NODES)['version'] == 0


def test_removed_node_is_not_resurrected(tmp_path):
    graph = CoordinationTopology(Database(tmp_path/'graph.db'), lambda *a: None)
    graph.save(0, {'pc': 'kingdom', 'pc/coder': 'pc'}, NODES)
    assert graph.read(NODES[1:])['parents'] == {'pc/coder': 'kingdom'}


def test_owner_api_and_optimistic_conflict(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.cluster import hierarchy_api
    from backend.cluster.hierarchy import CommandHierarchy
    from types import SimpleNamespace
    from tests.auth_support import owner_client
    hierarchy = CommandHierarchy(Database(tmp_path/'api.db'), SimpleNamespace(list_nodes=lambda: []), lambda *a: None)
    monkeypatch.setattr(hierarchy_api, 'hierarchy', hierarchy)
    monkeypatch.setattr(hierarchy_api.engine.swarm.registry, 'status', lambda: [])
    body = {'version': 0, 'parents': {'local': 'kingdom'}}
    assert TestClient(app).put('/hierarchy/topology', json=body).status_code in (401,403)
    client = owner_client(app)
    assert client.put('/hierarchy/topology', json=body).status_code == 200
    assert client.put('/hierarchy/topology', json=body).status_code == 409
    assert client.get('/hierarchy').json()['topology']['version'] == 1


def test_revocation_removes_coordinator_without_erasing_audit_record(tmp_path):
    from types import SimpleNamespace
    from backend.cluster.hierarchy import CommandHierarchy
    node=SimpleNamespace(node_id='revoked-pc',hostname='Former Knight',is_local=False,
                         public_identity={'node_id':'revoked-pc'},fingerprint='old',node_state='REVOKED')
    node.to_dict=lambda: {'node_id':node.node_id,'node_state':node.node_state}
    hierarchy=CommandHierarchy(Database(tmp_path/'revoked.db'),SimpleNamespace(list_nodes=lambda:[node]),lambda *a:None)
    snapshot=hierarchy.export([])
    assert snapshot['knights']==[]
    assert snapshot['archived_knights']==[node.to_dict()]
    assert [n['id'] for n in snapshot['topology']['nodes']]==['local']
