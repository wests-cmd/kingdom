"""Raw join inputs cannot initiate network access or confer destination approval."""
import asyncio
import copy
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from backend.cluster import mesh_api
from backend.cluster.identity import KingdomIdentity
from backend.cluster.mesh_membership import MeshMembership
from backend.cluster.node_registry import NodeRegistry
from backend.cluster.pairing import PairingManager
from backend.storage.db import Database
from backend.storage.repository import KnightRepository


@pytest.fixture
def context(tmp_path, monkeypatch):
    local, authority = [KingdomIdentity(kingdom_id=name) for name in ('local', 'authority')]
    db = Database(tmp_path/'mesh.db')
    mesh = MeshMembership(db, NodeRegistry(KnightRepository(db)), local,
                          SimpleNamespace(publish=lambda *args: None))
    monkeypatch.setattr(mesh_api, 'membership', lambda: mesh)
    invitation = copy.deepcopy(PairingManager(authority).create_invitation())
    calls, settings = [], []
    responder = {'get': lambda request: httpx.Response(200, json=authority.get_public_identity()),
                 'post': lambda request: httpx.Response(200, json={'success': True})}
    real_client = httpx.AsyncClient

    def handle(request):
        calls.append((request.method, str(request.url)))
        return responder[request.method.lower()](request)

    def client(**kwargs):
        settings.append(kwargs)
        return real_client(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(mesh_api.httpx, 'AsyncClient', client)
    return SimpleNamespace(mesh=mesh, authority=authority, invitation=invitation,
                           calls=calls, settings=settings, responder=responder)


def request(ctx, origin='https://10.0.0.2:8443', approval=None):
    return mesh_api.JoinMesh(authority_endpoint=origin, local_endpoint='https://local.tailnet.example',
        invitation=ctx.invitation, destination_approval_id=approval)


def approve(ctx, origin='https://10.0.0.2:8443'):
    return mesh_api.approve_destination(mesh_api.ApproveDestination(
        authority_endpoint=origin, invitation=ctx.invitation))


def test_genuine_or_fabricated_self_signed_invitation_is_not_destination_authority(context):
    # A genuine signature proves identity possession, never owner consent to fetch.
    for origin in ('https://arbitrary.example', 'http://127.0.0.1:8000'):
        with pytest.raises(HTTPException) as error:
            asyncio.run(mesh_api.join_mesh(request(context, origin)))
        assert error.value.status_code == 400
    assert context.calls == [] and context.settings == []


@pytest.mark.parametrize('change', ['unsigned', 'tampered', 'expired', 'nonfinite', 'used'])
def test_invalid_invitation_rejected_before_even_pinning_or_network(context, change):
    if change == 'unsigned': context.invitation.pop('invitation_signature')
    if change == 'tampered': context.invitation['code'] += 'changed'
    if change == 'expired': context.invitation['expires_at'] = 0
    if change == 'nonfinite': context.invitation['expires_at'] = float('inf')
    if change == 'used': context.invitation['used'] = True
    with pytest.raises(HTTPException): approve(context)
    assert context.calls == [] and context.mesh._get('join_destination') is None


@pytest.mark.parametrize('origin', ['https://10.0.0.2:8443', 'https://approved.tailnet.example', 'http://127.0.0.1:8012'])
def test_explicit_pin_permits_private_tailnet_and_loopback_without_grants(context, origin):
    pin = approve(context, origin)
    assert context.calls == []  # Approval is entirely local.
    assert asyncio.run(mesh_api.join_mesh(request(context, origin, pin['approval_id'])))['status'] == 'pending_owner_approval'
    assert context.calls == [('GET', origin+'/nodes/identity'), ('POST', origin+'/nodes/pair')]
    assert context.settings[0]['follow_redirects'] is False
    assert context.settings[0]['trust_env'] is False and context.settings[0]['verify'] is True
    assert context.mesh._get('join_destination')['consumed'] is True
    assert context.mesh.registry.get_node(context.authority.node_id).granted_capabilities == []


def test_pin_cannot_be_substituted_or_replayed_after_uncertain_post(context):
    pin = approve(context)
    with pytest.raises(HTTPException):
        asyncio.run(mesh_api.join_mesh(request(context, 'https://elsewhere.example', pin['approval_id'])))
    assert context.calls == []
    def uncertain(request): raise httpx.ReadTimeout('acknowledgement lost')
    context.responder['post'] = uncertain
    with pytest.raises(HTTPException):
        asyncio.run(mesh_api.join_mesh(request(context, approval=pin['approval_id'])))
    assert context.mesh._get('join_destination')['consumed'] is True
    before = list(context.calls)
    with pytest.raises(HTTPException):
        asyncio.run(mesh_api.join_mesh(request(context, approval=pin['approval_id'])))
    assert context.calls == before


def test_revocation_during_identity_get_blocks_post(context):
    context.mesh.registry.register_discovered_node({'id': context.authority.node_id,
        'public_identity': context.authority.get_public_identity(), 'fingerprint': context.authority.fingerprint,
        'node_state': 'APPROVED', 'is_local': False, 'granted_capabilities': [],
        'connection_metadata': {'kingdom_endpoint': 'https://10.0.0.2:8443'}})
    def revoke(request):
        from backend.cluster.node_registry import NodeState
        context.mesh.registry.update_node_state(context.authority.node_id, NodeState.REVOKED)
        return httpx.Response(200, json=context.authority.get_public_identity())
    context.responder['get'] = revoke
    with pytest.raises(HTTPException): asyncio.run(mesh_api.join_mesh(request(context)))
    assert len(context.calls) == 1


@pytest.mark.parametrize('state', ['REVOKED', 'QUARANTINED', 'REJECTED'])
def test_fresh_join_post_race_never_overwrites_owner_restriction(context, state):
    pin = approve(context)
    def restrict(request):
        context.mesh.registry.register_discovered_node({'id': context.authority.node_id,
            'public_identity': context.authority.get_public_identity(), 'fingerprint': context.authority.fingerprint,
            'node_state': state, 'is_local': False, 'granted_capabilities': [],
            'connection_metadata': {'kingdom_endpoint': 'https://10.0.0.2:8443'}})
        return httpx.Response(200, json={'success': True})
    context.responder['post'] = restrict
    with pytest.raises(HTTPException) as error:
        asyncio.run(mesh_api.join_mesh(request(context, approval=pin['approval_id'])))
    assert error.value.status_code == 409
    assert context.mesh.registry.get_node(context.authority.node_id).node_state == state
    assert context.mesh.config() == {}
    assert context.mesh._get('join_destination')['consumed'] is True


def test_post_race_does_not_replace_concurrent_identity(context):
    pin = approve(context)
    replacement = KingdomIdentity(kingdom_id=context.authority.node_id)
    def replace(request):
        context.mesh.registry.register_discovered_node({'id': replacement.node_id,
            'public_identity': replacement.get_public_identity(), 'fingerprint': replacement.fingerprint,
            'node_state': 'APPROVED', 'is_local': False, 'granted_capabilities': ['existing-grant'],
            'connection_metadata': {'kingdom_endpoint': 'https://10.0.0.2:8443'}})
        return httpx.Response(200, json={'success': True})
    context.responder['post'] = replace
    with pytest.raises(HTTPException) as error:
        asyncio.run(mesh_api.join_mesh(request(context, approval=pin['approval_id'])))
    assert error.value.status_code == 409
    retained = context.mesh.registry.get_node(replacement.node_id)
    assert retained.public_identity == replacement.get_public_identity()
    assert retained.granted_capabilities == ['existing-grant']
    assert context.mesh.config() == {}


def test_conditional_registry_commit_never_recreates_removed_existing_peer(context):
    with pytest.raises(ValueError, match='removed'):
        context.mesh.registry.retain_mesh_authority(context.authority.get_public_identity(),
            'https://10.0.0.2:8443', context.mesh.identity.node_id, allow_insert=False)
    assert context.mesh.registry.get_node(context.authority.node_id) is None


def test_conditional_registry_insert_preserves_concurrent_approved_row_and_grants(context):
    context.mesh.registry.register_discovered_node({'id': context.authority.node_id,
        'public_identity': context.authority.get_public_identity(), 'fingerprint': context.authority.fingerprint,
        'node_state': 'CONNECTED', 'is_local': False, 'granted_capabilities': ['existing-grant'],
        'connection_metadata': {'kingdom_endpoint': 'https://10.0.0.2:8443', 'owner_note': 'retain'}})
    before = context.mesh.registry.repo.get(context.authority.node_id)
    context.mesh.registry.retain_mesh_authority(context.authority.get_public_identity(),
        'https://10.0.0.2:8443', context.mesh.identity.node_id, allow_insert=True)
    assert context.mesh.registry.repo.get(context.authority.node_id) == before


def test_redirect_denied_and_get_failure_does_not_consume_pin(context):
    pin = approve(context)
    context.responder['get'] = lambda request: httpx.Response(302, headers={'Location': 'http://127.0.0.1:9000/'})
    with pytest.raises(HTTPException):
        asyncio.run(mesh_api.join_mesh(request(context, approval=pin['approval_id'])))
    assert context.calls == [('GET', 'https://10.0.0.2:8443/nodes/identity')]
    assert context.mesh._get('join_destination')['consumed'] is False


def test_expiry_during_identity_get_blocks_side_effect_post(context, monkeypatch):
    pin = approve(context)
    def expires(request):
        monkeypatch.setattr(mesh_api.time, 'time', lambda: pin['expires_at']+1)
        return httpx.Response(200, json=context.authority.get_public_identity())
    context.responder['get'] = expires
    with pytest.raises(HTTPException):
        asyncio.run(mesh_api.join_mesh(request(context, approval=pin['approval_id'])))
    assert len(context.calls) == 1


def test_existing_approved_peer_uses_only_saved_origin_and_current_identity(context):
    context.mesh.registry.register_discovered_node({'id': context.authority.node_id,
        'public_identity': context.authority.get_public_identity(), 'fingerprint': context.authority.fingerprint,
        'node_state': 'APPROVED', 'is_local': False, 'granted_capabilities': [],
        'connection_metadata': {'kingdom_endpoint': 'https://10.0.0.2:8443'}})
    with pytest.raises(HTTPException):
        asyncio.run(mesh_api.join_mesh(request(context, 'https://different.example')))
    assert context.calls == []
    assert asyncio.run(mesh_api.join_mesh(request(context)))['status'] == 'pending_owner_approval'


def test_owner_routes_are_authenticated_and_pin_is_single_current_cas(context):
    assert mesh_api.router.dependencies[0].dependency is mesh_api.require_owner
    first = approve(context)
    second = approve(context)
    with pytest.raises(HTTPException):
        asyncio.run(mesh_api.join_mesh(request(context, approval=first['approval_id'])))
    pin = context.mesh._get('join_destination')
    mesh_api.consume_destination(context.mesh, pin)
    with pytest.raises(ValueError): mesh_api.consume_destination(context.mesh, pin)
    assert second['approval_id'] == pin['approval_id'] and context.calls == []
