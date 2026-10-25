import base64
import hashlib
import io
import json
import tarfile
from types import SimpleNamespace

import pytest

from backend.runtime.knight_updates import stage, verify
from backend.runtime.knight_management import dispatch


def package(files, symlink=False):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            if symlink:
                member.type = tarfile.SYMTYPE
                member.linkname = '/etc/passwd'
                archive.addfile(member)
            else:
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
    raw = buffer.getvalue()
    return base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest()


def test_real_stage_verify_and_tampering(tmp_path):
    encoded, checksum = package({'backend/main.py': b'print("source only")'})
    receipt = stage(tmp_path, encoded, checksum)
    assert receipt['status'] == 'staged' and receipt['deployed'] is False
    source = tmp_path / checksum
    assert verify(source)['backend/main.py'] == hashlib.sha256(b'print("source only")').hexdigest()
    (source / 'backend/main.py').write_text('changed')
    with pytest.raises(ValueError, match='changed'):
        verify(source)


@pytest.mark.parametrize('files,symlink', [({'../escape.py': b''}, False),
                                         ({'backend/main.py': b''}, True),
                                         ({'data/owner-token': b''}, False),
                                         ({'C:/bad': b''}, False)])
def test_reject_unsafe_archive_before_writes(tmp_path, files, symlink):
    encoded, checksum = package(files, symlink)
    with pytest.raises(ValueError):
        stage(tmp_path, encoded, checksum)
    assert not list(tmp_path.iterdir())


def test_hash_mismatch(tmp_path):
    encoded, checksum = package({'backend/main.py': b''})
    with pytest.raises(ValueError, match='hash'):
        stage(tmp_path, encoded, '0' * 64)


def test_pairing_is_not_management_permission():
    registry = SimpleNamespace(get_node=lambda _: SimpleNamespace(node_state='CONNECTED', granted_capabilities=['compute']))
    with pytest.raises(PermissionError):
        dispatch('peer', 'inspect', {}, registry=registry)


def test_updater_requires_operator_profile(monkeypatch):
    monkeypatch.delenv('KINGDOM_KNIGHT_UPDATE_PROFILE', raising=False)
    registry = SimpleNamespace(get_node=lambda _: SimpleNamespace(node_state='CONNECTED', granted_capabilities=['knight.update.execute']))
    with pytest.raises(ValueError, match='owner-installed'):
        dispatch('peer', 'activate_update', {}, registry=registry)


@pytest.mark.parametrize('fail_health', [False, True])
def test_activate_identity_verification_and_rollback(tmp_path, monkeypatch, fail_health):
    from backend.runtime import knight_updates as updates
    encoded, checksum = package({'backend/main.py': b'# new backend'})
    releases = tmp_path / 'releases'
    stage(releases, encoded, checksum)
    unit = tmp_path / 'kingdom.service'
    original = '[Service]\nEnvironment=PYTHONPATH=/previous/source\n'
    unit.write_text(original)
    state = tmp_path / 'state'
    (state / 'data').mkdir(parents=True)
    (state / 'data/owner-token').write_text('private-token')
    profile = {'unit_file': str(unit), 'releases_root': str(releases), 'state_root': str(state),
               'base_url': 'http://127.0.0.1:8014'}
    monkeypatch.setattr(updates, 'load_profile', lambda _: profile)
    commands = []
    monkeypatch.setattr(updates.subprocess, 'run', lambda argv, **kwargs: commands.append(argv))
    monkeypatch.setattr(updates.time, 'sleep', lambda _: None)

    class Reply:
        def __init__(self, value): self.value = value
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps(self.value).encode()

    def response(request, **kwargs):
        if request.full_url.endswith('/tasks'): return Reply([])
        if request.full_url.endswith('/nodes/identity'): return Reply({'node_id': 'unchanged'})
        if request.full_url.endswith('/knight-management/local-source'):
            return Reply({'root': str((releases / checksum).resolve()), 'main_sha256': hashlib.sha256(b'# new backend').hexdigest()})
        # Failed candidate, then successful old unit after rollback.
        ready = not fail_health or unit.read_text() == original
        return Reply({'status': 'ready' if ready else 'failed'})

    monkeypatch.setattr(updates.urllib.request, 'urlopen', response)
    if fail_health:
        with pytest.raises(ValueError): updates.activate('profile.json', checksum)
        assert unit.read_text() == original
    else:
        assert updates.activate('profile.json', checksum)['status'] == 'verified'
        assert str(releases / checksum) in unit.read_text()
    receipt = json.loads((state / 'data' / ('update-' + checksum + '.json')).read_text())
    assert receipt['status'] == ('rolled_back' if fail_health else 'verified')
    assert receipt['identity_preserved'] is True
    assert commands.count(['systemctl', '--user', 'restart', 'kingdom.service']) == (2 if fail_health else 1)


def test_activation_is_a_governed_task_not_immediate_execution(tmp_path, monkeypatch):
    from backend.runtime import knight_updates as updates
    monkeypatch.setenv('KINGDOM_KNIGHT_UPDATE_PROFILE', str(tmp_path / 'operator.json'))
    monkeypatch.setattr(updates, 'load_profile', lambda _: {})
    monkeypatch.setattr(updates, 'schedule_command', lambda *_: ['systemd-run', '--user', 'fixed-updater'])
    submitted = []
    engine = SimpleNamespace(submit_task=lambda title, metadata: submitted.append(metadata) or {'status': 'waiting_approval'})
    registry = SimpleNamespace(get_node=lambda _: SimpleNamespace(node_state='CONNECTED', granted_capabilities=['knight.update.execute']))
    result = dispatch('peer', 'activate_update', {'release': '0' * 64}, registry=registry, engine=engine)
    assert result['verified'] is False and result['task']['status'] == 'waiting_approval'
    assert submitted[0]['tool'] == 'process.run@1.0.0'
    assert submitted[0]['actor'] == 'owner' and submitted[0]['requested_by_peer'] == 'peer'


@pytest.mark.asyncio
async def test_real_engine_requires_exact_approval_then_executes(tmp_path, monkeypatch):
    import sys
    from backend.runtime import knight_updates as updates
    from backend.runtime.engine import RuntimeEngine
    from backend.runtime.tasks import TaskManager
    from backend.runtime.policy import ExecutionPolicy
    from backend.security.approval_engine import ApprovalEngine
    from backend.storage.db import Database
    from backend.storage.repository import TaskRepository
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('KINGDOM_WORKSPACE', str(tmp_path / 'workspace'))
    monkeypatch.setenv('KINGDOM_KNIGHT_UPDATE_PROFILE', str(tmp_path / 'operator.json'))
    database = Database(tmp_path / 'isolated.db')
    Database(tmp_path / 'data/kingdom.db')
    runtime = RuntimeEngine()
    runtime.tasks = TaskManager(TaskRepository(database))
    runtime.execution_policy = ExecutionPolicy(database)
    runtime.security.approvals = ApprovalEngine(database=database)
    runtime.set_autonomy(3)
    for role in runtime.swarm.registry._knights:
        runtime.grant_computer_tools(role, ['process.execute'], persist=False)
    monkeypatch.setattr(updates, 'load_profile', lambda _: {})
    # A harmless real process exercises the production task executor while the
    # separate adapter tests above verify actual unit switch/rollback behavior.
    monkeypatch.setattr(updates, 'schedule_command', lambda *_: [sys.executable, '-c', 'print("scheduled-check")'])
    registry = SimpleNamespace(get_node=lambda _: SimpleNamespace(node_state='CONNECTED', granted_capabilities=['knight.update.execute']))
    result = dispatch('paired-controller', 'activate_update', {'release': '0' * 64}, registry=registry, engine=runtime)
    ident = result['task']['id']
    await runtime._process_next_task()
    waiting = runtime.tasks.get(ident)
    assert waiting['status'] == 'WAITING_APPROVAL'
    approval = waiting['metadata']['approval_id']
    runtime.security.approvals.approve(approval, approver='owner')
    runtime.tasks.transition_task(ident, 'queued')
    await runtime._process_next_task()
    finished = runtime.tasks.get(ident)
    assert finished['status'] == 'completed'
    assert runtime.security.approvals.get_request(approval)['status'] == 'consumed'
    assert finished['metadata']['requested_by_peer'] == 'paired-controller'


def test_signed_transport_relay_binds_pending_peer_operation_and_rejects_replay(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from backend.runtime import knight_management_api as api
    from backend.cluster import node_registry as registry_module, transport, identity
    from backend.storage import db as database_module
    from backend.storage.db import Database
    database = Database(tmp_path / 'relay.db')
    monkeypatch.setattr(database_module, 'db', database)
    local = identity.BaseNodeIdentity('local', 'commander')
    peer = identity.BaseNodeIdentity('peer', 'commander')
    node = SimpleNamespace(node_state='CONNECTED', kingdom_id='local', public_identity=peer.get_public_identity(), connection_metadata={})
    registry = SimpleNamespace(get_node=lambda ident: node if ident == 'peer' else None)
    monkeypatch.setattr(registry_module, 'node_registry', registry)
    monkeypatch.setattr(transport, 'node_registry', registry)
    monkeypatch.setattr(identity.KingdomIdentity, 'get_or_create', lambda: local)
    command = api.Command(operation='inspect')
    request = api.create_proof('peer', command)
    result = transport.RPCSecureTransport(peer).create_signed_message('local', 'knight_management_result', {
        'request_id': request['msg_id'], 'operation': 'inspect', 'result': {'services': []}})
    assert api.accept_receipt('peer', result) == {'services': []}
    with pytest.raises(HTTPException) as duplicate:
        api.accept_receipt('peer', result)
    assert duplicate.value.status_code == 409
    unknown = transport.RPCSecureTransport(peer).create_signed_message('local', 'knight_management_result', {
        'request_id': 'not-pending', 'operation': 'inspect', 'result': {'services': []}})
    with pytest.raises(HTTPException) as unsolicited:
        api.accept_receipt('peer', unknown)
    assert unsolicited.value.status_code == 409
    another = api.create_proof('peer', command)
    wrong_operation = transport.RPCSecureTransport(peer).create_signed_message('local', 'knight_management_result', {
        'request_id': another['msg_id'], 'operation': 'activate_update', 'result': {'status': 'verified'}})
    with pytest.raises(HTTPException) as mismatch:
        api.accept_receipt('peer', wrong_operation)
    assert mismatch.value.status_code == 403
