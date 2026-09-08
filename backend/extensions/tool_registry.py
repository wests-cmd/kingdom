from typing import Any, Dict, List, Optional, Callable, Tuple
from backend.extensions.models import ExtensionToolDeclaration, ExtensionTrustState
from backend.extensions.registry import ExtensionRegistry


class ToolExecutionError(Exception):
    pass


class ExtensionToolRegistry:

    def __init__(self, registry: ExtensionRegistry):
        self.registry = registry
        self.executors: Dict[str, Callable] = {}

    def register_tool_executor(self, tool_id: str, executor: Callable) -> None:
        self.executors[tool_id] = executor

    def find_tool(self, tool_id: str) -> Optional[Tuple[ExtensionToolDeclaration, str]]:
        for ext in self.registry.list_extensions(state=ExtensionTrustState.ENABLED):
            for tool in ext.manifest.tools:
                if tool.tool_id == tool_id:
                    return tool, ext.manifest.extension_id
        return None

    def execute_tool(
        self,
        tool_id: str,
        params: Dict[str, Any],
        caller_permissions: List[str]
    ) -> Any:
        found = self.find_tool(tool_id)
        if not found:
            raise KeyError(f"Tool '{tool_id}' not found among active extensions.")

        tool_decl, ext_id = found

        # Verify required permissions
        for required_perm in tool_decl.required_permissions:
            if required_perm not in caller_permissions and "admin" not in caller_permissions:
                raise PermissionError(
                    f"Caller missing required permission '{required_perm}' for tool '{tool_id}'."
                )

        # Validate required parameters from input schema
        if "required" in tool_decl.input_schema:
            for req_field in tool_decl.input_schema["required"]:
                if req_field not in params:
                    raise ToolExecutionError(f"Missing required parameter '{req_field}' for tool '{tool_id}'.")

        executor = self.executors.get(tool_id)
        if not executor:
            raise NotImplementedError(f"No executable handler registered for tool '{tool_id}'.")

        return executor(params)
