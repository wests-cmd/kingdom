"""Owner enrollment plus signed, permission-free membership synchronization."""
import ssl
import sqlite3
import hashlib
import json
import math
import time
import uuid
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
    destination_approval_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')


class ApproveDestination(BaseModel):
    model_config = ConfigDict(extra='forbid')
    authority_endpoint: str = Field(max_length=500)
    invitation: dict


def normalized_origin(value):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Use an exact peer origin without whitespace')
    try:
        parsed = httpx.URL(endpoint(value))
    except httpx.InvalidURL as error:
        raise ValueError('Invalid peer origin') from error
    return str(parsed).rstrip('/')


def validated_invitation(invitation, local):
    from backend.cluster.federation_api import pairing_proof
    from backend.cluster.pairing import invitation_message
    pairing_proof(invitation, [], local)  # Bounded identity/key/fingerprint checks.
    created, expires = invitation.get('created_at'), invitation.get('expires_at')
    now = time.time()
    if (type(created) not in (int, float) or type(expires) not in (int, float)
            or not math.isfinite(created) or not math.isfinite(expires)
            or not created <= now < expires <= created + 3600 or invitation.get('used') is not False):
        raise ValueError('A current unused signed invitation is required')
    signature = invitation.get('invitation_signature', '')
    if (not isinstance(signature, str) or len(signature) != 128
            or not local.verify_signature(invitation['kingdom_public_key_hex'],
                invitation_message(invitation), bytes.fromhex(signature))):
        raise ValueError('Unsigned or invalid mesh invitation; update the authority and recreate it')
    return hashlib.sha256(invitation_message(invitation)).hexdigest()


def approved_destination(mesh, invitation, requested, approval_id):
    """Resolve network targets from retained owner policy, never raw join input."""
    digest = validated_invitation(invitation, mesh.identity)
    requested = normalized_origin(requested)
    existing = mesh.registry.get_node(invitation['kingdom_id'])
    if existing:
        from backend.cluster.federation_api import check_identity
        expected = dict(node_id=invitation['kingdom_id'], fingerprint=invitation['kingdom_fingerprint'],
                        public_key_hex=invitation['kingdom_public_key_hex'])
        if existing.node_state not in {'APPROVED', 'CONNECTED', 'DISCONNECTED', 'RECONNECTING'}:
            raise ValueError('Existing authority is not approved')
        check_identity(existing.public_identity, expected, mesh.identity)
        saved = normalized_origin((existing.connection_metadata or {}).get('kingdom_endpoint'))
        if saved != requested:
            raise ValueError('Authority origin differs from the owner-approved peer endpoint')
        return saved, None
    pin = mesh._get('join_destination', {})
    if (not approval_id or pin.get('approval_id') != approval_id or pin.get('consumed')
            or time.time() >= pin.get('expires_at', 0) or pin.get('invitation_sha256') != digest
            or pin.get('authority_id') != invitation['kingdom_id']
            or pin.get('fingerprint') != invitation['kingdom_fingerprint']
            or pin.get('authority_endpoint') != requested):
        raise ValueError('Explicit current owner destination approval is required before joining a fresh authority')
    return pin['authority_endpoint'], pin


@router.post('/destinations')
def approve_destination(request: ApproveDestination):
    """Explicit local owner confirmation only: no discovery/network/peer grants."""
    mesh = membership()
    try:
        digest = validated_invitation(request.invitation, mesh.identity)
        pin = dict(approval_id=uuid.uuid4().hex,
                   authority_endpoint=normalized_origin(request.authority_endpoint),
                   authority_id=request.invitation['kingdom_id'],
                   fingerprint=request.invitation['kingdom_fingerprint'], invitation_sha256=digest,
                   expires_at=min(request.invitation['expires_at'], time.time()+300), consumed=False)
        mesh._set('join_destination', pin)
        mesh.events.publish('cluster.mesh_destination_approved', {k: pin[k] for k in
            ('approval_id', 'authority_endpoint', 'authority_id', 'fingerprint', 'expires_at')})
        return {k: pin[k] for k in ('approval_id', 'authority_endpoint', 'authority_id', 'fingerprint', 'expires_at')}
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(400, str(error)) from error


def consume_destination(mesh, pin):
    if pin is None:
        return
    with mesh.db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("SELECT value FROM mesh_state WHERE key='join_destination'").fetchone()
        current = json.loads(row[0]) if row else {}
        if current != pin or current.get('consumed') or time.time() >= current.get('expires_at', 0):
            raise ValueError('Destination approval changed or expired; confirm again')
        current['consumed'] = True
        conn.execute("UPDATE mesh_state SET value=? WHERE key='join_destination'", (json.dumps(current),))
        conn.commit()


@router.post('/join')
async def join_mesh(request: JoinMesh):
    from backend.cluster.federation_api import pairing_proof, check_identity
    mesh = membership()
    try:
        address, pin = approved_destination(mesh, request.invitation, request.authority_endpoint, request.destination_approval_id)
        local_address = endpoint(request.local_endpoint)
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
            # GET may have crossed an expiry, local revocation or owner pin change.
            current_address, pin = approved_destination(mesh, request.invitation,
                request.authority_endpoint, request.destination_approval_id)
            if current_address != address:
                raise ValueError('Approved destination changed during identity verification')
            consume_destination(mesh, pin)  # Single use before the side-effect POST; a failed GET remains retryable.
            response = await client.post(address + '/nodes/pair', json=proof); response.raise_for_status()
            if response.json().get('success') is not True:
                raise ValueError('Invitation was not accepted')
        try:
            validated_invitation(request.invitation, mesh.identity)
            # Never use the pre-network existing=None snapshot to overwrite a
            # concurrent owner revocation, quarantine or identity replacement.
            mesh.registry.retain_mesh_authority(authority, address, mesh.identity.node_id,
                                                allow_insert=existing is None)
            mesh.configure(authority['node_id'], local_address, request.ca_pem)
        except (ValueError, KeyError, TypeError, sqlite3.Error, httpx.InvalidURL) as error:
            raise HTTPException(409, 'Local enrollment held: current authority approval changed; '
                'remote pairing may have succeeded, reconcile before retrying') from error
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
