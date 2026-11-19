"""Read-only inventory of external agent adapters and configured models.

Adapted from the retired ACP discovery experiment. Discovery is not a handshake:
an executable, a configured profile, or a template is NEVER execution authority.
No discovery path executes subprocesses, opens credential vaults or writes to SQLite.
"""
from __future__ import annotations

import ipaddress
import json
import shutil
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field


class ToolAdapterManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    supports_acp: bool = False
    executable: str
    required_permissions: List[str] = Field(default_factory=list)
    version_command: List[str] = Field(default_factory=lambda: ["--version"])
    protocol_version: str = "1.0"
    documentation_url: str = ""
    protocol: str = "cli_wrapper"
    setup_hint: str = ""


SUPPORTED_TOOLS: Dict[str, ToolAdapterManifest] = {
    "codex": ToolAdapterManifest(
        id="codex", name="Codex CLI", supports_acp=True,
        executable="codex", protocol="acp",
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["codex", "--version"], documentation_url="https://github.com/openai/codex",
        setup_hint="Install and sign in through the official Codex CLI; Kingdom does not copy its credentials."),
    "claude_code": ToolAdapterManifest(
        id="claude_code", name="Claude Code", executable="claude",
        required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        version_command=["claude", "--version"], documentation_url="https://code.claude.com/docs",
        setup_hint="Install and authenticate the Claude Code CLI separately."),
    "gemini_cli": ToolAdapterManifest(
        id="gemini_cli", name="Gemini CLI", executable="gemini",
        required_permissions=["filesystem.read", "process.execute"],
        version_command=["gemini", "--version"], documentation_url="https://github.com/google-gemini/gemini-cli",
        setup_hint="Install Gemini CLI and configure its own sign-in."),
    "jules": ToolAdapterManifest(
        id="jules", name="Kingdom Jules adapter", supports_acp=True, executable="jules",
        protocol="native", required_permissions=["filesystem.read", "filesystem.write", "process.execute"],
        setup_hint="Configure the existing owner-governed Jules integration inside Kingdom."),
    "ollama": ToolAdapterManifest(
        id="ollama", name="Ollama local inference", executable="ollama",
        protocol="http_api", required_permissions=["network.access", "process.execute"],
        version_command=["ollama", "--version"], documentation_url="https://ollama.com",
        setup_hint="Install Ollama and separately verify the daemon and model weights."),
}


def is_local_endpoint(endpoint: str, hosting: str | None = None) -> bool:
    if hosting == "local":
        return True
    if hosting == "cloud":
        return False
    try:
        parsed = urlsplit(endpoint if "://" in endpoint else "http://" + endpoint)
        host = (parsed.hostname or "").lower()
        if host == "localhost":
            return True
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return False


class ACPToolManager:
    def __init__(self, tools: Optional[Dict[str, ToolAdapterManifest]] = None, db: Any = None):
        self.tools = dict(SUPPORTED_TOOLS if tools is None else tools)
        self._db = db

    def _database(self):
        if self._db is not None:
            return self._db
        from backend.storage.db import db
        return db

    def inspect_tool(self, tool_id: str) -> dict:
        manifest = self.tools.get(tool_id)
        if manifest is None:
            raise KeyError("Unknown adapter")
        # Native Jules code is bundled, but configuration and authorization are
        # not proved by module presence or a third-party executable's PATH.
        installed = tool_id == "jules" or shutil.which(manifest.executable) is not None
        return {
            **manifest.model_dump(),
            "installed": installed,
            "status": "installed_unverified" if installed else "not_installed",
            "connected": False,
            "authenticated": False,
            "protocol_verified": False,
            "acp_compliant": False,
            "available_to_planner": False,
            "granted_execution_authority": False,
            "unavailable_reasons": [
                "Installation alone does not prove credentials, connectivity or protocol negotiation"
                if installed else "Executable was not found on this host"
            ],
            "auth_isolation": "Other applications' cookies, tokens and passwords are not inspected.",
        }

    def list_tools(self) -> list[dict]:
        return [self.inspect_tool(ident) for ident in self.tools]

    def verify_connectivity(self, tool_id: str) -> dict:
        # Historical API name retained, but this is only passive observation.
        record = self.inspect_tool(tool_id)
        return {
            "id": record["id"], "installed": record["installed"],
            "connected": False, "authenticated": False,
            "supports_acp": record["supports_acp"],
            "acp_compliant": False, "protocol_verified": False,
            "available_to_planner": False, "granted_execution_authority": False,
            "permissions": record["required_permissions"],
            "unavailable_reasons": record["unavailable_reasons"],
        }

    def list_models(self) -> list[dict]:
        """Show configured model labels without triggering migrations or decrypting secrets."""
        found: list[dict] = []
        try:
            with self._database().get_connection() as conn:
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='model_profiles'").fetchone():
                    rows = conn.execute("SELECT id, config_json FROM model_profiles ORDER BY id LIMIT 200").fetchall()
                    for row in rows:
                        try:
                            cfg = json.loads(row[1])
                            if not isinstance(cfg, dict):
                                continue
                            disabled = bool(cfg.get("disabled"))
                            name = str(cfg.get("model") or row[0])[:150]
                            provider = str(cfg.get("provider") or "configured")[:60]
                            context = cfg.get("num_ctx") or cfg.get("context_window") or 0
                            if type(context) is not int or context < 0:
                                context = 0
                            found.append({
                                "id": str(row[0])[:150], "name": name,
                                "provider": provider, "source": "configured_profile",
                                "is_local": is_local_endpoint(str(cfg.get("endpoint") or ""),
                                                              str(cfg.get("hosting") or "") or None),
                                "supports_tools": bool(cfg.get("supports_tools")),
                                "supports_vision": bool(cfg.get("vision")),
                                "context_window": min(context, 10000000),
                                "available": False,
                                "unavailable_reasons": ["Profile disabled" if disabled else
                                    "Configured model requires a separately verified live inference check"],
                            })
                        except (TypeError, ValueError, IndexError, KeyError):
                            continue
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='chatgpt_plan_meta'").fetchone():
                    row = conn.execute("SELECT value_json FROM chatgpt_plan_meta WHERE id=1").fetchone()
                    if row:
                        data = json.loads(row[0])
                        selection = data.get("model") if isinstance(data, dict) else None
                        if isinstance(selection, str) and selection.strip():
                            found.append({
                                "id": "configured-chatgpt-" + selection[:120],
                                "name": selection[:150], "provider": "chatgpt",
                                "source": "configured_chatgpt", "is_local": False,
                                "supports_tools": False, "supports_vision": False,
                                "context_window": 0, "available": False,
                                "unavailable_reasons": ["Configured ChatGPT selection; remote inference not verified"],
                            })
        except Exception:
            # Read-only inventory must not leak DB errors or create/repair state.
            return []
        return found
