import copy
from types import SimpleNamespace
import pytest
from backend.cluster.shared_groups import SharedGroups,remap,validate_snapshot
from backend.cluster.team_editing import version
from backend.cluster.hierarchy import CommandHierarchy
from backend.cluster.node_registry import NodeInfo
from backend.storage.db import Database


def setup(tmp_path):
    db=Database(tmp_path/'groups.db')
    nodes=[NodeInfo(n,fingerprint=n,public_identity={'node_id':n}) for n in ('first','second')]
    registry=SimpleNamespace(list_nodes=lambda:nodes,get_node=lambda ident:next((n for n in nodes if n.node_id==ident),None))
    mesh=SimpleNamespace(identity=SimpleNamespace(node_id='authority'),registry=registry,config=lambda:{'authority_id':'authority'})
    hierarchy=CommandHierarchy(db,registry,lambda *a:None)
    return SharedGroups(mesh,hierarchy),hierarchy,nodes


def test_two_views_have_same_group_identity_and_canonical_revision(tmp_path):
    shared,hierarchy,_=setup(tmp_path)
    before=shared.local_snapshot()
    after=shared.receive('first',{'request_id':'one','edit':{'version':before['version'],
        'operation':'save','name':'Together','members':['authority','first','second'],'captain':'first'}})['snapshot']
    assert after['groups'][0]['members']==['authority','first','second']
    assert hierarchy.groups()[0]['members']==['local','first','second']
    follower=SharedGroups(SimpleNamespace(identity=SimpleNamespace(node_id='first')),hierarchy)
    view=follower.view(after)
    assert view['groups'][0]['members']==['authority','local','second']
    assert view['version']==shared.view(after)['version']
    assert view['groups'][0]['id']==shared.view(after)['groups'][0]['id']
    assert all(n.granted_capabilities==[] for n in shared.mesh.registry.list_nodes())


def test_stale_remote_save_and_revoked_peer_are_denied(tmp_path):
    shared,hierarchy,nodes=setup(tmp_path);old=shared.local_snapshot()
    edit={'version':old['version'],'operation':'save','name':'A','members':['first'],'captain':'first'}
    shared.receive('first',{'request_id':'one','edit':edit})
    with pytest.raises(ValueError,match='changed'):shared.receive('second',{'request_id':'two','edit':edit})
    nodes[0].node_state_val='REVOKED'
    with pytest.raises(PermissionError):shared.receive('first',{'request_id':'three','edit':None})
    assert len(hierarchy.groups())==1


def test_follower_cannot_become_authority_when_connection_is_missing(tmp_path):
    shared,_,_=setup(tmp_path);shared.mesh.config=lambda:{'authority_id':'someone-else'}
    with pytest.raises(ValueError):shared.local_snapshot()
    with pytest.raises(ValueError):shared.receive('first',{'request_id':'one','edit':None})


@pytest.mark.parametrize('mutation', ['version','local','duplicate'])
def test_replica_rejects_tampered_or_relative_identity_snapshot(mutation):
    g={'id':'group','name':'A','captain':'first','members':['first']}
    snapshot={'authority_id':'authority','groups':[g],'version':version([g])}
    validate_snapshot(snapshot)
    if mutation=='version':snapshot['version']='0'*64
    elif mutation=='local':g['captain']='local';g['members']=['local'];snapshot['version']=version([g])
    else:snapshot['groups'].append(copy.deepcopy(g));snapshot['version']=version(snapshot['groups'])
    with pytest.raises(ValueError):validate_snapshot(snapshot)
