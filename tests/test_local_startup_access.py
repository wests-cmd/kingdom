import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.security import local_access
from backend.storage.db import Database

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(local_access, 'db', Database(tmp_path/'state.db'))
    local_access.attempts.clear()
    app=FastAPI();app.include_router(local_access.router)
    with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1',1234)) as c:
        c.headers['X-Kingdom-Request']='1'
        yield c

def test_direct_open_by_default_and_owner_session(client):
    assert client.post('/auth/local/status').json()=={'passcode_enabled':False}
    result=client.post('/auth/local/session',json={})
    assert result.status_code==200
    assert 'HttpOnly' in result.headers['set-cookie']
    assert client.put('/auth/local/passcode',json={'enabled':False}).status_code==200

def test_passcode_lifecycle_hash_and_throttling(client):
    client.post('/auth/local/session',json={})
    assert client.put('/auth/local/passcode',json={'enabled':True,'new_passcode':'my-private-code'}).status_code==200
    row=local_access.record()
    assert 'my-private-code' not in str(dict(row))
    client.post('/auth/local/lock')
    assert not client.cookies.get('kingdom_session')
    assert client.post('/auth/local/session',json={}).status_code==401
    assert client.post('/auth/local/session',json={'passcode':'my-private-code'}).status_code==200
    assert client.put('/auth/local/passcode',json={'enabled':False,'current_passcode':'wrong'}).status_code==401
    assert client.put('/auth/local/passcode',json={'enabled':False,'current_passcode':'my-private-code'}).status_code==200
    assert client.post('/auth/local/status').json()['passcode_enabled'] is False

def test_remote_rebinding_and_cross_origin_rejected(client):
    for headers in [{'host':'attacker.example'},{'origin':'https://attacker.example'},{'X-Kingdom-Request':''}]:
        assert client.post('/auth/local/session',json={},headers=headers).status_code==403
    with TestClient(client.app,base_url='http://127.0.0.1',client=('100.64.0.2',1234)) as remote:
        assert remote.post('/auth/local/session',json={},headers={'X-Kingdom-Request':'1'}).status_code==403

def test_passcode_required_and_rate_limited(client):
    client.post('/auth/local/session',json={})
    assert client.put('/auth/local/passcode',json={'enabled':True,'new_passcode':'short'}).status_code==422
    client.put('/auth/local/passcode',json={'enabled':True,'new_passcode':'chosen-code'})
    client.post('/auth/local/lock')
    for _ in range(5):
        assert client.post('/auth/local/session',json={'passcode':'incorrect'}).status_code==401
    assert client.post('/auth/local/session',json={'passcode':'chosen-code'}).status_code==429
