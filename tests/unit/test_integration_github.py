"""
Tests for GitHubProvider end-to-end integration and L4 human approval gate.
"""

from backend.integrations.github import GitHubProvider
from backend.security.credential_broker import CredentialBroker
from backend.integrations.tool_engine import ToolEngine
from backend.integrations.provider import ProviderHealthStatus

def test_github_provider_auth_and_read():
    broker = CredentialBroker()
    tool_engine = ToolEngine()
    github = GitHubProvider(broker, tool_engine)

    assert github.check_health() == ProviderHealthStatus.UNAUTHENTICATED

    # Authenticate with valid token
    assert github.authenticate({"token": "ghp_1234567890abcdef"}) is True
    assert github.check_health() == ProviderHealthStatus.HEALTHY

    # List issues
    issues_res = github.execute_operation("list_issues", {"repo": "wests-cmd/kingdom"}, {})
    assert len(issues_res["issues"]) == 2
    assert github.metrics.successful_calls == 1

def test_github_provider_create_issue_approval_gate():
    broker = CredentialBroker()
    tool_engine = ToolEngine()
    github = GitHubProvider(broker, tool_engine)
    github.authenticate({"token": "test_token"})

    # Attempt create_issue without L4 approval
    res_unapproved = github.execute_operation(
        "create_issue",
        {"repo": "wests-cmd/kingdom", "title": "New feature", "body": "Details"},
        {"l4_human_approved": False}
    )
    assert res_unapproved["status"] == "APPROVAL_REQUIRED"
    assert res_unapproved["requires_approval"] is True

    # Attempt create_issue with L4 approval
    res_approved = github.execute_operation(
        "create_issue",
        {"repo": "wests-cmd/kingdom", "title": "New feature", "body": "Details"},
        {"l4_human_approved": True}
    )
    assert res_approved["status"] == "SUCCESS"
    assert res_approved["issue"]["title"] == "New feature"
