"""Owner-only vault interchange; no caller-controlled filesystem access."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner
from backend.memory.portable_vault import PortableVault

router = APIRouter(prefix='/vault', dependencies=[Depends(require_owner)])
service = None


def initialize(database, publish=None):
    global service
    service = PortableVault(database, publish)


class DocumentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    body: str = Field(max_length=262144)
    provenance: dict = Field(default_factory=dict)
    receipts: list[str] = Field(default_factory=list, max_length=100)
    id: str | None = Field(default=None, max_length=80)
    expected_revision: int = Field(default=0, ge=0)


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    files: dict[str, str]


def boundary(operation):
    if service is None:
        raise HTTPException(503, 'Vault is not initialized')
    try:
        return operation()
    except KeyError as error:
        raise HTTPException(404, 'Document not found in this project') from error
    except (ValueError, TypeError) as error:
        raise HTTPException(409, 'Invalid document, scope, checksum or revision; existing data preserved') from error


@router.post('/{project}/documents')
def put(project: str, request: DocumentRequest):
    return boundary(lambda: service.put(project, request.body, request.provenance, request.receipts, request.id, request.expected_revision))


@router.get('/{project}/export')
def export(project: str):
    return boundary(lambda: {'files': service.export(project), 'trust': 'untrusted', 'notice': 'Credential-shaped content is excluded; review before sharing. Receipt references are not fetched or verified.'})


@router.post('/{project}/import')
def import_files(project: str, request: ImportRequest):
    return boundary(lambda: service.import_files(project, request.files))


@router.post('/{project}/rebuild-index')
def rebuild(project: str):
    return boundary(lambda: {'indexed': service.rebuild_index(project)})


@router.get('/{project}/search')
def search(project: str, query: str = ''):
    if len(query) > 8000:
        raise HTTPException(400, 'Query exceeds limit')
    return boundary(lambda: {'documents': service.search(project, query)})
