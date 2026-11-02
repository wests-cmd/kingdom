"""Tests ensuring all Gap Register API endpoints strictly enforce owner authentication boundary."""
from fastapi.testclient import TestClient
from backend.main import app
from backend.security.http_auth import require_owner


def test_gap_api_routes_require_owner_authentication():
    # Clear any dependency overrides to test raw authentication requirements
    app.dependency_overrides.pop(require_owner, None)
    client = TestClient(app)

    # 1. GET list
    res_list = client.get("/system/gap-register")
    assert res_list.status_code in (401, 403)

    # 2. GET single
    res_get = client.get("/system/gap-register/autonomous-planning")
    assert res_get.status_code in (401, 403)

    # 3. PUT evidence
    res_put = client.put(
        "/system/gap-register/autonomous-planning/evidence",
        json={"test_evidence": "test", "status": "verified"}
    )
    assert res_put.status_code in (401, 403)

    # 4. POST sync-backlog
    res_sync = client.post("/system/gap-register/sync-backlog")
    assert res_sync.status_code in (401, 403)
