import time
from typing import Dict, Any, Optional
from backend.extensions.models import ExtensionInstance, ExtensionTrustState
from backend.extensions.registry import ExtensionRegistry
from backend.extensions.manifest_validator import ExtensionManifestValidator


class ExtensionLifecycleManager:

    def __init__(self, registry: ExtensionRegistry):
        self.registry = registry
        self.version_history: Dict[str, Dict[str, dict]] = {}  # ext_id -> {version -> manifest_data}

    def update_extension_side_by_side(
        self,
        extension_id: str,
        new_manifest_data: dict
    ) -> ExtensionInstance:
        existing = self.registry.get_extension(extension_id)
        if not existing:
            raise KeyError(f"Extension '{extension_id}' does not exist to update.")

        old_manifest_data = existing.manifest.model_dump()
        old_version = existing.manifest.version

        if extension_id not in self.version_history:
            self.version_history[extension_id] = {}
        self.version_history[extension_id][old_version] = old_manifest_data

        # Validate new manifest
        new_manifest = ExtensionManifestValidator.validate_manifest(new_manifest_data)

        # Update instance with new manifest while preserving configuration
        existing.manifest = new_manifest
        existing.updated_at = time.time()
        existing.state = ExtensionTrustState.INSTALLED
        existing.error_count = 0
        existing.last_error = None
        return existing

    def rollback_extension(self, extension_id: str, target_version: str) -> ExtensionInstance:
        existing = self.registry.get_extension(extension_id)
        if not existing:
            raise KeyError(f"Extension '{extension_id}' not found.")

        history = self.version_history.get(extension_id, {})
        target_manifest_data = history.get(target_version)
        if not target_manifest_data:
            raise KeyError(f"Version '{target_version}' for extension '{extension_id}' not found in rollback history.")

        restored_manifest = ExtensionManifestValidator.validate_manifest(target_manifest_data)
        existing.manifest = restored_manifest
        existing.updated_at = time.time()
        existing.state = ExtensionTrustState.INSTALLED
        existing.error_count = 0
        existing.last_error = f"Rolled back to version {target_version}"
        return existing
