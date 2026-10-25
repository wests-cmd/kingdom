"""Native bounded pure-analysis consumer for already approved peer links.

No shell, model inference, file writes, pairing, permission changes or SSH relay.
The controller must independently verify the exact signed lease result.
"""
import asyncio
import hashlib
import json
import time
from backend.cluster.transport import RPCSecureTransport

TOOLS={'text.analyze@1.0.0','code.python.analyze@1.0.0'}


def validate(task, worker):
    meta=task.get('metadata',{}) if isinstance(task,dict) else {}
    if (not isinstance(task,dict) or not isinstance(task.get('id'),str) or not task['id']
            or str(task.get('status','')).lower()!='leased'
            or not isinstance(task.get('lease_id'),str) or not task['lease_id']
            or type(task.get('fencing_token')) is not int or task['fencing_token']<1
            or (task.get('assigned_knight') or meta.get('assigned_knight'))!=worker
            or meta.get('execution_target')!='remote' or meta.get('capability','compute')!='compute'
            or meta.get('tool') not in TOOLS):
        raise ValueError('Expected a bounded native analysis task with an exact lease')
    params=meta.get('tool_parameters',{'text':task.get('prompt')})
    if not isinstance(params,dict) or set(params)!={'text'} or not isinstance(params['text'],str) or len(params['text'].encode())>2_000_000:
        raise ValueError('Only bounded literal text is accepted')


class PeerAnalysis:
    def __init__(self, database, registry, identity, permitted, exchange, publisher):
        self.db,self.registry,self.identity,self.permitted=database,registry,identity,permitted
        self.exchange,self.publish=exchange,publisher
        self.lock=asyncio.Lock()
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS peer_analysis_receipts(key TEXT PRIMARY KEY, digest TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at REAL NOT NULL)');conn.commit()

    def allowed(self, peer_id):
        node=self.registry.get_node(peer_id)
        if not self.permitted() or not node or node.node_state not in {'APPROVED','CONNECTED'}:
            return False
        deadline=(node.connection_metadata or {}).get('membership_expires_at')
        return ('compute' in node.granted_capabilities and node.health=='healthy'
                and 0<=time.time()-node.last_heartbeat<=45 and (deadline is None or deadline>time.time()))

    async def tick(self, peer_id):
        if self.lock.locked() or not self.allowed(peer_id):return {'status':'held'}
        from backend.cluster.local_load import local_load_metrics
        from backend.cluster.power_policy import power_budget
        load=await asyncio.to_thread(local_load_metrics)
        if (any(type(load.get(k)) not in (int,float) or not 0<=load[k]<85 for k in ('cpu_percent','memory_percent'))
                or not power_budget(load.get('power'),10)['allowed']):return {'status':'capacity_held'}
        async with self.lock:
            transport=RPCSecureTransport(self.identity)
            async def send(kind,payload):
                return await self.exchange(peer_id,transport.create_signed_message(peer_id,kind,payload))
            if not self.allowed(peer_id):return {'status':'held'}
            reply=await send('task_poll',{'node_id':self.identity.node_id,'supported_tools':sorted(TOOLS),'require_running':True})
            tasks=reply.get('tasks')
            if reply.get('status')!='ok' or not isinstance(tasks,list) or len(tasks)>1:
                raise ValueError('Invalid peer analysis poll response')
            if not tasks:return {'status':'idle'}
            task=tasks[0];validate(task,self.identity.node_id)
            if not self.allowed(peer_id):return {'status':'held'}
            key=hashlib.sha256(json.dumps([peer_id,task['id'],task['lease_id'],task['fencing_token']]).encode()).hexdigest()
            digest=hashlib.sha256(json.dumps(task,sort_keys=True).encode()).hexdigest()
            with self.db.get_connection() as conn:
                prior=conn.execute('SELECT digest,payload_json FROM peer_analysis_receipts WHERE key=?',(key,)).fetchone()
            if prior:
                if prior[0]!=digest:raise ValueError('Leased task changed after execution')
                payload=json.loads(prior[1])
            else:
                from backend.runtime.execution import execute_request,verify_request_result
                try:
                    output=await asyncio.to_thread(execute_request,task,['compute'])
                    if verify_request_result(task,output,allow_local_model=False).get('state')!='VERIFIED':
                        raise ValueError('Local analysis verification failed')
                    payload={'status':'completed','output':output}
                except Exception:
                    payload={'status':'failed','error':'Native analysis did not pass local verification'}
                payload.update(task_id=task['id'],executed_by=self.identity.node_id,
                               lease_id=task['lease_id'],fencing_token=task['fencing_token'])
                with self.db.get_connection() as conn:
                    conn.execute('INSERT INTO peer_analysis_receipts VALUES(?,?,?,?)',(key,digest,json.dumps(payload),time.time()))
                    # Retain at most 1000 recent pure-analysis receipts.
                    conn.execute('DELETE FROM peer_analysis_receipts WHERE key NOT IN (SELECT key FROM peer_analysis_receipts ORDER BY updated_at DESC LIMIT 1000)');conn.commit()
            result=await send('task_result',payload)
            completed=result.get('completed',{})
            verified=(completed.get('result') or {}).get('verification',{}).get('state')=='VERIFIED'
            if payload['status']=='completed' and (completed.get('id')!=task['id'] or not verified
                    or str(completed.get('status','')).lower()!='completed'
                    or (completed.get('result') or {}).get('executed_by')!=self.identity.node_id):
                raise ValueError('Controller did not independently verify the result')
            state='verified' if payload['status']=='completed' else 'failed'
            self.publish('cluster.native_analysis_'+state,{'task_id':task['id'],'controller_id':peer_id,'worker_id':self.identity.node_id})
            return {'status':state,'task_id':task['id']}
