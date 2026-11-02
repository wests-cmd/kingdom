"""Agent Client Protocol (ACP) and External Coding Application Adapter Layer.

Supports standard ACP negotiation, capability discovery, health checks,
and structured integration with:
- Codex
- Claude Code
- Gemini CLI
- Jules
- Ollama

Enforces strict credential isolation: Kingdom never extracts browser cookies
or other applications' credentials. Does not assume ACP support or universal
tool/model capabilities.
"""

import shutil
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolAdapterManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    protocol: str = Field(pattern=r"^(acp|cli_wrapper|http_api)$")
    supports_acp: bool
    executable: str
    required_permissions: List[str] = Field(default_factory=list)
    version_command: List[str] = Field(default_factory=lambda: ["--version"])
    protocol_version: str = "1.0"
    documentation_url: str = ""
    capabilities: List[str] = Field(default_factory=list)
    beginner_setup_guide: Dict[str, Any] = Field(default_factory=dict)


SUPPORTED_TOOLS: Dict[str, ToolAdapterManifest] = {
    "codex": ToolAdapterManifest(
        id="codex",
        name="OpenAI Codex CLI",
        protocol="acp",
        supports_acp=True,
        executable="codex",
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["codex", "--version"],
        protocol_version="1.0",
        documentation_url="https://github.com/openai/codex",
        capabilities=["code.generate", "code.edit", "process.execute", "tools.call"],
        beginner_setup_guide={
            "install_hint": "npm install -g @openai/codex or visit official docs",
            "signin_hint": "Run 'codex login' in your local terminal. Do not share session files.",
            "auth_type": "external_cli_auth"
        }
    ),
    "claude_code": ToolAdapterManifest(
        id="claude_code",
        name="Anthropic Claude Code",
        protocol="cli_wrapper",
        supports_acp=False,  # Documented CLI wrapper adapter, not ACP
        executable="claude",
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["claude", "--version"],
        protocol_version="0.9",
        documentation_url="https://docs.anthropic.com/claude-code",
        capabilities=["code.generate", "code.edit", "process.execute"],
        beginner_setup_guide={
            "install_hint": "npm install -g @anthropic-ai/claude-code",
            "signin_hint": "Run 'claude login' directly in host shell. Kingdom does not manage Anthropic tokens.",
            "auth_type": "external_cli_auth"
        }
    ),
    "gemini_cli": ToolAdapterManifest(
        id="gemini_cli",
        name="Google Gemini CLI",
        protocol="cli_wrapper",
        supports_acp=False,
        executable="gemini",
        required_permissions=["filesystem.read", "process.execute"],
        version_command=["gemini", "--version"],
        protocol_version="0.9",
        documentation_url="https://ai.google.dev/gemini-api",
        capabilities=["code.generate", "reasoning"],
        beginner_setup_guide={
            "install_hint": "Install Google Cloud SDK or Gemini CLI utility",
            "signin_hint": "Run 'gcloud auth application-default login' or set GEMINI_API_KEY locally.",
            "auth_type": "external_cli_auth"
        }
    ),
    "jules": ToolAdapterManifest(
        id="jules",
        name="Kingdom Native Jules Adapter",
        protocol="acp",
        supports_acp=True,
        executable="jules",
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["jules", "--version"],
        protocol_version="1.0",
        documentation_url="docs/MAINTENANCE_MODE.md",
        capabilities=["code.generate", "code.edit", "test.execute", "repo.inspect"],
        beginner_setup_guide={
            "install_hint": "Configured as supervised worker in Kingdom; see backend/integrations/jules.py",
            "signin_hint": "Requires Level 5 owner key stored in data/secrets/jules.key (mode 0o600).",
            "auth_type": "owner_key_isolated"
        }
    ),
    "ollama": ToolAdapterManifest(
        id="ollama",
        name="Ollama Local Engine",
        protocol="http_api",
        supports_acp=False,
        executable="ollama",
        required_permissions=["process.execute", "network.access"],
        version_command=["ollama", "--version"],
        protocol_version="1.0",
        documentation_url="https://ollama.com",
        capabilities=["model.inference", "embeddings"],
        beginner_setup_guide={
            "install_hint": "Download and install from https://ollama.com",
            "signin_hint": "Local engine; no external account login required. Starts on localhost:11434.",
            "auth_type": "local_daemon"
        }
    )
}


class ModelManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    provider: str
    is_local: bool
    context_window: int
    supports_tools: bool
    supports_vision: bool
    requires_auth: bool
    notes: str = ""


KNOWN_MODELS_MANIFEST: Dict[str, ModelManifest] = {
    "chatgpt-4o": ModelManifest(
        id="chatgpt-4o",
        name="GPT-4o (OpenAI)",
        provider="chatgpt",
        is_local=False,
        context_window=128000,
        supports_tools=True,
        supports_vision=True,
        requires_auth=True,
        notes="High-capacity multimodal reasoning and tool invocation."
    ),
    "ollama-qwen-coder": ModelManifest(
        id="ollama-qwen-coder",
        name="Qwen 2.5 Coder 7B",
        provider="ollama",
        is_local=True,
        context_window=32768,
        supports_tools=True,
        supports_vision=False,
        requires_auth=False,
        notes="Fast local code completion and editing; no cloud egress."
    ),
    "ollama-llama3": ModelManifest(
        id="ollama-llama3",
        name="Llama 3.1 8B",
        provider="ollama",
        is_local=True,
        context_window=131072,
        supports_tools=True,
        supports_vision=False,
        requires_auth=False,
        notes="General-purpose local reasoning and instruction following."
    ),
    "gemini-1.5-pro": ModelManifest(
        id="gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        provider="gemini_cli",
        is_local=False,
        context_window=1000000,
        supports_tools=True,
        supports_vision=True,
        requires_auth=True,
        notes="Ultra-long context window support."
    )
}


class ACPToolManager:
    """Manages adapter capability discovery and beginner setup readiness."""

    def __init__(
        self,
        tools: Optional[Dict[str, ToolAdapterManifest]] = None,
        models: Optional[Dict[str, ModelManifest]] = None
    ):
        self.tools = dict(tools or SUPPORTED_TOOLS)
        self.models = dict(models or KNOWN_MODELS_MANIFEST)

    def list_tools(self) -> List[Dict[str, Any]]:
        results = []
        for tool_id, manifest in self.tools.items():
            installed = shutil.which(manifest.executable) is not None
            unavailable_reasons = []
            if not installed:
                unavailable_reasons.append(f"Executable '{manifest.executable}' not found in system PATH")

            results.append({
                **manifest.model_dump(),
                "installed": installed,
                "supported": True,
                "status": "ready" if installed else "uninstalled",
                "unavailable_reasons": unavailable_reasons,
                "auth_isolation": "External tool credentials isolated; no cookies or browser passwords extracted by Kingdom"
            })
        return results

    def inspect_tool(self, tool_id: str) -> Dict[str, Any]:
        manifest = self.tools.get(tool_id)
        if not manifest:
            raise KeyError(f"Tool {tool_id} not supported")
        installed = shutil.which(manifest.executable) is not None
        unavailable_reasons = []
        if not installed:
            unavailable_reasons.append(f"Executable '{manifest.executable}' not found in system PATH")

        return {
            **manifest.model_dump(),
            "installed": installed,
            "supported": True,
            "status": "ready" if installed else "uninstalled",
            "acp_compliant": manifest.supports_acp,
            "unavailable_reasons": unavailable_reasons,
            "auth_isolation": "External tool credentials isolated; no cookies or browser passwords extracted by Kingdom",
            "beginner_setup_guide": manifest.beginner_setup_guide
        }

    def list_models(self) -> List[Dict[str, Any]]:
        results = []
        for model_id, manifest in self.models.items():
            parent_tool = self.tools.get(manifest.provider)
            provider_installed = shutil.which(parent_tool.executable) is not None if parent_tool else True
            unavailable_reasons = []
            if parent_tool and not provider_installed:
                unavailable_reasons.append(f"Provider engine '{parent_tool.name}' is not installed")

            results.append({
                **manifest.model_dump(),
                "available": provider_installed,
                "unavailable_reasons": unavailable_reasons
            })
        return results

    def verify_connectivity(self, tool_id: str) -> Dict[str, Any]:
        info = self.inspect_tool(tool_id)
        return {
            "id": tool_id,
            "connected": info["installed"],
            "supports_acp": info["supports_acp"],
            "protocol": info["protocol"],
            "available_to_planner": info["installed"],
            "permissions": info["required_permissions"],
            "unavailable_reasons": info["unavailable_reasons"]
        }
