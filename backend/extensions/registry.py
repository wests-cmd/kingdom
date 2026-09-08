import time
from typing import Dict, List, Optional
from backend.extensions.models import ExtensionManifest, ExtensionInstance, ExtensionTrustState
from backend.extensions.manifest_validator import ExtensionManifestValidator, ManifestValidationError


class ExtensionRegistry:

    def __init__(self):
        self.extensions: Dict[str, ExtensionInstance] = {}

    def discover_extension(self, manifest_data: dict) -> ExtensionInstance:
        manifest = ExtensionManifestValidator.validate_manifest(manifest_data)
        if manifest.extension_id in self.extensions:
            existing = self.extensions[manifest.extension_id]
            existing.manifest = manifest
            existing.updated_at = time.time()
            return existing

        instance = ExtensionInstance(
            manifest=manifest,
            state=ExtensionTrustState.DISCOVERED
        )
        self.extensions[manifest.extension_id] = instance
        return instance

    def install_extension(self, extension_id: str) -> ExtensionInstance:
        instance = self.extensions.get(extension_id)
        if not instance:
            raise KeyError(f"Extension '{extension_id}' not found in registry.")

        if instance.state == ExtensionTrustState.REVOKED:
            raise ValueError(f"Extension '{extension_id}' has been REVOKED and cannot be installed.")

        instance.state = ExtensionTrustState.INSTALLED
        instance.updated_at = time.time()
        return instance

    def enable_extension(self, extension_id: str) -> ExtensionInstance:
        instance = self.extensions.get(extension_id)
        if not instance:
            raise KeyError(f"Extension '{extension_id}' not found in registry.")

        if instance.state not in [ExtensionTrustState.INSTALLED, ExtensionTrustState.DISABLED]:
            raise ValueError(f"Extension '{extension_id}' must be INSTALLED or DISABLED to enable. Current state: {instance.state}")

        instance.state = ExtensionTrustState.ENABLED
        instance.updated_at = time.time()
        return instance

    def disable_extension(self, extension_id: str) -> ExtensionInstance:
        instance = self.extensions.get(extension_id)
        if not instance:
            raise KeyError(f"Extension '{extension_id}' not found in registry.")

        instance.state = ExtensionTrustState.DISABLED
        instance.updated_at = time.time()
        return instance

    def quarantine_extension(self, extension_id: str, reason: str) -> ExtensionInstance:
        instance = self.extensions.get(extension_id)
        if not instance:
            raise KeyError(f"Extension '{extension_id}' not found in registry.")

        instance.state = ExtensionTrustState.QUARANTINED
        instance.last_error = f"Quarantined: {reason}"
        instance.updated_at = time.time()
        return instance

    def revoke_extension(self, extension_id: str, reason: str) -> ExtensionInstance:
        instance = self.extensions.get(extension_id)
        if not instance:
            raise KeyError(f"Extension '{extension_id}' not found in registry.")

        instance.state = ExtensionTrustState.REVOKED
        instance.last_error = f"Revoked: {reason}"
        instance.updated_at = time.time()
        return instance

    def get_extension(self, extension_id: str) -> Optional[ExtensionInstance]:
        return self.extensions.get(extension_id)

    def list_extensions(self, state: Optional[ExtensionTrustState] = None) -> List[ExtensionInstance]:
        if state is None:
            return list(self.extensions.values())
        return [ext for ext in self.extensions.values() if ext.state == state]
