from pathlib import Path

import pytest

from backend.cluster.identity import KingdomIdentity
from backend.cluster.identity_migration import migrate_identity
from backend.storage.db import Database


@pytest.fixture
def installation(tmp_path):
    db=Database(tmp_path/'test.db')
    path=tmp_path/'identity.json'
    identity=KingdomIdentity();identity.save_to_file(str(path))
    with db.get_connection() as conn:
        conn.execute("INSERT INTO knights(id,role,status,health,last_heartbeat,created_at,updated_at,is_local,kingdom_id) VALUES('local','worker','idle','healthy',0,0,0,1,?)",(identity.node_id,));conn.commit()
    return db,path,identity


def test_migration_preserves_signatures_and_local_references(installation):
    db,path,identity=installation
    signature=identity.sign_message(b'proof')
    result=migrate_identity(db,identity.node_id,'KG-independent',str(path))
    updated=KingdomIdentity.load_from_file(str(path))
    assert updated.node_id=='KG-independent' and updated.fingerprint==identity.fingerprint
    assert updated.verify_signature(updated.public_bytes.hex(),b'proof',signature)
    assert KingdomIdentity.load_from_file(result['backup']).node_id==identity.node_id
    with db.get_connection() as conn:
        assert conn.execute("SELECT kingdom_id FROM knights WHERE id='local'").fetchone()[0]=='KG-independent'


def test_any_remote_registration_blocks_rename_without_altering_identity(installation):
    db,path,identity=installation
    original=path.read_bytes()
    with db.get_connection() as conn:
        conn.execute("INSERT INTO knights(id,role,status,health,last_heartbeat,created_at,updated_at,is_local) VALUES('remote','worker','idle','healthy',0,0,0,0)");conn.commit()
    with pytest.raises(ValueError,match='remote node'):
        migrate_identity(db,identity.node_id,'KG-new',str(path))
    assert path.read_bytes()==original


def test_stale_expected_identity_rejected(installation):
    db,path,_=installation
    with pytest.raises(ValueError,match='current identity changed'):
        migrate_identity(db,'KG-wrong','KG-new',str(path))


def test_active_task_prevents_identity_change(installation):
    db,path,identity=installation
    with db.get_connection() as conn:
        conn.execute("INSERT INTO tasks(id,type,status,created_at,updated_at) VALUES('running','generic','running',0,0)");conn.commit()
    with pytest.raises(ValueError,match='active tasks'):
        migrate_identity(db,identity.node_id,'KG-new',str(path))
    assert KingdomIdentity.load_from_file(str(path)).node_id==identity.node_id


def test_migration_api_requires_owner():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.cluster.federation_api import router
    app=FastAPI();app.include_router(router)
    response=TestClient(app).post('/federation/identity/migrate',json={'expected_id':'KG-MASTER-01'})
    assert response.status_code in {401,403}


def test_failed_file_swap_rolls_back_database(installation,monkeypatch):
    db,path,identity=installation
    original=path.read_bytes()
    def fail(*args):raise OSError('storage failure')
    monkeypatch.setattr('backend.cluster.identity_migration.os.replace',fail)
    with pytest.raises(OSError):migrate_identity(db,identity.node_id,'KG-new',str(path))
    assert path.read_bytes()==original
    with db.get_connection() as conn:
        assert conn.execute("SELECT kingdom_id FROM knights WHERE id='local'").fetchone()[0]==identity.node_id
