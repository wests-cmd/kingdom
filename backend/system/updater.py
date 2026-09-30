"""Verified release discovery and offline transactional server installation.

Native desktop upgrades use the published installer. This engine never claims
that changing version metadata updates an installed desktop application.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
import uuid
import urllib.request
from packaging.version import Version
from backend.state import STATE

RELEASES_URL = "https://api.github.com/repos/wests-cmd/kingdom/releases/latest"

class UpdaterEngine:
    def __init__(self, current_version=None):
        self.current_version = current_version or STATE.get("version", "1.0.0")

    def check_updates(self, manifest=None):
        if manifest is None:
            try:
                request = urllib.request.Request(RELEASES_URL, headers={"Accept":"application/vnd.github+json", "User-Agent":"Kingdom-release-check"})
                with urllib.request.urlopen(request, timeout=5) as response:
                    release = json.loads(response.read(1024 * 1024))
                if release.get("draft") or release.get("prerelease"):
                    raise ValueError("No stable published release")
                manifest = {"latest_version": release["tag_name"].removeprefix("v"), "release_channel":"stable",
                            "release_url": release["html_url"], "assets": [{"name":a["name"], "size":a["size"], "download_url":a["browser_download_url"]} for a in release.get("assets",[])]}
                if not manifest["assets"]:
                    raise ValueError("Published release contains no downloadable artifacts")
            except Exception as exc:
                return {"update_available":False, "current_version":self.current_version,
                        "latest_version":None, "manifest":None, "status":"unavailable", "error":str(exc)}
        latest = Version(manifest["latest_version"])
        available = latest > Version(self.current_version) and not latest.is_prerelease and manifest.get("release_channel", "stable") == "stable"
        return {"update_available":available, "current_version":self.current_version, "latest_version":str(latest), "manifest":manifest}

    def verify_checksum(self, file_content, expected_hash):
        return isinstance(expected_hash, str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash)) and hashlib.sha256(file_content).hexdigest() == expected_hash.lower()

    @staticmethod
    def _disjoint(source, destination):
        source, destination = Path(source).resolve(), Path(destination).resolve()
        if source == destination or source in destination.parents or destination in source.parents:
            raise ValueError("Backup and installation paths must be disjoint")
        if source == Path(source.anchor) or destination == Path(destination.anchor):
            raise ValueError("Filesystem roots cannot be installation targets")
        return source, destination

    def backup_data(self, source_dir, backup_dir):
        source, root = self._disjoint(source_dir, backup_dir)
        root.mkdir(parents=True, exist_ok=True)
        target = root / ("backup_" + uuid.uuid4().hex)
        shutil.copytree(source, target, symlinks=True)
        return str(target)

    def rollback(self, backup_path, restore_path):
        backup, target = self._disjoint(backup_path, restore_path)
        if not backup.is_dir():
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / (target.name + ".restore-" + uuid.uuid4().hex)
        shutil.copytree(backup, temporary, symlinks=True)
        failed = target.parent / (target.name + ".failed-" + uuid.uuid4().hex)
        if target.exists():
            target.rename(failed)
        try:
            temporary.rename(target)
        except Exception:
            if failed.exists():
                failed.rename(target)
            raise
        if failed.exists():
            shutil.rmtree(failed)
        return True

    def _extract_verified(self, artifact, stage, version):
        with tarfile.open(fileobj=io.BytesIO(artifact), mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) > 20000 or sum(m.size for m in members) > 1024 * 1024 * 1024:
                raise ValueError("Update archive exceeds installation limits")
            seen = set()
            for member in members:
                name = member.name
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise ValueError("Unsafe update archive entry")
                normalized = str(path)
                if normalized.casefold() in seen:
                    raise ValueError("Duplicate update archive entry")
                seen.add(normalized.casefold())
                target = stage.joinpath(*path.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(member.mode & 0o755)
        metadata = json.loads((stage / "install-manifest.json").read_text())
        if metadata.get("version") != version or metadata.get("format") != "kingdom.server.install.v1":
            raise ValueError("Installation manifest version or format mismatch")
        actual = {p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()} - {"install-manifest.json"}
        files = metadata.get("files")
        if not isinstance(files, dict) or not files or actual != set(files):
            raise ValueError("Installation file inventory mismatch")
        for filename, digest in files.items():
            if not self.verify_checksum((stage / filename).read_bytes(), digest):
                raise ValueError("Installed file checksum mismatch")

    def execute_update_pipeline(self, target_version, artifact_bytes, expected_checksum, data_dir="data", backup_dir=None, health_check_fn=None, migration_fn=None):
        target = Path(data_dir).resolve()
        old_version = self.current_version
        stage = None
        backup = None
        activated = False
        try:
            if Version(target_version) <= Version(old_version) or Version(target_version).is_prerelease:
                raise ValueError("Update must advance to a stable version")
            if not self.verify_checksum(artifact_bytes, expected_checksum):
                raise ValueError("Checksum verification failed")
            if not callable(health_check_fn):
                raise ValueError("A real post-installation health check is required")
            root = Path(backup_dir).resolve() if backup_dir else target.parent / (target.name + "-backups")
            self._disjoint(target, root)
            if not target.is_dir() or target.is_symlink():
                raise ValueError("An existing installation directory is required")
            stage = Path(tempfile.mkdtemp(prefix=target.name + ".stage-", dir=target.parent))
            self._extract_verified(artifact_bytes, stage, target_version)
            backup = self.backup_data(target, root)
            prior = target.parent / (target.name + ".prior-" + uuid.uuid4().hex)
            target.rename(prior)
            try:
                stage.rename(target)
                stage = None
                activated = True
            except Exception:
                prior.rename(target)
                raise
            shutil.rmtree(prior)
            if migration_fn:
                migration_fn(target)
            if health_check_fn() is not True:
                raise RuntimeError("Post-update health check failed")
            self.current_version = target_version
            return {"status":"success", "version":target_version, "backup_path":backup}
        except Exception as exc:
            if activated and backup:
                self.rollback(backup, target)
                return {"status":"rolled_back", "version":old_version, "backup_restored":backup, "error":str(exc)}
            return {"status":"failed", "version":old_version, "error":str(exc)}
        finally:
            if stage is not None and stage.exists():
                shutil.rmtree(stage)

updater_engine = UpdaterEngine()
def check_updates():
    return updater_engine.check_updates()
