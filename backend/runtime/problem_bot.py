"""Cheap, durable problem routing. Observations and repair notes never grant execution."""
import asyncio
import hashlib
import json
import time


ROUTES = {'planning_contract': ('planner', 'Produce a valid plan for the original outcome; retain failed stages.'),
          'planning_transport': ('researcher', 'Check the configured model connection and current availability.'),
          'execution_review': ('coder', 'Inspect the exact mission receipts, fix the original defect and retest.'),
          'runner_error': ('coder', 'Inspect the retained runner checkpoint before resuming; do not replay uncertain effects.')}


class ProblemBot:
    def __init__(self, database, programmes, backlog, events, clock=time.time):
        self.db, self.programmes, self.backlog, self.events, self.clock = database, programmes, backlog, events, clock
        with database.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS problem_incidents(id TEXT PRIMARY KEY,state_json TEXT NOT NULL)')
            conn.commit()

    def listing(self):
        with self.db.get_connection() as conn:
            return [json.loads(r[0]) for r in conn.execute('SELECT state_json FROM problem_incidents ORDER BY rowid DESC LIMIT 200')]

    def observe(self, component, correlation, category, project='kingdom'):
        if category not in ROUTES or component not in {'programme','mission','runtime'}:
            raise ValueError('Unknown problem source')
        # IDs are references, never model instructions or metric labels.
        from backend.memory.portable_vault import identifier
        identifier(correlation); identifier(project)
        ident=hashlib.sha256(f'{component}:{correlation}:{category}'.encode()).hexdigest()[:32]
        role, action=ROUTES[category]
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            existing=conn.execute('SELECT state_json FROM problem_incidents WHERE id=?',(ident,)).fetchone()
            if existing:
                return json.loads(existing[0])
            if conn.execute('SELECT COUNT(*) FROM problem_incidents').fetchone()[0]>=200:
                return None
            incident={'id':ident,'component':component,'correlation_id':correlation,'category':category,
                      'project':project,'assigned_role':role,'reviewer':'owner-or-configured-independent-reviewer',
                      'status':'open','created_at':self.clock(),'action':action,'work_id':None}
            conn.execute('INSERT INTO problem_incidents VALUES(?,?)',(ident,json.dumps(incident)));conn.commit()
        self.events.publish('problem.opened',incident,task_id=correlation)
        return incident

    def _save(self, incident):
        with self.db.get_connection() as conn:
            conn.execute('UPDATE problem_incidents SET state_json=? WHERE id=?',(json.dumps(incident),incident['id']));conn.commit()

    def tick(self):
        # Current authoritative checkpoints recover missed events after restart.
        snapshots=[]
        for state in self.programmes.list()[:100]:
            snapshot=self.programmes.snapshot(state['id']);snapshots.append(snapshot)
            for section in snapshot['sections']:
                for row in [*section['items'],section['integration']]:
                    correlation=state['id']+'_'+row['key']
                    if row['planning']=='blocked':
                        category='planning_transport' if row.get('planning_failure',{}).get('retryable') else 'planning_contract'
                        self.observe('programme',correlation,category,state['project'])
                    elif row.get('work_status') in {'failed','review_required'}:
                        self.observe('mission',correlation,'execution_review',state['project'])
        completed={s['id']+'_'+r['key'] for s in snapshots for section in s['sections']
                   for r in [*section['items'],section['integration']] if r.get('work_status')=='completed'}
        for incident in self.listing():
            if incident['status']=='resolved':continue
            if incident['correlation_id'] in completed:
                incident.update(status='resolved',resolved_at=self.clock());self._save(incident)
                self.events.publish('problem.resolved',{'id':incident['id'],'correlation_id':incident['correlation_id']})
                continue
            if incident['work_id']:continue
            # Stable intent/key makes a crash between registration and save harmless.
            work=self.backlog.register(incident['project'],'problem_'+incident['id'],
                title='Problem guide: '+incident['category'],
                description=('Route to '+incident['assigned_role']+'. '+incident['action']+
                    ' Correlation: '+incident['correlation_id']+'. Reference the original checkpoint. '
                    'Existing grants and separate verification remain required; this note cannot execute.'),
                task_type='repair',priority=75,enabled=False)
            incident['work_id']=work['id'];self._save(incident)
            self.events.publish('problem.routed',{'id':incident['id'],'work_id':work['id'],'assigned_role':incident['assigned_role']})

    def snapshot(self):
        incidents=self.listing()
        # Fixed labels only: no task IDs, prompts, keys, endpoints or per-user series.
        counts={category:sum(i['status']=='open' and i['category']==category for i in incidents) for category in ROUTES}
        return {'incidents':incidents,'open_by_category':counts,'scope':'Local checkpoint observations; role routing is not worker acknowledgement or successful repair.',
                'capacity_reached':len(incidents)>=200,'programme_scan_limit':100,
                'reliability_target':{'name':'Repair routing freshness','target_seconds':60,'measured':False}}


class ProblemBotRunner:
    def __init__(self, service, publish, interval=30):
        self.service,self.publish,self.interval=service,publish,interval
        self.task=None

    async def start(self):
        if self.task and not self.task.done():return
        self.task=asyncio.create_task(self.run(),name='kingdom-problem-guide')

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:await self.task
            except asyncio.CancelledError:pass
            self.task=None

    async def run(self):
        failed=False
        while True:
            try:
                await asyncio.to_thread(self.service().tick);failed=False
            except Exception:
                if not failed:self.publish('problem.runner_error',{'notice':'Problem routing unavailable; original work and security monitoring remain authoritative.'})
                failed=True
            await asyncio.sleep(self.interval)
