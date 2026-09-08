import json
import pytest
from backend.extensions.models import ExtensionTrustState
from backend.extensions.registry import ExtensionRegistry
from backend.extensions.manifest_validator import ExtensionManifestValidator, ManifestValidationError
from backend.extensions.sandbox import ExtensionSandbox, SandboxExecutionError
from backend.extensions.tool_registry import ExtensionToolRegistry, ToolExecutionError
from backend.extensions.event_bus import ExtensionEventBus
from backend.extensions.lifecycle import ExtensionLifecycleManager


@pytest.fixture
def sample_manifest_dict():
    return {
        "extension_id": "ext_weather_service",
        "name": "Weather Information Extension",
        "version": "1.0.0",
        "description": "Provides real-time weather forecasts.",
        "author": "Kingdom Ecosystem Team",
        "kingdom_compatibility": ">=40.0.0",
        "capabilities": ["weather.read"],
        "permissions": ["network.http_get"],
        "subscribed_events": ["system.city_selected"],
        "tools": [
            {
                "tool_id": "tool_get_weather",
                "name": "Get Weather Forecast",
                "description": "Fetches current weather.",
                "input_schema": {"required": ["city"]},
                "required_permissions": ["network.http_get"]
            }
        ]
    }


def test_manifest_validator_valid_and_prohibited(sample_manifest_dict):
    # Valid manifest
    manifest = ExtensionManifestValidator.validate_manifest(sample_manifest_dict)
    assert manifest.extension_id == "ext_weather_service"
    assert len(manifest.tools) == 1

    # Prohibited permission rejection
    bad_dict = sample_manifest_dict.copy()
    bad_dict["permissions"] = ["kernel.bypass_security"]
    with pytest.raises(ManifestValidationError, match="prohibited security permission"):
        ExtensionManifestValidator.validate_manifest(bad_dict)

    # Incompatible kingdom version rejection
    incompatible_dict = sample_manifest_dict.copy()
    incompatible_dict["kingdom_compatibility"] = ">=99.0.0"
    with pytest.raises(ManifestValidationError, match="requires Kingdom version"):
        ExtensionManifestValidator.validate_manifest(incompatible_dict)


def test_extension_registry_trust_lifecycle(sample_manifest_dict):
    registry = ExtensionRegistry()
    ext = registry.discover_extension(sample_manifest_dict)
    assert ext.state == ExtensionTrustState.DISCOVERED

    registry.install_extension("ext_weather_service")
    assert registry.get_extension("ext_weather_service").state == ExtensionTrustState.INSTALLED

    registry.enable_extension("ext_weather_service")
    assert registry.get_extension("ext_weather_service").state == ExtensionTrustState.ENABLED

    registry.disable_extension("ext_weather_service")
    assert registry.get_extension("ext_weather_service").state == ExtensionTrustState.DISABLED


def test_extension_sandbox_exception_and_quarantine(sample_manifest_dict):
    registry = ExtensionRegistry()
    registry.discover_extension(sample_manifest_dict)
    registry.install_extension("ext_weather_service")
    registry.enable_extension("ext_weather_service")

    sandbox = ExtensionSandbox(registry, max_error_threshold=2)

    def faulty_extension_func():
        raise ValueError("Simulated API connection timeout")

    # First error
    with pytest.raises(SandboxExecutionError, match="Simulated API connection timeout"):
        sandbox.execute_in_sandbox("ext_weather_service", faulty_extension_func)

    assert registry.get_extension("ext_weather_service").error_count == 1
    assert registry.get_extension("ext_weather_service").state == ExtensionTrustState.ENABLED

    # Second error triggers quarantine
    with pytest.raises(SandboxExecutionError):
        sandbox.execute_in_sandbox("ext_weather_service", faulty_extension_func)

    assert registry.get_extension("ext_weather_service").state == ExtensionTrustState.QUARANTINED

    # Execution when quarantined is blocked
    with pytest.raises(SandboxExecutionError, match="must be ENABLED"):
        sandbox.execute_in_sandbox("ext_weather_service", lambda: "ok")


def test_extension_tool_registry_and_permission_checks(sample_manifest_dict):
    registry = ExtensionRegistry()
    registry.discover_extension(sample_manifest_dict)
    registry.install_extension("ext_weather_service")
    registry.enable_extension("ext_weather_service")

    tool_registry = ExtensionToolRegistry(registry)

    def weather_handler(params):
        return f"Weather in {params['city']}: Sunny, 22C"

    tool_registry.register_tool_executor("tool_get_weather", weather_handler)

    # Missing caller permission should fail
    with pytest.raises(PermissionError, match="Caller missing required permission"):
        tool_registry.execute_tool("tool_get_weather", {"city": "London"}, caller_permissions=[])

    # Missing required parameter should fail
    with pytest.raises(ToolExecutionError, match="Missing required parameter 'city'"):
        tool_registry.execute_tool("tool_get_weather", {}, caller_permissions=["network.http_get"])

    # Valid execution
    res = tool_registry.execute_tool("tool_get_weather", {"city": "Tokyo"}, caller_permissions=["network.http_get"])
    assert res == "Weather in Tokyo: Sunny, 22C"


def test_extension_event_bus_scoping(sample_manifest_dict):
    registry = ExtensionRegistry()
    registry.discover_extension(sample_manifest_dict)
    registry.install_extension("ext_weather_service")
    registry.enable_extension("ext_weather_service")

    event_bus = ExtensionEventBus(registry)
    received = []

    def city_handler(payload):
        received.append(payload["city"])

    event_bus.subscribe("system.city_selected", city_handler)

    delivered = event_bus.publish("system.city_selected", {"city": "Paris"}, event_permission="network.http_get")
    assert delivered == 1
    assert received == ["Paris"]

    # Unsubscribed event
    delivered_unsub = event_bus.publish("system.user_logout", {"user": "alice"})
    assert delivered_unsub == 0


def test_extension_side_by_side_update_and_rollback(sample_manifest_dict):
    registry = ExtensionRegistry()
    registry.discover_extension(sample_manifest_dict)
    registry.install_extension("ext_weather_service")
    registry.enable_extension("ext_weather_service")

    lifecycle_mgr = ExtensionLifecycleManager(registry)

    # Prepare v1.1.0 update
    updated_manifest_dict = sample_manifest_dict.copy()
    updated_manifest_dict["version"] = "1.1.0"
    updated_manifest_dict["description"] = "v1.1.0 updated description"

    updated_instance = lifecycle_mgr.update_extension_side_by_side("ext_weather_service", updated_manifest_dict)
    assert updated_instance.manifest.version == "1.1.0"

    # Rollback to v1.0.0
    rolled_back_instance = lifecycle_mgr.rollback_extension("ext_weather_service", "1.0.0")
    assert rolled_back_instance.manifest.version == "1.0.0"
