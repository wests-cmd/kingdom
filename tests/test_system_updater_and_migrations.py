"""
Tests for System Updater Engine, SHA-256 Checksum Verification, Backup Creation, and Rollback.
"""

import pytest
import os
import shutil
import hashlib
from backend.system.updater import UpdaterEngine
from backend.system.migrator import run_migrations


def test_updater_check_updates():
    updater = UpdaterEngine(current_version="40.1.0")
    manifest = {
        "latest_version": "40.2.0",
        "release_channel": "stable",
        "release_date": "2026-09-10",
        "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "download_url": "https://releases.kingdom.network/v40.2.0/kingdom-v40.2.0.tar.gz"
    }
    res = updater.check_updates(manifest)
    assert res["update_available"] is True
    assert res["latest_version"] == "40.2.0"


def test_checksum_verification():
    updater = UpdaterEngine()
    data = b"Kingdom v40.2.0 production release package content"
    expected_hash = hashlib.sha256(data).hexdigest()

    assert updater.verify_checksum(data, expected_hash) is True
    assert updater.verify_checksum(data, "0000000000000000000000000000000000000000000000000000000000000000") is False


def test_backup_and_rollback(tmp_path):
    updater = UpdaterEngine(current_version="40.2.0")

    # 1. Source Data Directory
    source_dir = tmp_path / "data_source"
    source_dir.mkdir()
    (source_dir / "kingdom.db").write_text("sqlite database content")

    # 2. Backup Directory
    backup_root = tmp_path / "backups"
    backup_path = updater.backup_data(str(source_dir), str(backup_root))
    assert os.path.exists(backup_path)
    assert os.path.exists(os.path.join(backup_path, "kingdom.db"))

    # 3. Simulate Data Corruption
    (source_dir / "kingdom.db").write_text("corrupted database content")

    # 4. Rollback
    restore_target = tmp_path / "restored_data"
    rolled_back = updater.rollback(backup_path, str(restore_target))
    assert rolled_back is True
    assert (restore_target / "kingdom.db").read_text() == "sqlite database content"


def test_schema_migrator():
    # Verify migration runner executes without error
    try:
        run_migrations()
        migration_success = True
    except Exception:
        migration_success = False
    assert migration_success is True
