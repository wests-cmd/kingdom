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
    updater = UpdaterEngine(current_version="0.9.0")
    manifest = {
        "latest_version": "1.0.0",
        "release_channel": "stable",
        "release_date": "2026-09-10",
        "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "download_url": "https://releases.kingdom.network/v1.0.0/kingdom-v1.0.0.tar.gz"
    }
    res = updater.check_updates(manifest)
    assert res["update_available"] is True
    assert res["latest_version"] == "1.0.0"


def test_checksum_verification():
    updater = UpdaterEngine()
    data = b"Kingdom v1.0.0 production release package content"
    expected_hash = hashlib.sha256(data).hexdigest()

    assert updater.verify_checksum(data, expected_hash) is True
    assert updater.verify_checksum(data, "0000000000000000000000000000000000000000000000000000000000000000") is False


def test_backup_and_rollback(tmp_path):
    updater = UpdaterEngine(current_version="1.0.0")

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


def test_execute_update_pipeline_success_and_automatic_rollback(tmp_path):
    import io, json, tarfile
    target = tmp_path / "installed"
    target.mkdir()
    (target / "old-only.txt").write_text("old")
    (target / "app.py").write_text("old application")
    content = b"actual new application"
    manifest = json.dumps({"format":"kingdom.server.install.v1", "version":"1.0.1", "files":{"app.py":hashlib.sha256(content).hexdigest(), "new-only.txt":hashlib.sha256(b"new").hexdigest()}}).encode()
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, body in [("app.py",content), ("new-only.txt", b"new"), ("install-manifest.json",manifest)]:
            info = tarfile.TarInfo(name); info.size=len(body)
            archive.addfile(info, io.BytesIO(body))
    artifact = output.getvalue()
    checksum = hashlib.sha256(artifact).hexdigest()
    updater = UpdaterEngine(current_version="1.0.0")
    options = dict(target_version="1.0.1", artifact_bytes=artifact, data_dir=str(target), backup_dir=str(tmp_path / "backups"))
    assert updater.execute_update_pipeline(**options, expected_checksum="invalid")["status"] == "failed"
    assert updater.execute_update_pipeline(**options, expected_checksum=checksum)["status"] == "failed"
    def unhealthy():
        assert (target / "app.py").read_bytes() == content
        assert (target / "new-only.txt").exists()
        assert not (target / "old-only.txt").exists()
        return False
    failure = updater.execute_update_pipeline(**options, expected_checksum=checksum, health_check_fn=unhealthy)
    assert failure["status"] == "rolled_back"
    assert (target / "old-only.txt").read_text() == "old"
    assert (target / "app.py").read_text() == "old application"
    assert not (target / "new-only.txt").exists()
    success = updater.execute_update_pipeline(**options, expected_checksum=checksum, health_check_fn=lambda: (target / "app.py").read_bytes() == content)
    assert success["status"] == "success"
    assert updater.current_version == "1.0.1"


def test_backup_cannot_recurse_into_source(tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    with pytest.raises(ValueError, match="disjoint"):
        UpdaterEngine().backup_data(source, source / "backups")


def test_rollback_removes_files_introduced_by_failed_update(tmp_path):
    source = tmp_path / "old"; source.mkdir(); (source / "original").write_text("original")
    updater = UpdaterEngine()
    backup = updater.backup_data(source, tmp_path / "backups")
    (source / "introduced").write_text("must disappear")
    assert updater.rollback(backup, source)
    assert not (source / "introduced").exists()


def test_release_discovery_never_downgrades():
    result = UpdaterEngine("1.0.1").check_updates({"latest_version":"1.0.0", "release_channel":"stable"})
    assert result["update_available"] is False
