"""Owner can inspect the real service graph; anonymous callers cannot."""
from tests.auth_support import owner_client
from fastapi.testclient import TestClient

from backend.main import app


def test_authenticated_service_graph_exposed_without_credentials():
    result = owner_client(app).get("/system/services")
    assert result.status_code == 200
    data = result.json()
    assert "services" in data
    assert "scheduler" in data
    assert "schedules" in data["services"]
    assert "peer_connections" in data["services"]
    assert "kingdom_session" not in str(data)
    assert "owner-token" not in str(data)


def test_anonymous_service_graph_requires_owner():
    result = TestClient(app).get("/system/services")
    assert result.status_code in {401, 403}
