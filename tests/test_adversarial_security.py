"""Adversarial security regression test suite for Kingdom.

Verifies the six critical security layers:
1. Fake Laptop 2: Spoofed node_id claiming to be Laptop 2 without verified grant is rejected.
2. Fake Authorization: Claiming verified grant on a non-designated host is rejected.
3. Capability Injection: Injected system.admin on unauthorized actor without role mapping is checked/restricted.
4. Unauthorized API: Gap Register requests without owner token return HTTP 401 or 403.
5. Approved Knight: Authenticated Knight device operates strictly within authorized scope.
6. Revoked Knight: Revoking device authorization halts privileged execution.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.security.permissions import PermissionManager, permission_manager
from backend.security.http_auth import require_owner


def test_scenario_1_fake_laptop_2_node_id_spoof():
    """Actor claims node_id='laptop2' without verified grant flag -> rejected / downgraded to observe."""
    attacker_actor = {
        "role": "experimental",
        "node_id": "laptop2-fake-identity",
        "is_experimental_host": False,
        "verified_experimental_grant": False
    }
    # Unverified Laptop 2 spoof must NOT have privileged execute permissions
    assert permission_manager.check_capability(attacker_actor, "docker.execute") is False
    assert permission_manager.check_capability(attacker_actor, "process.execute") is False
    assert permission_manager.check_capability(attacker_actor, "filesystem.write") is False
    # Only downgraded observe capability
    assert permission_manager.check_capability(attacker_actor, "memory.read") is True


def test_scenario_2_fake_authorization_non_designated_host():
    """Actor provides verified_experimental_grant=True on non-Laptop 2 host (e.g. DT1 or general node) -> rejected."""
    attacker_actor = {
        "role": "experimental",
        "node_id": "dt1-control-node",
        "is_experimental_host": True,
        "verified_experimental_grant": True
    }
    # Even if verified flag is claimed, experimental authority is strictly bounded to designated Laptop 2 hosts
    assert permission_manager.check_capability(attacker_actor, "docker.execute") is False
    assert permission_manager.check_capability(attacker_actor, "process.execute") is False
    assert permission_manager.check_capability(attacker_actor, "filesystem.write") is False


def test_scenario_3_capability_injection():
    """Actor tries invalid actor payloads or unrecognized role structure."""
    # Invalid actor formats
    assert permission_manager.check_capability(None, "system.admin") is False
    assert permission_manager.check_capability("not_a_dict", "system.admin") is False
    assert permission_manager.check_capability({}, "system.admin") is False

    # Guest role cannot perform administrative or write capabilities
    guest_actor = {"role": "guest", "node_id": "unknown-node"}
    assert permission_manager.check_capability(guest_actor, "filesystem.write") is False
    assert permission_manager.check_capability(guest_actor, "process.execute") is False
    assert permission_manager.check_capability(guest_actor, "system.admin") is False


def test_scenario_4_unauthorized_api_call():
    """Calling Gap Register API without owner authentication yields HTTP 401 or 403."""
    app.dependency_overrides.pop(require_owner, None)
    client = TestClient(app)

    res = client.get("/system/gap-register")
    assert res.status_code in (401, 403)

    res_post = client.post("/system/gap-register/sync-backlog")
    assert res_post.status_code in (401, 403)


def test_scenario_5_approved_knight_operates_within_scope():
    """Legitimately authenticated Knight operates strictly within assigned role capabilities."""
    knight_actor = {"role": "knight", "node_id": "knight-01"}
    # Allowed
    assert permission_manager.check_capability(knight_actor, "model.inference") is True
    assert permission_manager.check_capability(knight_actor, "memory.read") is True
    assert permission_manager.check_capability(knight_actor, "node.execute") is True
    assert permission_manager.check_capability(knight_actor, "filesystem.read") is True

    # Denied (out of scope for standard Knight)
    assert permission_manager.check_capability(knight_actor, "filesystem.delete") is False
    assert permission_manager.check_capability(knight_actor, "process.execute") is False
    assert permission_manager.check_capability(knight_actor, "docker.execute") is False
    assert permission_manager.check_capability(knight_actor, "system.admin") is False


def test_scenario_6_revoked_knight_halts_execution():
    """Dynamic role revocation immediately removes privileged capabilities."""
    custom_pm = PermissionManager()
    active_knight = {"role": "knight", "node_id": "knight-02"}
    assert custom_pm.check_capability(active_knight, "model.inference") is True

    # Revoke role to guest/quarantined
    active_knight["role"] = "guest"
    assert custom_pm.check_capability(active_knight, "model.inference") is False
    assert custom_pm.check_capability(active_knight, "node.execute") is False
