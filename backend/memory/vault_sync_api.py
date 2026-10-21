"""Owner-controlled replication over pinned, replay-protected peer RPC."""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner
from backend.memory.vault_sync import VaultSync
from backend.cluster.node_registry import node_registry
from backend.cluster.identity import KingdomIdentity
from backend.cluster.transport import RPCSecureTransport
from backend.cluster.federation_api import endpoint, check_identity

router=APIRouter(prefix='/vault-sync',dependencies=[Depends(require_owner)])


def service():
    from backend.memory.portable_vault_api import service as vault
    from backend.events.event_bus import event_bus
    if vault is None:raise HTTPException(503,'Vault not initialized')
    return VaultSync(vault.local,vault,event_bus.publish)


def peer_node(peer):
    node=node_registry.get_node(peer)
    if not node or node.node_state not in {'APPROVED','CONNECTED','DISCONNECTED','RECONNECTING'} or (node.public_identity or {}).get('node_type')!='commander':raise HTTPException(403,'Approved paired Kingdom required')
    return node


class Grant(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    peer:str=Field(max_length=80)
    project:str=Field(max_length=80)
    direction:str
    allowed_roles:list[str]=Field(default_factory=list,max_length=32)


@router.put('/grants')
def grant(request:Grant):
    peer_node(request.peer)
    try:return service().grant(request.peer,request.project,request.direction,request.allowed_roles)
    except ValueError as error:raise HTTPException(400,str(error)) from error


@router.delete('/grants')
def revoke(peer:str,project:str,direction:str):
    return service().revoke(peer,project,direction)


class Push(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    peer:str=Field(max_length=80)
    project:str=Field(max_length=80)
    ids:list[str]|None=Field(default=None,max_length=100)


class AcceptProof(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    peer:str=Field(max_length=80)
    project:str=Field(max_length=80)
    expected_batch:str=Field(pattern=r'^[a-f0-9]{64}$')
    proof:dict


def verify_receipt(request,local=None,sync=None):
    peer_node(request.peer)
    local=local or KingdomIdentity.get_or_create();sync=sync or service()
    verified=RPCSecureTransport(local).verify_and_unwrap_message(request.proof,expected_target_id=local.node_id)
    if not verified.get('valid') or verified.get('sender_id')!=request.peer or verified.get('msg_type')!='vault_sync_ack':raise ValueError('Peer receipt signature invalid, replayed or revoked')
    return sync.accept_receipt(request.peer,request.expected_batch,request.project,verified['payload'],local.node_id)


@router.post('/prepare-proof')
def prepare_proof(request:Push):
    peer_node(request.peer)
    try:
        sync=service();payload=sync.prepare(request.peer,request.project,request.ids)
        sync.pending(request.peer,payload)
        proof=RPCSecureTransport(KingdomIdentity.get_or_create()).create_signed_message(request.peer,'vault_sync_push',payload)
        return {'status':'prepared','batch':payload['batch'],'project':request.project,'peer':request.peer,'proof':proof,'notice':'Relay this signed envelope to the paired Kingdom /nodes/rpc, then return its signed acknowledgement to /vault-sync/accept-proof. Preparation does not prove delivery.'}
    except PermissionError as error:raise HTTPException(403,str(error)) from error
    except (ValueError,KeyError) as error:raise HTTPException(409,str(error)) from error
    except OSError as error:raise HTTPException(503,'Vault archive unavailable') from error


@router.post('/accept-proof')
def accept_proof(request:AcceptProof):
    try:return verify_receipt(request)
    except (ValueError,KeyError,TypeError) as error:raise HTTPException(409,str(error)) from error


@router.get('/transfers/{peer}/{batch}')
def transfer_status(peer:str,batch:str):
    try:return service().transfer_status(peer,batch)
    except KeyError as error:raise HTTPException(404,'Transfer not found') from error


@router.post('/export-batches')
def export_batches(request:Push):
    peer_node(request.peer)
    try:
        sync=service();files=sync.vault.export(request.project)
        ids=sorted(request.ids if request.ids is not None else [name[:-3] for name in files])
        if any(ident+'.md' not in files for ident in ids):raise ValueError('Selected document not found')
        chunks=[];chunk=[];size=0
        for ident in ids:
            amount=len(files[ident+'.md'].encode())
            if chunk and (len(chunk)>=100 or size+amount>1024*1024):chunks.append(chunk);chunk=[];size=0
            chunk.append(ident);size+=amount
        if chunk:chunks.append(chunk)
        # Every suggested batch is checked against the current send grant before
        # exposing even its document identities to the connector.
        for chunk in chunks:sync.prepare(request.peer,request.project,chunk)
        return {'status':'planned','peer':request.peer,'project':request.project,'batches':[{'ids':chunk} for chunk in chunks],'notice':'Each chunk must be prepared, delivered and acknowledged separately. No delivery has occurred.'}
    except PermissionError as error:raise HTTPException(403,str(error)) from error
    except (ValueError,KeyError) as error:raise HTTPException(409,str(error)) from error
    except OSError as error:raise HTTPException(503,'Vault archive unavailable') from error


async def push_to_peer(request):
    node=peer_node(request.peer);local=KingdomIdentity.get_or_create();sync=service()
    try:
        address=endpoint((node.connection_metadata or {})['kingdom_endpoint'])
        payload=sync.prepare(request.peer,request.project,request.ids)
        sync.pending(request.peer,payload)
        async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
            response=await client.get(address+'/nodes/identity');response.raise_for_status()
            check_identity(response.json(),node.public_identity,local)
            envelope=RPCSecureTransport(local).create_signed_message(request.peer,'vault_sync_push',payload)
            response=await client.post(address+'/nodes/rpc',json=envelope);response.raise_for_status()
            proof=response.json().get('proof')
        return verify_receipt(AcceptProof(peer=request.peer,project=request.project,expected_batch=payload['batch'],proof=proof),local=local,sync=sync)
    except PermissionError as error:raise HTTPException(403,str(error)) from error
    except (ValueError,KeyError) as error:raise HTTPException(409,str(error)) from error
    except (OSError,httpx.HTTPError) as error:raise HTTPException(503,'Peer or archive unavailable; no success is claimed; retry preserves local documents') from error


@router.post('/push')
async def push(request:Push):return await push_to_peer(request)


class Replicate(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    project:str=Field(max_length=80)
    peers:list[str]=Field(min_length=1,max_length=8)
    ids:list[str]|None=Field(default=None,max_length=100)


@router.post('/replicate')
async def replicate(request:Replicate):
    # Greedy byte balancing distributes copies across explicitly selected peers.
    # Each transfer still needs its own two-sided project grants.
    sync=service();files=sync.vault.export(request.project)
    ids=list(request.ids if request.ids is not None else [name[:-3] for name in files])
    if any(ident+'.md' not in files for ident in ids):raise HTTPException(409,'Selected document not found')
    ids=sorted(set(ids),key=lambda ident:(-len(files[ident+'.md'].encode()),ident))
    peers=list(dict.fromkeys(request.peers))
    if not ids:return {'status':'empty','transfers':[]}
    buckets={peer:[] for peer in peers}
    sizes={peer:0 for peer in peers}
    for ident in ids:
        peer=min(peers,key=lambda item:(sizes[item],item))
        buckets[peer].append(ident);sizes[peer]+=len(files[ident+'.md'].encode())
    results=[]
    for peer,assigned in buckets.items():
        if not assigned:continue
        chunks=[];chunk=[];size=0
        for ident in assigned:
            amount=len(files[ident+'.md'].encode())
            if chunk and (len(chunk)>=100 or size+amount>1024*1024):chunks.append(chunk);chunk=[];size=0
            chunk.append(ident);size+=amount
        if chunk:chunks.append(chunk)
        receipts=[]
        for chunk in chunks:
            try:receipts.append(await push_to_peer(Push(peer=peer,project=request.project,ids=chunk)))
            except HTTPException as error:
                results.append({'peer':peer,'status':'failed','detail':error.detail,'completed_batches':receipts});break
        else:results.append({'peer':peer,'status':'replicated','batches':receipts})
    return {'status':'replicated' if all(row['status']=='replicated' for row in results) else 'partial','transfers':results,'assigned_bytes':sizes,'notice':'Source copies retained. This balances transferred document bytes, not total disk utilization; it is not a destructive migration.'}


def receive_verified(sender,payload,transport):
    peer_node(sender)
    try:receipt=service().receive(sender,payload)
    except PermissionError as error:raise HTTPException(403,str(error)) from error
    except (ValueError,TypeError,KeyError) as error:raise HTTPException(409,str(error)) from error
    except OSError as error:raise HTTPException(503,'Vault archive unavailable') from error
    return {'status':'ok','proof':transport.create_signed_message(sender,'vault_sync_ack',receipt)}
