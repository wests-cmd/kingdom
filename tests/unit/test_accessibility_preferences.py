from fastapi.testclient import TestClient
from backend.main import app
from backend import accessibility
from backend.storage.db import Database
from backend.storage.integration_repository import IntegrationRepository
from tests.auth_support import owner_client


def test_preferences_require_owner_and_persist_without_authority_changes(tmp_path, monkeypatch):
    database = Database(tmp_path/'preferences.sqlite3')
    repository = IntegrationRepository(database)
    monkeypatch.setattr(accessibility, 'repository', repository)
    public = TestClient(app)
    assert public.get('/preferences/accessibility').status_code == 401
    assert public.put('/preferences/accessibility', json={'scale':200}).status_code in (401,403)
    client = owner_client(app)
    assert client.get('/preferences/accessibility').json() == {'preferences':None}
    repository.put('sentinel','authority',{'grants':[],'approvals':False})
    response=client.put('/preferences/accessibility',json={'scale':200,'contrast':'high','targets':'large','motion':'reduced'})
    assert response.status_code==200
    saved=response.json()['preferences']
    assert saved['scale']==200 and saved['contrast']=='high'
    restarted=IntegrationRepository(Database(tmp_path/'preferences.sqlite3'))
    assert restarted.get('presentation_preferences','owner')==saved
    assert restarted.get('sentinel','authority')=={'grants':[],'approvals':False}
    for invalid in [{'scale':999},{'accent':'red; background:url(evil)'},{'grants':['system.admin']},{'approved':True}]:
        assert client.put('/preferences/accessibility',json=invalid).status_code==422
    assert client.get('/preferences/accessibility').json()['preferences']==saved
