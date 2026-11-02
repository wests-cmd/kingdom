"""Agent Client Protocol (ACP) and External Coding Application Adapter Layer.

Supports standard ACP capability discovery, status inspection, and structured
integration representation with external tools and engines:
- Codex
- Claude Code
- Gemini CLI
- Jules
- Ollama

Enforces strict boundaries:
- Credential isolation: Kingdom never extracts browser cookies or keychain/session credentials.
- Honest state distinction: Catalog installation hints vs observed filesystem/connectivity facts
  vs verified readiness vs granted execution authority.
- No blind execution: Discovered binaries are never executed merely to inspect or test them.
- Unknowns remain explicit unavailable/unknown states rather than invented capabilities.
- Public defaults stay least privilege.
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


# Catalog reference templates (not assumed to be available without configuration/weights)
CATALOG_MODEL_TEMPLATES: Dict[str, ModelManifest] = {
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

# Alias for backwards compatibility if referenced by name
KNOWN_MODELS_MANIFEST = CATALOG_MODEL_TEMPLATES


class ACPToolManager:
    """Manages adapter capability discovery and beginner setup readiness."""

    def __init__(
        self,
        tools: Optional[Dict[str, ToolAdapterManifest]] = None,
        models: Optional[Dict[str, ModelManifest]] = None,
        db: Any = None,
    ):
        self.tools = dict(tools or SUPPORTED_TOOLS)
        self.models = dict(models or CATALOG_MODEL_TEMPLATES)
        self._db = db

    def _get_db(self):
        if self._db is not None:
            return self._db
        from backend.storage.db import db
        return db

    def _inspect_jules_state(self) -> Dict[str, Any]:
        """Inspect native Jules service settings without executing external binary."""
        try:
            from backend.integrations.jules import JulesService
            db = self._get_db()
            service = JulesService(db)
            settings = service.settings()
            enabled = settings.get("enabled", False)
            has_credentials = settings.get("has_credentials", False)
            allowed_repos = settings.get("allowed_repositories", [])
            allowed_sources = settings.get("allowed_sources", [])

            reasons = []
            if not enabled:
                reasons.append("Native Jules adapter is disabled in settings")
            if not has_credentials:
                reasons.append("Native Jules credentials not configured in secrets vault")
            if not allowed_repos or not allowed_sources:
                reasons.append("No allowed repositories or sources configured")

            configured = enabled and has_credentials and bool(allowed_repos) and bool(allowed_sources)
            return {
                "configured": configured,
                "enabled": enabled,
                "has_credentials": has_credentials,
                "unavailable_reasons": reasons,
            }
        except Exception as e:
            return {
                "configured": False,
                "enabled": False,
                "has_credentials": False,
                "unavailable_reasons": [f"Unable to read Jules configuration: {type(e).__name__}"],
            }

    def list_tools(self) -> List[Dict[str, Any]]:
        results = []
        for tool_id in self.tools:
            results.append(self.inspect_tool(tool_id))
        return results

    def inspect_tool(self, tool_id: str) -> Dict[str, Any]:
        manifest = self.tools.get(tool_id)
        if not manifest:
            raise KeyError(f"Tool {tool_id} not supported")

        unavailable_reasons: List[str] = []
        is_jules = (tool_id == "jules")

        if is_jules:
            jules_info = self._inspect_jules_state()
            installed = True  # Native Python service is built into Kingdom
            authenticated = jules_info["has_credentials"]
            connected = jules_info["configured"]
            unavailable_reasons.extend(jules_info["unavailable_reasons"])
        else:
            installed = shutil.which(manifest.executable) is not None
            authenticated = False  # External tools manage their own auth; presence in PATH does not prove authentication
            connected = False      # Executable presence does not prove connection or active daemon
            if not installed:
                unavailable_reasons.append(f"Executable '{manifest.executable}' not found in system PATH")
            else:
                unavailable_reasons.append("Authentication and runtime handshake unverified; binary presence in PATH does not prove connectivity")
                if manifest.protocol == "http_api" or tool_id == "ollama":
                    unavailable_reasons.append("Local daemon connection and model weights unverified")

        # ACP compliance and protocol negotiation:
        # Documented support in manifest does NOT equal verified runtime compliance or live negotiation.
        protocol_verified = False
        acp_compliant = False
        available_to_planner = False
        granted_execution_authority = False

        status = "ready" if connected and authenticated else ("installed_unverified" if installed else "uninstalled")

        return {
            **manifest.model_dump(),
            "installed": installed,
            "supported": True,
            "status": status,
            "connected": connected,
            "authenticated": authenticated,
            "available_to_planner": available_to_planner,
            "protocol_verified": protocol_verified,
            "acp_compliant": acp_compliant,
            "granted_execution_authority": granted_execution_authority,
            "unavailable_reasons": unavailable_reasons,
            "auth_isolation": "External tool credentials isolated; no cookies or browser passwords extracted by Kingdom",
            "beginner_setup_guide": manifest.beginner_setup_guide
        }

    def list_models(self) -> List[Dict[str, Any]]:
        """List models based on actual configured profiles and truthful provider readiness.

        Does NOT fabricate availability from example catalog names.
        """
        results: List[Dict[str, Any]] = []

        # 1. Fetch actual configured custom model profiles from database
        configured_profiles = []
        try:
            from backend.models.profiles import ModelProfiles
            db = self._get_db()
            configured_profiles = ModelProfiles(db).list()
        except Exception:
            configured_profiles = []

        seen_model_ids = set()
        for p in configured_profiles:
            p_id = p.get("id")
            if not p_id or p_id in seen_model_ids:
                continue
            seen_model_ids.add(p_id)
            is_local = p.get("hosting") == "local" or (p.get("provider") == "ollama" and "localhost" in p.get("endpoint", ""))
            unavailable = []
            if p.get("disabled"):
                unavailable.append("Model profile is disabled by owner")
            results.append({
                "id": p_id,
                "name": p.get("model", p_id),
                "provider": p.get("provider", "custom"),
                "is_local": is_local,
                "context_window": p.get("num_ctx", 8192),
                "supports_tools": p.get("supports_tools", False),
                "supports_vision": p.get("vision", False),
                "requires_auth": p.get("has_credentials", False),
                "notes": f"Configured model profile ({p.get('provider')}) at {p.get('endpoint', '')}",
                "available": not p.get("disabled", False),
                "source": "configured_profile",
                "unavailable_reasons": unavailable
            })

        # 2. Check ChatGPT Plan status
        chatgpt_status = None
        try:
            from backend.models.chatgpt_plan import ChatGPTPlanConnection
            db = self._get_db()
            conn = ChatGPTPlanConnection(db)
            chatgpt_status = conn.status()
        except Exception:
            pass

        # Catalog templates:
        for model_id, manifest in self.models.items():
            if model_id in seen_model_ids:
                continue

            unavailable_reasons = []
            available = False

            if manifest.provider == "chatgpt":
                if chatgpt_status and chatgpt_status.get("state") == "ready":
                    available = True
                else:
                    state_reason = (chatgpt_status.get("state") if chatgpt_status else "unconfigured")
                    unavailable_reasons.append(f"ChatGPT plan connection is not ready (state: {state_reason})")
            elif manifest.provider == "ollama":
                parent_tool = self.tools.get("ollama")
                tool_installed = shutil.which(parent_tool.executable) is not None if parent_tool else False
                if not tool_installed:
                    unavailable_reasons.append("Ollama engine executable not found in system PATH")
                else:
                    unavailable_reasons.append("Ollama daemon running state and local model weights unverified")
            else:
                parent_tool = self.tools.get(manifest.provider)
                tool_installed = shutil.which(parent_tool.executable) is not None if parent_tool else False
                if not tool_installed:
                    unavailable_reasons.append(f"Provider engine '{manifest.provider}' is not installed")
                else:
                    unavailable_reasons.append(f"Provider '{manifest.provider}' authentication and models unverified")

            results.append({
                **manifest.model_dump(),
                "available": available,
                "source": "catalog_template",
                "unavailable_reasons": unavailable_reasons
            })

        return results

    def verify_connectivity(self, tool_id: str) -> Dict[str, Any]:
        info = self.inspect_tool(tool_id)
        return {
            "id": tool_id,
            "connected": info["connected"],
            "installed": info["installed"],
            "supports_acp": info["supports_acp"],
            "acp_compliant": info["acp_compliant"],
            "protocol_verified": info["protocol_verified"],
            "protocol": info["protocol"],
            "available_to_planner": info["available_to_planner"],
            "granted_execution_authority": info["granted_execution_authority"],
            "permissions": info["required_permissions"],
            "unavailable_reasons": info["unavailable_reasons"]
        }
