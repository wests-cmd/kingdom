from types import SimpleNamespace
import pytest
from backend.storage.db import Database
from backend.cluster.hierarchy import CommandHierarchy
from backend.cluster.node_registry import NodeInfo


def setup(tmp_path):
    nodes=[NodeInfo(name,fingerprint=name,public_identity={'node_id':name}) for name in ('leader','worker')]
    events=[]
    db=Database(tmp_path/'teams.db')
    hierarchy=CommandHierarchy(db,SimpleNamespace(list_nodes=lambda:nodes),lambda *args:events.append(args))
    return hierarchy, db, nodes, events


def test_team_preferences_persist_without_grants_and_delete(tmp_path):
    hierarchy,db,nodes,events=setup(tmp_path)
    before=[list(node.granted_capabilities) for node in nodes]
    team=hierarchy.create_group(' Review ', 'leader',['leader','worker'],['battery sensitive'],['documentation'])
    reopened=CommandHierarchy(db,hierarchy.registry,lambda *args:None)
    assert reopened.groups()==[team]
    assert team['name']=='Review' and team['preference_scope']=='planning_only'
    assert hierarchy.authorize_assignment('leader',team['id'],'worker')==team
    assert [node.granted_capabilities for node in nodes]==before
    hierarchy.delete_group(team['id'])
    assert reopened.groups()==[]
    with pytest.raises(PermissionError): hierarchy.authorize_assignment('leader',team['id'],'worker')
    assert events[-1]==('hierarchy.group_deleted',{'group_id':team['id']})
    with pytest.raises(ValueError): hierarchy.delete_group(team['id'])


@pytest.mark.parametrize('labels',[[''],['x']*2,['x'*81],list(map(str,range(13)))])
def test_team_labels_are_bounded(tmp_path,labels):
    hierarchy,*_=setup(tmp_path)
    with pytest.raises(ValueError): hierarchy.create_group('Team','leader',['leader'],flags=labels)
    with pytest.raises(ValueError): hierarchy.create_group('Team','leader',['leader'],preferred_task_types=labels)


def test_revoked_computer_cannot_be_team_leader(tmp_path):
    hierarchy,_,nodes,_=setup(tmp_path)
    nodes[0].node_state_val='REVOKED'
    with pytest.raises(ValueError): hierarchy.create_group('Team','leader',['leader','worker'])


def test_capability_removal_is_read_back_and_blocks_execution(tmp_path,monkeypatch):
    from backend.cluster import capabilities
    from backend.cluster.hierarchy import offload_candidate
    hierarchy,_,nodes,_=setup(tmp_path)
    node=nodes[0]
    import time
    node.last_heartbeat=time.time()
    node.health='healthy'
    node.status='APPROVED'
    node.granted_capabilities=['compute']
    node.connection_metadata={'load_metrics':{'cpu_percent':1,'memory_percent':1,'power':{'source':'ac','battery_percent':100,'charging':True}}}
    persisted=[]
    registry=SimpleNamespace(list_nodes=lambda:[node],get_node=lambda ident:node if ident==node.node_id else None,repo=SimpleNamespace(save=lambda value:persisted.append(value)))
    monkeypatch.setattr(capabilities,'node_registry',registry)
    monkeypatch.setattr(capabilities,'event_bus',SimpleNamespace(publish=lambda *args,**kwargs:None))
    assert capabilities.CapabilityAuthorizer.is_capability_granted(node.node_id,'compute')
    result=capabilities.CapabilityAuthorizer.update_capabilities(node.node_id,[])
    assert result['granted_capabilities']==[] and persisted[-1]['granted_capabilities']==[]
    assert not capabilities.CapabilityAuthorizer.is_capability_granted(node.node_id,'compute')
    assert offload_candidate(registry,'compute') is None

