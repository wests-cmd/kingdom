import urllib.parse
import urllib.request

from backend.models.chatgpt_plan import ChatGPTPlanConnection
from backend.storage.db import Database


def test_stable_host_and_disabled_default_and_live_loopback_before_authorization(tmp_path):
    db = Database(tmp_path/'state.db')
    first = ChatGPTPlanConnection(db, root=tmp_path/'secrets')
    host = first.status()['host_id']
    assert host.startswith('urn:uuid:')
    assert first.status()['state'] == 'sign_in_required'
    assert first.status()['enabled'] is False
    second = ChatGPTPlanConnection(db, root=tmp_path/'secrets')
    assert second.status()['host_id'] == host
    request = first.begin()
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(request['authorization_url']).query)
    assert query['client_id'] == ['dynamic_agent_client']
    assert query['ext_agent_host_id'] == [host]
    assert query['code_challenge_method'] == ['S256']
    callback = query['redirect_uri'][0]
    assert callback.startswith('http://127.0.0.1:') and callback.endswith('/auth/callback')
    try:
        urllib.request.urlopen(callback+'?state=wrong&code=wrong&client_id=oaiapp_wrong', timeout=2)
        assert False, 'Wrong state must not complete sign-in'
    except urllib.error.HTTPError as error:
        assert error.code == 400
    assert first.status()['pending'] is True
    first.cancel()
    assert first.status()['pending'] is False


# These fixtures speak actual HTTP. Only routing to the loopback test provider is
# substituted; OAuth signatures, parsing, encryption and service behavior run.
import asyncio
import base64
import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from backend.models.chatgpt_plan import ChatGPTPlanError, AUTH


def encoded(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


class Routed(httpx.AsyncBaseTransport):
    def __init__(self, base): self.base = base
    async def handle_async_request(self, request):
        transport = httpx.AsyncHTTPTransport(retries=0)
        outgoing = httpx.Request(request.method, self.base+request.url.raw_path.decode(),
                                headers=request.headers, content=await request.aread(), extensions=request.extensions)
        response = await transport.handle_async_request(outgoing)
        class Stream(httpx.AsyncByteStream):
            async def __aiter__(self):
                async for chunk in response.stream: yield chunk
            async def aclose(self):
                await response.aclose(); await transport.aclose()
        return httpx.Response(response.status_code, headers=response.headers, stream=Stream(), extensions=response.extensions)


@contextmanager
def provider():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_numbers()
    num = lambda n: encoded(n.to_bytes((n.bit_length()+7)//8, 'big'))
    state = {'nonce': None, 'mode': 'completed', 'posts': [], 'refreshes': 0,
             'bad_signature': False, 'drip': None, 'active': 0}
    def token():
        header = encoded(json.dumps({'alg': 'RS256', 'kid': 'fixture'}).encode())
        claims = encoded(json.dumps({'iss': AUTH, 'aud': 'oaiapp_fixture', 'sub': 'fixture-owner',
            'nonce': state['nonce'], 'exp': 10000}).encode())
        signature = key.sign((header+'.'+claims).encode(), padding.PKCS1v15(), hashes.SHA256())
        if state['bad_signature']: signature = b'wrong-signature'
        return header+'.'+claims+'.'+encoded(signature)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def output(self, value, media='application/json'):
            raw = json.dumps(value).encode() if not isinstance(value, bytes) else value
            self.send_response(200); self.send_header('Content-Type', media)
            if state['drip'] == self.path:
                self.send_header('Content-Length', str(len(raw)+100)); self.end_headers()
                state['active'] += 1
                try:
                    for _ in range(100):
                        self.wfile.write(b' '); self.wfile.flush(); time.sleep(.02)
                    self.wfile.write(raw)
                except ConnectionError: pass
                finally: state['active'] -= 1
            else:
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            if self.path.endswith('openid-configuration'):
                self.output({'issuer': AUTH, 'jwks_uri': AUTH+'/jwks', 'revocation_endpoint': AUTH+'/revoke'})
            elif self.path == '/jwks':
                self.output({'keys': [{'kid': 'fixture', 'kty': 'RSA', 'n': num(public.n), 'e': num(public.e)}]})
            else: self.output({'models': [{'slug': 'gpt-fixture', 'display_name': 'Fixture chat', 'visibility': 'list'}]})
        def do_POST(self):
            raw = self.rfile.read(int(self.headers['Content-Length']))
            state['posts'].append(self.path)
            if self.path == '/revoke':
                self.output(b'')
            elif self.path.endswith('/oauth/token'):
                form = urllib.parse.parse_qs(raw.decode())
                if form['grant_type'] == ['refresh_token']: state['refreshes'] += 1
                self.output({'access_token': 'fixture-access-token', 'refresh_token': 'fixture-refresh-token',
                    'id_token': token(), 'token_type': 'Bearer', 'expires_in': 3600,
                    'scope': 'openid profile offline_access resource.invoke chatgpt.tokens.use.direct'})
            else:
                body = json.loads(raw)
                assert body['store'] is False and body['stream'] is True
                assert 'max_output_tokens' not in body and not body.get('tools')
                events = [{'type': 'response.output_text.delta', 'delta': 'Propose a bounded check.'}]
                if state['mode'] == 'completed':
                    events += [{'type': 'response.completed', 'response': {'id': 'resp-fixture', 'status': 'completed'}}]
                elif state['mode'] == 'failed':
                    events += [{'type': 'response.failed', 'response': {'error': {'code': 'subscription_sharing_usage_limit_exceeded'}}}]
                self.output(b''.join(b'data: '+json.dumps(e).encode()+b'\n\n' for e in events), 'text/event-stream')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try: yield state, Routed('http://127.0.0.1:'+str(server.server_port))
    finally: server.shutdown(); server.server_close(); thread.join(2)


def connected(tmp_path, fixture, *, request_timeout=2, advice_timeout=3):
    state, transport = fixture
    clock = [1000.0]
    connection = ChatGPTPlanConnection(Database(tmp_path/'provider.db'), root=tmp_path/'secrets',
        async_transport=transport, clock=lambda: clock[0], request_timeout=request_timeout, advice_timeout=advice_timeout)
    auth = connection.begin()
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(auth['authorization_url']).query)
    state['nonce'] = query['nonce'][0]
    callback = query['redirect_uri'][0]+'?'+urllib.parse.urlencode({'code': 'fixture-code',
        'state': query['state'][0], 'client_id': 'oaiapp_fixture'})
    with urllib.request.urlopen(callback, timeout=5) as response: assert response.status == 200
    connection.configure(enabled=True, model='gpt-fixture')
    return connection, clock


def test_real_signed_oauth_and_completed_response_do_not_disclose_credentials(tmp_path):
    with provider() as fixture:
        connection, _ = connected(tmp_path, fixture)
        result = asyncio.run(connection.advise('What is the next diagnostic check?'))
        assert result['completed'] is True and result['text'] == 'Propose a bounded check.'
        assert 'fixture-access-token' not in json.dumps(connection.status())
        assert 'fixture-refresh-token' not in json.dumps(connection.status())


@pytest.mark.parametrize('mode', ['failed', 'incomplete'])
def test_failed_or_interrupted_sse_does_not_return_partial_advice(tmp_path, mode):
    with provider() as fixture:
        connection, _ = connected(tmp_path, fixture); fixture[0]['mode'] = mode
        with pytest.raises(ChatGPTPlanError): asyncio.run(connection.advise('Need help'))


def test_invalid_identity_signature_never_connects_account(tmp_path):
    with provider() as fixture:
        fixture[0]['bad_signature'] = True
        with pytest.raises(urllib.error.HTTPError): connected(tmp_path, fixture)
        # The callback rejected the signature; no Responses request was made.
        assert '/v1/responses' not in fixture[0]['posts']


def test_dripping_refresh_has_total_deadline_and_stops_network_worker(tmp_path):
    with provider() as fixture:
        connection, clock = connected(tmp_path, fixture)
        # Tighten only the exchange under test. Signed sign-in setup is not
        # the slow-response experiment and can take longer on hosted Windows.
        connection.request_timeout = .15
        clock[0] = 4590.0; fixture[0]['drip'] = '/api/accounts/oauth/token'
        started = time.monotonic()
        with pytest.raises(ChatGPTPlanError): asyncio.run(connection.advise('Need help'))
        assert time.monotonic()-started < 1.0
        until = time.monotonic()+1
        while fixture[0]['active'] and time.monotonic()<until: time.sleep(.02)
        assert fixture[0]['active'] == 0
        assert fixture[0]['refreshes'] == 1
        assert '/v1/responses' not in fixture[0]['posts']


def test_authorization_is_rechecked_after_refresh_before_question_is_sent(tmp_path):
    with provider() as fixture:
        connection, clock = connected(tmp_path, fixture); clock[0] = 4590.0
        async def revoked(): return False
        with pytest.raises(ChatGPTPlanError) as error:
            asyncio.run(connection.advise('Do not send private question', authorization_check=revoked))
        assert error.value.code == 'request_authorization_changed'
        assert error.value.outcome_unknown is False
        assert fixture[0]['refreshes'] == 1
        assert '/v1/responses' not in fixture[0]['posts']


def test_connection_change_during_refresh_prevents_question_delivery(tmp_path):
    with provider() as fixture:
        connection, clock = connected(tmp_path, fixture); clock[0] = 4590.0

        async def changed_connection():
            connection.configure(enabled=False)
            return True  # The task is still authorized; its connection is not.

        with pytest.raises(ChatGPTPlanError) as error:
            asyncio.run(connection.advise('Keep this question local', authorization_check=changed_connection))
        assert error.value.outcome_unknown is False
        assert '/v1/responses' not in fixture[0]['posts']


@pytest.mark.parametrize('drip', [False, True])
def test_sign_out_removes_local_credentials_and_bounds_remote_revocation(tmp_path, drip):
    with provider() as fixture:
        connection, _ = connected(tmp_path, fixture)
        if drip:
            connection.request_timeout = .15
        if drip:
            fixture[0]['drip'] = '/revoke'
        started = time.monotonic()
        result = connection.sign_out()
        assert time.monotonic() - started < 1.5
        assert result['remote_revocation_confirmed'] is (not drip)
        assert connection.status()['state'] == 'sign_in_required'
        with connection.db.get_connection() as db:
            assert db.execute('SELECT secret FROM chatgpt_plan_accounts').fetchone()[0] is None
