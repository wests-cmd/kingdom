from fastapi.testclient import TestClient
from backend.main import app

def test_manifest_and_worker_are_public_without_private_cache():
    client=TestClient(app)
    manifest=client.get('/kingdom.webmanifest')
    assert manifest.status_code==200
    assert manifest.json()['display']=='standalone'
    assert manifest.json()['scope']=='/'
    assert manifest.json()['icons'][0]['sizes']=='512x512'
    worker=client.get('/kingdom-sw.js')
    assert worker.status_code==200
    assert worker.headers['cache-control']=='no-store'
    assert worker.headers['service-worker-allowed']=='/'
    assert 'caches.open' not in worker.text and 'respondWith' not in worker.text
    assert 'fetch' in worker.text
