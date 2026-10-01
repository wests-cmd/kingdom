from backend.main import app
from tests.auth_support import owner_client
from .test_discord_skillmap_workflow import workflow, import_map


def test_rejected_upload_does_not_echo_input_or_credentials():
    client = owner_client(app)
    value = 'controlled-sensitive-upload-value'
    response = client.post('/skillmaps/preview',json={'filename':'map.json','content':{},'token':value})
    assert response.status_code == 422
    assert value not in response.text and 'input' not in response.text


def test_owner_only_integration_routes_and_disabled_discord():
    from fastapi.testclient import TestClient
    client = TestClient(app)
    for url in ['/skillmaps','/profiles/preferences','/providers/catalog','/discord/links']:
        assert client.get(url).status_code == 401
    assert client.post('/discord/interactions',json={}).status_code == 503


def test_download_is_authenticated_canonical_attachment(workflow, monkeypatch):
    import hashlib
    from backend.skills import portable_api
    service, _ = workflow
    monkeypatch.setattr(portable_api,'service',service)
    import_map(service)
    response = owner_client(app).get('/skillmaps/product-research/download')
    assert response.status_code == 200
    assert response.content == service.export('owner','product-research')['payload']
    assert response.headers['x-content-sha256'] == hashlib.sha256(response.content).hexdigest()
    assert response.headers['content-disposition'] == 'attachment; filename="product-research.skillmap.json"'
    from fastapi.testclient import TestClient
    assert TestClient(app).get('/skillmaps/product-research/download').status_code == 401
