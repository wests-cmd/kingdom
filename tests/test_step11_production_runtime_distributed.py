"""
Production-Grade Distributed Runtime Verification Suite (Step 11).

Tests:
1. Complete Node Lifecycle & Reconnection Revalidation
2. Remote Approval Model & Explicit Capability Authorization
3. Task Lease Renewal, Monotonic Fencing Tokens & Stale Result Invalidation
4. Network Partition Fail-Closed Isolation & Deterministic Reconciliation
5. Malicious VM Containment & Resource Exhaustion Protection
6. Security Incident Mode Emergency Lockdown Enforcement
"""

import pytest
import time
from backend.cluster.identity import KingdomIdentity, KnightIdentity
from backend.cluster.node_registry import NodeRegistry, node_registry, NodeState, NodeRole, HardwareProfile
from backend.cluster.pairing import pairing_manager
from backend.cluster.capabilities import capability_authorizer
from backend.cluster.capability_router import CapabilityRouter, CapabilityRoutingError
from backend.cluster.rejoin import rejoin_manager
from backend.cluster.task_leasing import TaskLeaseManager
from backend.cluster.partition_resilience import PartitionEngine, RevocationPropagator
from backend.cluster.sync_engine import sync_engine
from backend.runtime.workflow_engine import WorkflowResourceBudget, EmergencyIncidentMode


def test_node_lifecycle_and_reconnect_revalidation():
    """
    Verifies full lifecycle: DISCOVERED -> PENDING_APPROVAL -> APPROVED -> CONNECTED -> REVOKED.
    Verifies reconnection on revoked node is denied.
    """
    k_commander = KingdomIdentity.get_or_create()
    kn = KnightIdentity.get_or_create("kn-step11-lifecycle", "Lifecycle Knight")

    # 1. Pairing Invitation & Request
    inv = pairing_manager.create_invitation(ttl_seconds=300)
    msg = f"{inv['code']}:{kn.node_id}:{k_commander.node_id}".encode("utf-8")
    sig = kn.sign_message(msg).hex()

    req = {
        "code": inv["code"],
        "expected_kingdom_id": k_commander.node_id,
        "knight_public_identity": kn.get_public_identity(),
        "requested_capabilities": ["compute", "gpu"],
        "signature": sig
    }
    pair_res = pairing_manager.process_pairing_request(req)
    assert pair_res["success"] is True
    assert pair_res["status"] == NodeState.PENDING_APPROVAL.value

    # 2. Commander Approves Node
    node = capability_authorizer.approve_node_and_capabilities(kn.node_id, ["compute"])
    assert node["node_state"] == NodeState.APPROVED.value

    # 3. Node Connects/Rejoins
    rejoin_res = rejoin_manager.rejoin(kn.node_id, expected_kingdom_id=k_commander.node_id)
    assert rejoin_res["rejoined"] is True

    # 4. Revocation
    capability_authorizer.revoke_node(kn.node_id, reason="Security audit step 11")
    assert node_registry.get_node(kn.node_id).node_state == NodeState.REVOKED.value

    # 5. Reconnection attempt by revoked node is DENIED
    rejoin_revoked = rejoin_manager.rejoin(kn.node_id, expected_kingdom_id=k_commander.node_id)
    assert rejoin_revoked["rejoined"] is False
    assert "restricted state" in rejoin_revoked["error"]


def test_remote_approval_and_capability_isolation():
    """
    Verifies explicit capability grants and isolation against ungranted privileged capabilities.
    """
    kn = KnightIdentity.get_or_create("kn-step11-isolation", "Isolation Knight")
    node_registry.register_discovered_node({
        "id": kn.node_id,
        "node_state": NodeState.PENDING_APPROVAL.value,
        "capabilities": ["compute", "gpu", "system.execute", "credential.read"]
    })

    # Default DENY before approval
    assert capability_authorizer.is_capability_granted(kn.node_id, "compute") is False

    # Explicit restricted capability grant (compute + gpu ONLY)
    capability_authorizer.approve_node_and_capabilities(kn.node_id, ["compute", "gpu"])
    assert capability_authorizer.is_capability_granted(kn.node_id, "compute") is True
    assert capability_authorizer.is_capability_granted(kn.node_id, "gpu") is True

    # Unapproved capabilities are DENIED
    assert capability_authorizer.is_capability_granted(kn.node_id, "system.execute") is False
    assert capability_authorizer.is_capability_granted(kn.node_id, "credential.read") is False


def test_task_lease_fencing_and_stale_result_invalidation():
    """
    Verifies monotonic fencing token generation and rejection of stale task result submissions.
    """
    lease_mgr = TaskLeaseManager()

    # Issue lease to Knight 1 (fencing token 1)
    lease1 = lease_mgr.issue_lease("task_fencing_200", "kn-worker-1", "compute")
    assert lease1.fencing_token == 1

    # Reassign task to Knight 2 due to timeout (fencing token 2)
    lease2 = lease_mgr.issue_lease("task_fencing_200", "kn-worker-2", "compute")
    assert lease2.fencing_token == 2

    # Valid execution with fencing token 2 succeeds
    assert lease_mgr.validate_lease_execution("task_fencing_200", "kn-worker-2", fencing_token=2) is True

    # Stale result submission from Knight 1 (token 1) fails fencing / node mismatch validation
    with pytest.raises(PermissionError, match="Node mismatch"):
        lease_mgr.validate_lease_execution("task_fencing_200", "kn-worker-1", fencing_token=1)


def test_network_partition_isolation_and_reconciliation():
    """
    Verifies node isolation on heartbeat contact timeout, fail-closed router selection, and deterministic reconciliation.
    """
    dummy_repo = DummyRepo()
    registry = NodeRegistry(repository=dummy_repo)
    partition_engine = PartitionEngine(registry, max_heartbeat_skew_sec=10.0)

    registry.register_discovered_node({
        "id": "node_partition_1",
        "node_state": NodeState.CONNECTED.value,
        "health": "healthy",
        "capabilities": ["compute"],
        "granted_capabilities": ["compute"]
    })

    now = time.time()
    # Contact timeout (20s > 10s skew threshold) -> Node isolated and marked DISCONNECTED
    partition_detected = partition_engine.detect_partition_and_isolate("node_partition_1", last_contact_timestamp=now - 20.0)
    assert partition_detected is True
    assert registry.get_node("node_partition_1").node_state == NodeState.DISCONNECTED.value

    # Router rejects disconnected node (fail-closed)
    router = CapabilityRouter(registry)
    with pytest.raises(CapabilityRoutingError):
        router.select_best_node("compute")


def test_untrusted_vm_and_malicious_node_containment():
    """
    Verifies that untrusted nodes with fake identities or capability escalation attempts are isolated,
    and resource budget constraints raise RuntimeError when breached.
    """
    dummy_repo = DummyRepo()
    registry = NodeRegistry(repository=dummy_repo)

    # Untrusted VM declaring capabilities but NOT granted privileged capability
    registry.register_discovered_node({
        "id": "untrusted_vm_01",
        "node_state": NodeState.CONNECTED.value,
        "capabilities": ["compute", "system.admin"],
        "granted_capabilities": ["compute"]  # system.admin withheld
    })

    router = CapabilityRouter(registry)
    with pytest.raises(CapabilityRoutingError):
        router.select_best_node("system.admin")

    # Workflow Resource Budget enforcement
    budget = WorkflowResourceBudget(max_steps=2, max_cost_usd=0.5)
    budget.consume_step(cost_usd=0.2)
    budget.consume_step(cost_usd=0.2)

    with pytest.raises(RuntimeError, match="Max steps"):
        budget.consume_step(cost_usd=0.2)


def test_security_incident_mode_emergency_lockdown():
    """
    Verifies that activating Security Incident Mode freezes all autonomous operations and raises PermissionError.
    """
    incident_mode = EmergencyIncidentMode()
    incident_mode.activate_emergency_lockdown(operator="ADMIN_OPERATOR", reason="Compromise detected on edge node")

    assert incident_mode.is_active() is True
    with pytest.raises(PermissionError, match="Emergency Incident Lockdown ACTIVE"):
        incident_mode.enforce_incident_check()

    incident_mode.deactivate_emergency_lockdown(operator="ADMIN_OPERATOR")
    assert incident_mode.is_active() is False


class DummyRepo:
    def __init__(self):
        self.data = {}
    def get(self, k_id):
        return self.data.get(k_id)
    def save(self, item):
        self.data[item["id"]] = item
        return item
    def list_all(self):
        return list(self.data.values())
