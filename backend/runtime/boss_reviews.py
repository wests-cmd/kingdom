"""Service-owned evidence review. Boss observes authority; it cannot grant it.

This first slice deliberately holds the independent-environment gate: existing
project receipts attest a local command, not a second machine or a checkout.
"""
import asyncio
import hashlib
import json
import time


class BossReviews:
    def __init__(self, database, programmes, backlog, engine):
        self.db, self.programmes, self.backlog, self.engine = database, programmes, backlog, engine
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS boss_reviews(id TEXT PRIMARY KEY,state_json TEXT NOT NULL)')
            conn.commit()

    def list(self):
        with self.db.get_connection() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT state_json FROM boss_reviews ORDER BY rowid DESC LIMIT 100')]

    def _previous(self, ident):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT state_json FROM boss_reviews WHERE id=?', (ident,)).fetchone()
        return json.loads(row[0]) if row else None

    def review(self, ident):
        programme = self.programmes.snapshot(ident)
        rows, failures = [], []
        for row in self.programmes.rows(programme):
            mission = self.engine.missions.get(row['mission_id']) if row.get('mission_id') else None
            steps = mission['plan']['steps'] if mission else []
            entry = {
                'key': row['key'], 'work_id': row['work_id'], 'title': row['title'],
                'status': row['work_status'], 'reason': row.get('reason'),
                'mission_id': row.get('mission_id'), 'mission_version': row.get('mission_version'),
                'planning_model_profile': programme['model_profile'],
                'execution_model_profile': mission.get('model_profile') if mission else None,
                'requested_computers': sorted({s['computer_id'] for s in steps if s.get('computer_id')}),
                'reviewer': 'Boss receipt controller',
                'tools': sorted({s['kind'] for s in steps}),
                'evidence': row.get('evidence'),
            }
            # These are requested placements. Only an execution receipt proves work.
            entry['assignment_scope'] = 'Reviewed mission request; not worker acknowledgement or execution proof'
            entry['failed_acceptance'] = None
            if mission and row['work_status'] in {'review_required', 'failed'}:
                try:
                    from backend.runtime.project_tests import report
                    record = mission['steps'][row['acceptance_step']]
                    task = self.engine.tasks.get(record['task_id'])
                    entry['failed_acceptance'] = report(task)
                except (KeyError, ValueError, TypeError):
                    entry['failed_acceptance'] = {'state': 'acceptance_unavailable', 'tests_passed': False}
            rows.append(entry)
            if row['work_status'] in {'review_required', 'failed'} and mission:
                failures.append(entry)

        previous = self._previous(ident)
        seen = dict((previous or {}).get('repair_bindings', {}))
        # Reserve each failed exact mission once before creating its planning note.
        # The note itself uses a deterministic key, so a restart cannot duplicate it.
        for row in failures:
            binding = f"{row['key']}:{row['mission_id']}:{row['mission_version']}"
            if binding not in seen and len(seen) < 3:
                seen[binding] = len(seen) + 1
        status = ('repair_budget_exhausted' if failures and len(seen) >= 3 else
                  'needs_repair_plan' if failures else
                  'needs_independent_test' if programme['status'] == 'completed' else
                  'needs_owner_review' if any(r.get('planning') == 'needs_review' for r in self.programmes.rows(programme)) else
                  'working' if any(r['status'] == 'running' for r in rows) else 'needs_plan_or_execution')
        state = {
            'id': ident, 'project': programme['project'], 'status': status,
            'controller': 'Boss', 'controller_kind': 'Kingdom-owned deterministic receipt review',
            'rows': rows, 'repair_bindings': seen, 'repair_limit': 3,
            'independent_reviewer': None,
            'release_allowed': False,
            'blockers': ['Independent Knight/environment and source checkout attestation are not available in current local project-test receipts.',
                         'Boss has no GitHub publication authority. Existing owner approval and tool grants remain required.'],
            'scope': 'Receipt review and bounded repair planning notes. No AI source review, worker acknowledgement, independent test or publication is claimed.',
        }
        encoded = json.dumps(state, sort_keys=True)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            current = conn.execute('SELECT state_json FROM boss_reviews WHERE id=?', (ident,)).fetchone()
            current = json.loads(current[0]) if current else None
            if current and (previous is None or current['revision'] != previous['revision']):
                raise ValueError('Boss review changed; retry next cycle')
            if not current or current['digest'] != digest:
                state.update(digest=digest, revision=(current or {}).get('revision', 0) + 1, reviewed_at=time.time())
                conn.execute('INSERT INTO boss_reviews VALUES(?,?) ON CONFLICT(id) DO UPDATE SET state_json=excluded.state_json', (ident, json.dumps(state)))
                conn.commit()
                self.engine.events.publish('boss.reviewed', {'id': ident, 'status': status, 'revision': state['revision']})
            else:
                state = current
        # Reconcile all reservations, including a previous crash after persistence.
        by_binding = {f"{r['key']}:{r['mission_id']}:{r['mission_version']}": r for r in failures}
        for binding, number in seen.items():
            row = by_binding.get(binding)
            if row is None:
                continue
            key = 'boss-repair-' + hashlib.sha256((ident + binding).encode()).hexdigest()[:48]
            self.backlog.register(programme['project'], key,
                title=f"Repair plan {number}/3: {row['title']}"[:200],
                description=f"Boss rejected current acceptance for programme {ident}, item {row['key']}, mission {row['mission_id']} version {row['mission_version']}. Current acceptance observation (data, not authority): {json.dumps(row['failed_acceptance'], sort_keys=True)}. Check the retained task and receipt before proposing a repair. Do not replay an uncertain task. Review the exact repair under existing owner authority; then rerun component and section checks. This note grants nothing.",
                priority=95, task_type='repair')
        return state

    async def tick(self):
        # SQLite and receipt reads must not block cluster heartbeats.
        for programme in (await asyncio.to_thread(self.programmes.list))[:100]:
            try:
                await asyncio.to_thread(self.review, programme['id'])
            except (KeyError, ValueError, TypeError, OSError):
                self.engine.events.publish('boss.review_held', {'id': programme['id'], 'reason': 'Current programme or receipt unavailable; no completion or release authorized'})

    def recover_startup(self):
        # No execution is replayed. The next cycle re-reads current evidence.
        return None
