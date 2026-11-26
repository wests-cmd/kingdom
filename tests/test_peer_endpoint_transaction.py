"""Owner route changes cannot resurrect revoked peers or overwrite grants."""
import time
import pytest

from backend.storage.db import Database
from backend.storage.repository import KnightRepository


@pytest.fixture
def peer(tmp_path):
    repo = KnightRepository(Database(tmp_path / 'route.db'))
    identity = {'node_id':'peer', 'node_type':'commander', 'fingerprint':'pinned',
                'public_key_hex':'ab'*32}
    repo.save({'id':'peer', 'role':'commander', 'status':'CONNECTED',
               'node_state':'CONNECTED', 'is_local':False, 'public_identity':identity,
               'fingerprint':'pinned', 'capabilities':['compute'],
               'granted_capabilities':['compute'], 'current_task':'active-task',
               'connection_metadata':{'kingdom_endpoint':'https://old.example',
                                      'mesh_authority':'authority', 'load_metrics':{'cpu_percent':20}}})
    return repo, identity


def test_route_update_preserves_current_security_and_work_state(peer):
    repo, identity = peer
    before = repo.get('peer')
    with repo.db.get_connection() as conn:
        conn.execute("UPDATE knights SET granted_capabilities_json='[]', last_heartbeat=? WHERE id='peer'",
                     (123456,))
        conn.commit()
    assert repo.set_peer_endpoint('peer', identity, 'https://new.example') == 'https://new.example'
    after = repo.get('peer')
    assert after['granted_capabilities'] == []
    assert after['last_heartbeat'] == 123456
    assert after['current_task'] == before['current_task']
    assert after['public_identity'] == identity
    assert after['connection_metadata'] == {**before['connection_metadata'],
                                            'kingdom_endpoint':'https://new.example'}


@pytest.mark.parametrize('state', ['REVOKED','QUARANTINED','REJECTED','PENDING_APPROVAL'])
def test_restricted_peer_cannot_be_restored_by_old_route_edit(peer, state):
    repo, identity = peer
    with repo.db.get_connection() as conn:
        conn.execute("UPDATE knights SET node_state=?, status=?, granted_capabilities_json='[]' WHERE id='peer'",
                     (state,state))
        conn.commit()
    assert repo.set_peer_endpoint('peer', identity, 'https://new.example') is None
    after = repo.get('peer')
    assert after['node_state'] == state
    assert after['granted_capabilities'] == []
    assert after['connection_metadata']['kingdom_endpoint'] == 'https://old.example'


def test_changed_identity_denies_route_update(peer):
    repo, identity = peer
    assert repo.set_peer_endpoint('peer', {**identity,'public_key_hex':'cd'*32}, 'https://new.example') is None


def test_expired_membership_denies_route_update(peer):
    import json
    repo, identity = peer
    meta = {**repo.get('peer')['connection_metadata'], 'membership_expires_at': time.time()-1}
    with repo.db.get_connection() as conn:
        conn.execute("UPDATE knights SET connection_metadata_json=? WHERE id='peer'", (json.dumps(meta),))
        conn.commit()
    assert repo.set_peer_endpoint('peer', identity, 'https://new.example') is None
