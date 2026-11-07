"""Supervisor protocol and failure tests; OS principal separation is not simulated."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

from backend.security import monitor_supervisor as monitor
from backend.security.required_monitor import RequiredMonitor, PROTOCOL


def request():
    return {'protocol': PROTOCOL, 'nonce': 'a' * 64, 'operation_digest': hashlib.sha256(b'private').hexdigest(), 'expires_at': time.time() + 4}


class Audit:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail
    def append(self, event):
        if self.fail:
            raise OSError('storage unavailable')
        self.events.append(event)


class Signer:
    def __init__(self, audit):
        self.key = Ed25519PrivateKey.generate()
        self.calls = 0
        self.audit = audit
    def sign(self, payload):
        assert self.audit.events and self.audit.events[-1]['event'] == 'recorded'
        self.calls += 1
        return self.key.sign(payload)


def build(monkeypatch, fail=False):
    uid = getattr(os, 'geteuid', lambda: 1000)()
    monkeypatch.setattr(monitor.os, 'geteuid', lambda: uid, raising=False)
    audit = Audit(fail)
    signer = Signer(audit)
    return monitor.Supervisor(uid + 1, signer, audit), signer, audit


def test_records_exact_digest_before_signing_and_blocks_replay(monkeypatch):
    supervisor, signer, audit = build(monkeypatch)
    req = request()
    response = supervisor.record_and_sign(req, supervisor.allowed_peer_uid)
    public = signer.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    assert RequiredMonitor.verify_receipt(response, req, public, time.time())
    assert audit.events[0]['operation_digest'] == req['operation_digest']
    assert 'private' not in json.dumps(audit.events)
    with pytest.raises(PermissionError):
        supervisor.record_and_sign(req, supervisor.allowed_peer_uid)
    assert signer.calls == 1


def test_DOOMSDAY_MONITORING_INTEGRITY_logging_failure_never_signs(monkeypatch):
    supervisor, signer, audit = build(monkeypatch, fail=True)
    with pytest.raises(OSError):
        supervisor.record_and_sign(request(), supervisor.allowed_peer_uid)
    assert signer.calls == 0
    assert not supervisor.seen


def test_expired_during_durable_append_never_signs(monkeypatch):
    supervisor, signer, audit = build(monkeypatch)
    now = [time.time()]
    monkeypatch.setattr(monitor.time, 'time', lambda: now[0])
    req = request()
    original_append = audit.append
    def slow_append(event):
        original_append(event)
        now[0] += 6
    audit.append = slow_append
    with pytest.raises(PermissionError):
        supervisor.record_and_sign(req, supervisor.allowed_peer_uid)
    assert signer.calls == 0


@pytest.mark.parametrize('change', ['extra_field', 'bad_nonce', 'bad_digest', 'expired', 'long_expiry', 'bool_expiry', 'bad_protocol'])
def test_rejects_unbounded_or_ambiguous_requests(change):
    req = request()
    if change == 'extra_field': req['prompt'] = 'secret'
    if change == 'bad_nonce': req['nonce'] = 'small'
    if change == 'bad_digest': req['operation_digest'] = 'small'
    if change == 'expired': req['expires_at'] = time.time() - 1
    if change == 'long_expiry': req['expires_at'] = time.time() + 30
    if change == 'bool_expiry': req['expires_at'] = True
    if change == 'bad_protocol': req['protocol'] = 'other'
    with pytest.raises(ValueError):
        monitor.validate_request(req, time.time())


def test_refuses_same_or_root_allowed_uid_and_wrong_peer(monkeypatch):
    supervisor, signer, audit = build(monkeypatch)
    for uid in (0, os.geteuid()):
        with pytest.raises(PermissionError):
            monitor.Supervisor(uid, signer, audit)
    with pytest.raises(PermissionError):
        supervisor.record_and_sign(request(), supervisor.allowed_peer_uid + 1)
    assert signer.calls == 0


def test_nonce_window_is_bounded_and_not_evicted_while_live(monkeypatch):
    supervisor, signer, audit = build(monkeypatch)
    supervisor.seen.update({str(i): time.time() + 5 for i in range(1024)})
    with pytest.raises(PermissionError):
        supervisor.record_and_sign(request(), supervisor.allowed_peer_uid)
    assert signer.calls == 0 and len(supervisor.seen) == 1024


@pytest.mark.skipif(sys.platform != 'linux', reason='Real Linux ownership/fsync/peer credentials')
def test_real_socket_rejects_same_process_uid(monkeypatch):
    supervisor, signer, audit = build(monkeypatch)
    server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    with server, client:
        supervisor.handle_connection(server)
    assert signer.calls == 0
    assert audit.events[-1]['event'] == 'denied'
    assert audit.events[-1]['peer_uid'] == os.geteuid()


@pytest.mark.skipif(sys.platform != 'linux', reason='Real Linux ownership/fsync')
def test_protected_key_config_and_real_fsync_failure_latches(monkeypatch):
    with tempfile.TemporaryDirectory(prefix='.kingdom-monitor-test-', dir=Path.home()) as directory:
        base = Path(directory)
        key = base / 'key'
        key.write_bytes(Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
        key.chmod(0o600)
        config = base / 'config.json'
        config.write_text(json.dumps({'allowed_peer_uid': os.geteuid() + 1, 'socket_path': str(base/'monitor.sock'), 'key_path': str(key), 'audit_path': str(base/'events.jsonl')}))
        config.chmod(0o600)
        loaded, _ = monitor.load_configuration(config)
        assert loaded['allowed_peer_uid'] != os.geteuid()
        key.chmod(0o640)
        with pytest.raises(PermissionError): monitor.load_configuration(config)
        key.chmod(0o600)
        linked = base / 'linked-key'
        linked.symlink_to(key)
        with pytest.raises((PermissionError, OSError)): monitor.protected_read(linked, os.geteuid(), secret=True)
        audit = monitor.DurableAudit(base/'events.jsonl')
        try:
            audit.append({'event': 'first'})
            assert json.loads((base/'events.jsonl').read_text())['event'] == 'first'
            def unavailable(fd): raise OSError('fsync failed')
            monkeypatch.setattr(monitor.os, 'fsync', unavailable)
            with pytest.raises(OSError): audit.append({'event': 'failed'})
            assert audit.failed
            with pytest.raises(OSError): audit.append({'event': 'must not continue'})
        finally:
            audit.close()

@pytest.mark.skipif(sys.platform != 'linux', reason='Real Linux fsync ordering')
def test_real_durable_audit_fsync_precedes_signature(monkeypatch):
    with tempfile.TemporaryDirectory(prefix='.kingdom-monitor-test-', dir=Path.home()) as directory:
        audit = monitor.DurableAudit(Path(directory)/'events.jsonl')
        key = Ed25519PrivateKey.generate()
        syncs = []
        original = os.fsync
        def synced(fd):
            original(fd)
            syncs.append(fd)
        monkeypatch.setattr(monitor.os, 'fsync', synced)
        class ObservedSigner:
            def sign(self, payload):
                assert audit.fd in syncs
                return key.sign(payload)
        supervisor = monitor.Supervisor(os.geteuid() + 1, ObservedSigner(), audit)
        try:
            response = supervisor.record_and_sign(request(), supervisor.allowed_peer_uid)
            assert response['signature']
            assert json.loads((Path(directory)/'events.jsonl').read_text())['event'] == 'recorded'
        finally:
            audit.close()

@pytest.mark.skipif(sys.platform != 'linux', reason='Real Linux bounded transport parser; no authentication simulated')
@pytest.mark.parametrize('failure', ['oversized', 'truncated', 'timeout'])
def test_socket_input_bounds_without_simulating_peer_identity(failure):
    server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    with server, client:
        if failure == 'oversized': client.sendall(b'x' * 513)
        if failure == 'truncated':
            client.sendall(b'partial')
            client.shutdown(socket.SHUT_WR)
        raw = bytearray()
        with pytest.raises((ValueError, TimeoutError, socket.timeout)):
            monitor.read_request(server, raw)
        assert len(raw) <= 513


def test_duplicate_json_fields_are_rejected():
    with pytest.raises(ValueError):
        json.loads('{"nonce":"first","nonce":"substituted"}', object_pairs_hook=monitor.unique_object)
