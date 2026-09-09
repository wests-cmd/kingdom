"""
Kingdom Tool Generator, Schema Validation & Authorized Discovery Engine.
Generates versioned tool definitions (`tool@v`) from integration manifests and performs capability-filtered tool discovery.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from backend.integrations.manifest import IntegrationManifest

@dataclass
class ToolDefinition:
    tool_id: str
    version: str
    provider_id: str
    operation: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    required_capabilities: List[str]
    required_permissions: List[str]
    risk_level: str
    idempotent: bool = True
    timeout_seconds: int = 30

class ToolEngine:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        key = f"{tool.tool_id}@{tool.version}"
        self._tools[key] = tool

    def generate_tools_from_manifest(self, manifest: IntegrationManifest, operations: List[Dict[str, Any]]) -> List[ToolDefinition]:
        generated = []
        for op in operations:
            tool = ToolDefinition(
                tool_id=op["tool_id"],
                version=op.get("version", manifest.version),
                provider_id=manifest.integration_id,
                operation=op["operation"],
                description=op.get("description", ""),
                input_schema=op.get("input_schema", {}),
                output_schema=op.get("output_schema", {}),
                required_capabilities=op.get("capabilities", manifest.capabilities),
                required_permissions=op.get("permissions", manifest.permissions),
                risk_level=manifest.risk_level.value,
                idempotent=op.get("idempotent", True)
            )
            self.register_tool(tool)
            generated.append(tool)
        return generated

    def discover_authorized_tools(self, actor_capabilities: List[str], actor_permissions: List[str]) -> List[ToolDefinition]:
        """
        Returns only tools where the actor possesses ALL required capabilities and permissions.
        """
        authorized = []
        for tool in self._tools.values():
            has_caps = all(cap in actor_capabilities for cap in tool.required_capabilities)
            has_perms = all(perm in actor_permissions for perm in tool.required_permissions)
            if has_caps and has_perms:
                authorized.append(tool)
        return authorized

    def validate_tool_invocation(self, tool_key: str, params: Dict[str, Any], actor_capabilities: List[str], actor_permissions: List[str]) -> List[str]:
        errors = []
        tool = self._tools.get(tool_key)
        if not tool:
            return [f"Tool {tool_key} not found"]

        for cap in tool.required_capabilities:
            if cap not in actor_capabilities:
                errors.append(f"Missing required capability: {cap}")
        for perm in tool.required_permissions:
            if perm not in actor_permissions:
                errors.append(f"Missing required permission: {perm}")

        # Basic schema check for required parameters
        required_params = tool.input_schema.get("required", [])
        for req in required_params:
            if req not in params:
                errors.append(f"Missing required input parameter: {req}")

        return errors
