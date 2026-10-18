import pytest
from backend.memory.portable_vault import PortableVault
from backend.memory.tiered_vault import TieredVault
from backend.memory.vault_policy import placement
from backend.storage.db import Database


def test_coding_retrieval_cannot_read_payment_role_notes_online_or_offline(tmp_path):
    root=tmp_path/'archive';root.mkdir();(root/'.kingdom-vault-id').write_text('vault')
    vault=TieredVault(Database(tmp_path/'local.db'),root=root,vault_id='vault')
    vault.put('p','invoice provider reference',ident='private',allowed_roles=['payment'])
    vault.put('p','invoice renderer source',ident='public')
    for offline in (False,True):
        if offline:root.rename(tmp_path/'removed')
        assert [doc['id'] for doc in vault.search('p','invoice',reader_role='coder')]==['public']
        assert {doc['id'] for doc in vault.search('p','invoice',reader_role='payment')}=={'private','public'}
        assert [doc['id'] for doc in vault.search('p','invoice')]==['public']


def test_role_restriction_survives_portable_export_import(tmp_path):
    vault=PortableVault(Database(tmp_path/'notes.db'))
    vault.put('p','restricted note',ident='a',allowed_roles=['payment'])
    files=vault.export('p')
    vault.import_files('p',files)
    assert vault.search('p','restricted',reader_role='coder')==[]
    vault.put('p','restricted edited note',ident='a',expected_revision=1)
    assert vault.search('p','restricted',reader_role='coder')==[]


@pytest.mark.parametrize('body,metadata',[('test 4111 1111 1111 1111',{}),('CVV: 123',{}),('note',{'cvv':'123'}),('note',{'card':'4111111111111111'})])
def test_payment_details_rejected_before_storage(tmp_path,body,metadata):
    vault=PortableVault(Database(tmp_path/'notes.db'))
    with pytest.raises(ValueError):vault.put('p',body,provenance=metadata)
    assert vault.export('p')=={}


def test_single_and_balanced_placement_are_generic_and_exclude_offline_nodes():
    nodes=[{'id':'a','available':True,'free_bytes':100,'used_bytes':0}]
    assert placement('note',nodes)['archive_knights']==['a']
    nodes.extend([{'id':'b','available':True,'free_bytes':90,'used_bytes':10},{'id':'c','available':False,'free_bytes':1000}])
    assert placement('note',nodes,'balanced',copies=2)['archive_knights']==['a','b']
    assert placement('note',nodes,'central',central_id='b')['archive_knights']==['b']
    with pytest.raises(ValueError):placement('note',nodes,'central',central_id='c')
