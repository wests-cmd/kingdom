"""Connection status must reflect a real exchange, never a placeholder."""
import pytest

from backend.cluster.federation_api import check_inventory_receipt
from backend.cluster.transport_abstraction import (
    LocalLANTransport, DirectWANTransport, OverlayTailscaleTransport,
)


@pytest.mark.parametrize("adapter", [LocalLANTransport, DirectWANTransport, OverlayTailscaleTransport])
def test_unimplemented_route_cannot_claim_connection_or_delivery(adapter):
    route = adapter()
    assert route.send_message({"msg_id": "before"})["status"] == "not_sent"
    assert route.connect("https://peer.invalid") is False
    result = route.send_message({"msg_id": "after"})
    assert result["status"] == "not_sent"
    assert result["reason"] == "authenticated_transport_not_implemented"
    assert route.disconnect() is True


def receipt():
    return {"sender_id": "peer", "msg_type": "inventory_snapshot",
            "payload": {"node_id": "peer", "request_id": "current"}}


def test_exact_receipt_correlation_is_accepted_for_signature_verification():
    # Correlation is only a precondition; the existing RPC handler verifies
    # authenticity, trust, replay protection and the intended target.
    check_inventory_receipt(receipt(), "peer", "current")


@pytest.mark.parametrize("change", [
    {"sender_id": "other"},
    {"msg_type": "heartbeat"},
    {"payload": None},
    {"payload": []},
    {"payload": {"node_id": "other", "request_id": "current"}},
    {"payload": {"node_id": "peer", "request_id": "old"}},
    {"payload": {"node_id": "peer"}},
])
def test_unrelated_receipt_is_rejected_before_rpc_application(change):
    with pytest.raises(ValueError, match="unexpected inventory proof"):
        check_inventory_receipt({**receipt(), **change}, "peer", "current")


@pytest.mark.parametrize("proof", [None, [], "proof", 1])
def test_malformed_receipt_is_rejected(proof):
    with pytest.raises(ValueError, match="unexpected inventory proof"):
        check_inventory_receipt(proof, "peer", "current")
