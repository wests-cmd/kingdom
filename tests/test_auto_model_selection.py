import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.models.capacity import ModelCapacity
from backend.models.profiles import ModelProfiles
from backend.models.service import ModelService
from backend.storage.db import Database


@contextmanager
def server():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({'models': [{'name': 'installed'}]}).encode())
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({'response': 'REAL HTTP', 'choices': [{'message': {'content': 'REAL HTTP'}}],
                'message': {'role': 'assistant', 'content': 'REAL HTTP'}, 'done': True, 'done_reason': 'stop'}).encode())
    instance = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True); thread.start()
    try: yield f'http://127.0.0.1:{instance.server_port}', calls
    finally: instance.shutdown(); instance.server_close(); thread.join()


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = Database(tmp_path/'test.db')
    monkeypatch.setattr('backend.storage.db.db', db)
    monkeypatch.setattr('backend.models.capacity.capacity', ModelCapacity())
    return ModelProfiles(db)


def save(profiles, ident, endpoint, **kwargs):
    return profiles.save(ident, {'provider': 'ollama', 'endpoint': endpoint,
        'model': 'installed', 'variant': 'standard', **kwargs})


@pytest.mark.asyncio
async def test_default_selects_live_installed_connection_and_explains(profiles):
    with server() as (endpoint, calls):
        save(profiles, 'missing', endpoint, model='not-installed')
        save(profiles, 'eligible', endpoint)
        result = await ModelService().generate('question')
        assert result['profile'] == 'eligible' and result['text'] == 'REAL HTTP'
        assert result['selection']['mode'] == 'auto'
        assert len(calls) == 1


@pytest.mark.asyncio
async def test_explicit_profile_preserved_without_auto_probe(profiles):
    with server() as (endpoint, calls):
        save(profiles, 'explicit', endpoint, model='explicit-choice')
        result = await ModelService().generate('question', profile='explicit')
        assert result['profile'] == 'explicit'
        assert calls[0]['model'] == 'explicit-choice' and 'selection' not in result


@pytest.mark.asyncio
@pytest.mark.parametrize('kwargs,body_overrides', [({'disabled': True}, {}),
    ({'context_characters': 4}, {}), ({}, {'tools': [{'type': 'function'}]}),
    ({}, {'messages': [{'role': 'user', 'content': [{'type': 'image_url'}]}]})])
async def test_automatic_requirements_fail_closed(profiles, kwargs, body_overrides):
    with server() as (endpoint, calls):
        save(profiles, 'unsuitable', endpoint, **kwargs)
        body = {'messages': [{'role': 'user', 'content': 'question'}], **body_overrides}
        with pytest.raises(ValueError, match='eligible'):
            await ModelService().chat('auto', body)
        assert not calls


@pytest.mark.asyncio
async def test_declared_tools_supported_in_auto_chat(profiles):
    with server() as (endpoint, calls):
        save(profiles, 'tools', endpoint, supports_tools=True)
        result = await ModelService().chat(None, {'messages': [{'role': 'user', 'content': 'question'}], 'tools': [{'type': 'function'}]})
        assert result['kingdom_profile'] == 'tools'
        assert result['kingdom_selection']['mode'] == 'auto'


@pytest.mark.asyncio
async def test_required_pending_is_opt_in_and_does_not_force_completed_work(profiles):
    with server() as (endpoint, calls):
        save(profiles, 'bounded', endpoint, provider='openai_compatible',
             supports_tools=True, tool_choice_mode='required_pending')
        request = {'messages': [{'role': 'user', 'content': 'Use the tool'}],
                   'tools': [{'type': 'function'}], 'tool_choice': 'auto'}
        service = ModelService()
        await service.chat('bounded', {**request, 'tool_evidence_pending': True})
        await service.chat('bounded', {**request, 'tool_evidence_pending': False})
        await service.chat('bounded', {**request, 'tool_choice': 'none', 'tool_evidence_pending': True})
        assert [call['tool_choice'] for call in calls] == ['required', 'auto', 'none']
        assert all('tool_evidence_pending' not in call for call in calls)


def test_native_ollama_cannot_be_mislabeled_as_supporting_required_choice(profiles):
    with pytest.raises(ValueError, match='compatible OpenAI'):
        save(profiles, 'native', 'http://127.0.0.1:1234', tool_choice_mode='required_pending')


@pytest.mark.asyncio
async def test_trial_model_stays_out_of_automatic_selection_but_can_be_explicitly_tested(profiles):
    with server() as (endpoint, calls):
        save(profiles, 'trial', endpoint, auto_select=False)
        with pytest.raises(ValueError, match='eligible'):
            await ModelService().chat('auto', {'messages': [{'role':'user','content':'test'}]})
        assert calls == []
        await ModelService().chat('trial', {'messages': [{'role':'user','content':'test'}]})
        assert len(calls) == 1
