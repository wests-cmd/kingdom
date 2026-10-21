import copy
import json
import pytest
from backend.cluster.release_status import ReleaseReport, ReleasePreferences, local_release, reconciliation
from backend.cluster.apprentice_inventory import validate_inventory, aggregate_inventories
from backend.storage.db import Database


def release(**changes):
    return {'version':'1.2.1','revision':'a'*40,'source_sha256':'b'*64,'artifact_sha256':'c'*64,
            'source_scope':'backend-python-and-built-ui-v1','update_adapter':'unknown','source_evidence':'unknown',**changes}


@pytest.mark.parametrize('key,value',[('revision','main'),('artifact_sha256','https://code'),('source_sha256','x'),('source_scope','anything'),('version','bad\nlabel')])
def test_release_metadata_rejects_unbounded_or_mutable_values(key,value):
    with pytest.raises(ValueError):ReleaseReport.model_validate(release(**{key:value}))


def test_signed_inventory_roundtrip_keeps_release_but_not_grants():
    raw={'version':1,'apprentices':[],'release':release(),'granted_capabilities':['system.admin']}
    clean=validate_inventory(raw)
    assert clean['release']==release() and 'granted_capabilities' not in clean
    peer={'node_id':'peer','node_state':'CONNECTED','last_heartbeat':100,
          'connection_metadata':{'apprentice_inventory':{'received_at':100,'report':clean}}}
    current=aggregate_inventories([],[peer],now=101)['reports'][0]
    assert current['release']==release()
    assert aggregate_inventories([],[peer],now=160)['reports'][0]['release'] is None


@pytest.mark.parametrize('report,fresh,expected',[
    (release(),True,'current'),(release(revision='d'*40),True,'update_required'),
    (release(artifact_sha256='d'*64),True,'update_required'),
    (release(source_sha256='d'*64),True,'update_required'),
    (release(revision=None),True,'unknown'),(None,True,'unknown'),(release(),False,'stale')])
def test_exact_approved_release_comparison(report,fresh,expected):
    assert reconciliation(report,release(),fresh)==expected


def test_desired_release_persists_for_future_peers_without_granting_updates(tmp_path):
    database=Database(tmp_path/'state.db');events=[]
    preferences=ReleasePreferences(database,lambda *args:events.append(args))
    preferences.set({**release(),'auto_reconcile':True})
    restored=ReleasePreferences(database,lambda *args:None)
    assert restored.get()['auto_reconcile'] is True
    status=restored.status([{'node_id':'new-peer','node_state':'CONNECTED','last_heartbeat':100}],now=101)
    assert status['knights'][1]['status']=='unknown'
    assert status['auto_install_supported'] is False
    assert events[0][0]=='cluster.desired_release_changed'


def test_local_source_fingerprint_changes_on_real_edit_and_manifest_is_optional(tmp_path,monkeypatch):
    monkeypatch.delenv('KINGDOM_RELEASE_MANIFEST',raising=False)
    monkeypatch.delenv('KINGDOM_KNIGHT_UPDATE_PROFILE',raising=False)
    (tmp_path/'backend').mkdir();source=tmp_path/'backend/main.py';source.write_text('a=1',encoding='utf-8')
    first=local_release(tmp_path)
    assert first['revision'] is None and first['artifact_sha256'] is None
    assert first['update_adapter']=='absent'
    source.write_text('a=2',encoding='utf-8')
    assert local_release(tmp_path)['source_sha256']!=first['source_sha256']
    manifest=tmp_path/'release.json';manifest.write_text(json.dumps(release()),encoding='utf-8')
    monkeypatch.setenv('KINGDOM_RELEASE_MANIFEST',str(manifest))
    observed=local_release(tmp_path)
    assert observed['revision']=='a'*40 and observed['artifact_sha256']=='c'*64
    assert observed['source_sha256']!='b'*64  # Metadata cannot replace observed file bytes.


def test_release_status_owner_only_and_desired_validated(monkeypatch,tmp_path):
    from backend.main import app
    from fastapi.testclient import TestClient
    from tests.auth_support import owner_client
    from backend.cluster import hierarchy_api
    monkeypatch.setattr(hierarchy_api,'release_preferences',ReleasePreferences(Database(tmp_path/'api.db'),lambda *args:None))
    assert TestClient(app).get('/hierarchy/releases').status_code==401
    client=owner_client(app)
    assert client.put('/hierarchy/releases/desired',json=release()).status_code==200
    assert client.put('/hierarchy/releases/desired',json=release(source_sha256='branch')).status_code==422



def test_python_line_endings_normalized_but_ui_bytes_remain_exact(tmp_path,monkeypatch):
    monkeypatch.delenv('KINGDOM_RELEASE_MANIFEST',raising=False)
    (tmp_path/'backend').mkdir();source=tmp_path/'backend/main.py'
    source.write_bytes(b'def f():\n    return 1\n')
    first=local_release(tmp_path)
    source.write_bytes(b'def f():\r\n    return 1\r\n')
    assert local_release(tmp_path)['source_sha256']==first['source_sha256']
    assert first['source_evidence']=='observed_files'
    ui=tmp_path/'frontend/dist';ui.mkdir(parents=True)
    (ui/'blob.bin').write_bytes(b'\x00\r\n\xff')
    with_binary=local_release(tmp_path)['source_sha256']
    (ui/'blob.bin').write_bytes(b'\x00\n\xff')
    assert local_release(tmp_path)['source_sha256']!=with_binary


def test_frozen_build_manifest_reports_build_inputs_not_observed_source_or_installer(tmp_path,monkeypatch):
    import sys
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'_MEIPASS',str(tmp_path),raising=False)
    missing=local_release()
    assert missing['source_sha256'] is None and missing['source_evidence']=='unknown'
    # An external environment manifest cannot impersonate the bundled build proof.
    external=tmp_path/'external.json';external.write_text(json.dumps(release()),encoding='utf-8')
    monkeypatch.setenv('KINGDOM_RELEASE_MANIFEST',str(external))
    assert local_release()['source_sha256'] is None
    (tmp_path/'kingdom-release.json').write_text(json.dumps(release()),encoding='utf-8')
    installed=local_release()
    assert installed['source_sha256']=='b'*64 and installed['revision']=='a'*40
    assert installed['source_evidence']=='build_input_manifest'
    assert installed['artifact_sha256'] is None
