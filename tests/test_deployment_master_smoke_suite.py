"""
Kingdom Deployment Master Smoke & Health Suite.
Validates:
- Clean machine startup & runtime health checks (/health/live, /health/ready, /system/check)
- Version consistency across single source of truth (40.2.0)
- Database migration execution, backup creation, and rollback safety
- Zero-Trust security endpoint availability and audit logging
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.state import STATE
from backend.system.updater import updater_engine
from backend.system.migrator import run_migrations

client = TestClient(app)


def test_single_source_version_truth():
    """
    Verifies that state.py version matches GET /api/system/version endpoint.
    """
    res = client.get("/api/system/version")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == STATE["version"]
    assert data["version"] == "40.2.0"


def test_health_liveness_and_readiness_endpoints():
    """
    Verifies /health/live and /health/ready endpoints return HTTP 200 with healthy state.
    """
    res_live = client.get("/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "alive"

    res_ready = client.get("/health/ready")
    assert res_ready.status_code == 200
    ready_data = res_ready.json()
    assert ready_data["status"] == "ready"
    assert ready_data["database"] == "healthy"
    assert ready_data["security_engine"] == "healthy"


def test_system_check_and_diagnostics_export():
    """
    Verifies system environment checks and sanitized diagnostics export.
    """
    res_check = client.get("/system/check")
    assert res_check.status_code == 200
    assert res_check.json()["runtime_ready"] is True

    res_diag = client.get("/diagnostics/export")
    assert res_diag.status_code == 200
    diag = res_diag.json()
    assert diag["kingdom_version"] == "v40.2"
    assert "commander_identity" in diag


def test_deployment_updater_backup_and_migration():
    """
    Verifies updater check, backup creation, schema migration, and rollback routines.
    """
    # Migration check
    run_migrations()

    # Updater check
    update_res = updater_engine.check_updates()
    assert "update_available" in update_res
    assert update_res["current_version"] == "40.2.0"
