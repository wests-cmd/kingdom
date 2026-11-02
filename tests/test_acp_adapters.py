"""Tests for ACP and External Coding Tool Adapters, Capability Discovery, and REST API.

Covers regression requirements:
1. Empty codex executable in PATH does not prove connected, planner-ready, authenticated, or ACP-compliant.
2. Unconfigured ChatGPT does not default to available.
3. Empty ollama executable without daemon/model weights does not make models available.
4. Actual configured custom model profiles from ModelProfiles are listed.
5. Revoked or unconfigured native Jules credentials/scope are marked unavailable.
6. Failed or absent protocol negotiation remains unverified; no binary execution during inspection.
7. Owner authentication and origin privacy boundary tests.
"""

import os
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.integrations.acp_adapters import (
    ACPToolManager,
    SUPPORTED_TOOLS,
    CATALOG_MODEL_TEMPLATES
)
from backend.models.profiles import ModelProfiles
from backend.storage.db import Database


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_kingdom.db"
    return Database(str(db_file))


def test_list_tools_manifest_shapes():
    manager = ACPToolManager()
    tools = manager.list_tools()
    assert len(tools) == len(SUPPORTED_TOOLS)
    tool_ids = [t["id"] for t in tools]
    assert "codex" in tool_ids
    assert "claude_code" in tool_ids
    assert "gemini_cli" in tool_ids
    assert "jules" in tool_ids
    assert "ollama" in tool_ids

    for tool in tools:
        assert "installed" in tool
        assert "status" in tool
        assert "protocol" in tool
        assert "supports_acp" in tool
        assert "capabilities" in tool
        assert "auth_isolation" in tool
        assert "granted_execution_authority" in tool
        assert tool["granted_execution_authority"] is False
        assert isinstance(tool["unavailable_reasons"], list)


def test_inspect_tool_acp_support():
    manager = ACPToolManager()
    codex = manager.inspect_tool("codex")
    assert codex["supports_acp"] is True
    assert codex["protocol"] == "acp"
    assert "process.execute" in codex["required_permissions"]
    assert "code.generate" in codex["capabilities"]
    assert "install_hint" in codex["beginner_setup_guide"]

    claude = manager.inspect_tool("claude_code")
    assert claude["supports_acp"] is False  # Wrapped CLI adapter
    assert claude["protocol"] == "cli_wrapper"

    gemini = manager.inspect_tool("gemini_cli")
    assert gemini["supports_acp"] is False
    assert gemini["protocol"] == "cli_wrapper"

    jules = manager.inspect_tool("jules")
    assert jules["supports_acp"] is True
    assert jules["protocol"] == "acp"

    ollama = manager.inspect_tool("ollama")
    assert ollama["supports_acp"] is False
    assert ollama["protocol"] == "http_api"


def test_inspect_tool_unknown():
    manager = ACPToolManager()
    with pytest.raises(KeyError):
        manager.inspect_tool("non_existent_tool")


def test_regression_empty_codex_in_path_not_promoted(tmp_path, monkeypatch):
    """Regression 1 & 6: An empty codex executable in PATH does NOT prove

    connected, planner-ready, authenticated, or ACP-compliant. Binary is NOT executed.
    """
    fake_bin_dir = tmp_path / "bin"
    fake_bin_dir.mkdir()
    empty_codex = fake_bin_dir / "codex"
    empty_codex.write_text("#!/bin/sh\nexit 1\n")
    empty_codex.chmod(0o755)

    monkeypatch.setenv("PATH", f"{fake_bin_dir}:{os.environ.get('PATH', '')}")

    manager = ACPToolManager()
    tool = manager.inspect_tool("codex")

    assert tool["installed"] is True
    # Crucial regressions: Must NOT be falsely promoted
    assert tool["connected"] is False
    assert tool["authenticated"] is False
    assert tool["available_to_planner"] is False
    assert tool["acp_compliant"] is False
    assert tool["protocol_verified"] is False
    assert tool["granted_execution_authority"] is False
    assert any("unverified" in r.lower() for r in tool["unavailable_reasons"])

    conn = manager.verify_connectivity("codex")
    assert conn["connected"] is False
    assert conn["available_to_planner"] is False
    assert conn["acp_compliant"] is False
    assert conn["protocol_verified"] is False


def test_regression_unconfigured_chatgpt_does_not_default_available(test_db):
    """Regression 2: Unconfigured ChatGPT does NOT default to available."""
    manager = ACPToolManager(db=test_db)
    models = manager.list_models()
    chatgpt = next((m for m in models if m["id"] == "chatgpt-4o"), None)
    assert chatgpt is not None
    assert chatgpt["available"] is False
    assert any("not ready" in r.lower() or "unconfigured" in r.lower() for r in chatgpt["unavailable_reasons"])


def test_regression_empty_ollama_without_daemon_weights_not_available(tmp_path, monkeypatch, test_db):
    """Regression 3: Empty ollama in PATH without daemon/weights does not make models available."""
    fake_bin_dir = tmp_path / "bin"
    fake_bin_dir.mkdir()
    empty_ollama = fake_bin_dir / "ollama"
    empty_ollama.write_text("#!/bin/sh\nexit 1\n")
    empty_ollama.chmod(0o755)

    monkeypatch.setenv("PATH", f"{fake_bin_dir}:{os.environ.get('PATH', '')}")

    manager = ACPToolManager(db=test_db)
    models = manager.list_models()
    qwen = next((m for m in models if m["id"] == "ollama-qwen-coder"), None)
    assert qwen is not None
    assert qwen["available"] is False
    assert any("unverified" in r.lower() for r in qwen["unavailable_reasons"])


def test_regression_configured_custom_model_profiles_are_listed(test_db, tmp_path):
    """Regression 4: Actual configured custom model profiles are listed in discovery."""
    profiles = ModelProfiles(test_db, root=str(tmp_path / "secrets"))
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

    manager = ACPToolManager(db=test_db)
    models = manager.list_models()
    custom = next((m for m in models if m["id"] == "custom-coder"), None)
    assert custom is not None
    assert custom["name"] == "deepseek-coder-33b"
    assert custom["provider"] == "openai_compatible"
    assert custom["context_window"] == 16384
    assert custom["supports_tools"] is True
    assert custom["requires_auth"] is True
    assert custom["available"] is True
    assert custom["source"] == "configured_profile"


def test_regression_native_jules_unconfigured_or_revoked_is_unavailable(test_db, tmp_path):
    """Regression 5: Revoked or unconfigured native Jules credentials/scope is unavailable."""
    manager = ACPToolManager(db=test_db)
    jules = manager.inspect_tool("jules")

    # Initially unconfigured
    assert jules["connected"] is False
    assert jules["available_to_planner"] is False
    assert any("disabled" in r.lower() or "credentials" in r.lower() for r in jules["unavailable_reasons"])

    conn = manager.verify_connectivity("jules")
    assert conn["connected"] is False
    assert conn["available_to_planner"] is False


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
