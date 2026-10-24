"""Authenticated large task inputs and custom model connections."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, StrictBool
from backend.security.http_auth import require_owner
from backend.storage.db import db
from backend.runtime.attachments import AttachmentStore, MAX_FILE
from backend.models.profiles import ModelProfiles
from backend.models.service import ModelService
from fastapi.responses import FileResponse, StreamingResponse

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
    hosting: Literal['auto', 'local', 'cloud'] = 'auto'
    provider: Literal['ollama', 'openai_compatible']
    endpoint: str = Field(max_length=500)
    model: str = Field(min_length=1, max_length=200)
    variant: Literal['standard', 'fine_tuned', 'abliterated', 'custom'] = 'standard'
    vision: bool = False
    supports_tools: bool = False
    disabled: bool = False
    context_characters: int = Field(default=24000, ge=4000, le=400000)
    pool_group: str = Field(default='', max_length=64)
    computer_id: str = Field(default='', max_length=64)
    max_parallel: int = Field(default=1, ge=1, le=4)
    timeout_seconds: int = Field(default=120, ge=30, le=600)
    max_output_tokens: int = Field(default=2048, ge=16, le=8192)
    num_ctx: int = Field(default=8192, ge=512, le=131072)
    ollama_think: StrictBool | None = None
    ca_certificate: str = Field(default='', max_length=32000)
    api_key: str | None = Field(default=None, max_length=16000)


class ComputerGrant(BaseModel):
    capabilities: list[Literal['filesystem.read', 'filesystem.write', 'process.execute', 'computer.observe', 'computer.control']] = Field(max_length=5)


class ChatRequest(BaseModel):
    model: str = Field(default='kingdom', max_length=200)
    messages: list[dict] = Field(min_length=1, max_length=256)
    tools: list[dict] | None = Field(default=None, max_length=64)
    tool_choice: str | dict | None = None
    parallel_tool_calls: bool | None = None
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    reasoning_effort: str | None = Field(default=None, max_length=20)
    response_format: dict | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=131072)
    max_completion_tokens: int | None = Field(default=None, ge=1, le=131072)


@router.post('/model-chat/{ident}/chat/completions')
async def model_chat(ident: str, request: ChatRequest):
    import json
    body = request.model_dump(exclude_none=True)
    if len(json.dumps(body).encode()) > 2 * 1024 * 1024:
        raise HTTPException(413, 'Chat input exceeds two MiB')
    try:
        payload = await ModelService().chat(ident, body)
    except (KeyError, ValueError) as error:
        raise HTTPException(400, str(error)) from error
    except TimeoutError as error:
        raise HTTPException(429, str(error), headers={'Retry-After': '5'}) from error
    except Exception as error:
        raise HTTPException(502, 'Model computer unavailable; no other computer was silently substituted') from error
    if not request.stream:
        return payload
    # Buffer upstream to keep provider error reporting reliable. Preserve tool calls in SSE.
    async def events():
        base = {k: payload[k] for k in ('id', 'model', 'created') if k in payload}
        base['object'] = 'chat.completion.chunk'
        for choice in payload['choices']:
            message = choice.get('message', {})
            delta = {k: message[k] for k in ('role', 'content', 'reasoning_content', 'tool_calls') if k in message}
            if 'tool_calls' in delta:
                delta['tool_calls'] = [{**call, 'index': index} for index, call in enumerate(delta['tool_calls'])]
            yield 'data: ' + json.dumps({**base, 'choices': [{'index': choice.get('index', 0), 'delta': delta, 'finish_reason': None}]}) + '\n\n'
            yield 'data: ' + json.dumps({**base, 'choices': [{'index': choice.get('index', 0), 'delta': {}, 'finish_reason': choice.get('finish_reason', 'stop')}]}) + '\n\n'
        yield 'data: ' + json.dumps({**base, 'choices': [], 'usage': payload.get('usage', {})}) + '\n\n'
        yield 'data: [DONE]\n\n'
    return StreamingResponse(events(), media_type='text/event-stream', headers={'X-Kingdom-Model-Profile': payload['kingdom_profile']})


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
    from backend.models.capacity import capacity
    configured = ModelProfiles(db).list()
    return {'profiles': configured, 'capacity': capacity.status(configured),
            'pools': sorted({p['pool_group'] for p in configured if p.get('pool_group')}),
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
