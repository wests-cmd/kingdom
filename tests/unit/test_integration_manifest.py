"""
Tests for IntegrationManifest schema validation.
"""

import pytest
from backend.integrations.manifest import IntegrationManifest, IntegrationRiskLevel

def test_manifest_validation_valid():
    manifest = IntegrationManifest(
        integration_id="org.kingdom.github",
        name="GitHub Integration",
        version="1.0.0",
        publisher="Kingdom Core",
        protocol_version="1.0",
        description="GitHub PR and issue integration",
        capabilities=["github.read", "github.write"],
        permissions=["repo:read", "issue:create"],
        tools=["github.issues.list", "github.issues.create"],
        risk_level=IntegrationRiskLevel.MEDIUM,
        data_classification="SENSITIVE"
    )
    errors = manifest.validate()
    assert len(errors) == 0

def test_manifest_validation_invalid():
    manifest = IntegrationManifest(
        integration_id="invalidid",
        name="",
        version="1.0.0",
        publisher="Test",
        protocol_version="2.0",
        description="Bad manifest",
        capabilities=[],
        permissions=[],
        tools=[],
        risk_level=IntegrationRiskLevel.HIGH,
        data_classification="PUBLIC"
    )
    errors = manifest.validate()
    assert len(errors) >= 3
    assert any("reverse-domain" in err for err in errors)
    assert any("name is required" in err for err in errors)
    assert any("protocol_version" in err for err in errors)
