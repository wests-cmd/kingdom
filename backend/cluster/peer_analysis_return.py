"""Return bounded analysis over the controller's existing signed connection.

No reverse worker connection, shell, model, enrollment or new grant is required.
An interrupted worker claim is held, never silently executed a second time.
"""
import hashlib
import json
import math
import time

from backend.cluster.peer_analysis import TOOLS, validate
from backend.cluster.task_leasing import TaskLease
from backend.cluster.transport import RPCSecureTransport


class AnalysisReturn:
    def __init__(self, worker):
        self.worker = worker
        with worker.db.get_connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS native_analysis_returns(
                controller TEXT NOT NULL, task TEXT NOT NULL, token INTEGER NOT NULL,
                digest TEXT NOT NULL, state TEXT NOT NULL, payload TEXT,
                PRIMARY KEY(controller, task))''')
            conn.commit()

    def receive(self, controller, offer):
        """Called only after the public RPC boundary authenticates the sender."""
        if not self.worker.allowed(controller):
            raise PermissionError('Current analysis authority is required')
        if not isinstance(offer, dict) or set(offer) != {'task', 'lease'}:
            raise ValueError('An exact task and lease are required')
        task = offer['task']
        validate(task, self.worker.identity.node_id)
        lease = TaskLease.model_validate(offer['lease'])
        now = time.time()
        if (lease.task_id != task['id'] or lease.assigned_node_id != self.worker.identity.node_id
                or lease.lease_id != task['lease_id'] or lease.fencing_token != task['fencing_token']
                or lease.capability_scope != 'compute' or lease.revoked
                or not all(math.isfinite(v) for v in (lease.issued_at, lease.expires_at))
                or not lease.issued_at <= now < lease.expires_at or lease.expires_at - lease.issued_at > 300):
            raise PermissionError('The signed lease is expired or does not cover this task')
        digest = hashlib.sha256(json.dumps(offer, sort_keys=True, allow_nan=False).encode()).hexdigest()
        with self.worker.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            old = conn.execute('SELECT token,digest,state,payload FROM native_analysis_returns WHERE controller=? AND task=?',
                               (controller, task['id'])).fetchone()
            if old:
                if lease.fencing_token < old[0] or (lease.fencing_token == old[0] and digest != old[1]):
                    raise PermissionError('Stale or modified analysis lease')
                if old[2] == 'executing':
                    raise PermissionError('Prior analysis outcome is unresolved; no execution replay')
                if lease.fencing_token == old[0]:
                    return json.loads(old[3])
            elif conn.execute('SELECT COUNT(*) FROM native_analysis_returns').fetchone()[0] >= 1000:
                raise PermissionError('Analysis receipt retention requires owner review')
            from backend.cluster.local_load import local_load_metrics
            from backend.cluster.power_policy import power_budget
            load = local_load_metrics()
            if (any(type(load.get(k)) not in (int, float) or not 0 <= load[k] < 85
                    for k in ('cpu_percent', 'memory_percent'))
                    or not power_budget(load.get('power'), 10)['allowed']):
                raise PermissionError('Analysis is held for local capacity or power')
            if not self.worker.allowed(controller):
                raise PermissionError('Analysis authority changed')
            conn.execute('''INSERT INTO native_analysis_returns VALUES(?,?,?,?,?,NULL)
                ON CONFLICT(controller,task) DO UPDATE SET token=excluded.token,
                digest=excluded.digest,state=excluded.state,payload=NULL''',
                (controller, task['id'], lease.fencing_token, digest, 'executing'))
            conn.commit()
        from backend.runtime.execution import execute_request, verify_request_result
        try:
            output = execute_request(task, ['compute'])
            if verify_request_result(task, output, allow_local_model=False).get('state') != 'VERIFIED':
                raise ValueError('Analysis did not verify')
            payload = {'status': 'completed', 'output': output}
        except Exception:
            payload = {'status': 'failed', 'error': 'Native analysis did not pass local verification'}
        payload.update(task_id=task['id'], executed_by=self.worker.identity.node_id,
                       lease_id=task['lease_id'], fencing_token=task['fencing_token'])
        with self.worker.db.get_connection() as conn:
            conn.execute('UPDATE native_analysis_returns SET state=?,payload=? WHERE controller=? AND task=? AND token=? AND digest=?',
                         ('completed', json.dumps(payload), controller, task['id'], lease.fencing_token, digest))
            conn.commit()
        if not self.worker.allowed(controller) or time.time() >= lease.expires_at:
            raise PermissionError('Authority or lease changed before result delivery')
        self.worker.publish('cluster.native_analysis_return_ready', {'task_id': task['id'], 'controller_id': controller})
        return payload


async def dispatch_one(worker, peer_id, engine, leases, accept_result):
    """One authorized analysis offer; retry only the exact still-active lease."""
    if not worker.allowed(peer_id) or not engine.status()['running'] or engine.execution_policy.get()['level'] == 0:
        return {'status': 'held'}
    if (worker.registry.get_node(peer_id).connection_metadata or {}).get('native_analysis_return') is not True:
        return {'status': 'idle'}  # Older peers retain their existing worker-poll path.
    if worker.lock.locked():
        return {'status': 'held'}
    async with worker.lock:
        selected = None
        # Recover a lost response before selecting another task for this worker.
        for task in engine.tasks.list('leased') + engine.tasks.list('queued'):
            meta = task.get('metadata', {})
            target = task.get('assigned_knight') or meta.get('assigned_knight')
            if (meta.get('tool') not in TOOLS or meta.get('execution_target') != 'remote'
                    or meta.get('capability', 'compute') != 'compute' or target not in (None, peer_id)):
                continue
            if task['status'] == 'leased':
                if target != peer_id:
                    continue
                try:
                    leases.validate_lease_execution(task['id'], peer_id, task['fencing_token'])
                except PermissionError:
                    continue
                selected = task
            else:
                selected = engine.dispatch_remote_task(task['id'], peer_id, 'compute', leases)
            if selected:
                break
        if selected is None:
            return {'status': 'idle'}
        leases.validate_lease_execution(selected['id'], peer_id, selected['fencing_token'])
        if not worker.allowed(peer_id) or not engine.status()['running'] or engine.execution_policy.get()['level'] == 0:
            return {'status': 'held'}
        transport = RPCSecureTransport(worker.identity)
        message = transport.create_signed_message(peer_id, 'native_analysis_execute', {
            'task': selected, 'lease': leases.leases[selected['id']].model_dump()})
        reply = await worker.exchange(peer_id, message)
        result = reply.get('payload', {}) if isinstance(reply, dict) else {}
        if (not isinstance(reply, dict) or reply.get('sender_id') != peer_id
                or reply.get('target_id') != worker.identity.node_id or reply.get('msg_type') != 'task_result'
                or not isinstance(result, dict) or result.get('request_id') != message['msg_id']
                or result.get('task_id') != selected['id'] or result.get('lease_id') != selected['lease_id']
                or type(result.get('fencing_token')) is not int
                or result['fencing_token'] != selected['fencing_token'] or result.get('executed_by') != peer_id):
            raise ValueError('Peer did not return a correlated signed analysis result')
        # The normal RPC handler verifies the signature, active lease and current
        # grant, then independently recomputes analysis. Never accept its claim here.
        accepted = accept_result(reply)
        completed = accepted.get('completed')
        if completed:
            return {'status': 'verified', 'task_id': completed['id']}
        if accepted.get('failed'):
            return {'status': 'failed', 'task_id': selected['id']}
        raise ValueError('Analysis result was not independently accepted')
