import pytest
import time
from backend.cluster.identity import KingdomIdentity, KnightIdentity
from backend.cluster.node_registry import node_registry, NodeState
from backend.cluster.pairing import pairing_manager
from backend.cluster.capabilities import capability_authorizer
from backend.cluster.heartbeat import heartbeat_manager
from backend.cluster.transport import RPCSecureTransport
from backend.cluster.autoconnect import AutoConnector
from backend.cluster.rejoin import RejoinManager
from backend.cluster.sync_engine import SyncEngine
from backend.cluster.topology_sync import TopologySync

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

    kn = KnightIdentity.get_or_create("kn-pair-01", "Pair Knight 1")
    msg = f"{code}:{kn.node_id}:{inv['kingdom_id']}".encode("utf-8")
    sig = kn.sign_message(msg).hex()

    req = {
        "code": code,
        "expected_kingdom_id": inv["kingdom_id"],
        "knight_public_identity": kn.get_public_identity(),
        "requested_capabilities": ["compute", "gpu"],
        "signature": sig
    }
    res = pairing_manager.process_pairing_request(req)
    assert res["success"] is True
    assert res["status"] == NodeState.PENDING_APPROVAL.value

    res2 = pairing_manager.process_pairing_request(req)
    assert res2["success"] is False
    assert "Invalid, expired, or already used" in res2["error"]

def test_pairing_expiration_enforcement():
    inv = pairing_manager.create_invitation(ttl_seconds=1)
    time.sleep(1.2)
    assert pairing_manager.verify_invitation(inv["code"]) is None

def test_cross_kingdom_connection_blocked():
    k_master = KingdomIdentity.get_or_create()
    kn = KnightIdentity.get_or_create("kn-cross-01", "Cross Knight")
    inv = pairing_manager.create_invitation(ttl_seconds=300)

    msg = f"{inv['code']}:{kn.node_id}:KG-ROGUE-999".encode("utf-8")
    sig = kn.sign_message(msg).hex()

    req = {
        "code": inv["code"],
        "expected_kingdom_id": "KG-ROGUE-999",
        "knight_public_identity": kn.get_public_identity(),
        "requested_capabilities": ["compute"],
        "signature": sig
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

    kn_fake = KnightIdentity("kn-sub-01", "Attacker Knight")
    inv = pairing_manager.create_invitation(ttl_seconds=300)

    k_id = KingdomIdentity.get_or_create().node_id
    msg = f"{inv['code']}:{kn_fake.node_id}:{k_id}".encode("utf-8")
    sig = kn_fake.sign_message(msg).hex()

    req = {
        "code": inv["code"],
        "expected_kingdom_id": k_id,
        "knight_public_identity": kn_fake.get_public_identity(),
        "requested_capabilities": ["compute"],
        "signature": sig
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

    assert capability_authorizer.is_capability_granted(kn.node_id, "compute") is False

    capability_authorizer.approve_node_and_capabilities(kn.node_id, ["compute", "gpu"])
    assert capability_authorizer.is_capability_granted(kn.node_id, "compute") is True
    assert capability_authorizer.is_capability_granted(kn.node_id, "gpu") is True
    assert capability_authorizer.is_capability_granted(kn.node_id, "storage_write") is False

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

    v1 = k_transport.verify_and_unwrap_message(signed_msg)
    assert v1["valid"] is True
    assert v1["msg_type"] == "TASK_EXEC"

    v2 = k_transport.verify_and_unwrap_message(signed_msg)
    assert v2["valid"] is False
    assert "Replay attack" in v2["error"]

def test_cluster_subsystems_wiring():
    kn = KnightIdentity.get_or_create("kn-wire-01", "Wire Knight")
    node_registry.register_discovered_node({
        "id": kn.node_id,
        "node_state": NodeState.APPROVED.value,
        "public_identity": kn.get_public_identity()
    })

    rejoin_mgr = RejoinManager()
    res = rejoin_mgr.rejoin(kn.node_id)
    assert res["rejoined"] is True

    auto_conn = AutoConnector()
    res_conn = auto_conn.connect(kn.node_id)
    assert res_conn["success"] is True

    sync_engine = SyncEngine()
    synced = sync_engine.synchronize()
    assert synced["status"] == "synced"
    assert synced["total_nodes"] > 0

    topo_sync = TopologySync()
    topo = topo_sync.sync()
    assert topo["commander"] == "KG-MASTER-01"
    assert len(topo["knights"]) > 0

def test_full_node_lifecycle_and_unauthorized_capability_denial():
    # 1. Fresh Kingdom & Knight Identities
    k_commander = KingdomIdentity.get_or_create()
    kn = KnightIdentity.get_or_create("kn-lifecycle-e2e", "E2E Lifecycle Knight")

    # 2. Kingdom issues single-use pairing invitation
    inv = pairing_manager.create_invitation(ttl_seconds=300)
    code = inv["code"]

    # 3. Knight requests pairing with valid proof-of-possession signature
    msg = f"{code}:{kn.node_id}:{k_commander.node_id}".encode("utf-8")
    sig = kn.sign_message(msg).hex()
    req = {
        "code": code,
        "expected_kingdom_id": k_commander.node_id,
        "knight_public_identity": kn.get_public_identity(),
        "requested_capabilities": ["compute", "gpu", "storage_write"],
        "signature": sig
    }
    res_pair = pairing_manager.process_pairing_request(req)
    assert res_pair["success"] is True
    assert res_pair["status"] == NodeState.PENDING_APPROVAL.value

    # 4. Default deny check before human approval
    assert capability_authorizer.is_capability_granted(kn.node_id, "compute") is False

    # 5. Commander approves Knight with restricted capabilities (compute + gpu, NOT storage_write)
    capability_authorizer.approve_node_and_capabilities(kn.node_id, ["compute", "gpu"])
    assert capability_authorizer.is_capability_granted(kn.node_id, "compute") is True
    assert capability_authorizer.is_capability_granted(kn.node_id, "gpu") is True
    assert capability_authorizer.is_capability_granted(kn.node_id, "storage_write") is False # Denied!

    # 6. Execute signed RPC with granted capability -> Success
    kn_transport = RPCSecureTransport(kn)
    k_transport = RPCSecureTransport(k_commander)
    rpc_msg = kn_transport.create_signed_message(k_commander.node_id, "COMPUTE_EXEC", {"task": "matrix_mult"})
    v_rpc = k_transport.verify_and_unwrap_message(rpc_msg)
    assert v_rpc["valid"] is True

    # 7. Revoke Knight -> Immediate trust loss
    capability_authorizer.revoke_node(kn.node_id, reason="Lifecycle E2E Revocation")
    assert capability_authorizer.is_capability_granted(kn.node_id, "compute") is False
    assert node_registry.get_node(kn.node_id)["node_state"] == NodeState.REVOKED.value

    # 8. RPC from Revoked Knight -> Denied
    rpc_revoked = kn_transport.create_signed_message(k_commander.node_id, "COMPUTE_EXEC", {"task": "matrix_mult_2"})
    v_revoked = k_transport.verify_and_unwrap_message(rpc_revoked)
    assert v_revoked["valid"] is False
    assert "revoked or restricted state" in v_revoked["error"]

def test_multi_kingdom_matrix_isolation():
    # Instantiate Kingdom A and Kingdom B with distinct keypairs
    kingdom_a = KingdomIdentity(kingdom_id="KG-ALPHA-01", display_name="Kingdom Alpha")
    kingdom_b = KingdomIdentity(kingdom_id="KG-BETA-02", display_name="Kingdom Beta")
    assert kingdom_a.node_id != kingdom_b.node_id
    assert kingdom_a.fingerprint != kingdom_b.fingerprint

    # Instantiate Knight A and Knight B with unique test IDs
    knight_a = KnightIdentity.get_or_create("kn-matrix-alpha", "Knight Workstation")
    knight_b = KnightIdentity.get_or_create("kn-matrix-beta", "Knight Workstation") # Same display name!

    # Create Pairing invitation 1 on Kingdom A (for cross-kingdom test)
    inv_cross = pairing_manager.create_invitation(ttl_seconds=300)

    # 1. Knight A attempts to pair with Kingdom B using invitation from Kingdom A -> DENIED
    msg_b = f"{inv_cross['code']}:{knight_a.node_id}:{kingdom_b.node_id}".encode("utf-8")
    sig_b = knight_a.sign_message(msg_b).hex()
    req_cross = {
        "code": inv_cross["code"],
        "expected_kingdom_id": kingdom_b.node_id, # Target mismatch!
        "knight_public_identity": knight_a.get_public_identity(),
        "signature": sig_b
    }
    res_cross = pairing_manager.process_pairing_request(req_cross)
    assert res_cross["success"] is False
    assert "Cross-Kingdom mismatch" in res_cross["error"]

    # Create Pairing invitation 2 on Kingdom A (since inv_cross code failed validation but was unused)
    inv_legit = pairing_manager.create_invitation(ttl_seconds=300)

    # 2. Knight A pairs with Kingdom A legitimately
    msg_a = f"{inv_legit['code']}:{knight_a.node_id}:{pairing_manager.kingdom_identity.node_id}".encode("utf-8")
    sig_a = knight_a.sign_message(msg_a).hex()
    req_legit = {
        "code": inv_legit["code"],
        "expected_kingdom_id": pairing_manager.kingdom_identity.node_id,
        "knight_public_identity": knight_a.get_public_identity(),
        "signature": sig_a
    }
    res_legit = pairing_manager.process_pairing_request(req_legit)
    assert res_legit["success"] is True
    assert res_legit["status"] == NodeState.PENDING_APPROVAL.value

    # 3. Approve Knight A on Kingdom A
    capability_authorizer.approve_node_and_capabilities(knight_a.node_id, ["compute"])

    # 4. RPC from Knight A to Kingdom B transport -> DENIED
    transport_b = RPCSecureTransport(kingdom_b)
    transport_a_client = RPCSecureTransport(knight_a)
    msg_rpc = transport_a_client.create_signed_message(kingdom_b.node_id, "EXEC", {"cmd": "test"})

        # Verification at Kingdom B fails because Kingdom B rejects Knight A belonging to Kingdom A
    v_b = transport_b.verify_and_unwrap_message(msg_rpc)
    assert v_b["valid"] is False
    assert "Cross-Kingdom RPC blocked" in v_b["error"] or "Unknown or unauthenticated sender" in v_b["error"]
