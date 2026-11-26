import pytest
from pydantic import ValidationError
from backend.cluster.map_layout import MapLayouts,LayoutConflict,LayoutUpdate
from backend.storage.db import Database


def test_map_positions_survive_restart_and_views_are_independent(tmp_path):
    db=Database(tmp_path/'map.db')
    store=MapLayouts(db)
    assert store.read('teams')=={'view':'teams','version':0,'positions':{}}
    body={'version':0,'positions':{'knight:local':{'x':64,'y':128},'frame:team':{'x':0,'y':0,'w':500,'h':300}}}
    saved=store.save('teams',body)
    assert saved['version']==1
    assert MapLayouts(db).read('teams')==saved
    assert store.read('network')['positions']=={}
    with pytest.raises(LayoutConflict):store.save('teams',body)
    assert store.read('teams')==saved


@pytest.mark.parametrize('body',[
    {'version':True,'positions':{}},
    {'version':0,'positions':{'knight:local':{'x':True,'y':0}}},
    {'version':0,'positions':{'knight:local':{'x':-1,'y':0}}},
    {'version':0,'positions':{'knight:local':{'x':0,'y':100001}}},
    {'version':0,'positions':{'knight:local':{'x':0,'y':0,'role':'owner'}}},
    {'version':0,'positions':{'invalid':{'x':0,'y':0}}},
    {'version':0,'positions':{'frame:test':{'x':0,'y':0,'w':20001}}},
    {'version':0,'positions':{f'knight:{i}':{'x':0,'y':0} for i in range(1001)}},
    {'version':0,'positions':{},'permissions':['compute']},
])
def test_invalid_layout_fails_without_mutation(tmp_path,body):
    store=MapLayouts(Database(tmp_path/'map.db'))
    with pytest.raises(ValidationError):store.save('network',body)
    assert store.read('network')['version']==0


def test_owner_layout_api_does_not_change_membership_or_reporting(monkeypatch,tmp_path):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.cluster import hierarchy_api
    from backend.cluster.hierarchy import CommandHierarchy
    from types import SimpleNamespace
    from tests.auth_support import owner_client
    hierarchy=CommandHierarchy(Database(tmp_path/'api.db'),SimpleNamespace(list_nodes=lambda:[]),lambda *a:None)
    monkeypatch.setattr(hierarchy_api,'hierarchy',hierarchy)
    monkeypatch.setattr(hierarchy_api.engine.swarm.registry,'status',lambda:[])
    body={'version':0,'positions':{'knight:local':{'x':160,'y':96},'knight:removed':{'x':0,'y':0}}}
    assert TestClient(app).put('/hierarchy/map-layout/network',json=body).status_code in (401,403)
    client=owner_client(app)
    before=hierarchy.export([])
    assert client.put('/hierarchy/map-layout/network',json=body).status_code==200
    assert client.put('/hierarchy/map-layout/network',json=body).status_code==409
    assert client.get('/hierarchy/map-layout/network').json()['positions']==body['positions']
    assert client.get('/hierarchy/map-layout/invalid').status_code==422
    after=hierarchy.export([])
    assert before['topology']==after['topology'] and before['groups']==after['groups']
    assert all(n['id']!='removed' for n in after['topology']['nodes'])
