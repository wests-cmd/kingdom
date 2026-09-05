import pytest
import time
from backend.cluster.identity import KingdomIdentity, KnightIdentity
from backend.cluster.node_registry import node_registry, NodeState
from backend.cluster.pairing import pairing_manager
from backend.cluster.capabilities import capability_authorizer
from backend.cluster.heartbeat import heartbeat_manager
from backend.cluster.transport import RPCSecureTransport

def test_kingdom_and_knight_identity_persistence():
    k1 = KingdomIdentity.get_or_create()
    k2 = KingdomIdentity.get_or_create()
    assert k1.node_id == k2.node_id
    assert k1.fingerprint == k2.fingerprint

    kn1 = KnightIdentity.get_or_create("kn-security-01", "Security Knight")
    kn2 = KnightIdentity.get_or_create("kn-security-01", "Security Knight")
    assert kn1.node_id == kn2.node_id
    assert kn1.fingerprint == kn2.fingerprint

def test_pairing_invitation_lifecycle_and_single_use():
    inv = pairing_manager.create_invitation(ttl_seconds=300)
    code = inv["code"]
    assert pairing_manager.verify_invitation(code) is not None

    # Process valid pairing request
    kn = KnightIdentity.get_or_create("kn-pair-01", "Pair Knight 1")
    req = {
        "code": code,
        "expected_kingdom_id": inv["kingdom_id"],
        "knight_public_identity": kn.get_public_identity(),
        "requested_capabilities": ["compute", "gpu"]
    }
    res = pairing_manager.process_pairing_request(req)
    assert res["success"] is True
    assert res["status"] == NodeState.PENDING_APPROVAL.value

    # Reusing same code must be rejected
    res2 = pairing_manager.process_pairing_request(req)
    assert res2["success"] is False
    assert "Invalid, expired, or already used" in res2["error"]

def test_cross_kingdom_connection_blocked():
    k_master = KingdomIdentity.get_or_create()
    kn = KnightIdentity.get_or_create("kn-cross-01", "Cross Knight")
    inv = pairing_manager.create_invitation(ttl_seconds=300)

    req = {
        "code": inv["code"],
        "expected_kingdom_id": "KG-ROGUE-999", # Wrong Kingdom ID!
        "knight_public_identity": kn.get_public_identity(),
        "requested_capabilities": ["compute"]
    }
    res = pairing_manager.process_pairing_request(req)
    assert res["success"] is False
    assert "Cross-Kingdom mismatch" in res["error"]

def test_identity_substitution_detection():
    kn_orig = KnightIdentity.get_or_create("kn-sub-01", "Orig Knight")
    node_registry.register_discovered_node({
        "id": kn_orig.node_id,
        "fingerprint": kn_orig.fingerprint,
        "public_identity": kn_orig.get_public_identity()
    })

    # Fake attacker knight presenting same ID with different identity keypair
    kn_fake = KnightIdentity("kn-sub-01", "Attacker Knight") # Fresh keypair
    inv = pairing_manager.create_invitation(ttl_seconds=300)

    req = {
        "code": inv["code"],
        "expected_kingdom_id": KingdomIdentity.get_or_create().node_id,
        "knight_public_identity": kn_fake.get_public_identity(),
        "requested_capabilities": ["compute"]
    }
    res = pairing_manager.process_pairing_request(req)
    assert res["success"] is False
    assert res.get("security_alert") is True
    assert node_registry.get_node("kn-sub-01")["node_state"] == NodeState.QUARANTINED.value

def test_capability_authorization_and_revocation():
    kn = KnightIdentity.get_or_create("kn-cap-01", "Cap Knight")
    node_registry.register_discovered_node({
        "id": kn.node_id,
        "node_state": NodeState.PENDING_APPROVAL.value,
        "capabilities": ["compute", "gpu", "storage_write"]
    })

    # Default deny check before approval
    assert capability_authorizer.is_capability_granted(kn.node_id, "compute") is False

    # Approve
    capability_authorizer.approve_node_and_capabilities(kn.node_id, ["compute", "gpu"])
    assert capability_authorizer.is_capability_granted(kn.node_id, "compute") is True
    assert capability_authorizer.is_capability_granted(kn.node_id, "gpu") is True
    assert capability_authorizer.is_capability_granted(kn.node_id, "storage_write") is False # Denied

    # Revoke
    capability_authorizer.revoke_node(kn.node_id, reason="Security audit test")
    assert capability_authorizer.is_capability_granted(kn.node_id, "compute") is False
    assert node_registry.get_node(kn.node_id)["node_state"] == NodeState.REVOKED.value

def test_rpc_signed_transport_and_replay_protection():
    k_identity = KingdomIdentity.get_or_create()
    kn_identity = KnightIdentity.get_or_create("kn-rpc-01", "RPC Knight")
    node_registry.register_discovered_node({
        "id": kn_identity.node_id,
        "node_state": NodeState.APPROVED.value,
        "public_identity": kn_identity.get_public_identity()
    })

    k_transport = RPCSecureTransport(k_identity)
    kn_transport = RPCSecureTransport(kn_identity)

    signed_msg = kn_transport.create_signed_message(k_identity.node_id, "TASK_EXEC", {"task_id": "123"})

    # Valid verification
    v1 = k_transport.verify_and_unwrap_message(signed_msg)
    assert v1["valid"] is True
    assert v1["msg_type"] == "TASK_EXEC"

    # Replay attack check
    v2 = k_transport.verify_and_unwrap_message(signed_msg)
    assert v2["valid"] is False
    assert "Replay attack" in v2["error"]
