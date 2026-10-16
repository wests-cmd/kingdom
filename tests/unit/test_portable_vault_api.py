from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.storage.db import Database
from backend.security.http_auth import require_owner
from backend.memory import portable_vault_api
from backend.runtime import automation_api
from backend.runtime.durable_automation import DurableAutomations


def test_vault_http_requires_owner_and_preserves_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(portable_vault_api, 'service', portable_vault_api.PortableVault(Database(tmp_path/'vault.db')))
    app = FastAPI()
    app.include_router(portable_vault_api.router)
    with TestClient(app) as client:
        assert client.get('/vault/p/export').status_code in (401, 403)
        app.dependency_overrides[require_owner] = lambda: 'owner'
        created = client.post('/vault/p/documents', json={'body': 'Evidence', 'id': 'stable', 'receipts': ['receipt:1']})
        assert created.status_code == 200
        files = client.get('/vault/p/export').json()['files']
        assert client.post('/vault/other/import', json={'files': files}).status_code == 409
        assert client.get('/vault/other/search?query=Evidence').json()['documents'] == []
        assert client.post('/vault/p/documents', json={'body': 'Changed', 'id': 'stable'}).status_code == 409
        assert client.post('/vault/p/documents', json={'body': 'Changed', 'id': 'stable', 'expected_revision': 1}).status_code == 200
        assert client.post('/vault/p/rebuild-index').json()['indexed'] == 1


def test_schedule_http_owner_cancel_and_receipts(tmp_path, monkeypatch):
    service = DurableAutomations(Database(tmp_path/'schedules.db'), clock=lambda: 100)
    monkeypatch.setattr(automation_api, 'scheduled', service)
    app = FastAPI()
    app.include_router(automation_api.router)
    with TestClient(app) as client:
        assert client.post('/automations/schedules/tick').status_code in (401, 403)
        app.dependency_overrides[require_owner] = lambda: 'owner'
        response = client.post('/automations/schedules', json={'project': 'p', 'body': 'note', 'interval_sec': 60})
        assert response.status_code == 200
        schedule = response.json()
        assert len(client.post('/automations/schedules/tick').json()['completed']) == 1
        assert client.post('/automations/schedules/tick').json()['completed'] == []
        ident = schedule['id']
        assert client.get(f'/automations/schedules/other/{ident}/receipts').status_code == 404
        assert len(client.get(f'/automations/schedules/p/{ident}/receipts').json()['receipts']) == 1
        current = client.get('/automations/schedules/p').json()['schedules'][0]
        assert client.post(f'/automations/schedules/p/{ident}/status', json={'status': 'cancelled', 'expected_revision': current['revision']}).status_code == 200
