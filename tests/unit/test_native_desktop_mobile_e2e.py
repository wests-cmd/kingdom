import pytest
import time
from backend.cluster.identity import KingdomIdentity, KnightIdentity
from backend.cluster.mobile_pairing import mobile_pairing_manager, MobileDeviceState
from backend.cluster.node_registry import node_registry, NodeState
from backend.cluster.rejoin import rejoin_manager
from backend.cluster.transport import RPCSecureTransport

def test_e2e_desktop_mobile_pairing_lifecycle_and_reconnect():
    k_commander = KingdomIdentity.get_or_create()

    # 1. Challenge generation
    ch = mobile_pairing_manager.create_pairing_challenge(ttl_seconds=300)
    code = ch["code"]

    # 2. Phone signs challenge
    phone = KnightIdentity.get_or_create("e2e-phone-01", "User iPhone")
    msg = f"{code}:{phone.node_id}:{k_commander.node_id}".encode("utf-8")
    sig = phone.sign_message(msg).hex()

    req = {
        "code": code,
        "device_id": phone.node_id,
        "device_name": "User iPhone",
        "device_public_key_hex": phone.get_public_identity()["public_key_hex"],
        "signature": sig
    }

    # 3. Process pairing request
    res = mobile_pairing_manager.process_mobile_pairing(req)
    assert res["success"] is True
    assert res["device_state"] == MobileDeviceState.PENDING.value

    # 4. Commander approves phone
    assert mobile_pairing_manager.approve_mobile_device(phone.node_id) is True
    assert node_registry.get_node(phone.node_id)["node_state"] == NodeState.APPROVED.value

    # 5. Reconnection after network interruption expecting same Kingdom -> ALLOWED
    rejoin_res = rejoin_manager.rejoin(phone.node_id, expected_kingdom_id=k_commander.node_id)
    assert rejoin_res["rejoined"] is True

    # 6. Reconnection expecting WRONG Kingdom -> BLOCKED
    rejoin_wrong = rejoin_manager.rejoin(phone.node_id, expected_kingdom_id="KG-WRONG-999")
    assert rejoin_wrong["rejoined"] is False
    assert "Target Kingdom identity mismatch" in rejoin_wrong["error"]

    # 7. Remote device revocation
    assert mobile_pairing_manager.revoke_mobile_device(phone.node_id, reason="E2E Revocation") is True
    assert node_registry.get_node(phone.node_id)["node_state"] == NodeState.REVOKED.value

    # 8. Reconnection after revocation -> DENIED
    rejoin_revoked = rejoin_manager.rejoin(phone.node_id, expected_kingdom_id=k_commander.node_id)
    assert rejoin_revoked["rejoined"] is False
    assert "restricted state" in rejoin_revoked["error"]
