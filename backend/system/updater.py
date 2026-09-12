import os
import hashlib
import json
import shutil
import time
from typing import Dict, Any, Optional
from backend.state import STATE

class UpdaterEngine:
    def __init__(self, current_version: str = None):
        self.current_version = current_version or STATE.get("version", "40.2.0")

    def check_updates(self, manifest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not manifest:
            manifest = {
                "latest_version": "40.2.0",
                "release_channel": "stable",
                "release_date": "2026-09-10",
                "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "download_url": "https://releases.kingdom.network/v40.2.0/kingdom-v40.2.0.tar.gz",
                "release_notes": "Kingdom v40.2.0 Stable Release Candidate"
            }

        latest_ver = manifest.get("latest_version", self.current_version)
        update_available = latest_ver != self.current_version

        return {
            "update_available": update_available,
            "current_version": self.current_version,
            "latest_version": latest_ver,
            "manifest": manifest
        }

    def verify_checksum(self, file_content: bytes, expected_hash: str) -> bool:
        computed_hash = hashlib.sha256(file_content).hexdigest()
        return computed_hash.lower() == expected_hash.lower()

    def backup_data(self, source_dir: str, backup_dir: str) -> str:
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = int(time.time())
        target_path = os.path.join(backup_dir, f"backup_{self.current_version}_{timestamp}")
        shutil.copytree(source_dir, target_path, dirs_exist_ok=True)
        return target_path

    def rollback(self, backup_path: str, restore_path: str) -> bool:
        if os.path.exists(backup_path):
            shutil.copytree(backup_path, restore_path, dirs_exist_ok=True)
            return True
        return False

updater_engine = UpdaterEngine()

def check_updates():
    return updater_engine.check_updates()
