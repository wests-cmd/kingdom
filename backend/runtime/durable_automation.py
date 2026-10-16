"""Persistent interval schedules for bounded, transactional local operations.

Local notes commit atomically. Work schedules use a durable outbox and the
request bridge's stable idempotency key; enqueueing never executes the request.
No timer is installed here: the application invokes tick from its lifecycle.
"""
import json
import math
import time
import uuid
from backend.memory.portable_vault import clean_text, identifier


class DurableAutomations:
    def __init__(self, database, publish=None, clock=time.time, enqueue_request=None, cancel_request=None):
        self.db, self.publish, self.clock = database, publish or (lambda *args: None), clock
        self.enqueue_request, self.cancel_request = enqueue_request, cancel_request
        with self.db.get_connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS durable_schedules (
                id TEXT PRIMARY KEY,project TEXT NOT NULL,operation TEXT NOT NULL,payload TEXT NOT NULL,
                interval_sec INTEGER NOT NULL,next_due REAL NOT NULL,status TEXT NOT NULL,
                revision INTEGER NOT NULL,checkpoint TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS durable_schedule_runs (
                run_key TEXT PRIMARY KEY,schedule_id TEXT NOT NULL,due REAL NOT NULL,
                status TEXT NOT NULL,receipt TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS durable_schedule_notes (
                run_key TEXT PRIMARY KEY,project TEXT NOT NULL,body TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS durable_schedule_outbox (
                run_key TEXT PRIMARY KEY,schedule_id TEXT NOT NULL,request_json TEXT NOT NULL,
                status TEXT NOT NULL,attempts INTEGER NOT NULL,request_id TEXT)''')
            conn.commit()

    def create_work(self, project, prompt, interval_sec, model_profile='auto', mode='agent',
                    session_scope=None, allow_process=False, enabled=False, start_at=None,
                    review_instructions='Review execution evidence and tests before continuing.'):
        """Owner-created bounded request intent. Paused until explicitly enabled.

        RequestBridge currently runs two agent turns / 300 seconds per approved
        invocation. This scheduler never invokes run or changes tool permissions.
        """
        identifier(project)
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 20000:
            raise ValueError('Prompt exceeds limit')
        if mode not in {'auto', 'quick', 'agent'} or not isinstance(model_profile, str) or not 1 <= len(model_profile) <= 100:
            raise ValueError('Invalid request mode or model profile')
        session_scope = session_scope or 'automation-'+project
        if not isinstance(session_scope, str) or not 1 <= len(session_scope) <= 100 or len(review_instructions) > 2000:
            raise ValueError('Invalid session scope or review instructions')
        if not isinstance(allow_process, bool) or not isinstance(enabled, bool):
            raise ValueError('Owner grants must be explicit booleans')
        if isinstance(interval_sec, bool) or not isinstance(interval_sec, int) or not 60 <= interval_sec <= 2592000:
            raise ValueError('Interval must be 60 seconds to 30 days')
        start_at = self.clock() if start_at is None else start_at
        if isinstance(start_at, bool) or not isinstance(start_at, (int, float)) or not math.isfinite(start_at) or start_at < 0:
            raise ValueError('Invalid start time')
        ident = uuid.uuid4().hex
        payload = {'prompt': prompt, 'mode': mode, 'model_profile': model_profile,
                   'session_scope': session_scope, 'project_scope': 'projects/'+project,
                   'allow_process': allow_process, 'review_instructions': review_instructions,
                   'run_budget': {'max_turns': 2, 'max_seconds': 300}, 'autorun': False}
        with self.db.get_connection() as conn:
            conn.execute('INSERT INTO durable_schedules VALUES(?,?,?,?,?,?,?,?,?)',
                         (ident, project, 'enqueue_request', json.dumps(payload), interval_sec, start_at, 'active' if enabled else 'paused', 1, '{}'))
            conn.commit()
        self.publish('automation.work_schedule_created', {'id': ident, 'project': project, 'enabled': enabled})
        return self.get(project, ident)

    def create(self, project, body, interval_sec, start_at=None):
        identifier(project)
        if not isinstance(body, str) or not 1 <= len(body) <= 8000:
            raise ValueError('Note must contain 1 to 8000 characters')
        if isinstance(interval_sec, bool) or not isinstance(interval_sec, int) or not 60 <= interval_sec <= 2592000:
            raise ValueError('Interval must be 60 seconds to 30 days')
        start_at = self.clock() if start_at is None else start_at
        if isinstance(start_at, bool) or not isinstance(start_at, (int, float)) or not math.isfinite(start_at) or start_at < 0:
            raise ValueError('Invalid start time')
        ident = uuid.uuid4().hex
        with self.db.get_connection() as conn:
            conn.execute('INSERT INTO durable_schedules VALUES(?,?,?,?,?,?,?,?,?)',
                         (ident, project, 'record_note', json.dumps({'body': clean_text(body)}), interval_sec, start_at, 'active', 1, '{}'))
            conn.commit()
        self.publish('automation.schedule_created', {'id': ident, 'project': project})
        return self.get(project, ident)

    @staticmethod
    def _record(row):
        record = {'id': row['id'], 'project': row['project'], 'operation': row['operation'],
                'interval_sec': row['interval_sec'], 'next_due': row['next_due'],
                'status': row['status'], 'revision': row['revision'], 'checkpoint': json.loads(row['checkpoint'])}
        if row['operation'] == 'enqueue_request':
            payload = json.loads(row['payload'])
            record.update({key: payload.get(key) for key in ('model_profile','mode','project_scope','session_scope','allow_process','review_instructions','run_budget','autorun')})
        return record

    def get(self, project, ident):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT * FROM durable_schedules WHERE project=? AND id=?', (identifier(project), identifier(ident))).fetchone()
        if not row:
            raise KeyError(ident)
        return self._record(row)

    def list(self, project):
        with self.db.get_connection() as conn:
            return [self._record(row) for row in conn.execute('SELECT * FROM durable_schedules WHERE project=? ORDER BY next_due,id', (identifier(project),))]

    def change_status(self, project, ident, status, expected_revision):
        if status not in {'active', 'paused', 'cancelled'}:
            raise ValueError('Invalid status')
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM durable_schedules WHERE project=? AND id=?', (identifier(project), identifier(ident))).fetchone()
            if not row:
                raise KeyError(ident)
            if row['revision'] != expected_revision:
                raise ValueError('Schedule changed; reload before updating')
            if row['status'] == 'cancelled':
                raise ValueError('Cancelled schedules cannot restart; create a new schedule')
            conn.execute('UPDATE durable_schedules SET status=?,revision=revision+1 WHERE id=?', (status, ident))
            conn.commit()
        self.publish('automation.schedule_status', {'id': ident, 'project': project, 'status': status})
        return self.get(project, ident)

    def tick(self, limit=20):
        """Coalesce missed intervals to one due run; transactions fence all workers."""
        now = self.clock()
        completed = []
        paused = []
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            rows = conn.execute("SELECT * FROM durable_schedules WHERE status='active' AND next_due<=? ORDER BY next_due,id LIMIT ?", (now, min(max(int(limit), 1), 100))).fetchall()
            for row in rows:
                due = row['next_due']
                run_key = f"{row['id']}:{due:.6f}"
                old = conn.execute('SELECT status FROM durable_schedule_runs WHERE run_key=?', (run_key,)).fetchone()
                if old:
                    # An inconsistent imported DB is held for explicit investigation.
                    conn.execute("UPDATE durable_schedules SET status='paused',revision=revision+1 WHERE id=?", (row['id'],))
                    paused.append(row['id'])
                    continue
                if row['operation'] not in {'record_note', 'enqueue_request'}:
                    conn.execute("UPDATE durable_schedules SET status='paused',revision=revision+1 WHERE id=?", (row['id'],))
                    paused.append(row['id'])
                    continue
                payload = json.loads(row['payload'])
                if row['operation'] == 'record_note':
                    conn.execute('INSERT INTO durable_schedule_notes VALUES(?,?,?)', (run_key, row['project'], payload['body']))
                    receipt = {'run_key': run_key, 'operation': 'record_note', 'project': row['project'], 'completed_at': now, 'effect': 'sqlite_note'}
                    status = 'completed'
                    completed.append(receipt)
                else:
                    request = {key: payload[key] for key in ('mode','model_profile','session_scope','project_scope','allow_process')}
                    request['prompt'] = payload['prompt']+'\n\nReview requirements: '+payload['review_instructions']
                    request['idempotency_key'] = 'schedule:'+run_key
                    conn.execute('INSERT INTO durable_schedule_outbox VALUES(?,?,?,?,?,?)', (run_key, row['id'], json.dumps(request), 'pending', 0, None))
                    receipt = {'run_key': run_key, 'operation': 'enqueue_request', 'project': row['project'], 'status': 'pending_delivery', 'autorun': False}
                    status = 'pending_delivery'
                conn.execute('INSERT INTO durable_schedule_runs VALUES(?,?,?,?,?)', (run_key, row['id'], due, status, json.dumps(receipt)))
                next_due = due + (math.floor((now-due)/row['interval_sec'])+1)*row['interval_sec']
                conn.execute('UPDATE durable_schedules SET next_due=?,checkpoint=?,revision=revision+1 WHERE id=?',
                             (next_due, json.dumps(receipt), row['id']))
            conn.commit()
        for receipt in completed:
            self.publish('automation.schedule_completed', receipt)
        for ident in paused:
            self.publish('automation.schedule_status', {'id': ident, 'status': 'paused', 'reason': 'inconsistent_or_unsupported_state'})
        return completed

    def deliver(self, limit=20):
        """Replay only idempotent create calls outside the scheduling transaction.

        Concurrent deliveries can race on create; the bridge's unique scoped key
        produces one request. Interrupted delivery reuses the exact saved body.
        Pause/cancel before delivery suppresses it. A cancellation during create
        cancels the still-unexecuted request through the supplied bridge callback.
        """
        if self.enqueue_request is None:
            return []
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT o.* FROM durable_schedule_outbox o JOIN durable_schedules s ON s.id=o.schedule_id WHERE o.status IN ('pending','delivering') AND s.status='active' ORDER BY o.rowid LIMIT ?", (min(max(int(limit), 1), 100),)).fetchall()
        delivered = []
        for row in rows:
            with self.db.get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                current = conn.execute('SELECT o.status,s.status FROM durable_schedule_outbox o JOIN durable_schedules s ON s.id=o.schedule_id WHERE o.run_key=?', (row['run_key'],)).fetchone()
                if not current or current[0] not in {'pending','delivering'} or current[1] != 'active':
                    continue
                conn.execute("UPDATE durable_schedule_outbox SET status='delivering',attempts=attempts+1 WHERE run_key=?", (row['run_key'],))
                conn.commit()
            try:
                request = self.enqueue_request(json.loads(row['request_json']))
                request_id = request['id']
            except Exception:
                # Creation may have committed before failure; same key is safe to replay.
                with self.db.get_connection() as conn:
                    conn.execute("UPDATE durable_schedule_outbox SET status='pending' WHERE run_key=? AND status='delivering'", (row['run_key'],))
                    conn.execute("UPDATE durable_schedules SET status='paused',revision=revision+1 WHERE id=? AND (SELECT attempts FROM durable_schedule_outbox WHERE run_key=?)>=5", (row['schedule_id'], row['run_key']))
                    conn.commit()
                self.publish('automation.delivery_failed', {'run_key': row['run_key'], 'reason': 'Request bridge unavailable; checkpoint retained'})
                continue
            with self.db.get_connection() as conn:
                state = conn.execute('SELECT project,status FROM durable_schedules WHERE id=?', (row['schedule_id'],)).fetchone()
            if state['status'] != 'active':
                if self.cancel_request is None:
                    # Do not declare cancellation delivered without a bridge receipt.
                    self.publish('automation.delivery_needs_recovery', {'run_key': row['run_key'], 'request_id': request_id})
                    continue
                self.cancel_request(request_id)
                delivery_status = 'cancelled'
            else:
                delivery_status = 'enqueued'
            receipt = {'run_key': row['run_key'], 'operation': 'enqueue_request', 'project': state['project'],
                       'request_id': request_id, 'status': delivery_status, 'autorun': False, 'delivered_at': self.clock()}
            with self.db.get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute('UPDATE durable_schedule_outbox SET status=?,request_id=? WHERE run_key=?', (delivery_status, request_id, row['run_key']))
                conn.execute('UPDATE durable_schedule_runs SET status=?,receipt=? WHERE run_key=?', (delivery_status, json.dumps(receipt), row['run_key']))
                conn.execute('UPDATE durable_schedules SET checkpoint=?,revision=revision+1 WHERE id=?', (json.dumps(receipt), row['schedule_id']))
                conn.commit()
            delivered.append(receipt)
            self.publish('automation.request_enqueued', receipt)
        return delivered

    def receipts(self, project, ident):
        self.get(project, ident)
        with self.db.get_connection() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT receipt FROM durable_schedule_runs WHERE schedule_id=? ORDER BY due DESC LIMIT 100', (ident,))]
