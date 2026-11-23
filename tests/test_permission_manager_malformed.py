"""Legacy PermissionManager must deny malformed claim shapes without raising.

This helper only evaluates locally validated snapshots. It is NOT an authenticated
network boundary, a security policy approval authority, or proof of node identity.
"""
import pytest

from backend.security.permissions import PermissionManager


@pytest.mark.parametrize("actor", [
    {"role": "guest", "capabilities": None},
    {"role": "guest", "capabilities": 17},
    {"role": "guest", "capabilities": "system.admin"},
    {"role": "guest", "capabilities": {"system.admin": True}},
    {"role": "guest", "capabilities": [None]},
    {"role": "guest", "capabilities": [42]},
    {"role": "guest", "capabilities": [[]]},
    {"role": "guest", "capabilities": [{"capability": "*"}]},
    {"role": "guest", "capabilities": ["filesystem.read", None]},
    {"role": ["admin"], "capabilities": []},
    {"role": {"admin": True}, "capabilities": []},
    {"role": None, "capabilities": []},
])
def test_malformed_actor_fails_closed(actor):
    assert PermissionManager().check_capability(actor, "filesystem.read") is False


@pytest.mark.parametrize("actor,capability,expected", [
    ({"role": "guest", "capabilities": []}, "filesystem.read", False),
    ({"role": "guest", "capabilities": ["filesystem.read"]}, "filesystem.read", True),
    ({"role": "guest", "capabilities": ["filesystem.read"]}, "filesystem.write", False),
    ({"role": "guest", "capabilities": ["memory.*"]}, "memory.read", True),
    ({"role": "observe", "capabilities": []}, "memory.read", True),
    ({"role": "observe", "capabilities": []}, "process.execute", False),
    ({"role": "knight", "capabilities": []}, "model.inference", True),
    ({"role": "knight", "capabilities": []}, "system.admin", False),
])
def test_well_formed_claim_behavior_is_preserved(actor, capability, expected):
    assert PermissionManager().check_capability(actor, capability) is expected


def test_custom_role_with_invalid_grants_fails_closed():
    manager = PermissionManager(custom_roles={"bad": [42, "filesystem.read"]})
    assert manager.check_capability({"role": "bad"}, "filesystem.read") is False
    manager = PermissionManager(custom_roles={"bad": None})
    assert manager.check_capability({"role": "bad"}, "filesystem.read") is False


def test_invalid_required_capability_fails_closed():
    manager = PermissionManager()
    for required in (None, "", [], {"role": "admin"}, 42):
        assert manager.check_capability({"role": "admin"}, required) is False
