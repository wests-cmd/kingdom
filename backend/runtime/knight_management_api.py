"""Owner sends commands through pinned, signed, capability-limited peer RPC."""
import json
import time
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.security.http_auth import require_owner

router = APIRouter(prefix='/knight-management', dependencies=[Depends(require_owner)])


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation: Literal['inspect', 'service_action', 'stage_update', 'activate_update', 'update_status']
    arguments: dict = Field(default_factory=dict)


def pending_database():
    from backend.storage.db import db
    with db.get_connection() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS knight_management_pending(request_id TEXT PRIMARY KEY,peer TEXT NOT NULL,operation TEXT NOT NULL,expires_at REAL NOT NULL,receipt_json TEXT)')
    return db


def create_proof(node_id, request):
    from backend.cluster.node_registry import node_registry
    from backend.cluster.identity import KingdomIdentity
    from backend.cluster.transport import RPCSecureTransport
    node = node_registry.get_node(node_id)
    if not node or node.node_state not in {'APPROVED', 'CONNECTED'}:
        raise HTTPException(409, 'Use an approved paired Knight')
    if len(json.dumps(request.arguments)) > 45 * 1024 * 1024:
        raise HTTPException(413, 'Management request exceeds transfer budget')
    identity = KingdomIdentity.get_or_create()
    message = RPCSecureTransport(identity).create_signed_message(node_id, 'knight_management', {
        'node_id': identity.node_id, 'operation': request.operation, 'arguments': request.arguments})
    with pending_database().get_connection() as connection:
        connection.execute('INSERT INTO knight_management_pending VALUES(?,?,?,?,NULL)',
                           (message['msg_id'], node_id, request.operation, time.time() + 300))
    return message


def accept_receipt(node_id, message):
    from backend.cluster.identity import KingdomIdentity
    from backend.cluster.transport import RPCSecureTransport
    if not isinstance(message, dict) or len(json.dumps(message)) > 1024 * 1024:
        raise HTTPException(413, 'Expected a bounded signed receipt')
    if not isinstance(message.get('payload'), dict):
        raise HTTPException(400, 'Receipt payload must be an object')
    request_id = message['payload'].get('request_id')
    with pending_database().get_connection() as connection:
        pending = connection.execute('SELECT peer,operation,expires_at,receipt_json FROM knight_management_pending WHERE request_id=?', (request_id,)).fetchone()
    if (not pending or pending[0] != node_id or pending[2] < time.time() or pending[3] is not None):
        raise HTTPException(409, 'Receipt has no matching unexpired pending owner request')
    identity = KingdomIdentity.get_or_create()
    result = RPCSecureTransport(identity).verify_and_unwrap_message(message, expected_target_id=identity.node_id)
    payload = result.get('payload', {})
    if (not result.get('valid') or result.get('sender_id') != node_id
            or result.get('msg_type') != 'knight_management_result'
            or payload.get('request_id') != request_id or payload.get('operation') != pending[1]):
        raise HTTPException(403, 'Receipt does not match the pinned peer, request and operation')
    value = payload['result']
    with pending_database().get_connection() as connection:
        cursor = connection.execute('UPDATE knight_management_pending SET receipt_json=? WHERE request_id=? AND receipt_json IS NULL', (json.dumps(value), request_id))
        if cursor.rowcount != 1:
            raise HTTPException(409, 'Receipt was already consumed')
    return value


@router.post('/{node_id}/proof')
def proof(node_id: str, request: Command):
    return {'message': create_proof(node_id, request)}


@router.post('/{node_id}/receipt')
def receipt(node_id: str, message: dict):
    return accept_receipt(node_id, message)


@router.get('/local-source')
def local_source():
    import hashlib
    import sys
    from pathlib import Path
    module = sys.modules.get('backend.main')
    if module is None or not getattr(module, '__file__', None):
        raise HTTPException(409, 'Running main module unavailable')
    path = Path(module.__file__).resolve()
    return {'root': str(path.parent.parent), 'main_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


@router.post('/{node_id}')
async def send(node_id: str, request: Command):
    from backend.cluster.node_registry import node_registry
    from backend.cluster.identity import KingdomIdentity
    from backend.cluster.transport import RPCSecureTransport
    from backend.cluster.federation_api import endpoint, check_identity
    node = node_registry.get_node(node_id)
    if not node or node.node_state not in {'APPROVED', 'CONNECTED'}:
        raise HTTPException(409, 'Use an approved paired Knight')
    if len(json.dumps(request.arguments)) > 45 * 1024 * 1024:
        raise HTTPException(413, 'Management request exceeds transfer budget')
    try:
        address = endpoint((node.connection_metadata or {})['kingdom_endpoint'])
        identity = KingdomIdentity.get_or_create()
        message = create_proof(node_id, request)
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            response = await client.get(address + '/nodes/identity')
            response.raise_for_status()
            check_identity(response.json(), node.public_identity, identity)
            response = await client.post(address + '/nodes/rpc', json=message)
            response.raise_for_status()
        return accept_receipt(node_id, response.json())
    except (ValueError, KeyError) as error:
        raise HTTPException(409, str(error)) from error
    except httpx.HTTPStatusError as error:
        # Never expose response bodies that could include remote credentials.
        raise HTTPException(502, 'Peer denied or failed this management request; no completion claimed') from error
    except httpx.HTTPError as error:
        raise HTTPException(502, 'Peer unavailable; inspect its retained update receipt before retrying activation') from error
