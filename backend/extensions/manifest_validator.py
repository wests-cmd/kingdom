import re
from typing import Dict, Any, List, Tuple
from backend.state import STATE
from backend.extensions.models import ExtensionManifest, ExtensionToolDeclaration

RUNTIME_VERSION = STATE.get("version", "40.2.0")


class ManifestValidationError(Exception):
    pass


class ExtensionManifestValidator:

    PROHIBITED_PERMISSIONS = {
        "kernel.bypass_security",
        "system.disable_audit",
        "governance.auto_approve",
        "root.escalate"
    }

    @classmethod
    def parse_version_constraint(cls, constraint: str) -> Tuple[str, str]:
        """Parses constraint like '>=40.0.0' or '==40.2.0' into operator and version string."""
        match = re.match(r"^([><=]+)\s*(\d+\.\d+\.\d+)", constraint.strip())
        if match:
            return match.group(1), match.group(2)
        return "==", constraint.strip()

    @classmethod
    def compare_versions(cls, v1: str, v2: str) -> int:
        """Returns -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2."""
        p1 = [int(x) for x in v1.split(".")]
        p2 = [int(x) for x in v2.split(".")]
        if p1 < p2:
            return -1
        elif p1 > p2:
            return 1
        return 0

    @classmethod
    def check_compatibility(cls, constraint: str, current_version: str = RUNTIME_VERSION) -> bool:
        op, target_v = cls.parse_version_constraint(constraint)
        comp = cls.compare_versions(current_version, target_v)
        if op == ">=":
            return comp >= 0
        elif op == ">":
            return comp > 0
        elif op == "<=":
            return comp <= 0
        elif op == "<":
            return comp < 0
        elif op == "==":
            return comp == 0
        return True

    @classmethod
    def validate_manifest(cls, manifest_dict: Dict[str, Any]) -> ExtensionManifest:
        # Check required fields
        required_fields = ["extension_id", "name", "version", "description", "author"]
        for field in required_fields:
            if not manifest_dict.get(field):
                raise ManifestValidationError(f"Missing required field in extension manifest: '{field}'")

        ext_id = manifest_dict["extension_id"]
        if not re.match(r"^[a-zA-Z0-9_\-]+$", ext_id):
            raise ManifestValidationError(f"Invalid extension_id format '{ext_id}'. Must be alphanumeric/hyphen/underscore.")

        # Check compatibility
        compat = manifest_dict.get("kingdom_compatibility", ">=40.0.0")
        if not cls.check_compatibility(compat):
            raise ManifestValidationError(
                f"Extension '{ext_id}' requires Kingdom version '{compat}', but current runtime is '{RUNTIME_VERSION}'."
            )

        # Check prohibited permissions
        permissions = manifest_dict.get("permissions", [])
        for perm in permissions:
            if perm in cls.PROHIBITED_PERMISSIONS:
                raise ManifestValidationError(f"Extension '{ext_id}' requested prohibited security permission: '{perm}'")

        # Validate tools schema if present
        tools_data = manifest_dict.get("tools", [])
        tools = []
        tool_ids = set()
        for t in tools_data:
            if isinstance(t, ExtensionToolDeclaration):
                t_id = t.tool_id
                if t_id in tool_ids:
                    raise ManifestValidationError(f"Duplicate tool_id '{t_id}' declared in extension '{ext_id}'")
                tool_ids.add(t_id)
                tools.append(t)
            elif isinstance(t, dict):
                if "tool_id" not in t or "name" not in t:
                    raise ManifestValidationError(f"Malformed tool declaration in extension '{ext_id}'")
                t_id = t["tool_id"]
                if t_id in tool_ids:
                    raise ManifestValidationError(f"Duplicate tool_id '{t_id}' declared in extension '{ext_id}'")
                tool_ids.add(t_id)
                tools.append(ExtensionToolDeclaration(**t))
            else:
                raise ManifestValidationError(f"Malformed tool declaration in extension '{ext_id}'")

        manifest_dict["tools"] = tools
        return ExtensionManifest(**manifest_dict)
