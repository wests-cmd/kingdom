import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

from fastapi import FastAPI
import httpx
import pytest

from backend.models.capacity import ModelCapacity
from backend.models.profiles import ModelProfiles
from backend.models.service import ModelService
from backend.storage.db import Database


@contextmanager
def model_server(barrier=None, tool=False, fail=False):
    state = {'active': 0, 'peak': 0, 'bodies': []}
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with lock:
                state['active'] += 1
                state['peak'] = max(state['peak'], state['active'])
                state['bodies'].append(body)
            try:
                if barrier: barrier.wait(timeout=3)
                time.sleep(.1)
                message = {'role': 'assistant', 'content': 'READY'}
                if tool:
                    message = {'role': 'assistant', 'content': None, 'tool_calls': [
                        {'id': 'test-call', 'type': 'function', 'function': {'name': 'get_status', 'arguments': '{}'}}]}
                payload = {'id': 'test-response', 'created': 1, 'model': body['model'], 'choices': [
                    {'index': 0, 'message': message, 'finish_reason': 'tool_calls' if tool else 'stop'}],
                    'usage': {'prompt_tokens': 3, 'completion_tokens': 1}}
                if self.path == '/api/generate': payload = {'response': 'READY'}
                data = json.dumps(payload).encode()
                self.send_response(503 if fail else 200)
                self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data)))
                self.end_headers(); self.wfile.write(data)
            finally:
                with lock: state['active'] -= 1
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try: yield 'http://127.0.0.1:' + str(server.server_port), state
    finally: server.shutdown(); server.server_close(); thread.join()


@pytest.fixture
def profiles(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    database = Database(tmp_path / 'models.db')
    monkeypatch.setattr('backend.storage.db.db', database)
    monkeypatch.setattr('backend.models.capacity.capacity', ModelCapacity())
    return ModelProfiles(database)


def save(profiles, name, endpoint, **kwargs):
    return profiles.save(name, {'provider': 'ollama', 'endpoint': endpoint, 'model': name,
                               'variant': 'standard', 'pool_group': 'chat', 'max_parallel': 1, **kwargs})


@pytest.mark.asyncio
async def test_two_computers_run_chats_at_the_same_time(profiles):
    barrier = threading.Barrier(2)
    with model_server(barrier) as (first, a), model_server(barrier) as (second, b):
        save(profiles, 'local', first); save(profiles, 'laptop3', second)
        request = {'messages': [{'role': 'user', 'content': 'Hello'}]}
        results = await asyncio.gather(ModelService().chat('pool:chat', request), ModelService().chat('pool:chat', request))
        assert {r['kingdom_profile'] for r in results} == {'local', 'laptop3'}
        assert a['peak'] == b['peak'] == 1


@pytest.mark.asyncio
async def test_same_computer_serializes_across_service_instances(profiles):
    with model_server() as (endpoint, state):
        save(profiles, 'first', endpoint); save(profiles, 'alias', endpoint)
        await asyncio.gather(ModelService().generate('one', profile='first'), ModelService().generate('two', profile='alias'))
        assert state['peak'] == 1
        assert len(state['bodies']) == 2
        assert 'options' not in state['bodies'][0]  # Existing profiles keep their provider's runtime settings.


@pytest.mark.asyncio
async def test_explicit_computer_budgets_and_client_output_caps(profiles):
    with model_server() as (endpoint, state):
        save(profiles, 'small', endpoint, num_ctx=1024, max_output_tokens=32)
        await ModelService().generate('one', profile='small')
        assert state['bodies'][0]['options'] == {'num_ctx':1024,'num_predict':32}
        await ModelService().chat('small', {'messages':[{'role':'user','content':'hello'}], 'max_completion_tokens':100000})
        assert state['bodies'][1]['max_tokens'] == 32


@pytest.mark.asyncio
async def test_failed_request_releases_capacity(profiles):
    with model_server(fail=True) as (endpoint, state):
        save(profiles, 'broken', endpoint)
        with pytest.raises(httpx.HTTPStatusError): await ModelService().generate('one', profile='broken')
        with pytest.raises(httpx.HTTPStatusError): await ModelService().generate('two', profile='broken')
        assert len(state['bodies']) == 2
        assert state['peak'] == 1


@pytest.mark.asyncio
async def test_cancelled_request_and_queue_timeout_release_slots():
    slots = ModelCapacity()
    profile = {'id': 'one', 'endpoint': 'http://127.0.0.1:1', 'max_parallel': 1}
    started = asyncio.Event()
    async def held():
        async with slots.acquire([profile]):
            started.set(); await asyncio.sleep(20)
    task = asyncio.create_task(held()); await started.wait()
    with pytest.raises(TimeoutError):
        async with slots.acquire([profile], wait_seconds=.05): pass
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    async with slots.acquire([profile], wait_seconds=.05): pass
    assert slots.status([profile])[0]['active'] == 0


@pytest.mark.asyncio
async def test_different_ports_on_same_computer_share_capacity():
    slots = ModelCapacity()
    first = {'id':'a','computer_id':'laptop3','endpoint':'https://one:1','max_parallel':4}
    second = {'id':'b','computer_id':'laptop3','endpoint':'https://one:2','max_parallel':1}
    configured = [first, second]
    async with slots.acquire([first],server_profiles=configured):
        with pytest.raises(TimeoutError):
            async with slots.acquire([second],wait_seconds=.05,server_profiles=configured): pass
        assert slots.status(configured)[0]['max_parallel'] == 1


@pytest.mark.asyncio
async def test_tool_calls_survive_authenticated_chat_sse(profiles):
    from backend.runtime.workspace_api import router
    from backend.security.http_auth import owner_auth
    app = FastAPI(); app.include_router(router)
    with model_server(tool=True) as (endpoint, state):
        save(profiles, 'laptop3', endpoint)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            body = {'messages': [{'role': 'user', 'content': 'get status'}], 'stream': True,
                    'tools': [{'type': 'function', 'function': {'name': 'get_status', 'parameters': {'type': 'object', 'properties': {}}}}]}
            assert (await client.post('/workspace/model-chat/laptop3/chat/completions', json=body)).status_code in {401, 403}
            response = await client.post('/workspace/model-chat/laptop3/chat/completions', json=body,
                                         headers={'Authorization': 'Bearer ' + owner_auth.token})
            assert response.status_code == 200
            chunks = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: {')]
            call = chunks[0]['choices'][0]['delta']['tool_calls'][0]
            assert call['function']['name'] == 'get_status' and call['index'] == 0
            assert response.headers['x-kingdom-model-profile'] == 'laptop3'
            assert state['bodies'][0]['tools'] == body['tools']


@pytest.mark.asyncio
async def test_pool_excludes_text_only_models_for_images(profiles):
    with model_server() as (endpoint, state):
        save(profiles, 'text', endpoint)
        with pytest.raises(ValueError): await ModelService().chat('pool:chat', {'messages': [
            {'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AA=='}}]}]})
        assert not state['bodies']


@pytest.mark.parametrize('config', [{'max_parallel': 0}, {'timeout_seconds': 5000}, {'pool_group': '../escape'}, {'num_ctx': -1}])
def test_invalid_computer_configuration_rejected(profiles, config):
    with pytest.raises(ValueError): save(profiles, 'invalid', 'http://127.0.0.1:1', **config)


def test_certificate_validation_cannot_be_disabled(profiles):
    from backend.models.profiles import model_tls_context
    assert model_tls_context({}) is True
    with pytest.raises(ValueError): save(profiles, 'badcert', 'https://example.com', ca_certificate='not a certificate')
    with pytest.raises(ValueError): save(profiles, 'wrongtransport', 'http://127.0.0.1:1', ca_certificate='not a certificate')


@pytest.mark.asyncio
async def test_native_backend_rejects_unauthenticated_clients_and_hides_invalid_input():
    from backend.main import app
    from backend.security.http_auth import owner_auth
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/workspace/model-profiles')).status_code == 401
        response = await client.post('/workspace/model-chat/one/chat/completions', json={'messages':'synthetic-private-input'},
                                     headers={'Authorization':'Bearer '+owner_auth.token})
        assert response.status_code == 422
        assert 'synthetic-private-input' not in response.text
