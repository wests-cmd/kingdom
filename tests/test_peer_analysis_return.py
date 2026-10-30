"""Same-connection native analysis; real computation, leases and signed RPCs."""
import asyncio
import threading
import time
from types import SimpleNamespace
from copy import deepcopy
import pytest

from backend.cluster.peer_analysis_return import AnalysisReturn, dispatch_one
from backend.cluster.peer_analysis import PeerAnalysis
from backend.cluster.identity import KingdomIdentity
from backend.cluster.node_registry import NodeInfo
from backend.cluster.task_leasing import TaskLeaseManager
from backend.storage.db import Database
from backend.storage.repository import TaskRepository
from backend.runtime.tasks import TaskManager


def responsive_pair(offered):
    native_worker, _, offer = offered
    database = Database(native_worker.db.db_path.parent/'controller.db')
    tasks, leases = TaskManager(TaskRepository(database)), TaskLeaseManager(database=database)
    node = NodeInfo('worker', fingerprint=native_worker.identity.fingerprint,
        public_identity=native_worker.identity.get_public_identity(), granted_capabilities=['compute'],
        connection_metadata={'native_analysis_return': True})
    calls = []

    async def exchange(peer, message):
        calls.append(message)
        result = AnalysisReturn(native_worker).receive('controller', message['payload'])
        return RPCSecureTransport(native_worker.identity).create_signed_message('controller', 'task_result',
            {**result, 'request_id': message['msg_id']})

    from backend.cluster.transport import RPCSecureTransport
    controller = PeerAnalysis(database, SimpleNamespace(get_node=lambda _: node),
        KingdomIdentity('controller'), lambda: True, exchange, lambda *a: None)
    engine = SimpleNamespace(tasks=tasks, status=lambda: {'running': True}, dispatch_lock=threading.RLock(),
        execution_policy=SimpleNamespace(get=lambda: {'level': 5}),
        dispatch_remote_task=lambda ident, peer, cap, manager: tasks.claim_remote_atomically(ident, peer, cap, manager))

    def accept(proof):
        from backend.runtime.execution import verify_request_result
        payload = proof['payload']
        selected = tasks.get(payload['task_id'])
        leases.validate_lease_execution(selected['id'], 'worker', payload['fencing_token'])
        verified = verify_request_result(selected, payload['output'], allow_local_model=False)
        completed = tasks.complete(selected['id'], {'output': payload['output'], 'verification': verified, 'executed_by': 'worker'})
        leases.revoke_lease(selected['id'])
        return {'completed': completed}

    return database, controller, engine, leases, accept, calls, offer


@pytest.mark.parametrize('delay', ['sqlite', 'acceptance'])
def test_slow_sqlite_and_acceptance_leave_heartbeat_loop_responsive(offered, delay):
    database, controller, engine, leases, accept, _, _ = responsive_pair(offered)
    locked = threading.Event()
    threads = []
    if delay == 'sqlite':
        def busy_database():
            with database.get_connection() as conn:
                conn.execute('BEGIN EXCLUSIVE')
                locked.set()
                time.sleep(.35)
        thread = threading.Thread(target=busy_database)
        thread.start(); threads.append(thread)
        assert locked.wait(2)
    else:
        original = accept
        def accept(proof):
            time.sleep(.35)
            return original(proof)

    async def observe():
        beats = 0
        pending = asyncio.create_task(dispatch_one(controller, 'worker', engine, leases, accept))
        while not pending.done():
            await asyncio.sleep(.01)
            beats += 1
        result = await pending
        return result, beats
    try:
        result, beats = asyncio.run(observe())
        assert result['status'] == 'verified'
        assert beats >= 8, 'Slow storage/verification blocked unrelated heartbeat ticks'
    finally:
        for thread in threads: thread.join(2)


def test_cancelling_blocked_selection_retains_lease_without_sending_or_detaching_claim(offered):
    database, controller, engine, leases, accept, calls, offer = responsive_pair(offered)
    locked = threading.Event()
    def busy_database():
        with database.get_connection() as conn:
            conn.execute('BEGIN EXCLUSIVE')
            locked.set()
            time.sleep(.35)
    thread = threading.Thread(target=busy_database)
    thread.start()
    assert locked.wait(2)

    async def cancel_then_retry():
        pending = asyncio.create_task(dispatch_one(controller, 'worker', engine, leases, accept))
        await asyncio.sleep(.05)
        pending.cancel()
        await asyncio.sleep(.02)
        assert controller.lock.locked(), 'Cancelled dispatcher released a still-running claim'
        assert (await dispatch_one(controller, 'worker', engine, leases, accept))['status'] == 'held'
        assert calls == []
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert calls == []
        retained = engine.tasks.get(offer['task']['id'])
        assert retained['status'] == 'leased' and retained['lease_id'] == offer['task']['lease_id']
        return await dispatch_one(controller, 'worker', engine, leases, accept)
    try:
        assert asyncio.run(cancel_then_retry())['status'] == 'verified'
        assert len(calls) == 1
    finally:
        thread.join(2)


def test_cancelling_acceptance_waits_for_commit_and_does_not_reexecute(offered, monkeypatch):
    _, controller, engine, leases, accept, calls, offer = responsive_pair(offered)
    started = threading.Event()
    def slow_accept(proof):
        started.set()
        time.sleep(.25)
        return accept(proof)

    async def cancel_after_acceptance_starts():
        pending = asyncio.create_task(dispatch_one(controller, 'worker', engine, leases, slow_accept))
        while not started.is_set():
            await asyncio.sleep(.005)
        pending.cancel()
        await asyncio.sleep(.02)
        assert controller.lock.locked()
        assert (await dispatch_one(controller, 'worker', engine, leases, accept))['status'] == 'held'
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert engine.tasks.get(offer['task']['id'])['status'] == 'completed'
        monkeypatch.setattr('backend.runtime.execution.execute_request', lambda *a: pytest.fail('Duplicate execution'))
        assert (await dispatch_one(controller, 'worker', engine, leases, accept))['status'] == 'idle'
    asyncio.run(cancel_after_acceptance_starts())
    assert len(calls) == 1


@pytest.fixture
def offered(tmp_path, monkeypatch):
    worker_id = KingdomIdentity('worker')
    controller_id = KingdomIdentity('controller')
    node = NodeInfo('controller', fingerprint=controller_id.fingerprint,
                    public_identity=controller_id.get_public_identity(), granted_capabilities=['compute'])
    worker = PeerAnalysis(Database(tmp_path/'worker.db'), SimpleNamespace(get_node=lambda _: node),
                          worker_id, lambda: True, None, lambda *args: None)
    monkeypatch.setattr('backend.cluster.local_load.local_load_metrics', lambda: {
        'cpu_percent': 10, 'memory_percent': 10,
        'power': {'status': 'no_battery', 'plugged': None, 'battery_percent': None}})
    db = Database(tmp_path/'controller.db')
    tasks = TaskManager(TaskRepository(db)); leases = TaskLeaseManager(database=db)
    task = tasks.create('Analyse literal text', {'execution_target': 'remote', 'capability': 'compute',
        'assigned_knight': 'worker', 'tool': 'text.analyze@1.0.0', 'tool_parameters': {'text': 'hello world'}})
    leased = tasks.claim_remote_atomically(task['id'], 'worker', 'compute', leases)
    offer = {'task': leased, 'lease': leases.leases[task['id']].model_dump()}
    return worker, node, offer


def test_lost_response_reuses_durable_receipt_without_reverse_connection(offered, monkeypatch):
    worker, node, offer = offered
    receiver = AnalysisReturn(worker)
    first = receiver.receive('controller', offer)
    assert first['status'] == 'completed'
    from backend.runtime.execution import verify_request_result
    assert verify_request_result(offer['task'], first['output'], allow_local_model=False)['state'] == 'VERIFIED'
    monkeypatch.setattr('backend.runtime.execution.execute_request', lambda *args: pytest.fail('Duplicate execution'))
    # Lost HTTP response / worker restart: caller can obtain the stored payload.
    assert AnalysisReturn(worker).receive('controller', offer) == first
    node.granted_capabilities = []
    with pytest.raises(PermissionError):
        receiver.receive('controller', offer)


@pytest.mark.parametrize('change', ['expired', 'node', 'tool', 'capability', 'token', 'changed_text'])
def test_invalid_or_modified_offer_cannot_reuse_or_execute(offered, monkeypatch, change):
    worker, _, offer = offered
    receiver = AnalysisReturn(worker)
    receiver.receive('controller', offer)
    wrong = deepcopy(offer)
    if change == 'expired': wrong['lease']['expires_at'] = 1
    elif change == 'node': wrong['task']['assigned_knight'] = 'other'
    elif change == 'tool': wrong['task']['metadata']['tool'] = 'process.run@1.0.0'
    elif change == 'capability': wrong['lease']['capability_scope'] = 'process.execute'
    elif change == 'token': wrong['task']['fencing_token'] = 2
    else: wrong['task']['metadata']['tool_parameters']['text'] = 'Different work'
    monkeypatch.setattr('backend.runtime.execution.execute_request', lambda *a: pytest.fail('Unexpected execution'))
    with pytest.raises((ValueError, PermissionError)):
        receiver.receive('controller', wrong)


def test_worker_crash_holds_durable_execution_claim_instead_of_reexecuting(offered, monkeypatch):
    worker, _, offer = offered
    def interrupted(*a): raise SystemExit('Simulated process loss')
    monkeypatch.setattr('backend.runtime.execution.execute_request', interrupted)
    with pytest.raises(SystemExit):
        AnalysisReturn(worker).receive('controller', offer)
    monkeypatch.setattr('backend.runtime.execution.execute_request', lambda *a: pytest.fail('Duplicate execution'))
    with pytest.raises(PermissionError, match='unresolved'):
        AnalysisReturn(worker).receive('controller', offer)


@pytest.mark.parametrize('preleased', [False, True])
@pytest.mark.parametrize('fault', [None, 'revocation', 'stale_lease', 'signature'])
def test_signed_rpc_return_is_independently_accepted_without_worker_outbound_rpc(tmp_path, monkeypatch, preleased, fault):
    import backend.api as api
    import backend.storage.db as storage
    from backend.cluster import federation_api
    from backend.cluster.node_registry import node_registry
    controller_id, worker_id = KingdomIdentity('controller'), KingdomIdentity('worker')
    current_identity = [controller_id]
    db = Database(tmp_path/'controller.db')
    monkeypatch.setattr(storage.db, 'db_path', db.db_path)
    monkeypatch.setattr(api.KingdomIdentity, 'get_or_create', lambda: current_identity[0])
    nodes = {ident.node_id: NodeInfo(ident.node_id, fingerprint=ident.fingerprint,
        public_identity=ident.get_public_identity(), granted_capabilities=['compute'],
        connection_metadata={'native_analysis_return': True}) for ident in (controller_id, worker_id)}
    registry = SimpleNamespace(get_node=nodes.get)
    monkeypatch.setattr(node_registry, 'get_node', nodes.get)
    monkeypatch.setattr('backend.cluster.local_load.local_load_metrics', lambda: {
        'cpu_percent': 10, 'memory_percent': 10,
        'power': {'status': 'no_battery', 'plugged': None, 'battery_percent': None}})
    native_worker = PeerAnalysis(Database(tmp_path/'worker.db'), registry, worker_id,
                                 lambda: True, None, lambda *a: None)
    monkeypatch.setattr(federation_api, 'configured_analysis_worker', lambda: native_worker)
    tasks = TaskManager(TaskRepository(db)); leases = TaskLeaseManager(database=db)
    from backend.runtime.engine import RuntimeEngine
    from backend.runtime.policy import ExecutionPolicy
    from backend.state import STATE
    engine = RuntimeEngine()
    engine.tasks = tasks
    engine.execution_policy = ExecutionPolicy(db)
    engine.execution_policy.set(5)
    monkeypatch.setitem(STATE, 'running', True)
    monkeypatch.setattr(api, 'engine', engine)
    monkeypatch.setattr(api, 'task_lease_manager', leases)
    monkeypatch.setattr(api.capability_authorizer, 'is_capability_granted',
                        lambda node, cap: cap in nodes[node].granted_capabilities)
    from backend.cluster.transport import RPCSecureTransport
    nodes['worker'].connection_metadata['native_analysis_return'] = False
    advertised = RPCSecureTransport(worker_id).create_signed_message('controller', 'heartbeat', {
        'node_id': 'worker', 'native_analysis_return': True,
        'load_metrics': {'cpu_percent': 10, 'memory_percent': 10}})
    assert api.handle_cluster_rpc(api.RPCMessageRequest.model_validate(advertised))['status'] == 'ok'
    assert nodes['worker'].connection_metadata['native_analysis_return'] is True
    task = tasks.create('Analyse exact literal', {'execution_target': 'remote', 'capability': 'compute',
        'actor': 'owner', 'assigned_knight': 'worker', 'tool': 'text.analyze@1.0.0', 'tool_parameters': {'text': 'hello world'}})
    if preleased:
        tasks.claim_remote_atomically(task['id'], 'worker', 'compute', leases)
    calls, lost = [], [True]

    async def exchange(peer, message):
        calls.append(message['msg_type'])
        assert peer == 'worker' and message['msg_type'] == 'native_analysis_execute'
        current_identity[0] = worker_id
        try:
            reply = api.handle_cluster_rpc(api.RPCMessageRequest.model_validate(message))
        finally:
            current_identity[0] = controller_id
        if lost[0]:
            lost[0] = False
            raise TimeoutError('Simulated lost response')
        return reply

    controller = PeerAnalysis(db, registry, controller_id, lambda: True, exchange, lambda *a: None)
    def accept(proof):
        if fault == 'revocation': nodes['worker'].granted_capabilities = []
        elif fault == 'stale_lease': leases.revoke_lease(task['id'])
        elif fault == 'signature': proof['signature'] = '00'*64
        return api.handle_cluster_rpc(api.RPCMessageRequest.model_validate(proof))
    with pytest.raises(TimeoutError):
        asyncio.run(dispatch_one(controller, 'worker', engine, leases, accept))
    assert tasks.get(task['id'])['status'] == 'leased'
    monkeypatch.setattr('backend.runtime.execution.execute_request', lambda *a: pytest.fail('Duplicate execution'))
    if fault:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as rejected:
            asyncio.run(dispatch_one(controller, 'worker', engine, leases, accept))
        assert rejected.value.status_code == 403
        assert tasks.get(task['id'])['result'] is None
        assert tasks.get(task['id'])['status'] == 'leased'
        return
    assert asyncio.run(dispatch_one(controller, 'worker', engine, leases, accept)) == {
        'status': 'verified', 'task_id': task['id']}
    completed = tasks.get(task['id'])
    assert completed['status'] == 'completed'
    assert completed['result']['verification']['state'] == 'VERIFIED'
    assert completed['result']['executed_by'] == 'worker'
    assert calls == ['native_analysis_execute', 'native_analysis_execute']
    with pytest.raises(PermissionError):
        leases.validate_lease_execution(task['id'], 'worker', completed['fencing_token'])


def test_poll_and_controller_offer_share_one_execution_receipt(offered, monkeypatch):
    worker, _, offer = offered
    receipt = AnalysisReturn(worker).receive('controller', offer)
    monkeypatch.setattr('backend.runtime.execution.execute_request', lambda *a: pytest.fail('Duplicate execution'))

    async def exchange(peer, message):
        if message['msg_type'] == 'task_poll':
            return {'status': 'ok', 'tasks': [offer['task']], 'analysis_lease': offer['lease']}
        assert message['payload'] == receipt
        return {'completed': {'id': offer['task']['id'], 'status': 'completed',
            'result': {'executed_by': 'worker', 'verification': {'state': 'VERIFIED'}}}}

    worker.exchange = exchange
    assert asyncio.run(worker.tick('controller')) == {'status': 'verified', 'task_id': offer['task']['id']}
