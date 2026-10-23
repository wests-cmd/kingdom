"""Adversarial receipt protocol tests, not a claim of OS supervisor isolation."""
import json
import socket
import sys
import threading
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from backend.security.required_monitor import MonitorRequirement, RequiredMonitor, PROTOCOL, canonical
from tests.test_execution_policy import engine


def signer():
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return key, public


def signed(key, request):
    receipt = {**request, 'decision': 'recorded'}
    return {'receipt': receipt, 'signature': key.sign(canonical(receipt)).hex()}


def test_exact_signed_receipt_and_nontransferable_context():
    key, public = signer()
    request = {'protocol': PROTOCOL, 'nonce': 'fresh', 'operation_digest': 'abc', 'expires_at': time.time() + 4}
    response = signed(key, request)
    assert RequiredMonitor.verify_receipt(response, request, public, time.time())
    for field in ['nonce', 'operation_digest', 'protocol', 'expires_at']:
        changed = {**request, field: 'substituted'}
        with pytest.raises(Exception):
            RequiredMonitor.verify_receipt(response, changed, public, time.time())
    wrong_key, _ = signer()
    with pytest.raises(Exception):
        RequiredMonitor.verify_receipt(signed(wrong_key, request), request, public, time.time())
    for delta in [-1, 20]:
        changed = {**request, 'expires_at': time.time() + delta}
        with pytest.raises(Exception):
            RequiredMonitor.verify_receipt(signed(key, changed), changed, public, time.time())


def test_monitor_requirement_is_frozen_and_not_task_controlled(engine, monkeypatch):
    monkeypatch.setenv('KINGDOM_REQUIRED_MONITOR_SOCKET', '')
    requirement = MonitorRequirement.from_environment()
    assert requirement.required
    guard = RequiredMonitor(requirement)
    monkeypatch.delenv('KINGDOM_REQUIRED_MONITOR_SOCKET')
    with pytest.raises(PermissionError):
        guard.attest(actor='owner', capability='process.execute', operation='check', parameters={'monitor': {'enabled': False}})
    assert RequiredMonitor(MonitorRequirement()).attest(actor='owner', capability='process.execute', operation='check', parameters={}) is None


def test_DOOMSDAY_MONITORING_INTEGRITY_unavailable_even_level_five(engine):
    engine.set_autonomy(5)
    engine.security.required_monitor = RequiredMonitor(MonitorRequirement('/missing-supervisor', '00' * 32))
    task = engine.submit_task('legitimate migration', {'actor': 'owner', 'capability': 'process.execute',
        'monitor_enabled': False, 'monitor_receipt': 'model claims monitor healthy'})
    result = engine.authorize_task(task)
    assert not result['authorized']
    assert result['approval_id'] is None
    assert any(row['decision'] == 'DENIED' and 'monitoring' in row['reason'] for row in engine.security.audit.history(50))
    assert engine.tasks.get(task['id'])['status'] == 'queued'


def test_missing_monitor_does_not_consume_existing_human_approval(engine):
    engine.set_autonomy(3)
    task = engine.submit_task('approved migration', {'actor': 'owner', 'capability': 'process.execute'})
    approval = engine.authorize_task(task)['approval_id']
    engine.security.approvals.approve(approval, approver='owner')
    task['metadata']['approval_id'] = approval
    engine.security.required_monitor = RequiredMonitor(MonitorRequirement('/missing-supervisor', '00' * 32))
    assert not engine.authorize_task(task)['authorized']
    assert engine.security.approvals.get_request(approval)['status'] == 'approved'


@pytest.mark.skipif(sys.platform != 'linux', reason='Unix socket transport is Linux-only')
@pytest.mark.parametrize('attack', ['valid', 'wrong_nonce', 'wrong_digest', 'wrong_key', 'oversized', 'malformed', 'truncated', 'timeout'])
def test_real_socket_signed_attestation(tmp_path, attack):
    key, public = signer()
    endpoint = str(tmp_path / 'monitor.sock')
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(endpoint)
    listener.listen(1)
    requests = []
    def supervise():
        try:
            with listener.accept()[0] as connection:
                raw = bytearray()
                while not raw.endswith(b'\n'):
                    raw.extend(connection.recv(1024))
                request = json.loads(raw)
                requests.append(request)
                if attack == 'timeout':
                    time.sleep(0.8)
                    return
                if attack == 'truncated':
                    return
                if attack == 'malformed':
                    connection.sendall(b'not json\n')
                    return
                if attack == 'oversized':
                    connection.sendall(b'x' * 4097)
                    return
                if attack == 'wrong_nonce': request['nonce'] = 'previous receipt'
                if attack == 'wrong_digest': request['operation_digest'] = 'another operation'
                signing_key = signer()[0] if attack == 'wrong_key' else key
                connection.sendall(canonical(signed(signing_key, request)) + b'\n')
        finally:
            listener.close()
    worker = threading.Thread(target=supervise, daemon=True)
    worker.start()
    guard = RequiredMonitor(MonitorRequirement(endpoint, public))
    try:
        if attack == 'valid':
            assert guard.attest(actor='owner', capability='process.execute', operation='private operation', parameters={'password': 'must not cross socket'})
        else:
            with pytest.raises(PermissionError):
                guard.attest(actor='owner', capability='process.execute', operation='private operation', parameters={})
    finally:
        worker.join(timeout=2)
        assert not worker.is_alive()
    assert 'must not cross socket' not in json.dumps(requests)
    assert 'private operation' not in json.dumps(requests)
