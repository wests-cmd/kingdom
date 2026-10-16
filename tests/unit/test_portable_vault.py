from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from backend.storage.db import Database
from backend.memory.portable_vault import PortableVault


def test_round_trip_stable_scope_provenance_receipts_and_secret_exclusion(tmp_path):
    source = PortableVault(Database(tmp_path/'source.db'))
    document = source.put('kingdom', 'Cluster evidence\napi_key=do-not-share\nghp_abcdefghijklmno',
        {'source': 'reviewed:mission-1', 'token': 'private', 'origin': {'password': 'hidden'}}, ['receipt:task-1'], ident='stable-1')
    files = source.export('kingdom')
    serialized = json.dumps(files)
    for secret in ['do-not-share', 'abcdefghijklmno', 'private', 'hidden']:
        assert secret not in serialized
    target_db = Database(tmp_path/'target.db')
    target = PortableVault(target_db)
    assert target.import_files('kingdom', files)['imported'] == ['stable-1']
    assert target.import_files('kingdom', files)['unchanged'] == 1
    restored = PortableVault(target_db).get('kingdom', 'stable-1')
    assert restored == document
    assert restored['receipts'] == ['receipt:task-1']
    assert restored['provenance']['source'] == 'reviewed:mission-1'
    assert restored['trust'] == 'untrusted'
    with pytest.raises(KeyError):
        target.get('other', 'stable-1')
    with pytest.raises(ValueError):
        target.import_files('other', files)


def test_atomic_import_rejects_tamper_traversal_and_identity_conflict(tmp_path):
    source = PortableVault(Database(tmp_path/'source.db'))
    source.put('project', 'first', ident='a')
    source.put('project', 'second', ident='b')
    files = source.export('project')
    target = PortableVault(Database(tmp_path/'target.db'))
    tampered = {**files, 'b.md': files['b.md']+'tampered'}
    with pytest.raises(ValueError):
        target.import_files('project', tampered)
    assert target.export('project') == {}
    with pytest.raises(ValueError):
        target.import_files('project', {'../a.md': files['a.md']})
    target.put('project', 'existing different', ident='b')
    with pytest.raises(ValueError):
        target.import_files('project', files)
    with pytest.raises(KeyError):
        target.get('project', 'a')


def test_concurrent_expected_revision_and_derived_index_rebuild(tmp_path):
    database = Database(tmp_path/'vault.db')
    services = [PortableVault(database), PortableVault(database)]
    services[0].put('p', 'initial', ident='id')
    def update(index):
        try:
            return services[index].put('p', f'changed{index}', ident='id', expected_revision=1)
        except ValueError:
            return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(update, range(2)))
    assert sum(result is not None for result in results) == 1
    persisted = PortableVault(database).get('p', 'id')
    assert persisted['revision'] == 2
    with database.get_connection() as conn:
        conn.execute('DELETE FROM portable_vault_index')
        conn.commit()
    assert services[0].search('p', persisted['body']) == []
    assert services[1].rebuild_index('p') == 1
    assert services[0].search('p', persisted['body'])[0] == persisted
    assert services[0].search('other', persisted['body']) == []


def test_configured_export_directory_is_contained_and_never_overwrites(tmp_path):
    service = PortableVault(Database(tmp_path/'vault.db'))
    service.put('p', 'data', ident='doc')
    root = tmp_path/'exports'
    service.export_directory('p', root)
    assert (root/'p'/'doc.md').is_file()
    with pytest.raises(FileExistsError):
        service.export_directory('p', root)
    with pytest.raises(ValueError):
        service.export_directory('../outside', root)
