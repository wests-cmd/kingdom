import pytest
from backend.memory.tiered_vault import TieredVault,VaultUnavailable
from backend.storage.db import Database


def make(tmp_path,budget=8192):
    root=tmp_path/'archive';root.mkdir();(root/'.kingdom-vault-id').write_text('owned-drive')
    service=TieredVault(Database(tmp_path/'local/state.db'),root=root,vault_id='owned-drive',cache_bytes=budget)
    return service,root


def test_missing_media_keeps_scoped_cache_and_refuses_writes(tmp_path):
    vault,root=make(tmp_path)
    vault.put('p','remember this',ident='a')
    moved=root.rename(tmp_path/'unplugged')
    assert not vault.status()['online']
    cached=vault.get('p','a')
    assert cached['body']=='remember this' and cached['cache']['offline']
    assert vault.search('p','remember')[0]['id']=='a'
    assert vault.search('other','remember')==[]
    with pytest.raises(VaultUnavailable):vault.put('p','cannot write',ident='b')
    assert not root.exists()
    moved.rename(root)
    assert 'cache' not in vault.get('p','a') and vault.status()['online']


def test_wrong_drive_is_never_written_and_cache_is_limited(tmp_path):
    vault,root=make(tmp_path,600)
    for i in range(6):vault.put('p','x'*100,ident=str(i))
    assert vault.status()['cache_bytes']<=600
    assert vault.status()['cache_documents']<6
    (root/'.kingdom-vault-id').write_text('different-drive')
    with pytest.raises(VaultUnavailable):vault.put('p','bad',ident='wrong')
    assert vault.status()['online'] is False


def test_deletion_and_revision_conflicts_do_not_resurrect_cache(tmp_path):
    vault,root=make(tmp_path)
    vault.put('p','first',ident='a')
    with pytest.raises(ValueError):vault.put('p','wrong',ident='a',expected_revision=0)
    vault.trash('p','a',1)
    root.rename(tmp_path/'removed')
    with pytest.raises(VaultUnavailable):vault.get('p','a')


def test_local_default_and_invalid_cache_configuration(tmp_path):
    db=Database(tmp_path/'state.db');vault=TieredVault(db,cache_bytes=0)
    vault.put('p','first',ident='a')
    assert vault.get('p','a')['body']=='first' and vault.status()['cache_bytes']==0
    with pytest.raises(ValueError):TieredVault(db,cache_bytes=True)
    with pytest.raises(ValueError):TieredVault(db,root=tmp_path/'missing')
