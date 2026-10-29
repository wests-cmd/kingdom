"""Real dual-loopback HTTP, Ed25519 signatures, SQLite replay and dedup ledgers.

These tests do not simulate or claim physical Bluetooth hardware.
"""
import asyncio
import json
import threading
import ssl
import datetime
import ipaddress
import time
from types import SimpleNamespace
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.cluster.alternate_paths import AlternatePaths, local_endpoint
from backend.cluster.identity import KingdomIdentity
from backend.cluster.node_registry import NodeRegistry
from backend.cluster.transport import RPCSecureTransport
from backend.storage.db import Database
from backend.storage.repository import KnightRepository
from backend.events.event_bus import EventBus


@pytest.fixture
def setup(tmp_path, monkeypatch):
    database = Database(tmp_path / 'state.db')
    registry = NodeRegistry(KnightRepository(database))
    local, remote = KingdomIdentity('KG-path-controller'), KingdomIdentity('KG-path-peer')
    for identity in (local, remote):
        registry.repo.save({'id': identity.node_id, 'node_state': 'APPROVED', 'is_local': False,
                            'public_identity': identity.get_public_identity(), 'fingerprint': identity.fingerprint,
                            'capabilities': [], 'granted_capabilities': []})
    import backend.storage.db as db_module
    import backend.cluster.transport as rpc_module
    monkeypatch.setattr(db_module, 'db', database)
    monkeypatch.setattr(rpc_module, 'node_registry', registry)
    events = EventBus()
    service = AlternatePaths(database, registry, local, events)
    return database, registry, local, remote, events, service


@contextmanager
def peer_server(remote, *, barrier=None, lose_reply=False, wrong_request=False, redirect=False, wait_reply=None, tls=None, drip=None):
    state = {'posts': 0, 'gets': 0, 'verified': 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def answer(self, value, status=200):
            body = json.dumps(value).encode()
            slow = (drip == 'identity' and self.command == 'GET') or (drip == 'receipt' and self.command == 'POST')
            prefix = b' ' * 50 if slow else b''
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)+len(prefix)))
            self.end_headers()
            try:
                for byte in prefix:
                    self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(.06)
                self.wfile.write(body)
            except ConnectionError:
                # Closing a timed-out drip also raises ConnectionAbortedError
                # on Windows; this is the expected client cancellation.
                pass

        def do_GET(self):
            state['gets'] += 1
            if redirect:
                self.send_response(302)
                self.send_header('Location', 'http://169.254.169.254/latest/meta-data/')
                self.end_headers()
                return
            assert self.path == '/nodes/identity'
            self.answer(remote.get_public_identity())

        def do_POST(self):
            assert self.path == '/nodes/rpc'
            state['posts'] += 1
            value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            transport = RPCSecureTransport(remote)
            verified = transport.verify_and_unwrap_message(value)
            if not verified.get('valid'):
                return self.answer({'error': 'denied'}, 403)
            assert verified['msg_type'] == 'heartbeat'
            state['verified'] += 1
            if wait_reply:
                wait_reply[0].set()
                wait_reply[1].wait(3)
            if barrier:
                barrier.wait(3)
            if lose_reply:
                self.close_connection = True
                return
            proof = transport.create_signed_message(verified['sender_id'], 'inventory_snapshot', {
                'node_id': remote.node_id, 'request_id': 'different' if wrong_request else verified['msg_id'],
                'apprentice_inventory': []})
            self.answer({'status': 'ok', 'ping': {'success': True}, 'inventory_proof': proof})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    if tls:
        server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'{"https" if tls else "http"}://127.0.0.1:{server.server_port}', state
    finally:
        server.shutdown(); server.server_close(); thread.join(3)


def config(service, remote, urls):
    return service.configure(remote.node_id, [
        {'name': 'wifi', 'endpoint': urls[0], 'transport_hint': 'lan'},
        *([{'name': 'pan', 'endpoint': urls[1], 'transport_hint': 'lan'}] if len(urls) > 1 else [])], 0)


def test_two_actual_ip_paths_exchange_signed_control_in_parallel_and_dedup_restart(setup):
    database, registry, local, remote, events, service = setup
    assert service.get(remote.node_id)['paths'] == []  # Opt-in; legacy endpoint untouched.
    barrier = threading.Barrier(2)
    with peer_server(remote, barrier=barrier) as a, peer_server(remote, barrier=barrier) as b:
        config(service, remote, [a[0], b[0]])

        async def run():
            return await asyncio.gather(service.probe(remote.node_id, 'a', 'wifi'), service.probe(remote.node_id, 'b', 'pan'))

        results = asyncio.run(run())
        assert all(r['status'] == 'verified_control_exchange' for r in results)
        assert results[1]['transport_evidence'] == 'owner_configured_not_radio_observed'
        restarted = AlternatePaths(database, registry, local, events)
        assert asyncio.run(restarted.probe(remote.node_id, 'a', 'wifi')) == results[0]
        assert a[1]['verified'] == b[1]['verified'] == 1
        assert 'kingdom_endpoint' not in registry.get_node(remote.node_id).connection_metadata
        assert registry.get_node(remote.node_id).granted_capabilities == []


def private_ca(tmp_path, name):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    now = datetime.datetime.now(datetime.timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    ca = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1))
          .not_valid_after(now+datetime.timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False)
          .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),critical=False)
          .add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=False,
                                      data_encipherment=False,key_agreement=False,key_cert_sign=True,crl_sign=True,
                                      encipher_only=None,decipher_only=None),critical=True)
          .sign(key,hashes.SHA256()))
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')]))
            .issuer_name(subject).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1))
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()),critical=False)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
            .sign(key,hashes.SHA256()))
    certfile, keyfile = tmp_path/(name+'.pem'), tmp_path/(name+'.key')
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(server_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(certfile,keyfile)
    return ca.public_bytes(serialization.Encoding.PEM).decode(), context


def test_parallel_signed_https_paths_reuse_current_mesh_ca_and_reject_wrong_ca(setup,tmp_path,monkeypatch):
    _, registry, _, remote, _, service = setup
    from backend.cluster import mesh_api
    ca, server_context = private_ca(tmp_path,'approved')
    other_ca, _ = private_ca(tmp_path,'unrelated')
    configured = {'ca_pem': ca}
    monkeypatch.setattr(mesh_api,'membership',lambda:SimpleNamespace(config=lambda:dict(configured)))
    barrier = threading.Barrier(2)
    with peer_server(remote,barrier=barrier,tls=server_context) as first, peer_server(remote,barrier=barrier,tls=server_context) as second:
        config(service,remote,[first[0],second[0]])
        async def parallel():
            return await asyncio.gather(service.probe(remote.node_id,'tls-a','wifi'),service.probe(remote.node_id,'tls-b','pan'))
        results=asyncio.run(parallel())
        assert all(r['status']=='verified_control_exchange' for r in results)
        assert first[1]['verified']==second[1]['verified']==1
        configured['ca_pem']=other_ca
        rejected=asyncio.run(service.probe(remote.node_id,'wrong-ca','wifi'))
        assert rejected['status']=='not_sent'
        assert first[1]['gets']==first[1]['posts']==1
        node=registry.get_node(remote.node_id).to_dict();node['node_state']='REVOKED';registry.repo.save(node)
        with pytest.raises(ValueError):
            asyncio.run(service.probe(remote.node_id,'tls-a','wifi'))
        assert first[1]['posts']==1


def test_bluetooth_hint_cannot_relabel_loopback_as_real_radio(setup):
    _, _, _, remote, _, service = setup
    with peer_server(remote) as server:
        service.configure(remote.node_id, [{'name': 'pan', 'endpoint': server[0], 'transport_hint': 'bluetooth_pan'}], 0)
        result = asyncio.run(service.probe(remote.node_id, 'no-fake-radio', 'pan'))
        assert result['status'] == 'not_sent'
        assert server[1]['gets'] == server[1]['posts'] == 0


@pytest.mark.parametrize('stage,status', [('identity','not_sent'),('receipt','outcome_unknown')])
def test_total_deadline_releases_both_dripping_slots_without_resending(setup,stage,status):
    database, registry, local, remote, events, service = setup
    # Leave enough time for both loopback requests to start on busy Windows CI.
    # Drips last three seconds, so a one-second total deadline must still win
    # even though each byte arrives well within the HTTP inactivity timeout.
    service.probe_timeout = 1
    with peer_server(remote,drip=stage) as slow, peer_server(remote) as healthy:
        config(service,remote,[slow[0],healthy[0]])
        async def run():
            started = time.monotonic()
            first = asyncio.create_task(service.probe(remote.node_id,'drip-a','wifi'))
            second = asyncio.create_task(service.probe(remote.node_id,'drip-b','wifi'))
            async def both_slow_requests_started():
                counter = 'gets' if stage == 'identity' else 'posts'
                while slow[1][counter] < 2:
                    await asyncio.sleep(.01)
            await asyncio.wait_for(both_slow_requests_started(), 2)
            assert not first.done() and not second.done()
            # Reaching the server proves both requests captured the short
            # deadline. The healthy request gets the normal budget rather than
            # testing Windows TLS/signature/SQLite scheduling against one second.
            service.probe_timeout = 5
            good = asyncio.create_task(service.probe(remote.node_id,'healthy','pan'))
            timed_out = await asyncio.wait_for(asyncio.gather(first,second), 2)
            slow_elapsed = time.monotonic()-started
            verified = await asyncio.wait_for(good, 6)
            return [*timed_out,verified],slow_elapsed
        results,elapsed = asyncio.run(run())
        assert elapsed < 2.5, elapsed
        assert [r['status'] for r in results[:2]] == [status,status]
        assert results[2]['status'] == 'verified_control_exchange'
        assert slow[1]['posts'] == (0 if stage == 'identity' else 2)
        fresh = AlternatePaths(database,registry,local,events)
        cached = asyncio.run(fresh.probe(remote.node_id,'drip-a','wifi'))
        assert cached['status'] == status
        assert slow[1]['gets'] == 2
        assert slow[1]['posts'] == (0 if stage == 'identity' else 2)


def test_expired_membership_never_probes_any_path(setup):
    _, registry, _, remote, _, service = setup
    with peer_server(remote) as server:
        config(service, remote, [server[0]])
        node = registry.get_node(remote.node_id)
        node.connection_metadata['membership_expires_at'] = 1
        registry.repo.save(node.to_dict())
        with pytest.raises(ValueError):
            asyncio.run(service.probe(remote.node_id, 'expired', 'wifi'))
        assert server[1]['gets'] == server[1]['posts'] == 0


def test_lost_response_holds_key_across_restart_without_second_effect(setup):
    database, registry, local, remote, events, service = setup
    with peer_server(remote, lose_reply=True) as endpoint:
        config(service, remote, [endpoint[0]])
        result = asyncio.run(service.probe(remote.node_id, 'uncertain', 'wifi'))
        assert result['status'] == 'outcome_unknown'
        fresh = AlternatePaths(database, registry, local, events)
        assert asyncio.run(fresh.probe(remote.node_id, 'uncertain', 'wifi')) == result
        assert endpoint[1]['verified'] == 1


def test_cancelled_real_exchange_is_held_and_not_retransmitted(setup):
    database, registry, local, remote, events, service = setup
    accepted, release = threading.Event(), threading.Event()
    with peer_server(remote, wait_reply=(accepted, release)) as endpoint:
        config(service, remote, [endpoint[0]])

        async def run():
            pending = asyncio.create_task(service.probe(remote.node_id, 'cancelled', 'wifi'))
            assert await asyncio.to_thread(accepted.wait, 2)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            release.set()
            fresh = AlternatePaths(database, registry, local, events)
            assert (await fresh.probe(remote.node_id, 'cancelled', 'wifi'))['status'] == 'outcome_unknown'

        try:
            asyncio.run(run())
        finally:
            release.set()
        assert endpoint[1]['verified'] == 1


@pytest.mark.parametrize('kind', ['wrong_request', 'redirect'])
def test_substituted_request_receipt_or_redirect_never_claims_success(setup, kind):
    _, _, _, remote, _, service = setup
    with peer_server(remote, **{kind: True}) as endpoint:
        config(service, remote, [endpoint[0]])
        result = asyncio.run(service.probe(remote.node_id, 'rejected', 'wifi'))
        assert result['status'] != 'verified_control_exchange'
        if kind == 'redirect':
            assert endpoint[1]['posts'] == 0


def test_duplicate_concurrent_key_sends_only_once_and_revocation_blocks_cached_success(setup):
    _, registry, _, remote, _, service = setup
    with peer_server(remote) as endpoint:
        config(service, remote, [endpoint[0]])

        async def run():
            return await asyncio.gather(*(service.probe(remote.node_id, 'same', 'wifi') for _ in range(4)))

        results = asyncio.run(run())
        assert any(r['status'] == 'verified_control_exchange' for r in results)
        assert endpoint[1]['verified'] == 1
        node = registry.get_node(remote.node_id).to_dict()
        node['node_state'] = 'REVOKED'
        registry.repo.save(node)
        with pytest.raises(ValueError):
            asyncio.run(service.probe(remote.node_id, 'same', 'wifi'))
        assert endpoint[1]['verified'] == 1


@pytest.mark.parametrize('url', ['http://192.168.1.2:8000', 'https://example.com', 'https://169.254.169.254',
                                    'https://8.8.8.8', 'http://127.0.0.1:8000/path', 'https://user:pass@192.168.1.2'])
def test_paths_reject_dns_redirect_targets_cleartext_lan_and_credentials(url):
    with pytest.raises(ValueError):
        local_endpoint(url)


def test_owner_configuration_cas_and_key_cannot_change_paths(setup):
    _, _, _, remote, _, service = setup
    with peer_server(remote) as a, peer_server(remote) as b:
        state = config(service, remote, [a[0]])
        result = asyncio.run(service.probe(remote.node_id, 'fixed', 'wifi'))
        assert result['status'] == 'verified_control_exchange'
        with pytest.raises(ValueError):
            config(service, remote, [b[0]])  # Stale configuration revision.
        paths = [{'name': 'wifi', 'endpoint': b[0], 'transport_hint': 'bluetooth_pan'}]
        service.configure(remote.node_id, paths, state['revision'])
        with pytest.raises(ValueError):
            asyncio.run(service.probe(remote.node_id, 'fixed', 'wifi'))
        assert b[1]['posts'] == 0


def test_http_owner_boundary_and_no_rpc_execution_payloads(setup, monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from pydantic import ValidationError
    from backend.cluster import alternate_path_api as api
    from backend.security.http_auth import require_owner
    app = FastAPI()
    app.include_router(api.router)
    calls = []
    monkeypatch.setattr(api, 'service', lambda: calls.append('must not initialize'))

    def denied():
        raise HTTPException(403, 'Owner required')

    app.dependency_overrides[require_owner] = denied
    client = TestClient(app)
    for method, path in [('get', '/peer-paths/test'), ('put', '/peer-paths/test'), ('post', '/peer-paths/test/probe')]:
        assert getattr(client, method)(path, **({'json': {}} if method != 'get' else {})).status_code == 403
    assert not calls
    with pytest.raises(ValidationError):
        api.Probe(key='key', path='pan', operation='task_poll', payload={'tool': 'process.execute'})
