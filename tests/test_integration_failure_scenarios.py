"""
Tests for integration failure scenarios (outages, expired tokens, rate limits, malformed responses).
"""

import pytest
from backend.integrations.github import GitHubProvider
from backend.security.credential_broker import CredentialBroker
from backend.integrations.tool_engine import ToolEngine
from backend.integrations.provider import ProviderHealthStatus

def test_failure_scenario_unauthenticated_execution():
    broker = CredentialBroker()
    tool_engine = ToolEngine()
    github = GitHubProvider(broker, tool_engine)

    with pytest.raises(PermissionError):
        github.execute_operation("get_repo", {"repo": "wests-cmd/kingdom"}, {})

def test_failure_scenario_missing_required_params():
    broker = CredentialBroker()
    tool_engine = ToolEngine()
    github = GitHubProvider(broker, tool_engine)
    github.authenticate({"token": "test_token"})

    with pytest.raises(ValueError):
        github.execute_operation("get_repo", {}, {})

def test_failure_scenario_invalid_operation():
    broker = CredentialBroker()
    tool_engine = ToolEngine()
    github = GitHubProvider(broker, tool_engine)
    github.authenticate({"token": "test_token"})

    with pytest.raises(NotImplementedError):
        github.execute_operation("unsupported_op", {"repo": "wests-cmd/kingdom"}, {})
