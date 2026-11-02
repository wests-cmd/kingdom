"""Tests for Laptop 2 Experimental Autonomous Host profile and Swarm permission tiers."""
import pytest
from backend.security.permissions import permission_manager


def test_permission_tiers():
    # 1. Observe: Read-only telemetry
    actor_observe = {"role": "observe", "node_id": "knight-node-1"}
    assert permission_manager.check_capability(actor_observe, "memory.read") is True
    assert permission_manager.check_capability(actor_observe, "ai_map.read") is True
    assert permission_manager.check_capability(actor_observe, "filesystem.write") is False
    assert permission_manager.check_capability(actor_observe, "process.execute") is False

    # 2. Assist: Normal low-risk approved tasks
    actor_assist = {"role": "assist", "node_id": "knight-node-2"}
    assert permission_manager.check_capability(actor_assist, "model.inference") is True
    assert permission_manager.check_capability(actor_assist, "filesystem.read") is True
    assert permission_manager.check_capability(actor_assist, "filesystem.write") is False

    # 3. Develop: Coding, testing, and sandbox execution
    actor_develop = {"role": "develop", "node_id": "knight-node-3"}
    assert permission_manager.check_capability(actor_develop, "filesystem.write") is True
    assert permission_manager.check_capability(actor_develop, "process.execute") is True
    assert permission_manager.check_capability(actor_develop, "docker.execute") is False

    # 4. Admin Delegated
    actor_admin = {"role": "admin_delegated", "node_id": "controller"}
    assert permission_manager.check_capability(actor_admin, "system.admin") is True
    assert permission_manager.check_capability(actor_admin, "filesystem.delete") is True


def test_laptop2_experimental_host_isolation():
    # Laptop 2 authorized host with verified grant receives experimental capabilities
    actor_laptop2 = {"role": "experimental", "node_id": "laptop2-host", "is_experimental_host": True}
    assert permission_manager.check_capability(actor_laptop2, "docker.execute") is True
    assert permission_manager.check_capability(actor_laptop2, "process.execute") is True
    assert permission_manager.check_capability(actor_laptop2, "filesystem.write") is True

    # Forged node_id claiming to be laptop2 without verified grant is rejected
    actor_spoofed = {"role": "experimental", "node_id": "laptop2-spoof", "is_experimental_host": False}
    assert permission_manager.check_capability(actor_spoofed, "docker.execute") is False
    assert permission_manager.check_capability(actor_spoofed, "memory.read") is True

    # Untrusted / Non-experimental node (e.g. DT1 or ordinary knight) MUST NOT inherit experimental privileges
    actor_dt1 = {"role": "experimental", "node_id": "dt1-remote-knight", "is_experimental_host": True}
    # Must be downgraded to observe privileges even if spoofing flag
    assert permission_manager.check_capability(actor_dt1, "docker.execute") is False
    assert permission_manager.check_capability(actor_dt1, "process.execute") is False
    assert permission_manager.check_capability(actor_dt1, "filesystem.write") is False
    assert permission_manager.check_capability(actor_dt1, "memory.read") is True


def test_install_profiles_includes_experimental_autonomous():
    from pathlib import Path
    import json
    catalog_path = Path("configs/install_profiles.json")
    assert catalog_path.exists()
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert "experimental_autonomous" in data["profiles"]
    exp = data["profiles"]["experimental_autonomous"]
    assert exp["name"] == "Experimental Autonomous Host"
    assert "planner" in exp["knights"]
    assert "coder" in exp["knights"]
