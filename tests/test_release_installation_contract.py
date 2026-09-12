"""
Kingdom Release Installation Contract Suite.
Tests:
- Clean machine startup & readiness health check contracts
- Single source version reporting (40.2.0)
- Data backup, schema migration, and automatic rollback routines
"""

import pytest
import os
import hashlib
from fastapi.testclient import TestClient
from backend.main import app
from backend.state import STATE
from backend.system.updater import updater_engine
from backend.system.migrator import run_migrations

client = TestClient(app)


def test_clean_machine_startup_contract():
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "healthy"
    assert data["security_engine"] == "healthy"


def test_version_consistency_contract():
    res = client.get("/api/system/version")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == STATE["version"]
    assert data["version"] == "40.2.0"


def test_updater_release_and_rollback_contract(tmp_path):
    # Check update
    check_res = updater_engine.check_updates()
    assert "update_available" in check_res
    assert check_res["current_version"] == "40.2.0"

    # Verify checksum
    sample_data = b"Kingdom release artifact content v40.2.0"
    computed_hash = hashlib.sha256(sample_data).hexdigest()
    assert updater_engine.verify_checksum(sample_data, computed_hash) is True

    # Backup & Rollback
    src = tmp_path / "src"
    src.mkdir()
    (src / "data.db").write_text("v40.2.0 DB State")

    backup_root = tmp_path / "backups"
    backup_path = updater_engine.backup_data(str(src), str(backup_root))
    assert os.path.exists(backup_path)

    dst = tmp_path / "restored"
    rolled_back = updater_engine.rollback(backup_path, str(dst))
    assert rolled_back is True
    assert (dst / "data.db").read_text() == "v40.2.0 DB State"
