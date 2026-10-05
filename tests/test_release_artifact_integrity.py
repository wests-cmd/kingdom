"""The publication gate rejects tampered downloads and incomplete platforms."""
import json
import pytest
from scripts.release_artifacts import INVENTORY, digest, verify


def inventory(tmp_path):
    for platform, names in INVENTORY.items():
        artifacts = []
        evidence = tmp_path / f"{platform}-desktop-evidence.json"
        evidence.write_text(json.dumps({"version": "1.0.0", "platform": {
            "linux": "linux", "windows": "win32", "macos": "darwin"}[platform]}))
        artifacts.append({"filename": evidence.name, "size": evidence.stat().st_size,
                          "sha256": digest(evidence), "platform": platform, "arch": "x86_64"})
        for template in names:
            name = template.format(version="1.0.0")
            file = tmp_path / name
            file.write_bytes(b"test fixture bytes")
            artifacts.append({"filename": name, "size": file.stat().st_size,
                              "sha256": digest(file), "platform": platform, "arch": "x86_64"})
        (tmp_path / f"{platform}-manifest.json").write_text(json.dumps({
            "version": "1.0.0", "tag": "v1.0.0", "commit": "source-commit",
            "platform": platform, "artifacts": artifacts}))


def test_downloaded_artifact_tampering_blocks_publication(tmp_path):
    inventory(tmp_path)
    (tmp_path / "Kingdom-Setup-1.0.0.exe").write_bytes(b"tampered data bytes")
    with pytest.raises(AssertionError):
        verify(tmp_path, "1.0.0", "source-commit")


def test_missing_platform_blocks_publication(tmp_path):
    inventory(tmp_path)
    (tmp_path / "macos-manifest.json").unlink()
    with pytest.raises(FileNotFoundError):
        verify(tmp_path, "1.0.0", "source-commit")


def test_foreign_commit_blocks_publication(tmp_path):
    inventory(tmp_path)
    with pytest.raises(AssertionError):
        verify(tmp_path, "1.0.0", "different-commit")


def test_release_manifest_exposes_centipede_and_kingdom_contracts(tmp_path):
    inventory(tmp_path)
    verify(tmp_path, "1.0.0", "source-commit")
    release = json.loads((tmp_path / "release-manifest.json").read_text())
    assert release["version"] == "v1TAS"
    assert release["release_version"] == "1.0.0"
    assert release["kingdom_version"] == "1.0.0"
    assert release["contract_version"] == "1.4.0"
    assert release["protocol"] == {"major": 1, "minor": 4}
    assert release["protocol_version"] == "kingdom.cluster.v1"
    assert "process.execute" in release["capabilities"]
