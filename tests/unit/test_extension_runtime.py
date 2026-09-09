"""
Tests for KingdomExtensionSDK and ExtensionRuntime namespace isolation.
"""

import pytest
from sdk.kingdom_extension_sdk import KingdomExtensionSDK, ExtensionConfig
from backend.extensions.runtime import ExtensionRuntime

def test_extension_sdk_tool_registration():
    config = ExtensionConfig(
        extension_id="org.kingdom.ext.test",
        name="Test Ext",
        version="1.0.0",
        required_capabilities=["test.cap"],
        required_permissions=["test.perm"]
    )
    sdk = KingdomExtensionSDK(config)

    def echo_handler(params):
        return {"echo": params.get("msg")}

    sdk.register_tool_handler("ext.echo", echo_handler)
    res = sdk.handle_tool_call("ext.echo", {"msg": "hello world"})
    assert res["echo"] == "hello world"

def test_extension_runtime_namespace_isolation_and_events():
    runtime = ExtensionRuntime()
    runtime.initialize_extension_namespace("ext_a", ["task.completed"])
    runtime.initialize_extension_namespace("ext_b", ["workflow.started"])

    # Write isolated data
    runtime.write_isolated_data("ext_a", "secret_state", "data_a")
    assert runtime.read_isolated_data("ext_a", "secret_state", "ext_a") == "data_a"

    # Cross-extension access rejection
    with pytest.raises(PermissionError):
        runtime.read_isolated_data("ext_a", "secret_state", "ext_b")

    # Unauthorized event subscription rejection
    with pytest.raises(PermissionError):
        runtime.subscribe_event("ext_a", "security.audit_log")

    # Authorized event subscription
    assert runtime.subscribe_event("ext_a", "task.completed") is True
