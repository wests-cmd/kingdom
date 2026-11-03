"""Agent Client Protocol (ACP) and External Coding Application Adapter Layer.

Supports standard ACP negotiation, capability discovery, health checks,
and structured integration with:
- Codex
- Claude Code
- Gemini CLI
- Jules
- Ollama

Zero-trust principles:
1. No binary execution during inspection (presence in PATH does not prove readiness).
2. Credential isolation (no password or token extraction).
3. Documented protocol support is not verified runtime compliance.
4. Models report actual configured profiles and truthful readiness.
5. All unverified states explicitly set required false flags and actionable reasons.
"""
import ipaddress
import shutil
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field


class BeginnerSetupGuide(BaseModel):
    model_config = ConfigDict(extra="forbid")
    install_hint: str
    signin_hint: str
    troubleshooting_url: str = ""


class ToolAdapterManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    supports_acp: bool
    executable: str
    required_permissions: List[str] = Field(default_factory=list)
    version_command: List[str] = Field(default_factory=lambda: ["--version"])
    protocol: str = "acp"  # "acp", "cli_wrapper", "http_api"
    capabilities: List[str] = Field(default_factory=list)
    beginner_setup_guide: Optional[BeginnerSetupGuide] = None
    protocol_version: str = "1.0"
    documentation_url: str = ""


SUPPORTED_TOOLS: Dict[str, ToolAdapterManifest] = {
    "codex": ToolAdapterManifest(
        id="codex",
        name="OpenAI Codex CLI",
        supports_acp=True,
        executable="codex",
        protocol="acp",
        capabilities=["code.generate", "code.review", "shell.exec", "file.patch"],
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["codex", "--version"],
        protocol_version="1.0",
        documentation_url="https://github.com/openai/codex",
        beginner_setup_guide=BeginnerSetupGuide(
            install_hint="Install via npm: `npm install -g @openai/codex` or platform package manager.",
            signin_hint="Run `codex login` in terminal; credentials are stored in user profile, not extracted.",
            troubleshooting_url="https://platform.openai.com/docs"
        )
    ),
    "claude_code": ToolAdapterManifest(
        id="claude_code",
        name="Anthropic Claude Code",
        supports_acp=False,  # Documented CLI wrapper adapter
        executable="claude",
        protocol="cli_wrapper",
        capabilities=["code.generate", "code.edit", "explanation"],
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["claude", "--version"],
        protocol_version="0.9",
        documentation_url="https://docs.anthropic.com/claude-code",
        beginner_setup_guide=BeginnerSetupGuide(
            install_hint="Install via npm: `npm install -g @anthropic-ai/claude-code`.",
            signin_hint="Authenticate using `claude login` directly in terminal. No Kingdom credentials used.",
            troubleshooting_url="https://docs.anthropic.com"
        )
    ),
    "gemini_cli": ToolAdapterManifest(
        id="gemini_cli",
        name="Google Gemini CLI",
        supports_acp=False,
        executable="gemini",
        protocol="cli_wrapper",
        capabilities=["code.generate", "multimodal.analysis"],
        required_permissions=["filesystem.read", "process.execute"],
        version_command=["gemini", "--version"],
        protocol_version="0.9",
        documentation_url="https://cloud.google.com/gemini",
        beginner_setup_guide=BeginnerSetupGuide(
            install_hint="Install Google Cloud SDK and Gemini CLI utility via official Google documentation.",
            signin_hint="Authenticate via `gcloud auth application-default login` or API key.",
            troubleshooting_url="https://cloud.google.com/docs"
        )
    ),
    "jules": ToolAdapterManifest(
        id="jules",
        name="Kingdom Native Jules Adapter",
        supports_acp=True,
        executable="jules",
        protocol="acp",
        capabilities=["mission.handoff", "patch.verify", "repair.loop"],
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["jules", "--version"],
        protocol_version="1.0",
        documentation_url="https://github.com/google/jules",
        beginner_setup_guide=BeginnerSetupGuide(
            install_hint="Native Python supervisor integrated into Kingdom; no external binary install needed.",
            signin_hint="Requires owner authorization in `data/secrets/jules.key` (0o600) and Level 5 standing policy.",
            troubleshooting_url="docs/ADAPTER_CAPABILITY_DISCOVERY.md"
        )
    ),
    "ollama": ToolAdapterManifest(
        id="ollama",
        name="Ollama Local Engine",
        supports_acp=False,
        executable="ollama",
        protocol="http_api",
        capabilities=["local.inference", "embeddings", "tool_calling"],
        required_permissions=["process.execute", "network.access"],
        version_command=["ollama", "--version"],
        protocol_version="1.0",
        documentation_url="https://ollama.com",
        beginner_setup_guide=BeginnerSetupGuide(
            install_hint="Download and install Ollama from https://ollama.com.",
            signin_hint="No login required; run `ollama serve` and pull models using `ollama run <model>`.",
            troubleshooting_url="https://ollama.com/download"
        )
    )
}


class ModelManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    provider: str
    is_local: bool = False
    context_window: int = 8192
    supports_tools: bool = False
    supports_vision: bool = False
    requires_auth: bool = True
    notes: str = ""


CATALOG_MODEL_TEMPLATES: Dict[str, ModelManifest] = {
    "chatgpt-4o": ModelManifest(
        id="chatgpt-4o",
        name="ChatGPT 4o (Reasoning & Code)",
        provider="chatgpt",
        is_local=False,
        context_window=128000,
        supports_tools=True,
        supports_vision=True,
        requires_auth=True,
        notes="High-capability reasoning model via ChatGPT plan connection."
    ),
    "ollama-qwen-coder": ModelManifest(
        id="ollama-qwen-coder",
        name="Qwen 2.5 Coder 7B (Local)",
        provider="ollama",
        is_local=True,
        context_window=32768,
        supports_tools=True,
        supports_vision=False,
        requires_auth=False,
        notes="Fast local code generation and editing on CPU/GPU."
    ),
    "ollama-llama3": ModelManifest(
        id="ollama-llama3",
        name="Llama 3.1 8B (Local)",
        provider="ollama",
        is_local=True,
        context_window=8192,
        supports_tools=True,
        supports_vision=False,
        requires_auth=False,
        notes="General-purpose instruction following local engine."
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


def is_local_endpoint(endpoint: str, hosting: Optional[str] = None) -> bool:
    """Determine whether an endpoint is local based on explicit hosting and parsed IP/hostname."""
    if hosting == "local":
        return True
    if hosting == "cloud":
        return False

    if not endpoint:
        return False

    try:
        parts = urlsplit(endpoint if "//" in endpoint else f"http://{endpoint}")
        hostname = (parts.hostname or "").strip().lower()
        if not hostname:
            return False

        if hostname == "localhost":
            return True

        # Check loopback IP
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_loopback:
                return True
        except ValueError:
            pass

        return False
    except Exception:
        return False


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
            if configured:
                # Crucial: local configuration presence does NOT verify remote provider reachability or auth
                reasons.append("Provider authentication and remote connectivity unverified; local credential presence does not verify provider identity or reachability")

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

        # Crucial zero-trust flags:
        connected = False
        authenticated = False
        available_to_planner = False
        protocol_verified = False
        acp_compliant = False
        granted_execution_authority = False

        if is_jules:
            jules_info = self._inspect_jules_state()
            installed = True  # Native Python service is built into Kingdom
            unavailable_reasons.extend(jules_info["unavailable_reasons"])
        else:
            installed = shutil.which(manifest.executable) is not None
            if not installed:
                unavailable_reasons.append(f"Executable '{manifest.executable}' not found in system PATH")
            else:
                unavailable_reasons.append("Authentication and runtime handshake unverified; binary presence in PATH does not prove connectivity")
                if manifest.protocol == "http_api" or tool_id == "ollama":
                    unavailable_reasons.append("Local daemon connection and model weights unverified")

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
            "beginner_setup_guide": manifest.beginner_setup_guide.model_dump() if manifest.beginner_setup_guide else None
        }

    def list_models(self) -> List[Dict[str, Any]]:
        """List models based on actual configured profiles and truthful provider readiness.

        Does NOT fabricate availability from example catalog names or unverified configs.
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

            is_local = is_local_endpoint(p.get("endpoint", ""), p.get("hosting"))
            unavailable: List[str] = []
            if p.get("disabled"):
                unavailable.append("Model profile is disabled by owner")
            else:
                # Merely configured/enabled profile is NOT verified live inference availability
                unavailable.append("Inference availability and endpoint health unverified; endpoint has not been tested")

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
                "available": False,  # Configured is not verified!
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
            "authenticated": info["authenticated"],
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
