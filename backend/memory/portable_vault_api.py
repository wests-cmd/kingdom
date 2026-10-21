"""Owner-only vault interchange; no caller-controlled filesystem access."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner
from backend.memory.portable_vault import PortableVault

router = APIRouter(prefix='/vault', dependencies=[Depends(require_owner)])
service = None


def initialize(database, publish=None):
    global service
    from backend.memory.tiered_vault import configured_vault
    service = configured_vault(database, publish)


@router.get('/storage')
def storage():
    return boundary(lambda: service.status())


@router.get('/{project}/documents/{ident}')
def get_document(project: str, ident: str):
    return boundary(lambda: service.get(project,ident))


@router.get('/{project}/cached')
def cached_documents(project: str):
    return boundary(lambda: {'documents':service.cached(project)})


@router.get('/project-id')
def scope_identity(scope: str):
    from backend.memory.portable_vault import project_identity
    try:
        return {'project': project_identity(scope), 'scope': scope}
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get('/{project}/download')
def download(project: str):
    import io
    import zipfile
    from fastapi.responses import StreamingResponse
    files = boundary(lambda: service.export(project))
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    output.seek(0)
    return StreamingResponse(output, media_type='application/zip',
        headers={'Content-Disposition': 'attachment; filename="kingdom-project-vault.zip"'})


class DocumentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    body: str = Field(max_length=262144)
    provenance: dict = Field(default_factory=dict)
    receipts: list[str] = Field(default_factory=list, max_length=100)
    id: str | None = Field(default=None, max_length=80)
    expected_revision: int = Field(default=0, ge=0)
    allowed_roles: list[str] | None = Field(default=None,max_length=32)


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    files: dict[str, str]


class RevisionRequest(BaseModel):
    expected_revision: int = Field(strict=True, ge=1)


@router.post('/{project}/documents/{ident}/trash')
def trash(project: str, ident: str, request: RevisionRequest):
    return boundary(lambda: service.trash(project, ident, request.expected_revision))


@router.post('/{project}/documents/{ident}/restore')
def restore(project: str, ident: str):
    return boundary(lambda: service.restore(project, ident))


def boundary(operation):
    if service is None:
        raise HTTPException(503, 'Vault is not initialized')
    try:
        return operation()
    except KeyError as error:
        raise HTTPException(404, 'Document not found in this project') from error
    except OSError as error:
        raise HTTPException(503, 'Vault storage unavailable; local cached reads may still be available') from error
    except (ValueError, TypeError) as error:
        raise HTTPException(409, 'Invalid document, scope, checksum or revision; existing data preserved') from error


@router.post('/{project}/documents')
def put(project: str, request: DocumentRequest):
    return boundary(lambda: service.put(project, request.body, request.provenance, request.receipts, request.id, request.expected_revision,allowed_roles=request.allowed_roles))


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
    return boundary(lambda: {'documents': service.search(project, query,reader_role='owner')})
