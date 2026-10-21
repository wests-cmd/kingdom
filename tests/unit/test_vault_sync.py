import pytest
from backend.storage.db import Database
from backend.memory.portable_vault import PortableVault
from backend.memory.vault_sync import VaultSync, digest
from backend.memory.tiered_vault import TieredVault


def pair(tmp_path):
    a=Database(tmp_path/'a.db');b=Database(tmp_path/'b.db')
    av=PortableVault(a);bv=PortableVault(b)
    source=VaultSync(a,av);target=VaultSync(b,bv)
    source.grant('b','p','send',[]);target.grant('a','p','receive',[])
    return av,bv,source,target


def test_replicates_updates_idempotently_and_retains_project_scope(tmp_path):
    av,bv,source,target=pair(tmp_path)
    av.put('p','first shared note',ident='doc');av.put('private','not shared',ident='secret')
    payload=source.prepare('b','p');assert target.receive('a',payload)['applied']==['doc']
    assert target.receive('a',payload)['replayed'] is True
    assert bv.get('p','doc')['body']=='first shared note'
    assert bv.export('private')=={}
    av.put('p','second shared note',ident='doc',expected_revision=1)
    assert target.receive('a',source.prepare('b','p'))['applied']==['doc']
    assert bv.get('p','doc')['revision']==2
    with pytest.raises(ValueError,match='Historical receipt'):target.receive('a',payload) # No stale success or rollback.
    assert bv.get('p','doc')['body']=='second shared note'


def test_two_sided_grants_and_role_limits_are_mandatory(tmp_path):
    av,bv,source,target=pair(tmp_path)
    av.put('p','payment provider reference',ident='private',allowed_roles=['payment'])
    with pytest.raises(PermissionError):source.prepare('b','p')
    source.grant('b','p','send',['payment']);payload=source.prepare('b','p')
    with pytest.raises(PermissionError):target.receive('a',payload)
    target.grant('a','p','receive',['payment']);target.receive('a',payload)
    assert bv.search('p','payment',reader_role='coder')==[]
    assert bv.search('p','payment',reader_role='payment')[0]['id']=='private'
    target.revoke('a','p','receive')
    with pytest.raises(PermissionError):target.receive('a',payload)


def test_conflict_rolls_back_whole_batch_and_never_restores_trash(tmp_path):
    av,bv,source,target=pair(tmp_path)
    av.put('p','source',ident='a');av.put('p','source',ident='b');target.receive('a',source.prepare('b','p'))
    bv.put('p','owner local edit',ident='b',expected_revision=1)
    av.put('p','new source',ident='a',expected_revision=1);av.put('p','new source',ident='b',expected_revision=1)
    with pytest.raises(ValueError,match='Local edit'):target.receive('a',source.prepare('b','p'))
    assert bv.get('p','a')['body']=='source'
    bv.trash('p','a',1)
    with pytest.raises(ValueError,match='trash'):target.receive('a',source.prepare('b','p',['a']))


def test_tamper_duplicate_project_and_payment_rejected(tmp_path):
    av,bv,source,target=pair(tmp_path);av.put('p','safe',ident='a');payload=source.prepare('b','p')
    payload['documents'][0]['body']='tampered'
    with pytest.raises(ValueError,match='checksum'):target.receive('a',payload)
    payload['documents'][0]['body']='CVV: 123'
    with pytest.raises(ValueError,match='security'):target.receive('a',payload)
    assert bv.export('p')=={}


def test_archive_offline_does_not_replace_or_claim_success(tmp_path):
    av,bv,source,target=pair(tmp_path);av.put('p','safe',ident='a');payload=source.prepare('b','p')
    root=tmp_path/'external';root.mkdir();(root/'.kingdom-vault-id').write_text('one')
    target.vault=TieredVault(target.db,root=root,vault_id='one')
    root.rename(tmp_path/'missing')
    with pytest.raises(OSError):target.receive('a',payload)
    assert not root.exists()


def test_stale_source_revision_rejected_even_with_distinct_batch(tmp_path):
    av,bv,source,target=pair(tmp_path);av.put('p','first',ident='a')
    target.receive('a',source.prepare('b','p'))
    payload=source.prepare('b','p');payload['documents'][0]['body']='stale altered'
    payload['batch']=digest({key:value for key,value in payload.items() if key!='batch'})
    with pytest.raises(ValueError,match='Stale'):target.receive('a',payload)
    assert bv.get('p','a')['body']=='first'

def test_real_signed_transport_detects_tampering_replay_and_revocation(tmp_path,monkeypatch):
    from backend.cluster.identity import BaseNodeIdentity
    from backend.cluster.node_registry import NodeInfo,node_registry
    from backend.cluster.transport import RPCSecureTransport
    import backend.storage.db as storage
    av,bv,source,target=pair(tmp_path)
    sender=BaseNodeIdentity('a','commander');receiver=BaseNodeIdentity('b','commander')
    node=NodeInfo(node_id='a',kingdom_id='b',public_identity=sender.get_public_identity(),node_state_val='APPROVED')
    monkeypatch.setattr(node_registry,'get_node',lambda ident:node if ident=='a' else None)
    monkeypatch.setattr(storage,'db',Database(tmp_path/'transport.db'))
    av.put('p','real Ed25519 proof',ident='one')
    message=RPCSecureTransport(sender).create_signed_message('b','vault_sync_push',source.prepare('b','p'))
    receiver_transport=RPCSecureTransport(receiver)
    verified=receiver_transport.verify_and_unwrap_message(message)
    assert verified['valid'];target.receive(verified['sender_id'],verified['payload'])
    assert bv.get('p','one')['body']=='real Ed25519 proof'
    assert not receiver_transport.verify_and_unwrap_message(message)['valid']
    tampered=RPCSecureTransport(sender).create_signed_message('b','vault_sync_push',source.prepare('b','p'))
    tampered['payload']['documents'][0]['body']='altered'
    assert not receiver_transport.verify_and_unwrap_message(tampered)['valid']
    node.node_state_val='REVOKED'
    assert not receiver_transport.verify_and_unwrap_message(RPCSecureTransport(sender).create_signed_message('b','vault_sync_push',source.prepare('b','p')))['valid']

@pytest.mark.asyncio
async def test_balanced_replication_distributes_bytes_and_chunks_batches(tmp_path,monkeypatch):
    from backend.memory import vault_sync_api as api
    class Vault:
        def export(self,project):return {f'{index}.md':'x'*10000 for index in range(203)}
    class Service:vault=Vault()
    monkeypatch.setattr(api,'service',lambda:Service())
    sent=[]
    async def execute(request):
        sent.append(request)
        return {'status':'replicated','receipt':{'ids':request.ids}}
    monkeypatch.setattr(api,'push_to_peer',execute)
    result=await api.replicate(api.Replicate(project='p',peers=['one','two']))
    assert result['status']=='replicated'
    assert abs(result['assigned_bytes']['one']-result['assigned_bytes']['two'])<=10000
    assert sum(len(request.ids) for request in sent)==203
    assert all(len(request.ids)<=100 for request in sent)
    assert len({ident for request in sent for ident in request.ids})==203

def test_owner_relay_prepares_signs_and_requires_verified_ack_before_success(tmp_path,monkeypatch):
    from fastapi import HTTPException
    from backend.memory import vault_sync_api as api
    from backend.cluster.identity import BaseNodeIdentity
    from backend.cluster.node_registry import NodeInfo,node_registry
    from backend.cluster.transport import RPCSecureTransport
    import backend.storage.db as storage
    av,bv,source,target=pair(tmp_path)
    a=BaseNodeIdentity('a','commander');b=BaseNodeIdentity('b','commander')
    source_node=NodeInfo(node_id='a',public_identity=a.get_public_identity(),node_state_val='APPROVED')
    target_node=NodeInfo(node_id='b',public_identity=b.get_public_identity(),node_state_val='APPROVED')
    monkeypatch.setattr(node_registry,'get_node',lambda ident:{'a':source_node,'b':target_node}.get(ident))
    monkeypatch.setattr(storage,'db',Database(tmp_path/'relay-ledger.db'))
    monkeypatch.setattr(api,'service',lambda:source)
    monkeypatch.setattr(api.KingdomIdentity,'get_or_create',lambda:a)
    av.put('p','relay through an existing owner connection',ident='note')
    prepared=api.prepare_proof(api.Push(peer='b',project='p'))
    assert prepared['status']=='prepared'
    assert source.transfer_status('b',prepared['batch'])['status']=='prepared'
    verified=RPCSecureTransport(b).verify_and_unwrap_message(prepared['proof'])
    assert verified['valid']
    receipt=target.receive(verified['sender_id'],verified['payload'])
    ack=RPCSecureTransport(b).create_signed_message('a','vault_sync_ack',receipt)
    accepted=api.accept_proof(api.AcceptProof(peer='b',project='p',expected_batch=prepared['batch'],proof=ack))
    assert accepted['status']=='replicated'
    assert VaultSync(source.db,av).transfer_status('b',prepared['batch'])['status']=='replicated'
    with pytest.raises(HTTPException) as failure:api.accept_proof(api.AcceptProof(peer='b',project='p',expected_batch=prepared['batch'],proof=ack))
    assert failure.value.status_code==409 and 'signature' in failure.value.detail
    # A valid peer signature still cannot certify an unprepared or incomplete batch.
    receipt={**receipt,'applied':[],'unchanged':[]}
    bad_ack=RPCSecureTransport(b).create_signed_message('a','vault_sync_ack',receipt)
    with pytest.raises(HTTPException) as failure:api.accept_proof(api.AcceptProof(peer='b',project='p',expected_batch=prepared['batch'],proof=bad_ack))
    assert failure.value.status_code==409 and 'identities' in failure.value.detail
    assert bv.get('p','note')['body']=='relay through an existing owner connection'


def test_export_batch_plan_does_not_claim_delivery(tmp_path,monkeypatch):
    from backend.memory import vault_sync_api as api
    av,bv,source,target=pair(tmp_path)
    for index in range(105):av.put('p',f'note {index}',ident=f'doc_{index}')
    monkeypatch.setattr(api,'service',lambda:source)
    monkeypatch.setattr(api,'peer_node',lambda peer:None)
    plan=api.export_batches(api.Push(peer='b',project='p'))
    assert plan['status']=='planned'
    assert [len(batch['ids']) for batch in plan['batches']]==[100,5]
    assert bv.export('p')=={}
