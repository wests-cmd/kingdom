from fastapi.testclient import TestClient
from backend.security.http_auth import owner_auth

def owner_client(app):
    client = TestClient(app, headers={"Authorization": "Bearer " + owner_auth.token})
    response = client.post("/auth/session")
    assert response.status_code == 200
    return client
