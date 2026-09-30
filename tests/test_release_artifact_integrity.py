"""The publication gate rejects tampered downloads and incomplete platforms."""
import json
import pytest
from scripts.release_artifacts import INVENTORY, digest, verify


def inventory(tmp_path):
    for platform, names in INVENTORY.items():
        artifacts = []
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
