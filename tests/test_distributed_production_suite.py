"""
Multi-Process Production Distributed Topology, Enrollment Lifecycle, and Security Contract Suite.

Tests:
1. Multi-Node Topology Enrollment Lifecycle: Startup -> WAITING_FOR_APPROVAL -> Commander Approval -> CONNECTED -> RPC Transport
2. Pairing Security Contracts: Single-use codes, replay attack rejection, wrong target rejection, invalid signature rejection
3. Transport Verification Contract: Verify RPCSecureTransport.verify_and_unwrap_message NEVER returns None across 10 security rejection cases
"""

import pytest
import time
import secrets
from typing import Dict, Any, Optional
from backend.cluster.identity import KingdomIdentity, KnightIdentity, BaseNodeIdentity
from backend.cluster.node_registry import NodeRegistry, NodeState, NodeRole
from backend.cluster.pairing import PairingManager
from backend.cluster.transport import RPCSecureTransport, RPCMessage, MAX_TIME_SKEW_SECONDS
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
    # Register node in default registry so capability_authorizer can find it
    from backend.cluster.node_registry import node_registry
    node_registry.register_discovered_node(registered_node.to_dict())

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
    assert unwrapped is not None
    assert isinstance(unwrapped, dict)
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


def test_verify_and_unwrap_message_never_returns_none():
    """
    Comprehensive regression test proving RPCSecureTransport.verify_and_unwrap_message()
    NEVER returns None across 10 distinct security rejection paths and malformed input scenarios.
    """
    cmd_identity = KingdomIdentity.get_or_create()
    kn_identity = KnightIdentity.get_or_create("kn-contract-test", "Contract Knight")

    cmd_transport = RPCSecureTransport(cmd_identity)
    kn_transport = RPCSecureTransport(kn_identity)

    from backend.cluster.node_registry import node_registry
    node_registry.register_discovered_node({
        "id": kn_identity.node_id,
        "node_state": NodeState.CONNECTED.value,
        "public_identity": kn_identity.get_public_identity(),
        "kingdom_id": cmd_identity.node_id
    })

    # 1. Non-dict payload
    res1 = cmd_transport.verify_and_unwrap_message("string_not_dict")
    assert res1 is not None and isinstance(res1, dict)
    assert res1["valid"] is False
    assert "expected dict" in res1["error"]

    # 2. None payload
    res2 = cmd_transport.verify_and_unwrap_message(None)
    assert res2 is not None and isinstance(res2, dict)
    assert res2["valid"] is False

    # 3. Protocol version mismatch
    msg = kn_transport.create_signed_message(cmd_identity.node_id, "test", {"data": 1})
    msg["protocol_version"] = "invalid.version.v99"
    res3 = cmd_transport.verify_and_unwrap_message(msg)
    assert res3 is not None and isinstance(res3, dict)
    assert res3["valid"] is False
    assert "Protocol mismatch" in res3["error"]

    # 4. Unregistered / unknown sender node
    unknown_kn = KnightIdentity.get_or_create("kn-unknown-999", "Unknown Knight")
    unknown_transport = RPCSecureTransport(unknown_kn)
    msg_unknown = unknown_transport.create_signed_message(cmd_identity.node_id, "test", {"data": 1})
    res4 = cmd_transport.verify_and_unwrap_message(msg_unknown)
    assert res4 is not None and isinstance(res4, dict)
    assert res4["valid"] is False
    assert "Unknown or unauthenticated sender" in res4["error"]

    # 5. Wrong target node
    msg_valid = kn_transport.create_signed_message(cmd_identity.node_id, "test", {"data": 1})
    res5 = cmd_transport.verify_and_unwrap_message(msg_valid, expected_target_id="KG-WRONG-TARGET")
    assert res5 is not None and isinstance(res5, dict)
    assert res5["valid"] is False
    assert "wrong target" in res5["error"].lower()

    # 6. Replay attack / duplicate msg_id
    res_first = cmd_transport.verify_and_unwrap_message(msg_valid)
    assert res_first["valid"] is True
    res_replay = cmd_transport.verify_and_unwrap_message(msg_valid)
    assert res_replay is not None and isinstance(res_replay, dict)
    assert res_replay["valid"] is False
    assert "Replay attack" in res_replay["error"]

    # 7. Clock skew / expired timestamp
    msg_skew = kn_transport.create_signed_message(cmd_identity.node_id, "test2", {"data": 1})
    msg_skew["timestamp"] = time.time() - (MAX_TIME_SKEW_SECONDS + 10.0)
    res7 = cmd_transport.verify_and_unwrap_message(msg_skew)
    assert res7 is not None and isinstance(res7, dict)
    assert res7["valid"] is False
    assert "clock skew" in res7["error"].lower()

    # 8. Missing signature
    msg_nosig = kn_transport.create_signed_message(cmd_identity.node_id, "test3", {"data": 1})
    del msg_nosig["signature"]
    res8 = cmd_transport.verify_and_unwrap_message(msg_nosig)
    assert res8 is not None and isinstance(res8, dict)
    assert res8["valid"] is False
    assert "Missing signature" in res8["error"]

    # 9. Invalid signature hex
    msg_badhex = kn_transport.create_signed_message(cmd_identity.node_id, "test4", {"data": 1})
    msg_badhex["signature"] = "not_hex_!!!"
    res9 = cmd_transport.verify_and_unwrap_message(msg_badhex)
    assert res9 is not None and isinstance(res9, dict)
    assert res9["valid"] is False
    assert "Invalid signature hex" in res9["error"]

    # 10. Restricted node state (REVOKED / REJECTED / QUARANTINED / PENDING_APPROVAL)
    node_registry.update_node_state(kn_identity.node_id, NodeState.REVOKED)
    msg_rev = kn_transport.create_signed_message(cmd_identity.node_id, "test5", {"data": 1})
    res10 = cmd_transport.verify_and_unwrap_message(msg_rev)
    assert res10 is not None and isinstance(res10, dict)
    assert res10["valid"] is False
    assert "revoked or restricted state" in res10["error"]
