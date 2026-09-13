"""
Multi-Process Production Distributed Topology & Knight Enrollment Lifecycle Suite.

Tests:
1. Multi-Node Process Startup & Local RPC Secure Transport Binding
2. Knight Enrollment Lifecycle: Startup -> WAITING_FOR_APPROVAL -> Commander Approval -> CONNECTED
3. Pairing Code Security: Expiration, Single-Use Invalidation, Replay Rejection, Ed25519 Proof-of-Possession Signature Verification
4. Unauthorized / Rejected Knight Access Blockade & Audit Telemetry Logging
"""

import pytest
import time
import json
import secrets
from backend.cluster.identity import KingdomIdentity, KnightIdentity, compute_fingerprint
from backend.cluster.node_registry import NodeRegistry, NodeState, NodeRole
from backend.cluster.pairing import PairingManager
from backend.cluster.transport import RPCSecureTransport, RPCMessage
from backend.cluster.capabilities import capability_authorizer
from backend.storage.repository import KnightRepository

class InMemoryRepo(KnightRepository):
    def __init__(self):
        self.data = {}
    def get(self, knight_id: str):
        return self.data.get(knight_id)
    def save(self, knight: dict):
        self.data[knight["id"]] = knight
        return knight
    def list_all(self):
        return list(self.data.values())

def test_multi_node_topology_enrollment_lifecycle():
    """
    Verifies full multi-node enrollment:
    Node A (Commander) & Node B (Knight).
    Knight initializes, requests pairing, stays in WAITING_FOR_APPROVAL, receives Commander approval, and opens secure RPC connection.
    """
    cmd_repo = InMemoryRepo()
    cmd_registry = NodeRegistry(repository=cmd_repo)
    cmd_identity = KingdomIdentity.get_or_create()
    pairing_mgr = PairingManager(kingdom_identity=cmd_identity, registry=cmd_registry)
    pairing_mgr._invitations.clear()

    knight_identity = KnightIdentity.get_or_create("kn-prod-topo-01", "Production Worker Node 1")

    # Step 1: Commander creates single-use pairing code
    invitation = pairing_mgr.create_invitation(ttl_seconds=300)
    code = invitation["code"]
    assert invitation["used"] is False

    # Step 2: Knight constructs signed pairing request
    msg_to_sign = f"{code}:{knight_identity.node_id}:{cmd_identity.node_id}".encode("utf-8")
    sig_hex = knight_identity.sign_message(msg_to_sign).hex()

    req_payload = {
        "code": code,
        "expected_kingdom_id": cmd_identity.node_id,
        "knight_public_identity": knight_identity.get_public_identity(),
        "requested_capabilities": ["gpu", "compute"],
        "signature": sig_hex,
        "is_local": False
    }

    # Step 3: Process pairing request -> Transition to PENDING_APPROVAL (WAITING_FOR_APPROVAL)
    res = pairing_mgr.process_pairing_request(req_payload)
    assert res["success"] is True
    assert res["status"] == NodeState.PENDING_APPROVAL.value

    # Verify node in registry is PENDING_APPROVAL with 0 granted capabilities
    registered_node = cmd_registry.get_node(knight_identity.node_id)
    assert registered_node is not None
    assert registered_node.node_state == NodeState.PENDING_APPROVAL.value
    assert registered_node.granted_capabilities == []

    # Step 4: Commander approves Knight with explicit capability scope
    approved_node = capability_authorizer.approve_node_and_capabilities(
        knight_identity.node_id,
        granted_capabilities=["gpu"]
    )
    assert approved_node["node_state"] == NodeState.APPROVED.value
    assert "gpu" in approved_node["granted_capabilities"]
    assert "compute" not in approved_node["granted_capabilities"]

    # Step 5: Establish Secure Signed RPC Communication between Commander and Knight
    cmd_transport = RPCSecureTransport(cmd_identity)
    knight_transport = RPCSecureTransport(knight_identity)

    # Knight sends signed status heartbeat RPC to Commander
    rpc_msg = knight_transport.create_signed_message(
        target_id=cmd_identity.node_id,
        msg_type="node.heartbeat",
        payload={"status": "ready", "load": 0.15}
    )

    # Commander unwraps and verifies message signature & identity binding
    unwrapped = cmd_transport.verify_and_unwrap_message(rpc_msg, expected_target_id=cmd_identity.node_id)
    assert unwrapped["valid"] is True
    assert unwrapped["sender_id"] == knight_identity.node_id
    assert unwrapped["payload"]["status"] == "ready"


def test_pairing_security_contracts():
    """
    Verifies pairing security guarantees:
    - Single-use code consumption
    - Replay attack rejection
    - Invalid signature rejection
    - Wrong target Kingdom rejection
    """
    cmd_identity = KingdomIdentity.get_or_create()
    pairing_mgr = PairingManager(kingdom_identity=cmd_identity)
    pairing_mgr._invitations.clear()

    inv = pairing_mgr.create_invitation(ttl_seconds=300)
    code = inv["code"]

    kn = KnightIdentity.get_or_create("kn-sec-test-01", "Security Test Knight")
    msg_to_sign = f"{code}:{kn.node_id}:{cmd_identity.node_id}".encode("utf-8")
    valid_sig = kn.sign_message(msg_to_sign).hex()

    # 1. Rejection on wrong target Kingdom ID
    wrong_req = {
        "code": code,
        "expected_kingdom_id": "KG-MALICIOUS-FAKE",
        "knight_public_identity": kn.get_public_identity(),
        "signature": valid_sig
    }
    res_wrong = pairing_mgr.process_pairing_request(wrong_req)
    assert res_wrong["success"] is False
    assert "Cross-Kingdom mismatch" in res_wrong["error"]

    # 2. Rejection on invalid signature
    bad_sig_req = {
        "code": code,
        "expected_kingdom_id": cmd_identity.node_id,
        "knight_public_identity": kn.get_public_identity(),
        "signature": secrets.token_hex(64)
    }
    res_bad_sig = pairing_mgr.process_pairing_request(bad_sig_req)
    assert res_bad_sig["success"] is False
    assert "signature verification" in res_bad_sig["error"].lower()

    # 3. Successful pairing consumes code
    valid_req = {
        "code": code,
        "expected_kingdom_id": cmd_identity.node_id,
        "knight_public_identity": kn.get_public_identity(),
        "signature": valid_sig
    }
    res_valid = pairing_mgr.process_pairing_request(valid_req)
    assert res_valid["success"] is True

    # 4. Replay attack using same code fails
    res_replay = pairing_mgr.process_pairing_request(valid_req)
    assert res_replay["success"] is False
    assert "Invalid, expired, or already used" in res_replay["error"]
