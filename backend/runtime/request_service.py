"""Durable request identities shared by authenticated front doors."""
import json
import asyncio
import time
import re
from datetime import datetime
from uuid import uuid4
from backend.events.event_bus import event_bus


class RequestService:
    def __init__(self, database, engine, models, agents):
        self.db, self.engine, self.models, self.agents = database, engine, models, agents
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS conversation_requests(id TEXT PRIMARY KEY, session_scope TEXT NOT NULL, project_scope TEXT NOT NULL, idem TEXT NOT NULL, state_json TEXT NOT NULL, UNIQUE(session_scope,project_scope,idem))')
            conn.commit()

    def _event(self, state):
        event_bus.publish('request.updated', {'id':state['id'],'status':state['status']})

    def create(self, body):
        state = {**body, 'id':uuid4().hex,'status':'queued','answer':'','evidence':[], 'created_at':time.time(),'updated_at':time.time(), 'agent_session_id':None}
        text = body['prompt'].strip().lower().rstrip('?.!')
        route = body['mode']
        if route == 'auto':
            if text in {'what time is it','time','what is the current time'}: route='time'
            elif text in {'status','system status','what is the status'}: route='status'
            elif text in {'priorities','what are my priorities','what needs doing'}: route='priorities'
            elif re.match(r'^(?:please\s+)?(?:inspect|implement|edit|modify|fix|refactor|build|run tests|test the|create a file|write a file)\b', text): route='agent'
            else: route='quick'
        state['route']=route
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            old=conn.execute('SELECT state_json FROM conversation_requests WHERE session_scope=? AND project_scope=? AND idem=?',(body['session_scope'],body['project_scope'],body['idempotency_key'])).fetchone()
            if old:
                existing=json.loads(old[0])
                if any(existing.get(key)!=value for key,value in body.items()): raise ValueError('Idempotency key already belongs to another request')
                return existing
            conn.execute('INSERT INTO conversation_requests VALUES(?,?,?,?,?)',(state['id'],body['session_scope'],body['project_scope'],body['idempotency_key'],json.dumps(state)))
            conn.commit()
        self._event(state)
        return state

    def get(self, ident):
        with self.db.get_connection() as conn:
            row=conn.execute('SELECT state_json FROM conversation_requests WHERE id=?',(ident,)).fetchone()
        if not row: raise KeyError(ident)
        return json.loads(row[0])

    def list(self, session_scope, project_scope):
        with self.db.get_connection() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT state_json FROM conversation_requests WHERE session_scope=? AND project_scope=? ORDER BY rowid DESC LIMIT 100',(session_scope,project_scope))]

    def update(self, ident, change, expected=None):
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT state_json FROM conversation_requests WHERE id=?',(ident,)).fetchone()
            if not row: raise KeyError(ident)
            state=json.loads(row[0])
            if expected is not None and state['status'] not in expected: return None
            state.update(change,updated_at=time.time())
            conn.execute('UPDATE conversation_requests SET state_json=? WHERE id=?',(json.dumps(state),ident))
            conn.commit()
        self._event(state)
        return state

    async def run(self, ident):
        saved=await asyncio.to_thread(self.get,ident)
        if saved['status'] in {'completed','cancelled','failed','running'}: return saved
        state=await asyncio.to_thread(self.update,ident,{'status':'running'},expected={'queued','waiting_review','ready'})
        if state is None:return await asyncio.to_thread(self.get,ident)
        try:
            route=state['route']
            evidence=[]
            if route=='time':
                answer=datetime.now().astimezone().strftime('%I:%M %p %Z on %B %d, %Y')
                evidence=[{'type':'controller_clock','observed_at':time.time()}]
            elif route=='status':
                status=await asyncio.to_thread(self.engine.status)
                answer='Runtime: '+('running' if status.get('running') else 'stopped')+'. Mode: '+str(status.get('mode','not reported'))+'.'
                evidence=[{'type':'runtime_status','snapshot':status}]
            elif route=='priorities':
                tasks=[task for task in await asyncio.to_thread(self.engine.tasks.list) if task.get('metadata',{}).get('project_scope')==state['project_scope'] and task['status'].lower() not in {'completed','succeeded','cancelled'}]
                answer='\n'.join(f"{task['status']}: {task['prompt'][:160]}" for task in tasks[:20]) or 'No unfinished tasks recorded for this project scope.'
                evidence=[{'type':'project_tasks','task_ids':[task['id'] for task in tasks[:20]]}]
            elif route=='agent':
                if not state['agent_session_id']:
                    agent=await asyncio.to_thread(self.agents.create,state['prompt'],state['model_profile'],workspace=state['project_scope'],allow_process=state['allow_process'],use_owner_memory=False)
                    state=await asyncio.to_thread(self.update,ident,{'agent_session_id':agent['id']},expected={'running'})
                    if state is None:
                        await asyncio.to_thread(self.agents.cancel,agent['id'])
                        return await asyncio.to_thread(self.get,ident)
                agent=await self.agents.run(state['agent_session_id'],2,300)
                answer=next((message.get('content','') for message in reversed(agent['messages']) if message['role']=='assistant' and message.get('content')), 'Agent work saved; inspect progress and pending approvals.')
                evidence=[{'type':'agent_session','id':agent['id'],'status':agent['status'],'pending':agent.get('pending',[]),'turns':agent['turns'],'messages':agent['messages']}]
                status='completed' if agent['status']=='completed' else 'waiting_review'
                return await asyncio.to_thread(self.update,ident,{'status':status,'answer':answer,'evidence':evidence},expected={'running'}) or await asyncio.to_thread(self.get,ident)
            else:
                payload=await self.models.chat(state['model_profile'],{'messages':[{'role':'user','content':state['prompt']}], 'stream':False})
                answer=payload['choices'][0]['message'].get('content') or 'The model returned no text.'
                evidence=[{'type':'model_response','profile':payload.get('kingdom_profile',state['model_profile']),'model':payload.get('model'),'usage':payload.get('usage',{}),'verified_execution':False}]
            return await asyncio.to_thread(self.update,ident,{'status':'completed','answer':answer,'evidence':evidence},expected={'running'}) or await asyncio.to_thread(self.get,ident)
        except Exception as error:
            await asyncio.to_thread(self.update,ident,{'status':'failed','answer':'Request failed; no automatic model substitution or replay occurred.','error':str(error)[:500]},expected={'running'})
            raise

    def cancel(self, ident):
        state=self.update(ident,{'status':'cancelled'},expected={'queued','running','waiting_review','ready'})
        if state and state.get('agent_session_id'):self.agents.cancel(state['agent_session_id'])
        return state or self.get(ident)
