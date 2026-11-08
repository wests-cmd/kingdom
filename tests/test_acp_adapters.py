import json
import os
import shutil
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.integrations.acp_adapters import (
    ACPToolManager,
    SUPPORTED_TOOLS,
    ToolAdapterManifest,
    is_local_endpoint,
    AdapterListResponse,
    ToolInspectionResponse,
    ToolConnectivityResponse,
    DiscoveredModel,
)
from backend.main import app
from backend.models.profiles import ModelProfiles
from backend.integrations.jules import JulesService
from backend.models.chatgpt_plan import ChatGPTPlanConnection


class InMemoryDB:
    def __init__(self):
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.db_path = ":memory:"

    def get_connection(self):
        class ConnContext:
            def __init__(self, conn):
                self.conn = conn

            def __enter__(self):
                return self.conn

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        return ConnContext(self._conn)


@pytest.fixture
def test_db():
    return InMemoryDB()


def test_supported_tools_manifest():
    manager = ACPToolManager()
    tools = manager.list_tools()
    assert len(tools) == len(SUPPORTED_TOOLS)
    tool_ids = {t.id for t in tools}
    assert "codex" in tool_ids
    assert "claude_code" in tool_ids
    assert "gemini_cli" in tool_ids
    assert "jules" in tool_ids
    assert "ollama" in tool_ids


def test_inspect_tool_details():
    manager = ACPToolManager()
    codex = manager.inspect_tool("codex")
    assert codex.id == "codex"
    assert codex.supports_acp is True
    assert codex.protocol == "acp"
    assert "filesystem.read" in codex.required_permissions
    assert codex.beginner_setup_guide is not None

    claude = manager.inspect_tool("claude_code")
    assert claude.id == "claude_code"
    assert claude.supports_acp is False  # CLI wrapper
    assert claude.protocol == "cli_wrapper"

    with pytest.raises(KeyError):
        manager.inspect_tool("nonexistent_tool")


# =========================================================================
# Findings 1 & 2 & 3: Read-Only Discovery, Schema Contracts & Unrelated Models
# =========================================================================

def test_discovery_is_strictly_read_only_on_empty_db(test_db, tmp_path, monkeypatch):
    """Discovery MUST be read-only over existing public configuration.

    It must NOT create tables in database (no schema migrations) or generate vault keys on disk.
    """
    secrets_dir = tmp_path / "secrets"
    monkeypatch.chdir(tmp_path)

    manager = ACPToolManager(db=test_db)

    # Call discovery methods
    tools = manager.list_tools()
    models = manager.list_models()
    jules = manager.inspect_tool("jules")

    # Assert responses are typed models
    assert isinstance(tools[0], ToolInspectionResponse)
    assert isinstance(models[0], DiscoveredModel)
    assert isinstance(jules, ToolInspectionResponse)

    # Verify no tables were created in test_db
    with test_db.get_connection() as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert len(tables) == 0, f"Expected no tables created, found: {tables}"

    # Verify no vault keys were created in secrets directory
    assert not secrets_dir.exists() or not list(secrets_dir.iterdir())


def test_catalog_templates_never_inherit_availability_from_unrelated_chatgpt_model(test_db, tmp_path):
    """Finding 1: Catalog templates must never inherit availability from an unrelated selected ChatGPT model.

    A saved-ready connection selecting gpt-6-sol or gpt-6.1-sol must NOT make the hardcoded
    chatgpt-4o template available.
    """
    conn = ChatGPTPlanConnection(test_db, root=str(tmp_path / "secrets"))
    # Mock ready state with an active account and model selection 'gpt-6-sol'
    account_id = "test-account-id"
    public = {
        "id": account_id,
        "client_id": "oaiapp_123",
        "subject": "sub_123",
        "label": "owner@example.com",
        "connected": True,
        "expires_at": 9999999999.0,
        "scopes": ["openid", "profile", "resource.invoke", "chatgpt.tokens.use.direct"],
        "refresh_available": True,
        "refresh_state": "idle",
        "session_generation": "gen_1",
        "revision": 1,
    }
    with test_db.get_connection() as db_conn:
        db_conn.execute(
            "INSERT INTO chatgpt_plan_accounts VALUES(?,?,?)",
            (account_id, json.dumps(public), b"dummy_secret"),
        )
        meta = {
            "host_id": "urn:uuid:test",
            "enabled": True,
            "model": "gpt-6-sol",
            "active_account": account_id,
            "last_error": None,
            "revision": 1,
        }
        db_conn.execute("UPDATE chatgpt_plan_meta SET value_json=? WHERE id=1", (json.dumps(meta),))
        db_conn.commit()

    # Verify status() reports ready
    status = conn.status()
    assert status["state"] == "ready"
    assert status["model"] == "gpt-6-sol"

    # Now run discovery
    manager = ACPToolManager(db=test_db)
    models = manager.list_models()

    # The catalog template chatgpt-4o MUST NOT be available!
    chatgpt_4o = next((m for m in models if m.id == "chatgpt-4o"), None)
    assert chatgpt_4o is not None
    assert chatgpt_4o.available is False
    assert any("does not match" in r.lower() or "not match" in r.lower() for r in chatgpt_4o.unavailable_reasons)

    # Actual configured model selection gpt-6-sol is surfaced distinctly
    configured_gpt6 = next((m for m in models if "gpt-6-sol" in m.id), None)
    assert configured_gpt6 is not None
    assert configured_gpt6.source == "configured_chatgpt"
    # Live inference is explicitly separated from configuration and unverified
    assert configured_gpt6.available is False
    assert any("unverified" in r.lower() for r in configured_gpt6.unavailable_reasons)


# =========================================================================
# Preserved 7 Regressions (Owner Auth, Configured Profiles, False Readiness)
# =========================================================================

def test_regression_binary_in_path_does_not_falsely_promote_readiness(tmp_path, monkeypatch):
    """Regression 1: Binary presence in PATH does NOT prove connectivity, authentication,
    protocol compliance, or execution authority.
    """
    fake_bin_dir = tmp_path / "bin"
    fake_bin_dir.mkdir()
    empty_codex = fake_bin_dir / "codex"
    empty_codex.write_text("#!/bin/sh\nexit 1\n")
    empty_codex.chmod(0o755)

    empty_codex_exe = fake_bin_dir / "codex.exe"
    empty_codex_exe.write_bytes(b"")

    monkeypatch.setenv("PATH", f"{fake_bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    manager = ACPToolManager()
    tool = manager.inspect_tool("codex")

    assert tool.installed is True
    # Crucial regressions: Must NOT be falsely promoted
    assert tool.connected is False
    assert tool.authenticated is False
    assert tool.available_to_planner is False
    assert tool.acp_compliant is False
    assert tool.protocol_verified is False
    assert tool.granted_execution_authority is False
    assert any("unverified" in r.lower() for r in tool.unavailable_reasons)

    conn = manager.verify_connectivity("codex")
    assert conn.connected is False
    assert conn.available_to_planner is False
    assert conn.acp_compliant is False
    assert conn.protocol_verified is False


def test_regression_unconfigured_chatgpt_does_not_default_available(test_db):
    """Regression 2: Unconfigured ChatGPT does NOT default to available."""
    manager = ACPToolManager(db=test_db)
    models = manager.list_models()
    chatgpt = next((m for m in models if m.id == "chatgpt-4o"), None)
    assert chatgpt is not None
    assert chatgpt.available is False
    assert any("not ready" in r.lower() or "unconfigured" in r.lower() for r in chatgpt.unavailable_reasons)


def test_regression_empty_ollama_without_daemon_weights_not_available(tmp_path, monkeypatch, test_db):
    """Regression 3: Empty ollama in PATH without daemon/weights does not make models available."""
    fake_bin_dir = tmp_path / "bin"
    fake_bin_dir.mkdir()
    empty_ollama = fake_bin_dir / "ollama"
    empty_ollama.write_text("#!/bin/sh\nexit 1\n")
    empty_ollama.chmod(0o755)

    empty_ollama_exe = fake_bin_dir / "ollama.exe"
    empty_ollama_exe.write_bytes(b"")

    monkeypatch.setenv("PATH", f"{fake_bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    manager = ACPToolManager(db=test_db)
    models = manager.list_models()
    qwen = next((m for m in models if m.id == "ollama-qwen-coder"), None)
    assert qwen is not None
    assert qwen.available is False
    assert any("unverified" in r.lower() for r in qwen.unavailable_reasons)


def test_regression_configured_custom_model_profiles_are_unverified(test_db, tmp_path):
    """Regression 4 & 5: Configured custom model profiles appear in discovery,
    but remain available=False with explicit reasons whether disabled or enabled.
    """
    profiles = ModelProfiles(test_db, root=str(tmp_path / "secrets"))
    # 1. Enabled custom profile
    profiles.save("custom-coder", {
        "provider": "openai_compatible",
        "endpoint": "https://custom-server.internal/v1",
        "model": "deepseek-coder-33b",
        "hosting": "cloud",
        "variant": "custom",
        "num_ctx": 16384,
        "supports_tools": True,
        "vision": False,
        "auto_select": True
    }, api_key="sk-test-key")

    # 2. Disabled custom profile
    profiles.save("disabled-profile", {
        "provider": "ollama",
        "endpoint": "http://127.0.0.1:1",
        "model": "uninstalled-model",
        "hosting": "local",
        "variant": "custom",
        "disabled": True,
        "auto_select": False
    })

    manager = ACPToolManager(db=test_db)
    models = manager.list_models()

    custom = next((m for m in models if m.id == "custom-coder"), None)
    assert custom is not None
    assert custom.name == "deepseek-coder-33b"
    assert custom.provider == "openai_compatible"
    assert custom.context_window == 16384
    assert custom.supports_tools is True
    assert custom.requires_auth is True
    assert custom.available is False  # Must NOT be falsely promoted to available!
    assert custom.source == "configured_profile"
    assert any("unverified" in r.lower() for r in custom.unavailable_reasons)

    disabled = next((m for m in models if m.id == "disabled-profile"), None)
    assert disabled is not None
    assert disabled.available is False
    assert any("disabled" in r.lower() for r in disabled.unavailable_reasons)


def test_regression_is_local_endpoint_detection():
    """Regression 6: Substring 'localhost' in cloud domains must not be classified as local,
    while valid loopback hostnames/IPs and explicit local hosting are.
    """
    assert is_local_endpoint("https://localhost.example.invalid", hosting="cloud") is False
    assert is_local_endpoint("https://localhost.example.invalid", hosting=None) is False
    assert is_local_endpoint("http://localhost:11434", hosting=None) is True
    assert is_local_endpoint("http://127.0.0.1:11434", hosting=None) is True
    assert is_local_endpoint("http://[::1]:11434", hosting=None) is True
    assert is_local_endpoint("https://remote.server.internal", hosting="local") is True


def test_regression_native_jules_unconfigured_or_revoked_is_unavailable(test_db):
    """Regression 7a: Revoked or unconfigured native Jules credentials/scope is unavailable."""
    manager = ACPToolManager(db=test_db)
    jules = manager.inspect_tool("jules")

    # Initially unconfigured
    assert jules.connected is False
    assert jules.authenticated is False
    assert jules.available_to_planner is False
    assert any("disabled" in r.lower() or "credentials" in r.lower() or "unconfigured" in r.lower() for r in jules.unavailable_reasons)

    conn = manager.verify_connectivity("jules")
    assert conn.connected is False
    assert conn.authenticated is False
    assert conn.available_to_planner is False


def test_regression_native_jules_configured_with_invalid_key_remains_unverified(test_db, tmp_path):
    """Regression 7b: Saved invalid native Jules key + enabled + allowlists remains
    unauthenticated/unconnected/not planner-ready. Presence of local key is not proof of provider auth.
    """
    service = JulesService(test_db, secrets_root=str(tmp_path / "secrets"))
    service.configure(
        enabled=True,
        allowed_repositories=["wests-cmd/kingdom"],
        allowed_sources=["sources/github/wests-cmd/kingdom"],
        api_key="invalid-disposable-key-12345"
    )

    manager = ACPToolManager(db=test_db)
    jules = manager.inspect_tool("jules")

    assert jules.connected is False
    assert jules.authenticated is False
    assert jules.available_to_planner is False
    assert jules.acp_compliant is False
    assert jules.protocol_verified is False
    assert jules.granted_execution_authority is False
    assert any("unverified" in r.lower() for r in jules.unavailable_reasons)

    conn = manager.verify_connectivity("jules")
    assert conn.connected is False
    assert conn.authenticated is False
    assert conn.available_to_planner is False


def test_adapter_api_unauthorized():
    client = TestClient(app)
    # Without owner auth token, endpoints should be rejected (401)
    res = client.get("/integrations/adapters")
    assert res.status_code == 401

    res_tool = client.get("/integrations/adapters/codex")
    assert res_tool.status_code == 401


def test_adapter_api_untrusted_origin(monkeypatch):
    from backend.security.http_auth import require_owner
    client = TestClient(app)
    # Request from untrusted external origin with token should be rejected (403)
    res = client.get(
        "/integrations/adapters",
        headers={
            "Authorization": "Bearer some-token",
            "Origin": "https://malicious-website.com"
        }
    )
    assert res.status_code in {401, 403}


def test_adapter_api_authorized(monkeypatch, test_db):
    from backend.security.http_auth import require_owner
    from backend.integrations import adapter_api

    # Override manager to use test db
    test_manager = ACPToolManager(db=test_db)
    monkeypatch.setattr(adapter_api, "get_manager", lambda: test_manager)

    # Mock require_owner dependency to simulate authenticated owner session
    app.dependency_overrides[require_owner] = lambda: {"role": "owner"}
    try:
        client = TestClient(app)
        res = client.get("/integrations/adapters")
        assert res.status_code == 200
        data = res.json()
        assert "tools" in data
        assert "models" in data
        assert "credential_isolation" in data
        assert data["execution_authority_granted"] is False
        assert len(data["tools"]) == len(SUPPORTED_TOOLS)

        # Inspect specific tool
        tool_res = client.get("/integrations/adapters/codex")
        assert tool_res.status_code == 200
        tool_data = tool_res.json()
        assert tool_data["id"] == "codex"
        assert tool_data["supports_acp"] is True
        assert tool_data["acp_compliant"] is False
        assert tool_data["available_to_planner"] is False

        # Unknown tool
        unknown_res = client.get("/integrations/adapters/unknown_tool")
        assert unknown_res.status_code == 404

        # Connectivity check
        conn_res = client.get("/integrations/adapters/codex/connectivity")
        assert conn_res.status_code == 200
        conn_data = conn_res.json()
        assert conn_data["id"] == "codex"
        assert conn_data["connected"] is False
        assert conn_data["available_to_planner"] is False
    finally:
        app.dependency_overrides.clear()
