import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.cluster.federation_api import pairing_proof, router
from backend.cluster.identity import KingdomIdentity


def invitation(peer):
    public=peer.get_public_identity()
    return {'code':'single-use-code','kingdom_id':peer.node_id,
        'kingdom_public_key_hex':public['public_key_hex'],'kingdom_fingerprint':peer.fingerprint}


def test_relay_pairing_proof_has_real_bound_signature_no_private_material():
    sender=KingdomIdentity('KG-sender');receiver=KingdomIdentity('KG-receiver')
    request=pairing_proof(invitation(receiver),['compute'],sender)
    message=f"{request['code']}:{sender.node_id}:{receiver.node_id}".encode()
    assert sender.verify_signature(request['knight_public_identity']['public_key_hex'],message,bytes.fromhex(request['signature']))
    assert not sender.verify_signature(request['knight_public_identity']['public_key_hex'],message+b'changed',bytes.fromhex(request['signature']))
    assert set(request)=={'code','knight_public_identity','requested_capabilities','signature','is_local'}
    assert 'private' not in str(request)


@pytest.mark.parametrize('change',[{'kingdom_fingerprint':'wrong'},{'code':'x'*201},{'kingdom_public_key_hex':'bad'}])
def test_invalid_pinned_invitation_rejected(change):
    sender=KingdomIdentity('KG-sender');receiver=KingdomIdentity('KG-receiver')
    with pytest.raises(ValueError):pairing_proof({**invitation(receiver),**change},['compute'],sender)


def test_self_pairing_rejected():
    sender=KingdomIdentity('KG-self')
    with pytest.raises(ValueError):pairing_proof(invitation(sender),['compute'],sender)


@pytest.mark.parametrize('path', ['/federation/pairing-proof','/federation/KG-peer/heartbeat-proof'])
def test_export_requires_owner(path):
    app=FastAPI();app.include_router(router)
    assert TestClient(app).post(path,json={'invitation':{}}).status_code in {401,403}
