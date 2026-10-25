"""Owner enrollment plus signed, permission-free membership synchronization."""
import ssl
from functools import lru_cache

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.security.http_auth import require_owner
from backend.cluster.mesh_membership import MeshMembership
from backend.cluster.peer_endpoints import endpoint

router = APIRouter(prefix='/federation/mesh', dependencies=[Depends(require_owner)])


@lru_cache(maxsize=1)
def membership():
    from backend.storage.db import db
    from backend.cluster.node_registry import node_registry
    from backend.cluster.identity import KingdomIdentity
    from backend.events.event_bus import event_bus
    return MeshMembership(db, node_registry, KingdomIdentity.get_or_create(), event_bus)


def mesh_tls():
    ca = membership().config().get('ca_pem')
    return ssl.create_default_context(cadata=ca) if ca else True


class ConfigureMesh(BaseModel):
    model_config = ConfigDict(extra='forbid')
    authority_id: str = Field(min_length=1, max_length=100)
    local_endpoint: str = Field(max_length=500)
    ca_pem: str = Field(default='', max_length=64000)


class JoinMesh(BaseModel):
    model_config = ConfigDict(extra='forbid')
    authority_endpoint: str = Field(max_length=500)
    local_endpoint: str = Field(max_length=500)
    invitation: dict
    ca_pem: str = Field(default='', max_length=64000)


@router.post('/join')
async def join_mesh(request: JoinMesh):
    from backend.cluster.federation_api import pairing_proof, check_identity
    mesh = membership()
    try:
        address, local_address = endpoint(request.authority_endpoint), endpoint(request.local_endpoint)
        proof = pairing_proof(request.invitation, [], mesh.identity)
        authority = {'node_id': request.invitation['kingdom_id'], 'node_type': 'commander',
                     'public_key_hex': request.invitation['kingdom_public_key_hex'],
                     'fingerprint': request.invitation['kingdom_fingerprint'],
                     'display_name': request.invitation.get('kingdom_display_name', 'Membership authority')}
        previous = mesh.config()
        existing = mesh.registry.get_node(authority['node_id'])
        if previous and previous['authority_id'] != authority['node_id']:
            raise ValueError('Disable the previous mesh before joining another')
        if existing and (existing.node_state not in {'APPROVED','CONNECTED','DISCONNECTED','RECONNECTING'}
                         or existing.public_identity.get('public_key_hex') != authority['public_key_hex']):
            raise ValueError('Existing local identity approval conflicts with this invitation')
        proof['mesh_endpoint'] = local_address
        proof['signature'] = mesh.identity.sign_message(
            f"{request.invitation['code']}:{mesh.identity.node_id}:{authority['node_id']}:{local_address}".encode()).hex()
        tls = ssl.create_default_context(cadata=request.ca_pem) if request.ca_pem else True
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False, verify=tls) as client:
            response = await client.get(address + '/nodes/identity'); response.raise_for_status()
            check_identity(response.json(), authority, mesh.identity)
            response = await client.post(address + '/nodes/pair', json=proof); response.raise_for_status()
            if response.json().get('success') is not True:
                raise ValueError('Invitation was not accepted')
        # The authenticated local owner explicitly pinned this authority through
        # its invitation. The remote owner must approve this Knight once.
        if not existing:
            mesh.registry.register_discovered_node({'id': authority['node_id'], 'public_identity': authority,
                'fingerprint': authority['fingerprint'], 'kingdom_id': mesh.identity.node_id,
                'node_state': 'APPROVED', 'is_local': False, 'capabilities': [], 'granted_capabilities': [],
                'connection_metadata': {'kingdom_endpoint': address}})
        mesh.configure(authority['node_id'], local_address, request.ca_pem)
        return {'status': 'pending_owner_approval', 'message': 'Approve this Knight once on the membership authority. All approved Knights will connect automatically.'}
    except (ValueError, KeyError, TypeError, ssl.SSLError) as error:
        raise HTTPException(400, str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(502, 'Could not reach the membership authority securely') from error


@router.put('')
def configure_mesh(request: ConfigureMesh):
    try:
        return membership().configure(request.authority_id, request.local_endpoint, request.ca_pem)
    except (ValueError, ssl.SSLError) as error:
        raise HTTPException(400, str(error)) from error


@router.delete('')
def disable_mesh():
    membership().disable()
    return {'enabled': False}


@router.get('')
def mesh_status():
    mesh = membership()
    config = mesh.config()
    return {'enabled': bool(config), 'authority_id': config.get('authority_id'), 'last_roster': mesh._get('received'),
            'local_endpoint': config.get('local_endpoint'), 'tool_grants_added': False}


async def sync_mesh():
    from backend.cluster.transport import RPCSecureTransport
    from backend.api import handle_cluster_rpc, RPCMessageRequest
    mesh = membership()
    config = mesh.config()
    if not config or config['authority_id'] == mesh.identity.node_id:
        return
    authority = mesh.registry.get_node(config['authority_id'])
    if not authority or authority.node_state not in {'APPROVED', 'CONNECTED', 'DISCONNECTED', 'RECONNECTING'}:
        return
    address = endpoint(authority.connection_metadata['kingdom_endpoint'])
    proof = RPCSecureTransport(mesh.identity).create_signed_message(authority.node_id, 'mesh_roster_request', {})
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False, verify=mesh_tls()) as client:
        response = await client.post(address + '/nodes/rpc', json=proof)
        response.raise_for_status()
        if len(response.content) > 131072:
            raise ValueError('Membership reply exceeds its size limit')
        reply = response.json()
    if reply.get('sender_id') != authority.node_id or reply.get('msg_type') != 'mesh_roster_response':
        raise ValueError('Unexpected membership response')
    return handle_cluster_rpc(RPCMessageRequest.model_validate(reply))


@router.post('/sync')
async def refresh_membership():
    try:
        return await sync_mesh() or {'status': 'not_required'}
    except (ValueError, KeyError, httpx.HTTPError) as error:
        raise HTTPException(409, 'Membership authority unavailable or reply rejected') from error
