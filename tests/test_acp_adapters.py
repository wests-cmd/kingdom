"""Tests for ACP and External Coding Tool Adapters, Capability Discovery, and REST API."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.integrations.acp_adapters import (
    ACPToolManager,
    SUPPORTED_TOOLS,
    KNOWN_MODELS_MANIFEST
)


def test_list_tools():
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


def test_list_models():
    manager = ACPToolManager()
    models = manager.list_models()
    assert len(models) == len(KNOWN_MODELS_MANIFEST)
    model_ids = [m["id"] for m in models]
    assert "chatgpt-4o" in model_ids
    assert "ollama-qwen-coder" in model_ids
    assert "ollama-llama3" in model_ids
    assert "gemini-1.5-pro" in model_ids

    for model in models:
        assert "context_window" in model
        assert "supports_tools" in model
        assert "supports_vision" in model
        assert "is_local" in model
        assert isinstance(model["unavailable_reasons"], list)


def test_verify_connectivity():
    manager = ACPToolManager()
    conn = manager.verify_connectivity("codex")
    assert "connected" in conn
    assert conn["supports_acp"] is True
    assert conn["protocol"] == "acp"
    assert isinstance(conn["permissions"], list)
    assert isinstance(conn["unavailable_reasons"], list)


def test_adapter_api_unauthorized():
    client = TestClient(app)
    # Without owner auth token, endpoints should be rejected (401)
    res = client.get("/integrations/adapters")
    assert res.status_code == 401

    res_tool = client.get("/integrations/adapters/codex")
    assert res_tool.status_code == 401


def test_adapter_api_authorized(monkeypatch):
    from backend.security.http_auth import require_owner
    # Mock require_owner dependency to simulate authenticated owner session
    app.dependency_overrides[require_owner] = lambda: {"role": "owner", "level": 5}
    try:
        client = TestClient(app)
        res = client.get("/integrations/adapters")
        assert res.status_code == 200
        data = res.json()
        assert "tools" in data
        assert "models" in data
        assert "credential_isolation" in data
        assert len(data["tools"]) == len(SUPPORTED_TOOLS)
        assert len(data["models"]) == len(KNOWN_MODELS_MANIFEST)

        # Inspect specific tool
        tool_res = client.get("/integrations/adapters/codex")
        assert tool_res.status_code == 200
        tool_data = tool_res.json()
        assert tool_data["id"] == "codex"
        assert tool_data["supports_acp"] is True
        assert "code.generate" in tool_data["capabilities"]

        # Unknown tool
        unknown_res = client.get("/integrations/adapters/unknown_tool")
        assert unknown_res.status_code == 404

        # Connectivity check
        conn_res = client.get("/integrations/adapters/codex/connectivity")
        assert conn_res.status_code == 200
        conn_data = conn_res.json()
        assert conn_data["id"] == "codex"
        assert conn_data["supports_acp"] is True
    finally:
        app.dependency_overrides.clear()
