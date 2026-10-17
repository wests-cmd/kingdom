import copy
import pytest
from backend.cluster.apprentice_inventory import aggregate_inventories, validate_inventory


def report(*ids):
    return {'version': 1, 'apprentices': [{'id': ident, 'role': 'coder', 'display_name': 'Coding', 'status': 'ready', 'active': 0} for ident in ids]}


def peer(ident='peer', state='CONNECTED', received=100):
    return {'node_id': ident, 'node_state': state, 'last_heartbeat': 100,
            'connection_metadata': {'apprentice_inventory': {'received_at': received, 'report': report('coder')}}}


def test_identity_scoped_counts_do_not_deduplicate_roles_across_kingdoms():
    result = aggregate_inventories([{'id': 'coder'}], [peer('a'),peer('b'),peer('a')], now=101)
    assert result['total_current'] == 3
    assert {row['scoped_id'] for row in result['remote_apprentices']} == {'a/coder','b/coder'}
    assert result['complete']


@pytest.mark.parametrize('state', ['DISCONNECTED','REVOKED','REJECTED','QUARANTINED','PENDING_APPROVAL'])
def test_noncurrent_peer_does_not_contribute_to_live_total(state):
    result=aggregate_inventories([{}], [peer(state=state)], now=101)
    assert result['remote_count']==0 and not result['complete']


@pytest.mark.parametrize('received', [0, 200, '100', None])
def test_stale_future_or_invalid_receipt_is_not_current(received):
    assert not aggregate_inventories([], [peer(received=received)], now=101)['complete']


def test_missing_report_and_explicit_zero_are_distinct():
    missing=peer();missing['connection_metadata']={}
    zero=peer();zero['connection_metadata']['apprentice_inventory']['report']=report()
    assert aggregate_inventories([], [missing], now=101)['reports'][0]['state']=='missing'
    assert aggregate_inventories([], [zero], now=101)['complete']


@pytest.mark.parametrize('bad', [None, {}, {'version': True, 'apprentices': []}, report('duplicate','duplicate'),report(*[str(i) for i in range(129)])])
def test_malformed_or_inflated_report_rejected(bad):
    with pytest.raises(ValueError):validate_inventory(bad)


@pytest.mark.parametrize('key,value',[('status',[]),('active',True),('id','../escape'),('display_name','bad\nlabel')])
def test_invalid_worker_fields_rejected(key,value):
    data=report('coder');data['apprentices'][0][key]=value
    with pytest.raises(ValueError):validate_inventory(data)


def test_report_does_not_import_permissions_or_nested_inventory():
    data=report('coder');data['apprentices'][0].update(granted_capabilities=['system.admin'],apprentices=[{'id':'invented'}],api_key='private')
    assert validate_inventory(data)==report('coder')


def test_signed_report_metadata_survives_reconnect_without_changing_grants(monkeypatch):
    from backend.cluster.node_registry import node_registry, NodeInfo
    from backend.cluster.heartbeat import HeartbeatManager
    stored=NodeInfo(node_id='peer',node_state_val='DISCONNECTED',last_heartbeat=1,granted_capabilities=['compute']).to_dict()
    monkeypatch.setattr(node_registry.repo,'get',lambda ident:copy.deepcopy(stored))
    monkeypatch.setattr(node_registry.repo,'save',lambda data:stored.update(copy.deepcopy(data)))
    monkeypatch.setattr('backend.cluster.heartbeat.time.time',lambda:100)
    assert HeartbeatManager().ping('peer',apprentice_inventory=report('coder'))['success']
    assert stored['granted_capabilities']==['compute']
    assert aggregate_inventories([], [stored], now=101)['total_current']==1
