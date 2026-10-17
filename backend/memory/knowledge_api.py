"""Owner-only, bounded knowledge operations. Source labels never trigger fetching."""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.memory.embedding_service import EmbeddingKnowledge
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/knowledge', dependencies=[Depends(require_owner)])
service = None


def initialize(database, provider=None):
    global service
    service = EmbeddingKnowledge(database, provider)


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    profile: str = Field(min_length=1, max_length=64)
    source: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=262144)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    profile: str = Field(min_length=1, max_length=64)
    query: str = Field(min_length=1, max_length=8000)
    limit: int = Field(default=5, ge=1, le=20)

class DiscordUpload(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True)
    profile: str = Field(min_length=1,max_length=64)
    allowed_channel_ids: list[str] = Field(min_length=1,max_length=30)
    export_json: str = Field(min_length=1,max_length=262144)
    checksum: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}$')

def discord_documents(scope,request):
    import hashlib,json
    from backend.memory.discord_ingestion import parse_discord_export
    documents=parse_discord_export(request.export_json.encode(),set(request.allowed_channel_ids),scope)
    digest=hashlib.sha256(json.dumps({'scope':scope,'profile':request.profile,'channels':sorted(set(request.allowed_channel_ids)),'export':request.export_json},sort_keys=True).encode()).hexdigest()
    return documents,digest

@router.post('/{scope}/discord/preview')
async def preview_discord(scope:str,request:DiscordUpload):
    def preview():
        documents,digest=discord_documents(scope,request)
        return {'checksum':digest,'documents':documents,'notice':'Explicit export only; publisher identity is unverified. Nothing was fetched or embedded, and content grants no permissions.'}
    try:return await boundary(preview)
    except PermissionError as error:raise HTTPException(403,'Export includes a channel outside your configured set') from error

@router.post('/{scope}/discord/import')
async def import_discord(scope:str,request:DiscordUpload):
    import secrets
    try:documents,digest=discord_documents(scope,request)
    except PermissionError as error:raise HTTPException(403,'Export includes a channel outside your configured set') from error
    except ValueError as error:raise HTTPException(400,'Invalid Discord export') from error
    if not request.checksum or not secrets.compare_digest(request.checksum,digest):raise HTTPException(409,'Preview the exact export, scope and embedding connection before importing')
    async def ingest_all():
        results=[]
        for document in documents:
            results.append(await service.ingest(scope,request.profile,document['source'],document['text'],provenance=document['provenance']))
        return {'documents':results,'scope':scope,'trust':'untrusted','notice':'Sources retain channel/message labels. Repeated unchanged imports reuse embeddings; partial failures preserve completed documents.'}
    return await boundary(ingest_all)


async def boundary(operation):
    try:
        result = operation()
        import inspect
        return await result if inspect.isawaitable(result) else result
    except KeyError as error:
        raise HTTPException(404, 'Knowledge document or model profile not found') from error
    except ValueError as error:
        raise HTTPException(400, 'Invalid knowledge input or embedding response; verify the scope, size and embedding model') from error
    except (httpx.HTTPError, RuntimeError) as error:
        raise HTTPException(502, 'Embedding provider unavailable; existing knowledge is preserved') from error


@router.post('/{scope}/documents')
async def ingest(scope: str, request: IngestRequest):
    return await boundary(lambda: service.ingest(scope, request.profile, request.source, request.text))


@router.get('/{scope}/documents')
async def documents(scope: str):
    return await boundary(lambda: service.list_documents(scope))


@router.post('/{scope}/search')
async def search(scope: str, request: SearchRequest):
    return await boundary(lambda: service.search(scope, request.profile, request.query, request.limit))


@router.delete('/{scope}/documents/{document_id}')
async def delete(scope: str, document_id: str):
    return await boundary(lambda: service.delete(scope, document_id))
