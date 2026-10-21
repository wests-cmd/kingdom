"""Owner-reviewed work queue over existing missions and actual acceptance receipts.

The queue selects work; it grants nothing and never invents an executor. An
interrupted claim is retained until stopped-worker reconciliation, not expired.
"""
import hashlib
import json
import time
import uuid
import threading
import os
import socket
import psutil

from backend.memory.portable_vault import identifier, clean_text

_advancement_guard = threading.RLock()


class WorkBacklog:
    def __init__(self, database, engine, clock=time.time):
        self.db, self.engine, self.clock = database, engine, clock
        with self.db.get_connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS work_backlog (
                id TEXT PRIMARY KEY, project TEXT NOT NULL, idem TEXT NOT NULL,
                state_json TEXT NOT NULL, UNIQUE(project,idem))''')
            conn.execute('''CREATE TABLE IF NOT EXISTS work_backlog_findings (
                id TEXT PRIMARY KEY, work_id TEXT NOT NULL, finding_json TEXT NOT NULL)''')
            conn.execute('CREATE TABLE IF NOT EXISTS work_backlog_settings(id INTEGER PRIMARY KEY,enabled INTEGER,revision INTEGER)')
            conn.execute('INSERT OR IGNORE INTO work_backlog_settings VALUES(1,0,1)')
            conn.commit()

    def _publish(self, state):
        self.engine.events.publish('backlog.updated', {'id': state['id'], 'project': state['project'],
                                                     'status': state['status'], 'reason': state['reason']})

    @staticmethod
    def _save(conn, state):
        state['revision'] += 1
        conn.execute('UPDATE work_backlog SET state_json=? WHERE id=?', (json.dumps(state), state['id']))

    def get(self, project, ident):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT state_json FROM work_backlog WHERE project=? AND id=?',
                               (identifier(project), identifier(ident))).fetchone()
        if not row:
            raise KeyError(ident)
        return json.loads(row[0])

    def list(self, project=None):
        with self.db.get_connection() as conn:
            rows = conn.execute('SELECT state_json FROM work_backlog ORDER BY rowid') if project is None else conn.execute(
                'SELECT state_json FROM work_backlog WHERE project=? ORDER BY rowid', (identifier(project),))
            return [json.loads(row[0]) for row in rows]

    def register(self, project, idempotency_key, mission_id=None, mission_version=None, acceptance_step=None,
                 depends_on=None, enabled=False, title='Reviewed work', description='', priority=50):
        identifier(project); identifier(idempotency_key)
        if type(enabled) is not bool or type(priority) is not int or not 0 <= priority <= 100 or not isinstance(title, str) or not 1 <= len(title) <= 200 or not isinstance(description, str) or len(description) > 12000:
            raise ValueError('Choose an exact mission version and explicit enabled setting')
        depends_on = depends_on or []
        if not isinstance(depends_on, list) or len(depends_on) > 30:
            raise ValueError('At most 30 existing dependencies')
        depends_on = sorted(set(identifier(item) for item in depends_on))
        if mission_id:
            identifier(mission_id); identifier(acceptance_step)
            if type(mission_version) is not int or mission_version < 1:
                raise ValueError('Exact mission version required')
            self._reviewed(self.engine.missions.get(mission_id), mission_version, acceptance_step)
        elif mission_version is not None or acceptance_step is not None or enabled:
            raise ValueError('Unplanned notes cannot execute or carry partial mission bindings')
        intent = {'mission_id': mission_id, 'mission_version': mission_version,
                  'acceptance_step': acceptance_step, 'depends_on': depends_on,
                  'title': title, 'description': description, 'priority': priority}
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            previous = conn.execute('SELECT state_json FROM work_backlog WHERE project=? AND idem=?',
                                    (project, idempotency_key)).fetchone()
            if previous:
                saved = json.loads(previous[0])
                if saved['intent'] != intent:
                    raise ValueError('Idempotency key belongs to different work')
                return saved
            duplicate = conn.execute('SELECT state_json FROM work_backlog').fetchall()
            if mission_id and any(json.loads(row[0])['intent']['mission_id'] == mission_id for row in duplicate):
                raise ValueError('Mission is already tracked; reuse its work item')
            for ident in depends_on:
                if not conn.execute('SELECT 1 FROM work_backlog WHERE project=? AND id=?', (project, ident)).fetchone():
                    raise ValueError('Dependencies must already exist in this project')
            state = {'id': uuid.uuid4().hex, 'project': project, 'intent': intent, 'enabled': enabled,
                     'title': title, 'description': description, 'priority': priority,
                     'revision': 1, 'status': ('ready' if enabled else 'paused') if mission_id else 'needs_planning', 'lease': None,
                     'created_at': self.clock(), 'evidence': None,
                     'reason': ('Awaiting eligible scheduler tick' if enabled else 'Owner has not enabled this work') if mission_id else 'Owner backlog note has no reviewed executable mission',
                     'next_step': 'Review an executable mission and its fixed acceptance before enabling'}
            conn.execute('INSERT INTO work_backlog VALUES(?,?,?,?)',
                         (state['id'], project, idempotency_key, json.dumps(state)))
            conn.commit()
        self._publish(state)
        return state

    @staticmethod
    def _reviewed(mission, version, acceptance_step):
        if (type(version) is not int or mission['version'] != version or mission.get('approved_version') != version
                or mission['plan'].get('missing_requirements')
                or mission['status'] not in {'approved', 'running', 'completed'}):
            raise ValueError('Exact executable owner-reviewed mission required')
        step = next((step for step in mission['plan']['steps'] if step['id'] == acceptance_step), None)
        if not step or step['kind'] != 'function_check':
            raise ValueError('Select the reviewed native function acceptance step')

    def configure(self, project, ident, enabled, expected_revision):
        if type(enabled) is not bool:
            raise ValueError('Explicit enabled setting required')
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT state_json FROM work_backlog WHERE project=? AND id=?', (project, ident)).fetchone()
            if not row:
                raise KeyError(ident)
            state = json.loads(row[0])
            if state['revision'] != expected_revision or state['lease'] or state['status'] in {'completed', 'failed', 'review_required', 'needs_planning'}:
                raise ValueError('Reload or reconcile this retained checkpoint first')
            state.update(enabled=enabled, status='ready' if enabled else 'paused',
                         reason='Awaiting eligible scheduler tick' if enabled else 'Paused by owner')
            self._save(conn, state); conn.commit()
        self._publish(state)
        return state

    def attach(self, project, ident, mission_id, mission_version, acceptance_step, expected_revision):
        identifier(mission_id); identifier(acceptance_step)
        self._reviewed(self.engine.missions.get(mission_id), mission_version, acceptance_step)
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT state_json FROM work_backlog WHERE project=? AND id=?', (project, ident)).fetchone()
            if not row:
                raise KeyError(ident)
            state = json.loads(row[0])
            if state['revision'] != expected_revision or state['lease'] or state['status'] != 'needs_planning':
                raise ValueError('Only an unchanged unplanned owner note can attach a mission')
            if any(json.loads(row[0])['intent']['mission_id'] == mission_id for row in conn.execute('SELECT state_json FROM work_backlog')):
                raise ValueError('Mission is already tracked')
            state['intent'].update(mission_id=mission_id, mission_version=mission_version, acceptance_step=acceptance_step)
            state.update(status='paused', reason='Reviewed mission attached; explicit enable required')
            self._save(conn, state); conn.commit()
        self._publish(state)
        return state

    def _finding(self, state, mission, reason):
        # Derived observations are suggestions for review, never executable plans.
        facts = {'mission_id': state['intent']['mission_id'], 'mission_version': mission.get('version'),
                 'mission_status': mission.get('status'), 'missing_requirements': mission.get('plan', {}).get('missing_requirements', []),
                 'repair_attempts': len(mission.get('repair_history', [])),
                 'failure': clean_text(mission.get('failure', ''))[:2000],
                 'retained_task_ids': sorted(record['task_id'] for record in mission.get('steps', {}).values() if record.get('task_id')),
                 'reason': reason}
        ident = hashlib.sha256(json.dumps({'work_id': state['id'], **facts}, sort_keys=True).encode()).hexdigest()
        finding = {'id': ident, 'work_id': state['id'], 'provenance': facts,
                   'status': 'proposed_for_review', 'next_step': 'Inspect retained task evidence, resolve requirements and review a new mission; no new privileges were granted'}
        with self.db.get_connection() as conn:
            inserted = conn.execute('INSERT OR IGNORE INTO work_backlog_findings VALUES(?,?,?)', (ident, state['id'], json.dumps(finding))).rowcount
            conn.commit()
        if inserted:
            self.engine.events.publish('backlog.finding_proposed', {'id': ident, 'work_id': state['id'], 'status': 'proposed_for_review'})
        return finding

    def findings(self, project=None):
        with self.db.get_connection() as conn:
            rows = conn.execute('SELECT finding_json FROM work_backlog_findings ORDER BY rowid') if project is None else conn.execute('''SELECT f.finding_json FROM work_backlog_findings f
                JOIN work_backlog w ON w.id=f.work_id WHERE w.project=? ORDER BY f.rowid''', (identifier(project),))
            return [json.loads(row[0]) for row in rows]

    def snapshot(self):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT enabled,revision FROM work_backlog_settings WHERE id=1').fetchone()
        items = self.list()
        by_id = {item['id']: item for item in items}
        for item in items:
            pending = [ident for ident in item['intent']['depends_on'] if by_id[ident]['status'] != 'completed']
            if pending and item['status'] in {'ready', 'running'}:
                item.update(reason='Dependencies lack current accepted evidence: ' + ', '.join(pending),
                            next_step='Complete or review the prerequisite work; no dependent work was dispatched')
        return {'items': items, 'findings': self.findings(), 'enabled': bool(row[0]), 'revision': row[1]}

    def settings(self, enabled, expected_revision):
        if type(enabled) is not bool:
            raise ValueError('Explicit enabled setting required')
        with self.db.get_connection() as conn:
            changed = conn.execute('UPDATE work_backlog_settings SET enabled=?,revision=revision+1 WHERE id=1 AND revision=?', (int(enabled), expected_revision)).rowcount
            if changed != 1:
                raise ValueError('Settings changed; reload')
            conn.commit()
        self.engine.events.publish('backlog.settings_changed', {'enabled': enabled})
        return self.snapshot()

    def review(self):
        for state in self.list():
            if not state['intent']['mission_id']:
                continue
            try:
                mission = self.engine.missions.get(state['intent']['mission_id'])
                if state['status'] == 'completed':
                    from backend.runtime.bounded_function_tests import validated_acceptance
                    try:
                        validated_acceptance(self.engine, state['intent']['mission_id'], state['intent']['mission_version'], state['intent']['acceptance_step'])
                    except (ValueError, KeyError, OSError, ImportError):
                        with self.db.get_connection() as conn:
                            conn.execute('BEGIN IMMEDIATE')
                            current = json.loads(conn.execute('SELECT state_json FROM work_backlog WHERE id=?', (state['id'],)).fetchone()[0])
                            current.update(status='review_required', reason='Previously accepted source or receipt changed', evidence=None)
                            self._save(conn, current); conn.commit()
                        self._publish(current)
                        self._finding(current, mission, current['reason'])
                if mission['status'] in {'needs_review', 'cancelled'} or mission['plan'].get('missing_requirements'):
                    self._finding(state, mission, 'Current mission requires owner review')
            except KeyError:
                if state['status'] == 'completed':
                    with self.db.get_connection() as conn:
                        conn.execute('BEGIN IMMEDIATE')
                        current = json.loads(conn.execute('SELECT state_json FROM work_backlog WHERE id=?', (state['id'],)).fetchone()[0])
                        current.update(status='review_required', reason='Accepted mission no longer exists', evidence=None)
                        self._save(conn, current); conn.commit()
                    self._publish(current)
                self._finding(state, {}, 'Linked mission no longer exists')
        return self.snapshot()

    def tick(self, limit=1):
        with _advancement_guard:
            return self._tick(limit)

    def _tick(self, limit=1):
        """At most one existing mission advancement; no lease timeout or retry."""
        # Read-only observations remain useful while execution is paused/L3.
        self.review()
        if not self.snapshot()['enabled'] or self.engine.execution_policy.get()['level'] < 4 or not self.engine.status().get('running'):
            return {'status': 'stopped', 'reason': 'Runtime must be running with autonomy level 4 or 5'}
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if not conn.execute('SELECT enabled FROM work_backlog_settings WHERE id=1').fetchone()[0]:
                return {'status': 'stopped', 'reason': 'Backlog is paused'}
            rows = conn.execute('SELECT state_json FROM work_backlog ORDER BY rowid').fetchall()
            states = [json.loads(row[0]) for row in rows]
            states.sort(key=lambda item: (-item['priority'], item['created_at'], item['id']))
            if any(state['lease'] for state in states):
                return {'status': 'recovery_required', 'reason': 'An outstanding durable lease requires reconciliation'}
            by_id = {state['id']: state for state in states}
            state = next((state for state in states if state['enabled'] and state['status'] in {'ready', 'running'}
                          and all(by_id[dep]['status'] == 'completed' for dep in state['intent']['depends_on'])), None)
            if state is None:
                return {'status': 'idle', 'reason': 'No enabled work has completed dependencies'}
            lease = uuid.uuid4().hex
            state.update(lease=lease, lease_owner=self._owner_proof(), status='running', reason='Advancing the same reviewed mission', next_step='Wait for retained task evidence')
            self._save(conn, state); conn.commit()
        self._publish(state)
        mission = {}
        try:
            intent = state['intent']; mission = self.engine.missions.get(intent['mission_id'])
            self._reviewed(mission, intent['mission_version'], intent['acceptance_step'])
            mission = self.engine.missions.advance(intent['mission_id'])
            status, evidence = 'running', None
            reason = 'Existing mission has unfinished governed tasks'
            if mission['status'] == 'completed':
                from backend.runtime.bounded_function_tests import validated_acceptance
                record = mission['steps'].get(intent['acceptance_step'])
                if not record:
                    raise ValueError('Acceptance task receipt missing')
                evidence = validated_acceptance(self.engine, intent['mission_id'], intent['mission_version'], intent['acceptance_step'])
                if evidence.get('accepted') is not True:
                    raise ValueError('Native acceptance did not pass')
                status, reason = 'completed', 'Native fixed-case acceptance verified; broader roadmap remains open'
            elif mission['status'] in {'needs_review', 'cancelled'}:
                status, reason = 'review_required', 'Mission stopped for review; inspect its failed or exhausted steps'
            if status == 'review_required':
                self._finding(state, mission, reason)
        except (ValueError, KeyError, TypeError, OSError, ImportError):
            status, evidence = 'review_required', None
            reason = 'Exact mission or independently verified native acceptance unavailable'
            self._finding(state, mission, reason)
        except Exception:
            # Unknown effects keep the lease: never automatically replay dispatch.
            self._finding(state, mission, 'Interrupted advancement; reconcile the stopped worker and retained tasks')
            raise
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            current = json.loads(conn.execute('SELECT state_json FROM work_backlog WHERE id=?', (state['id'],)).fetchone()[0])
            if current['lease'] != lease:
                raise ValueError('Work lease changed')
            current.update(status=status, reason=reason, evidence=evidence, lease=None,
                           next_step='Inspect retained acceptance receipt' if status == 'completed' else 'Inspect existing mission tasks before changing this work')
            self._save(conn, current); conn.commit()
        self._publish(current)
        return current

    def _owner_proof(self):
        return {'pid': os.getpid(), 'process_created': psutil.Process().create_time(),
                'host': socket.gethostname(), 'database': str(self.db.db_path.resolve()),
                'host_boot_time': psutil.boot_time()}

    def _prior_owner_stopped(self, proof):
        if (not isinstance(proof, dict) or proof.get('host') != socket.gethostname()
                or proof.get('database') != str(self.db.db_path.resolve())
                or type(proof.get('pid')) is not int or proof['pid'] <= 0
                or type(proof.get('process_created')) not in (int, float)):
            return False
        try:
            return psutil.Process(proof['pid']).create_time() != proof['process_created']
        except psutil.NoSuchProcess:
            return True
        except (psutil.AccessDenied, OSError):
            return False

    def recover_startup(self):
        """Single-controller startup recovery of proven stopped pure observations.

        No elapsed lease age proves safety. Legacy/foreign/alive owners, missing
        tasks, writes, processes, repair transitions and uncertain effects remain
        for explicit review. Recovery never creates or replays a governed task.
        """
        recovered, retained = [], []
        with _advancement_guard:
            for state in self.list():
                if not state['lease']:
                    continue
                try:
                    if not self._prior_owner_stopped(state.get('lease_owner')):
                        raise ValueError('Previous controller stop is not proved')
                    intent = state['intent']; mission = self.engine.missions.get(intent['mission_id'])
                    self._reviewed(mission, intent['mission_version'], intent['acceptance_step'])
                    if not mission['steps'] or mission.get('repair') or mission.get('repair_history'):
                        raise ValueError('No completed pure checkpoint or repair transition present')
                    task_ids = []
                    for step, record in mission['steps'].items():
                        task = self.engine.tasks.get(record['task_id'])
                        self._completed_pure_receipt(task, intent['mission_id'], intent['mission_version'], step)
                        task_ids.append(task['id'])
                    with self.db.get_connection() as conn:
                        conn.execute('BEGIN IMMEDIATE')
                        current = json.loads(conn.execute('SELECT state_json FROM work_backlog WHERE id=?', (state['id'],)).fetchone()[0])
                        if current['lease'] != state['lease'] or current['revision'] != state['revision']:
                            raise ValueError('Checkpoint changed during reconciliation')
                        current.update(lease=None, status='ready', reason='Previous controller stopped; completed pure receipts reconciled without replay',
                                       next_step='Continue the same reviewed mission and retained task identities',
                                       recovery={'prior_lease': state['lease'], 'owner_proof': state['lease_owner'],
                                                 'verified_task_ids': task_ids, 'recovered_at': self.clock()})
                        self._save(conn, current); conn.commit()
                    self._publish(current)
                    recovered.append(current['id'])
                except (ValueError, KeyError, TypeError, OSError):
                    with self.db.get_connection() as conn:
                        conn.execute('BEGIN IMMEDIATE')
                        current = json.loads(conn.execute('SELECT state_json FROM work_backlog WHERE id=?', (state['id'],)).fetchone()[0])
                        if current['lease'] == state['lease']:
                            current.update(reason='Startup cannot prove a stopped controller and completed pure receipts',
                                           next_step='Review the retained lease and task effects; do not retry unknown operations')
                            self._save(conn, current); conn.commit()
                    self._publish(current)
                    retained.append(state['id'])
        return {'recovered': recovered, 'review_required': retained,
                'scope': 'Stopped controller and completed pure receipts only; no lease expiry or side-effect replay'}

    @staticmethod
    def _completed_pure_receipt(task, mission_id, version, step_id):
        pure = {'workspace.read@1.0.0', 'workspace.list@1.0.0', 'text.analyze@1.0.0',
                'code.python.analyze@1.0.0', 'code.function.check@1.0.0'}
        if not task or task['status'].lower() != 'completed' or task['metadata'].get('tool') not in pure:
            raise ValueError('Task is not a completed pure operation')
        metadata = task['metadata']
        if any(metadata.get(key) != value for key, value in {'mission_id': mission_id, 'mission_version': version, 'step_id': step_id}.items()):
            raise ValueError('Task identity differs from approved mission')
        item, = task['result']['results']; subtask, = task['result']['plan']['subtasks']
        if (task['result']['plan']['task_id'] != task['id'] or subtask['prompt'] != task['prompt']
                or subtask['knight'] != item['knight'] or item['verification']['state'] != 'VERIFIED'):
            raise ValueError('Pure execution receipt binding mismatch')
        from backend.swarm.manager import execution_request
        from backend.runtime.execution import verify_request_result
        verify_request_result(execution_request(task, subtask['prompt']), item['outcome'])

    def reconcile(self, project, ident, expected_revision, lease):
        with _advancement_guard:
            return self._reconcile(project, ident, expected_revision, lease)

    def _reconcile(self, project, ident, expected_revision, lease):
        state = self.get(project, ident)
        if state['revision'] != expected_revision or not lease or state['lease'] != lease:
            raise ValueError('Identify the exact outstanding lease')
        mission = self.engine.missions.get(state['intent']['mission_id'])
        for record in mission['steps'].values():
            task = self.engine.tasks.get(record['task_id'])
            if task and task['status'].lower() in {'running', 'leased', 'executing'}:
                raise ValueError('Prior governed task has not stopped')
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            current = json.loads(conn.execute('SELECT state_json FROM work_backlog WHERE id=?', (ident,)).fetchone()[0])
            if current['revision'] != expected_revision or current['lease'] != lease:
                raise ValueError('Checkpoint changed')
            current.update(lease=None, status='ready', reason='Stopped task state reconciled; resume the same mission and task identities')
            self._save(conn, current); conn.commit()
        self._publish(current)
        return current
