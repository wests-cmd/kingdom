import time
import pytest
from backend.extensions.models import ExtensionTrustState
from backend.extensions.registry import ExtensionRegistry
from backend.extensions.manifest_validator import ExtensionManifestValidator, ManifestValidationError
from backend.extensions.sandbox import ExtensionSandbox, SandboxExecutionError
from backend.extensions.tool_registry import ExtensionToolRegistry
from backend.extensions.event_bus import ExtensionEventBus
from backend.learning.models import SkillOutcome, ImprovementProposal
from backend.learning.experiment import LearningExperimentRunner, LearningDefenseError, LearningPoisoningDefense


def test_adversarial_manifest_prohibited_permissions():
    malicious_manifest = {
        "extension_id": "ext_evil_root",
        "name": "Evil Root Escalation",
        "version": "1.0.0",
        "description": "Attempts root escalation",
        "author": "Attacker",
        "permissions": ["kernel.bypass_security", "system.disable_audit"]
    }
    with pytest.raises(ManifestValidationError, match="prohibited security permission"):
        ExtensionManifestValidator.validate_manifest(malicious_manifest)


def test_adversarial_tool_permission_escalation():
    registry = ExtensionRegistry()
    manifest_dict = {
        "extension_id": "ext_protected_tool",
        "name": "Protected Tool",
        "version": "1.0.0",
        "description": "Sensitive tool",
        "author": "Security Team",
        "tools": [{
            "tool_id": "tool_sensitive_write",
            "name": "Sensitive Write",
            "description": "Sensitive filesystem modification",
            "required_permissions": ["filesystem.root_write"]
        }]
    }
    registry.discover_extension(manifest_dict)
    registry.install_extension("ext_protected_tool")
    registry.enable_extension("ext_protected_tool")

    tool_reg = ExtensionToolRegistry(registry)
    tool_reg.register_tool_executor("tool_sensitive_write", lambda p: "modified")

    # Call with insufficient permissions
    with pytest.raises(PermissionError, match="Caller missing required permission"):
        tool_reg.execute_tool("tool_sensitive_write", {}, caller_permissions=["read_only"])


def test_adversarial_event_bus_flooding_rate_limit():
    registry = ExtensionRegistry()
    manifest_dict = {
        "extension_id": "ext_listener",
        "name": "Listener Extension",
        "version": "1.0.0",
        "description": "Subscribes to events",
        "author": "Team",
        "subscribed_events": ["system.ping"]
    }
    registry.discover_extension(manifest_dict)
    registry.install_extension("ext_listener")
    registry.enable_extension("ext_listener")

    event_bus = ExtensionEventBus(registry, max_events_per_sec=10)
    event_bus.subscribe("system.ping", lambda p: None)

    for i in range(10):
        event_bus.publish("system.ping", {"seq": i})

    # 11th publish within 1 second triggers rate limit
    with pytest.raises(RuntimeError, match="rate limit exceeded"):
        event_bus.publish("system.ping", {"seq": 11})


def test_adversarial_revoked_extension_execution_blocked():
    registry = ExtensionRegistry()
    manifest_dict = {
        "extension_id": "ext_revoked",
        "name": "Revoked Extension",
        "version": "1.0.0",
        "description": "To be revoked",
        "author": "Unknown"
    }
    registry.discover_extension(manifest_dict)
    registry.install_extension("ext_revoked")
    registry.revoke_extension("ext_revoked", reason="Security vulnerability detected")

    # Attempting to enable revoked extension fails
    with pytest.raises(ValueError, match="must be INSTALLED or DISABLED"):
        registry.enable_extension("ext_revoked")


def test_adversarial_poisoned_learning_detection():
    # Construct 15 outcomes with identical timestamp to simulate automated injection attack
    ts = time.time()
    poisoned_outcomes = [
        SkillOutcome(
            timestamp=ts,
            skill_id="skill_attack",
            skill_version="2.0.0",
            task_id=f"t_{i}",
            success=True,
            latency_sec=0.01,
            provenance="untrusted_external"
        ) for i in range(15)
    ]

    is_poisoned = LearningPoisoningDefense.check_poisoning_risk(poisoned_outcomes)
    assert is_poisoned is True
