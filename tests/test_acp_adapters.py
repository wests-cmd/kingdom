"""Tests for ACP and External Coding Tool Adapters."""
import pytest
from backend.integrations.acp_adapters import (
    ACPToolManager,
    SUPPORTED_TOOLS
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


def test_inspect_tool_acp_support():
    manager = ACPToolManager()
    codex = manager.inspect_tool("codex")
    assert codex["supports_acp"] is True
    assert "process.execute" in codex["required_permissions"]

    claude = manager.inspect_tool("claude_code")
    assert claude["supports_acp"] is False  # Wrapped CLI adapter

    jules = manager.inspect_tool("jules")
    assert jules["supports_acp"] is True


def test_inspect_tool_unknown():
    manager = ACPToolManager()
    with pytest.raises(KeyError):
        manager.inspect_tool("non_existent_tool")


def test_verify_connectivity():
    manager = ACPToolManager()
    conn = manager.verify_connectivity("codex")
    assert "connected" in conn
    assert conn["supports_acp"] is True
    assert isinstance(conn["permissions"], list)
