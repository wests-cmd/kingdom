import time
from types import SimpleNamespace
import pytest
from backend.storage.db import Database
from backend.cluster.node_registry import NodeInfo
from backend.cluster.hierarchy import CommandHierarchy


def make(tmp_path):
    nodes=[NodeInfo(str(i),fingerprint=str(i),public_identity={'node_id':str(i)}) for i in range(5)]
    db=Database(tmp_path/'groups.db');events=[]
    service=CommandHierarchy(db,SimpleNamespace(list_nodes=lambda:nodes),lambda *a:events.append(a))
    return service,nodes,events


def change(service,operation,**kwargs):
    return service.edit_groups(service.group_version(),operation,**kwargs)


def test_bulk_move_is_confirmed_atomic_and_repairs_previous_leader(tmp_path):
    service,nodes,events=make(tmp_path)
    a=service.create_group('A','0',['0','1','2'])
    b=service.create_group('B','3',['3','4'])
    before=service.groups()
    with pytest.raises(ValueError,match='confirm'):
        change(service,'save',group_ids=[b['id']],name='B',captain='3',members=['0','1','3','4'])
    assert service.groups()==before
    change(service,'save',group_ids=[b['id']],name='B',captain='3',members=['0','1','3','4'],move=True)
    groups={g['id']:g for g in service.groups()}
    assert groups[a['id']]['members']==['2'] and groups[a['id']]['captain']=='2'
    assert len(groups[b['id']]['members'])==4
    assert all(node.granted_capabilities==[] for node in nodes)
    assert events[-1][0]=='hierarchy.groups_changed'


def test_combine_split_extra_in_first_and_stale_revision_rejected(tmp_path):
    service,_,_=make(tmp_path)
    a=service.create_group('A','0',['0','1','2'])
    b=service.create_group('B','3',['3','4'])
    old=service.group_version()
    change(service,'combine',group_ids=[a['id'],b['id']],name='Together')
    group=service.groups()[0]
    assert len(group['members'])==5
    with pytest.raises(ValueError,match='changed'):
        service.edit_groups(old,'remove',group_ids=[group['id']])
    change(service,'split',group_ids=[group['id']],names=['First','Second'])
    groups=service.groups()
    first=next(g for g in groups if g['name']=='First')
    second=next(g for g in groups if g['name']=='Second')
    assert len(first['members'])==3 and len(second['members'])==2
    assert set(first['members']).isdisjoint(second['members'])


def test_offline_archive_range_return_and_trust_preserved(tmp_path):
    service,nodes,_=make(tmp_path)
    nodes[0].last_heartbeat=time.time()-8*86400
    nodes[0].node_state_val='DISCONNECTED'
    result=service.visible_computers()
    assert nodes[0] not in result and nodes[1] in result
    service.set_visibility(240)
    assert nodes[0] in service.visible_computers()
    service.set_visibility(12)
    assert nodes[0] not in service.visible_computers()
    nodes[0].last_heartbeat=time.time()
    nodes[0].node_state_val='CONNECTED'
    assert nodes[0] in service.visible_computers()
    assert nodes[0].public_identity and nodes[0].fingerprint
    for hours in (11,241,True,float('nan')):
        with pytest.raises(ValueError):service.set_visibility(hours)


def test_local_knight_can_be_grouped_and_revoked_knight_cannot(tmp_path):
    service,nodes,_=make(tmp_path)
    change(service,'save',name='Local team',captain='local',members=['local','0'])
    assert service.groups()[0]['captain']=='local'
    nodes[1].node_state_val='REVOKED'
    with pytest.raises(ValueError):change(service,'save',name='Bad',captain='1',members=['1'])


def test_group_api_is_owner_only_and_timeout_bounds_are_strict(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.cluster import hierarchy_api
    from backend.security.http_auth import require_owner
    service,_,_=make(tmp_path)
    monkeypatch.setattr(hierarchy_api,'hierarchy',service)
    app=FastAPI();app.include_router(hierarchy_api.router)
    with TestClient(app) as client:
        assert client.put('/hierarchy/visibility',json={'offline_hours':12}).status_code in {401,403,503}
        app.dependency_overrides[require_owner]=lambda:'owner'
        for hours in (11,241,True,12.5):
            assert client.put('/hierarchy/visibility',json={'offline_hours':hours}).status_code==422
        assert client.put('/hierarchy/visibility',json={'offline_hours':12}).status_code==200
        response=client.post('/hierarchy/groups/edit',json={'version':service.group_version(),
            'operation':'save','name':'Test','captain':'0','members':['0','1']})
        assert response.status_code==200 and len(response.json()['groups'])==1
