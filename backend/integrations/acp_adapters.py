"""Agent Client Protocol (ACP) and External Coding Application Adapter Layer.

Supports standard ACP negotiation, capability discovery, health checks,
and structured integration with:
- Codex
- Claude Code
- Gemini CLI
- Jules
- Ollama
"""
import shutil
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolAdapterManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    supports_acp: bool
    executable: str
    required_permissions: List[str] = Field(default_factory=list)
    version_command: List[str] = Field(default_factory=lambda: ["--version"])
    protocol_version: str = "1.0"
    documentation_url: str = ""


SUPPORTED_TOOLS: Dict[str, ToolAdapterManifest] = {
    "codex": ToolAdapterManifest(
        id="codex",
        name="OpenAI Codex CLI",
        supports_acp=True,
        executable="codex",
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["codex", "--version"],
        protocol_version="1.0"
    ),
    "claude_code": ToolAdapterManifest(
        id="claude_code",
        name="Anthropic Claude Code",
        supports_acp=False,  # Documented CLI wrapper adapter
        executable="claude",
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["claude", "--version"],
        protocol_version="0.9"
    ),
    "gemini_cli": ToolAdapterManifest(
        id="gemini_cli",
        name="Google Gemini CLI",
        supports_acp=False,
        executable="gemini",
        required_permissions=["filesystem.read", "process.execute"],
        version_command=["gemini", "--version"],
        protocol_version="0.9"
    ),
    "jules": ToolAdapterManifest(
        id="jules",
        name="Kingdom Native Jules Adapter",
        supports_acp=True,
        executable="jules",
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["jules", "--version"],
        protocol_version="1.0"
    ),
    "ollama": ToolAdapterManifest(
        id="ollama",
        name="Ollama Local Engine",
        supports_acp=False,
        executable="ollama",
        required_permissions=["process.execute", "network.access"],
        version_command=["ollama", "--version"],
        protocol_version="1.0"
    )
}


class ACPToolManager:
    def __init__(self, tools: Optional[Dict[str, ToolAdapterManifest]] = None):
        self.tools = dict(tools or SUPPORTED_TOOLS)

    def list_tools(self) -> List[Dict[str, Any]]:
        results = []
        for tool_id, manifest in self.tools.items():
            installed = shutil.which(manifest.executable) is not None
            results.append({
                **manifest.model_dump(),
                "installed": installed,
                "status": "ready" if installed else "uninstalled"
            })
        return results

    def inspect_tool(self, tool_id: str) -> Dict[str, Any]:
        manifest = self.tools.get(tool_id)
        if not manifest:
            raise KeyError(f"Tool {tool_id} not supported")
        installed = shutil.which(manifest.executable) is not None
        return {
            **manifest.model_dump(),
            "installed": installed,
            "status": "ready" if installed else "uninstalled",
            "acp_compliant": manifest.supports_acp,
            "auth_isolation": "External tool credentials isolated; no password collection through Kingdom"
        }

    def verify_connectivity(self, tool_id: str) -> Dict[str, Any]:
        info = self.inspect_tool(tool_id)
        return {
            "id": tool_id,
            "connected": info["installed"],
            "supports_acp": info["supports_acp"],
            "available_to_planner": info["installed"],
            "permissions": info["required_permissions"]
        }
