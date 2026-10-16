"""Owner-managed links between independent Kingdoms, with mutual pairing."""
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from backend.security.http_auth import require_owner
from backend.cluster.identity import KingdomIdentity
from backend.cluster.node_registry import node_registry, NodeState
from backend.cluster.transport import RPCSecureTransport
from backend.cluster.heartbeat import heartbeat_manager

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
            message=RPCSecureTransport(local).create_signed_message(node_id,'heartbeat',{'node_id':local.node_id})
            response=await client.post(address+'/nodes/rpc',json=message);response.raise_for_status()
            result=response.json()
            if result.get('status')!='ok' or result.get('ping',{}).get('success') is not True:
                raise ValueError('Other Kingdom has not approved this identity')
        heartbeat_manager.ping(node_id)
        return {'peer':node_id,'connected':True,'mutual_identity_accepted':True}
    except (ValueError,KeyError) as e:raise HTTPException(409,str(e)) from e
    except httpx.HTTPError as e:raise HTTPException(502,'Peer connection failed; identity and grants retained for retry') from e
