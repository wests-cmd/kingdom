"""Tests for the Persistent Gap Register backend and API endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.system.gap_register import INITIAL_CAPABILITIES


from backend.security.http_auth import require_owner


@pytest.fixture(autouse=True)
def override_owner_auth():
    app.dependency_overrides[require_owner] = lambda: {"role": "owner"}
    yield
    app.dependency_overrides.pop(require_owner, None)


def test_gap_register_seeding_and_list():
    client = TestClient(app)
    response = client.get("/system/gap-register")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "summary" in data
    assert data["summary"]["total"] == len(INITIAL_CAPABILITIES)
    assert data["summary"]["total"] == 14

    # Verify key P0 entries exist
    item_map = {item["id"]: item for item in data["items"]}
    assert "autonomous-planning" in item_map
    assert "multi-model-routing" in item_map
    assert "acp-tool-adapters" in item_map
    assert "autonomous-coding" in item_map
    assert "independent-verification" in item_map
    assert "self-repair" in item_map
    assert "persistent-memory" in item_map
    assert "recovery-after-restart" in item_map
    assert "swarm-administration" in item_map
    assert "security-isolation" in item_map


def test_gap_register_get_and_update_evidence():
    client = TestClient(app)
    get_res = client.get("/system/gap-register/autonomous-planning")
    assert get_res.status_code == 200
    entry = get_res.json()
    assert entry["capability"] == "Autonomous planning"
    assert entry["priority"] == "P0"

    # Update evidence
    update_res = client.put(
        "/system/gap-register/autonomous-planning/evidence",
        json={
            "test_evidence": "tests/test_gap_register.py (verified by test suite)",
            "status": "verified"
        }
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["status"] == "verified"
    assert "test_gap_register.py" in updated["test_evidence"]

    # Re-fetch and check persistence
    re_get = client.get("/system/gap-register/autonomous-planning")
    assert re_get.status_code == 200
    assert re_get.json()["status"] == "verified"


def test_gap_register_not_found():
    client = TestClient(app)
    res = client.get("/system/gap-register/non-existent-capability")
    assert res.status_code == 404

    put_res = client.put(
        "/system/gap-register/non-existent-capability/evidence",
        json={"test_evidence": "some test", "status": "verified"}
    )
    assert put_res.status_code == 404


def test_gap_register_auth_required():
    app.dependency_overrides.pop(require_owner, None)
    client = TestClient(app)
    res = client.get("/system/gap-register")
    assert res.status_code in (401, 403)


def test_sync_backlog_endpoint():
    client = TestClient(app)
    res = client.post("/system/gap-register/sync-backlog")
    assert res.status_code == 200
    data = res.json()
    assert "synced_count" in data
    assert "items" in data
