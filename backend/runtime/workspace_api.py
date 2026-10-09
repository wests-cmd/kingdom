"""Authenticated large task inputs and custom model connections."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from backend.security.http_auth import require_owner
from backend.storage.db import db
from backend.runtime.attachments import AttachmentStore, MAX_FILE
from backend.models.profiles import ModelProfiles
from backend.models.service import ModelService
from fastapi.responses import FileResponse

router = APIRouter(prefix='/workspace', dependencies=[Depends(require_owner)])


@router.get('/tasks/{task_id}/artifact')
def task_artifact(task_id: str):
    from backend.api import engine
    from backend.runtime.computer_tools import verify_receipt, workspace_path
    import hashlib
    task = engine.tasks.get(task_id)
    if not task or task['status'].lower() != 'completed': raise HTTPException(404, 'Completed artifact not found')
    try:
        outcome = task['result']['results'][0]['outcome']
        if outcome['tool'] not in {'workspace.write@1.0.0', 'workspace.package@1.0.0', 'computer.screenshot@1.0.0'}:
            raise ValueError('This task has no downloadable file')
        if len(task['result']['results']) != 1 or task['metadata'].get('subtasks'):
            raise ValueError('Download requires a single reviewed file operation')
        execution_task = {**task, 'id': task['id'] + ':' + hashlib.sha256(task['prompt'].encode()).hexdigest()}
        verify_receipt(execution_task, outcome)
        path = outcome['output']['path']
        if outcome['tool'] == 'computer.screenshot@1.0.0':
            from pathlib import Path
            target = Path(path).resolve()
            if not target.is_relative_to(workspace_path('captures')): raise ValueError('Invalid capture location')
        else: target = workspace_path(path)
        if target.stat().st_size > 24*1024*1024 or hashlib.sha256(target.read_bytes()).hexdigest() != outcome['output']['sha256']:
            raise ValueError('Artifact no longer matches execution evidence')
        return FileResponse(target, media_type='application/octet-stream', filename=target.name)
    except (ValueError, KeyError, OSError) as error:
        raise HTTPException(409, 'Artifact unavailable or changed since verification') from error


class ProfileRequest(BaseModel):
    provider: Literal['ollama', 'openai_compatible']
    endpoint: str = Field(max_length=500)
    model: str = Field(min_length=1, max_length=200)
    variant: Literal['standard', 'fine_tuned', 'abliterated', 'custom'] = 'standard'
    vision: bool = False
    context_characters: int = Field(default=24000, ge=4000, le=400000)
    api_key: str | None = Field(default=None, max_length=16000)


class ComputerGrant(BaseModel):
    capabilities: list[Literal['filesystem.read', 'filesystem.write', 'process.execute', 'computer.observe', 'computer.control']] = Field(max_length=5)


@router.get('/computer-tools')
def computer_tools():
    from backend.api import engine
    from backend.runtime.computer_tools import TOOL_CAPABILITIES
    return {'tools': TOOL_CAPABILITIES, 'apprentices': [{'role': name, 'capabilities': list(engine.security.nodes.get_node_capabilities(name) & set(TOOL_CAPABILITIES.values()))}
            for name in engine.swarm.registry._knights],
            'notice': 'File tools stay within the Kingdom workspace. Process tools run on the host and require exact human approval. Desktop capture needs an interactive desktop; headless servers cannot capture one.'}


@router.put('/apprentices/{role}/tools')
def grants(role: str, request: ComputerGrant):
    from backend.api import engine
    try: return engine.grant_computer_tools(role, request.capabilities)
    except ValueError as error: raise HTTPException(400, str(error)) from error


@router.post('/attachments', status_code=201)
async def upload(request: Request, filename: str = Query(min_length=1, max_length=180)):
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_FILE:
            raise HTTPException(413, 'Maximum file size is 20 MB')
        body.extend(chunk)
    try:
        result = AttachmentStore(db).put(filename, bytes(body))
        from backend.api import engine
        engine.events.publish('attachment.saved', {'id': result['id'], 'kind': result['kind'], 'bytes': result['bytes']})
        return result
    except Exception as error:
        raise HTTPException(400, 'File could not be inspected: use a supported, unencrypted file within the extraction limits') from error


@router.get('/attachments/{ident}')
def attachment(ident: str):
    try: return AttachmentStore(db).get(ident)
    except (KeyError, ValueError) as error: raise HTTPException(404, 'Attachment not found') from error


@router.get('/attachments/{ident}/download')
def download(ident: str):
    try:
        store = AttachmentStore(db); item = store.get(ident)
        return Response(store.raw(ident), media_type='application/octet-stream',
                        headers={'Content-Disposition': f'attachment; filename="{ident}.bin"'})
    except (KeyError, ValueError) as error: raise HTTPException(404, 'Attachment unavailable') from error


@router.get('/model-profiles')
def profiles():
    return {'profiles': ModelProfiles(db).list(),
            'notice': 'Use installed Ollama models or an OpenAI-compatible endpoint, including custom, fine-tuned or abliterated models. These labels never change autonomy or permissions. Training and weight downloads are separate operations.'}


@router.put('/model-profiles/{ident}')
def save_profile(ident: str, request: ProfileRequest):
    try:
        result = ModelProfiles(db).save(ident, request.model_dump(exclude={'api_key'}), request.api_key)
        from backend.api import engine
        engine.events.publish('model.profile_saved', {'id': ident, 'provider': request.provider})
        return result
    except ValueError as error: raise HTTPException(400, str(error)) from error


@router.post('/model-profiles/{ident}/test')
async def test_profile(ident: str):
    try:
        result = await ModelService().generate('Reply with the word READY only. This is a model connection test.', profile=ident)
        return {'connected': True, 'model': result['model'], 'response': result['text'][:200]}
    except Exception as error:
        raise HTTPException(502, 'Model test failed. Check the installed model name, endpoint and credentials.') from error
