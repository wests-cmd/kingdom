"""Owner-managed links between independent Kingdoms, with mutual pairing."""
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from backend.security.http_auth import require_owner
from backend.cluster.identity import KingdomIdentity
from backend.cluster.node_registry import node_registry, NodeState
from backend.cluster.transport import RPCSecureTransport
from backend.cluster.heartbeat import heartbeat_manager
from backend.cluster.local_load import local_load_metrics

router=APIRouter(prefix='/federation', dependencies=[Depends(require_owner)])

def endpoint(value):
    p=urlsplit(value)
    if p.scheme not in {'https','http'} or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in {'','/'}:
        raise ValueError('Use the other Kingdom base URL without credentials or a path')
    if p.scheme=='http' and p.hostname not in {'127.0.0.1','localhost','::1'}:
        raise ValueError('Remote Kingdoms require HTTPS; SSH tunnels may use loopback HTTP')
    return value.rstrip('/')

def check_identity(peer,expected,local):
    if peer.get('node_type')!='commander' or peer.get('node_id')==local.node_id:
        raise ValueError('Expected a different Kingdom with its own unique identity')
    if any(peer.get(k)!=expected.get(k) for k in ('node_id','fingerprint','public_key_hex')):
        raise ValueError('Other Kingdom identity differs from the pinned invitation or pairing')

class ConnectRequest(BaseModel):
    endpoint: str=Field(max_length=500)
    invitation: dict
    capabilities: list[str]=Field(default_factory=lambda:['compute'],max_length=32)

class EndpointRequest(BaseModel):
    endpoint: str=Field(max_length=500)

class PairingProofRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    invitation: dict
    capabilities: list[str]=Field(default_factory=lambda:['compute'],max_length=32)

def pairing_proof(invitation,capabilities,local=None):
    import json
    import re
    from backend.cluster.identity import compute_fingerprint
    local=local or KingdomIdentity.get_or_create()
    if len(json.dumps(invitation))>16000 or any(not isinstance(c,str) or len(c)>100 for c in capabilities):
        raise ValueError('Pairing request exceeds its bounded invitation or capability budget')
    code=invitation.get('code')
    target=invitation.get('kingdom_id')
    key=invitation.get('kingdom_public_key_hex')
    if (not isinstance(code,str) or not 1<=len(code)<=200 or not isinstance(target,str)
            or not 1<=len(target)<=100 or target==local.node_id or not isinstance(key,str)
            or not re.fullmatch(r'[0-9a-fA-F]{64}',key)
            or compute_fingerprint(bytes.fromhex(key))!=invitation.get('kingdom_fingerprint')):
        raise ValueError('Supply a bounded invitation for a distinct Kingdom with a consistent public key and fingerprint')
    signature=local.sign_message(f'{code}:{local.node_id}:{target}'.encode()).hex()
    return {'code':code,'knight_public_identity':local.get_public_identity(),
            'requested_capabilities':capabilities,'signature':signature,'is_local':False}

@router.post('/pairing-proof')
def export_pairing_proof(request:PairingProofRequest):
    try:return pairing_proof(request.invitation,request.capabilities)
    except ValueError as error:raise HTTPException(400,str(error)) from error

@router.post('/{node_id}/heartbeat-proof')
def export_heartbeat_proof(node_id:str):
    node=node_registry.get_node(node_id)
    if not node or (node.public_identity or {}).get('node_type')!='commander':
        raise HTTPException(404,'Paired Kingdom not found')
    if node.node_state not in {'APPROVED','CONNECTED','DISCONNECTED','RECONNECTING'}:
        raise HTTPException(409,'Peer is not approved for reconnection')
    local=KingdomIdentity.get_or_create()
    from backend.cluster.apprentice_inventory import local_inventory
    return RPCSecureTransport(local).create_signed_message(node_id,'heartbeat',{'node_id':local.node_id,'apprentice_inventory':local_inventory(),'load_metrics':local_load_metrics()})

class IdentityMigrationRequest(BaseModel):
    expected_id: str=Field(min_length=1,max_length=100)
    new_id: str | None=Field(default=None,max_length=100)

@router.post('/identity/migrate')
def migrate_local_identity(request:IdentityMigrationRequest):
    from backend.cluster.identity_migration import migrate_identity
    from backend.storage.db import db
    from backend.events.event_bus import event_bus
    try:
        result=migrate_identity(db,request.expected_id,request.new_id)
    except ValueError as error:
        raise HTTPException(409,str(error)) from error
    event_bus.publish('cluster.identity_migrated',{k:v for k,v in result.items() if k!='backup'})
    return result

async def connect_peer(address,invitation,capabilities,local=None):
    local=local or KingdomIdentity.get_or_create()
    address=endpoint(address)
    expected={'node_id':invitation.get('kingdom_id'),'fingerprint':invitation.get('kingdom_fingerprint'),
              'public_key_hex':invitation.get('kingdom_public_key_hex')}
    async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
        response=await client.get(address+'/nodes/identity');response.raise_for_status()
        check_identity(response.json(),expected,local)
        code=invitation['code']
        signature=local.sign_message(f'{code}:{local.node_id}:{expected["node_id"]}'.encode()).hex()
        response=await client.post(address+'/nodes/pair',json={'code':code,'knight_public_identity':local.get_public_identity(),
            'requested_capabilities':capabilities,'signature':signature,'is_local':False})
        response.raise_for_status(); result=response.json()
        if result.get('success') is not True:raise ValueError(result.get('error','Pairing not accepted'))
    return {'peer':expected['node_id'],'status':'pending_remote_approval',
            'message':'Approve this Kingdom as a Knight on the other installation. Repeat in the opposite direction for mutual cooperation. No task execution was granted by this request.'}

@router.post('/connect')
async def connect(request:ConnectRequest):
    try:return await connect_peer(request.endpoint,request.invitation,request.capabilities)
    except (ValueError,KeyError) as e:raise HTTPException(400,str(e)) from e
    except httpx.HTTPError as e:raise HTTPException(502,'Other Kingdom could not be reached securely') from e

@router.put('/{node_id}/endpoint')
def save_endpoint(node_id:str,request:EndpointRequest):
    node=node_registry.get_node(node_id)
    if not node or (node.public_identity or {}).get('node_type')!='commander':raise HTTPException(404,'Paired Kingdom not found')
    try:address=endpoint(request.endpoint)
    except ValueError as e:raise HTTPException(400,str(e)) from e
    node.connection_metadata={**(node.connection_metadata or {}),'kingdom_endpoint':address}
    node_registry.repo.save(node.to_dict())
    return {'peer':node_id,'endpoint':address}

@router.post('/{node_id}/reconnect')
async def reconnect(node_id:str):
    node=node_registry.get_node(node_id)
    if not node or (node.public_identity or {}).get('node_type')!='commander':raise HTTPException(404,'Paired Kingdom not found')
    if node.node_state not in {'APPROVED','CONNECTED','DISCONNECTED','RECONNECTING'}:raise HTTPException(409,'Peer is not approved for reconnection')
    try:
        address=endpoint((node.connection_metadata or {})['kingdom_endpoint'])
        local=KingdomIdentity.get_or_create()
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            response=await client.get(address+'/nodes/identity');response.raise_for_status()
            check_identity(response.json(),node.public_identity,local)
            from backend.cluster.apprentice_inventory import local_inventory
            message=RPCSecureTransport(local).create_signed_message(node_id,'heartbeat',{'node_id':local.node_id,'apprentice_inventory':local_inventory(),'load_metrics':local_load_metrics()})
            response=await client.post(address+'/nodes/rpc',json=message);response.raise_for_status()
            result=response.json()
            if result.get('status')!='ok' or result.get('ping',{}).get('success') is not True:
                raise ValueError('Other Kingdom has not approved this identity')
        if result.get('inventory_proof'):
            from backend.api import handle_cluster_rpc, RPCMessageRequest
            handle_cluster_rpc(RPCMessageRequest.model_validate(result['inventory_proof']))
        else: heartbeat_manager.ping(node_id)
        return {'peer':node_id,'connected':True,'mutual_identity_accepted':True}
    except (ValueError,KeyError) as e:raise HTTPException(409,str(e)) from e
    except httpx.HTTPError as e:raise HTTPException(502,'Peer connection failed; identity and grants retained for retry') from e
