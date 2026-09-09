"""
Tests for ToolEngine tool generation, authorized discovery, and validation chain.
"""

from backend.integrations.tool_engine import ToolEngine, ToolDefinition
from backend.integrations.manifest import IntegrationManifest, IntegrationRiskLevel

def test_tool_generation_and_discovery():
    manifest = IntegrationManifest(
        integration_id="org.kingdom.github",
        name="GitHub Integration",
        version="1.0.0",
        publisher="Kingdom Core",
        protocol_version="1.0",
        description="GitHub PR and issue integration",
        capabilities=["github.read"],
        permissions=["repo:read"],
        tools=["github.issues.list"],
        risk_level=IntegrationRiskLevel.LOW,
        data_classification="PUBLIC"
    )

    engine = ToolEngine()
    ops = [
        {
            "tool_id": "github.issues.list",
            "operation": "list_issues",
            "description": "List repository issues",
            "input_schema": {"type": "object", "properties": {"repo": {"type": "string"}}, "required": ["repo"]},
            "capabilities": ["github.read"],
            "permissions": ["repo:read"]
        },
        {
            "tool_id": "github.issues.create",
            "operation": "create_issue",
            "description": "Create issue in repository",
            "input_schema": {"type": "object", "properties": {"repo": {"type": "string"}, "title": {"type": "string"}}, "required": ["repo", "title"]},
            "capabilities": ["github.write"],
            "permissions": ["repo:write"]
        }
    ]

    generated = engine.generate_tools_from_manifest(manifest, ops)
    assert len(generated) == 2

    # Discovery with read-only actor
    discovered_read = engine.discover_authorized_tools(["github.read"], ["repo:read"])
    assert len(discovered_read) == 1
    assert discovered_read[0].tool_id == "github.issues.list"

    # Discovery with admin actor
    discovered_all = engine.discover_authorized_tools(["github.read", "github.write"], ["repo:read", "repo:write"])
    assert len(discovered_all) == 2

def test_tool_invocation_validation():
    engine = ToolEngine()
    tool = ToolDefinition(
        tool_id="github.issues.create",
        version="1.0.0",
        provider_id="org.kingdom.github",
        operation="create_issue",
        description="Create issue",
        input_schema={"required": ["repo", "title"]},
        output_schema={},
        required_capabilities=["github.write"],
        required_permissions=["repo:write"],
        risk_level="MEDIUM"
    )
    engine.register_tool(tool)

    # Valid invocation
    errs_valid = engine.validate_tool_invocation(
        "github.issues.create@1.0.0",
        {"repo": "wests-cmd/kingdom", "title": "Bug fix"},
        ["github.write"],
        ["repo:write"]
    )
    assert len(errs_valid) == 0

    # Missing capability and missing parameter
    errs_invalid = engine.validate_tool_invocation(
        "github.issues.create@1.0.0",
        {"repo": "wests-cmd/kingdom"},
        ["github.read"],
        ["repo:write"]
    )
    assert len(errs_invalid) == 2
    assert any("capability" in e for e in errs_invalid)
    assert any("parameter: title" in e for e in errs_invalid)
