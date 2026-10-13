from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from backend.security.http_auth import require_owner
from backend.runtime.harnesses import HarnessConfig, HarnessService

router = APIRouter(prefix='/harnesses', dependencies=[Depends(require_owner)])

def service():
    from backend.api import engine
    from backend.storage.db import db
    return HarnessService(engine, db)

class JobRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    cwd: str = Field(default='.', max_length=300)

@router.get('')
def profiles():
    return {'profiles': service().list(), 'notice': 'Connect an installed CLI with an explicit argument template. Jobs use existing task permissions and exact process approval. No CLI is downloaded or granted authority automatically.'}

@router.put('/{ident}')
def save(ident: str, request: HarnessConfig):
    try: return service().save(ident, request)
    except ValueError as error: raise HTTPException(400, str(error)) from error

@router.post('/{ident}/jobs', status_code=201)
def submit(ident: str, request: JobRequest):
    try: return service().submit(ident, request.prompt, request.cwd)
    except ValueError as error: raise HTTPException(400, str(error)) from error
