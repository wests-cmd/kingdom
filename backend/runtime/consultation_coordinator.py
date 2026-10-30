"""Bounded proposal assistance, separate from task execution and acceptance."""
import asyncio
import json
import math
import time

from backend.runtime.consultations import ConsultationStore


class ConsultationCoordinator:
    def __init__(self, database, engine, programmes, connection, *, clock=time.time):
        self.db, self.engine, self.programmes, self.connection, self.clock = database, engine, programmes, connection, clock
        self.store = ConsultationStore(database, verifier=self.verify, publish=engine.events.publish, clock=clock)
        self.lock = asyncio.Lock()
        with database.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS assistance_settings(id INTEGER PRIMARY KEY,value_json TEXT NOT NULL)')
            conn.execute('INSERT OR IGNORE INTO assistance_settings VALUES(1,?)',
                         (json.dumps({'enabled': False, 'max_daily_calls': 8, 'revision': 1}),))
            conn.execute('CREATE TABLE IF NOT EXISTS assistance_budget(id INTEGER PRIMARY KEY,day INTEGER NOT NULL,used INTEGER NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS assistance_links(id TEXT PRIMARY KEY,programme TEXT NOT NULL,item TEXT NOT NULL)')
            if 'automatic' not in {row[1] for row in conn.execute('PRAGMA table_info(assistance_links)')}:
                conn.execute('ALTER TABLE assistance_links ADD COLUMN automatic INTEGER NOT NULL DEFAULT 0')
            conn.commit()

    def settings(self):
        with self.db.get_connection() as conn:
            return json.loads(conn.execute('SELECT value_json FROM assistance_settings WHERE id=1').fetchone()[0])

    def configure(self, enabled, max_daily_calls, expected_revision):
        if type(enabled) is not bool or type(max_daily_calls) is not int or not 1 <= max_daily_calls <= 32:
            raise ValueError('Choose explicit help settings and a daily limit of1–32')
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            previous = json.loads(conn.execute('SELECT value_json FROM assistance_settings WHERE id=1').fetchone()[0])
            if type(expected_revision) is not int or previous['revision'] != expected_revision:
                raise ValueError('Help settings changed')
            result = {'enabled': enabled, 'max_daily_calls': max_daily_calls, 'revision': expected_revision+1}
            conn.execute('UPDATE assistance_settings SET value_json=? WHERE id=1', (json.dumps(result),)); conn.commit()
        self.engine.events.publish('assistance.settings_changed', {'revision': result['revision']})
        return result

    def status(self):
        return {'settings': self.settings(), 'connection': self.connection.status(),
                'requests': self.store.list(limit=100),
                'scope': 'Advice and retained learning; no mission approval, execution or release authority.'}

    async def request_programme(self, ident, key, *, automatic=False):
        programme = self.programmes.get(ident)
        item = next(r for r in self.programmes.rows(programme) if r['key'] == key)
        request = await (self.programmes.execution_help_request(ident, key) if item.get('mission_id')
                         else self.programmes.planning_help_request(ident, key))
        row = self.store.request(**request)
        with self.db.get_connection() as conn:
            conn.execute('INSERT OR IGNORE INTO assistance_links(id,programme,item,automatic) VALUES(?,?,?,?)',
                         (row['id'], ident, key, int(automatic)))
            if not automatic:
                conn.execute('UPDATE assistance_links SET automatic=0 WHERE id=?', (row['id'],))
            conn.commit()
        return row

    async def current_request(self, row):
        with self.db.get_connection() as conn:
            link = conn.execute('SELECT programme,item,automatic FROM assistance_links WHERE id=?', (row['id'],)).fetchone()
        if not link:
            return False
        state = self.programmes.get(link[0])
        if link[2] and not state.get('auto_plan'):
            return False
        request = await (self.programmes.execution_help_request(*link[:2]) if row['kind'] == 'error'
                         else self.programmes.planning_help_request(*link[:2]))
        normalized = self.store._request(**request)
        return all(normalized[key] == row[key] for key in (
            'project', 'parent_work_id', 'context_revision', 'kind', 'question_sha256', 'context_sha256'))

    def automatic_paused(self, row):
        with self.db.get_connection() as conn:
            link = conn.execute('SELECT programme,automatic FROM assistance_links WHERE id=?', (row['id'],)).fetchone()
        return bool(link and link[1] and not self.programmes.get(link[0]).get('auto_plan'))

    async def authorize_delivery(self, row):
        try:
            return (self.delivery_claim_current(row) and self.settings()['enabled'] and self.engine.status().get('running')
                    and self.engine.execution_policy.get()['level'] > 0
                    and self.connection.status()['state'] == 'ready'
                    and await self.current_request(row))
        except (ValueError, KeyError, StopIteration):
            return False

    def delivery_claim_current(self, claimed):
        current = self.store.get(claimed['id'])
        now = self.clock()
        return (current['status'] == 'sending'
                and current.get('claim_token') == claimed.get('claim_token')
                and current['generation'] == claimed['generation']
                and current['claimed_at'] <= now < current['lease_expires_at'])

    def apply(self, ident):
        row = self.store.get(ident)
        if row['status'] != 'answered':
            raise ValueError('A completed answer is required')
        if row['kind'] == 'error':
            return {'advice': row, 'state': 'repair_review_required',
                    'scope': 'Retained error advice; does not dispatch or certify a repair.'}
        with self.db.get_connection() as conn:
            link = conn.execute('SELECT programme,item FROM assistance_links WHERE id=?', (ident,)).fetchone()
        if not link:
            raise ValueError('No original programme binding')
        return self.programmes.apply_help_response(*link, row['answer'], row['context_revision'], ident)

    def verify(self, row, evidence_id):
        from backend.runtime.mission_acceptance import validated_acceptance
        from backend.runtime.work_programmes import validate_binding
        with self.db.get_connection() as conn:
            link = conn.execute('SELECT programme,item FROM assistance_links WHERE id=?', (row['id'],)).fetchone()
        if not link:
            raise PermissionError('No original programme evidence binding')
        programme = self.programmes.get(link[0])
        item = next(r for r in self.programmes.rows(programme) if r['key'] == link[1])
        if (item.get('consultation_id') != row['id'] or item.get('consultation_answer_sha256') != row['answer_sha256']
                or item.get('consultation_context_revision') != row['context_revision']
                or item['work_id'] != row['parent_work_id'] or programme['project'] != row['project']
                or self.programmes._help_context(programme, item) != row['context_revision']):
            raise PermissionError('Advice no longer matches its source and accepted work')
        work = self.programmes.backlog.get(row['project'], row['parent_work_id'])
        validate_binding(self.engine, programme, item, work)
        expected = f"{item['mission_id']}:{item['mission_version']}:{item['acceptance_step']}"
        if expected != evidence_id:
            raise PermissionError('Unrelated acceptance evidence')
        accepted = validated_acceptance(self.engine, item['mission_id'], item['mission_version'], item['acceptance_step'])
        if accepted.get('accepted') is not True:
            raise PermissionError('Acceptance is not verified')
        mission = self.engine.missions.get(item['mission_id'])
        step = next(s for s in mission['plan']['steps'] if s['id'] == item['acceptance_step'])
        return {'evidence_id': expected, 'project': row['project'], 'parent_work_id': row['parent_work_id'],
                'context_revision': row['context_revision'], 'question_id': row['id'],
                'answer_sha256': row['answer_sha256'], 'kind': step['kind'],
                'tests_passed': True, 'revoked': False}

    def verify_current(self, ident):
        with self.db.get_connection() as conn:
            link = conn.execute('SELECT programme,item FROM assistance_links WHERE id=?', (ident,)).fetchone()
        if not link:
            raise PermissionError('No original work binding')
        state = self.programmes.get(link[0])
        item = next(r for r in self.programmes.rows(state) if r['key'] == link[1])
        if not item.get('mission_id'):
            raise PermissionError('No accepted mission')
        evidence_id = f"{item['mission_id']}:{item['mission_version']}:{item['acceptance_step']}"
        return self.store.record_verification(ident, evidence_id)

    def _reserve_daily(self):
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now) or not 0 <= now <= 253402300799:
            raise ValueError('Invalid clock')
        day, limit = int(now // 86400), self.settings()['max_daily_calls']
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            old = conn.execute('SELECT day,used FROM assistance_budget WHERE id=1').fetchone()
            if old and (day < old[0] or day == old[0] and old[1] >= limit):
                return False
            used = old[1]+1 if old and day == old[0] else 1
            conn.execute('INSERT INTO assistance_budget VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET day=excluded.day,used=excluded.used', (day, used))
            conn.commit()
        return True

    async def tick(self):
        if self.lock.locked() or not self.settings()['enabled']:
            return
        async with self.lock:
            if not self.engine.status().get('running') or self.engine.execution_policy.get()['level'] == 0:
                return
            for saved in self.store.list(limit=1024):
                if saved['status'] == 'answered' and not saved.get('verification'):
                    try:
                        self.verify_current(saved['id'])
                    except (PermissionError, ValueError, KeyError, StopIteration):
                        pass
            # Only owner-enabled programmes; this does not bulk-adopt or enable notes.
            for programme in self.programmes.list():
                if not programme.get('auto_plan'):
                    continue
                current = self.programmes.snapshot(programme['id'])
                for item in self.programmes.rows(current):
                    eligible = (item.get('work_status') in {'review_required', 'failed'} if item.get('mission_id') else
                                item.get('planning') in {'blocked', 'awaiting_chatgpt', 'awaiting_answer'})
                    if not eligible:
                        continue
                    if (not item.get('mission_id') and item.get('consultation_id')
                            and item.get('consultation_context_revision') == self.programmes._help_context(current, item)):
                        # The helper has already responded to this exact context.
                        # Its request for owner input is not another model retry.
                        continue
                    try:
                        await self.request_programme(programme['id'], item['key'], automatic=True)
                    except (ValueError, KeyError, StopIteration):
                        continue
            ready = self.connection.status()['state'] == 'ready'
            candidate, lesson = None, None
            for row in self.store.list(limit=1024):
                if row['status'] != 'queued' or self.automatic_paused(row):
                    continue
                found = self.store.lookup_verified(row['project'], row['context_revision'], row['kind'],
                                                    row['question'], row['context'])
                if found:
                    candidate, lesson = row, found
                    break
                if ready and candidate is None:
                    candidate = row
            if candidate is None:
                return
            claim = self.store.claim('native-assistance', candidate['id'], lease_seconds=300)
            if not claim:
                return
            ident, token = claim['id'], claim['claim_token']
            try:
                current = await self.current_request(claim)
            except (ValueError, KeyError, StopIteration):
                current = False
            if not current:
                if self.automatic_paused(claim):
                    self.store.fail_not_sent(ident, token, 'programme_paused')
                else:
                    self.store.mark_failed(ident, token, 'parent_changed')
                return
            if not lesson and not self._reserve_daily():
                self.store.fail_not_sent(ident, token, 'daily_limit'); return
            if not self.settings()['enabled'] or self.engine.execution_policy.get()['level'] == 0:
                self.store.fail_not_sent(ident, token, 'policy_changed'); return
            self.store.mark_sending(ident, token)
            try:
                reply = {'text': lesson['answer']} if lesson else await self.connection.advise(
                    claim['question'], authorization_check=lambda: self.authorize_delivery(claim))
                self.store.finish(ident, token, reply['text'], 'verified_local_lesson' if lesson else 'chatgpt-plan')
            except asyncio.CancelledError:
                if self.delivery_claim_current(claim):
                    self.store.mark_unknown(ident, token, 'runtime_interrupted')
                raise
            except Exception as error:
                # Owner cancellation or recovery may have fenced this worker
                # while token refresh or the provider response was in flight.
                if not self.delivery_claim_current(claim):
                    return
                if getattr(error, 'code', None) == 'request_authorization_changed':
                    if self.automatic_paused(claim) or not self.settings()['enabled']:
                        self.store.fail_not_sent(ident, token, 'programme_paused')
                    else:
                        self.store.mark_failed(ident, token, 'parent_changed')
                else:
                    self.store.mark_unknown(ident, token, 'provider_not_completed')
                return
            try:
                self.apply(ident)
            except (ValueError, KeyError, StopIteration):
                # Preserve completed advice, but never force an invalid/stale plan.
                pass
