"""Real HTTP transport checks: truncation is never a completed review."""
import asyncio
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from backend.models.service import ModelService


@contextmanager
def endpoint(payload):
    bodies = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            bodies.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try: yield 'http://127.0.0.1:' + str(server.server_port), bodies
    finally:
        server.shutdown(); server.server_close(); thread.join()


def profile(url, provider='ollama'):
    return {'id': 'review', 'model': 'local', 'provider': provider, 'endpoint': url,
            'api_key': '', 'ollama_think': False, 'num_ctx': 4096, 'max_output_tokens': 256}


def test_quick_review_forwards_explicit_thinking_context_and_usage():
    with endpoint({'response': 'YES', 'done': True, 'done_reason': 'stop',
                   'prompt_eval_count': 12, 'eval_count': 3}) as (url, bodies):
        result = asyncio.run(ModelService()._generate_connection('Review code', profile(url), None))
    assert bodies[0]['think'] is False
    assert bodies[0]['options'] == {'num_ctx': 4096, 'num_predict': 256}
    assert result['text'] == 'YES' and result['usage']['total_tokens'] == 15


@pytest.mark.parametrize('payload', [
    {'response': 'Partial review...', 'done': True, 'done_reason': 'length'},
    {'response': 'Partial review...', 'done': False},
])
def test_partial_ollama_review_is_not_a_completed_answer(payload):
    with endpoint(payload) as (url, _):
        with pytest.raises(RuntimeError, match='incomplete response'):
            asyncio.run(ModelService()._generate_connection('Review code', profile(url), None))


def test_partial_compatible_review_is_not_a_completed_answer():
    with endpoint({'choices': [{'message': {'content': 'Partial'}, 'finish_reason': 'length'}]}) as (url, _):
        with pytest.raises(RuntimeError, match='incomplete response'):
            asyncio.run(ModelService()._generate_connection('Review code', profile(url, 'openai_compatible'), None))
