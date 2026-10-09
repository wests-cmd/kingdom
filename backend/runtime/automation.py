"""Verified adoption of explicitly registered, reviewed automation adapters.

Discovery never executes arbitrary commands. Adapters supply read-only inspection
and candidate checks, and retain their original runner as a rollback target.
"""
import json
import time
import uuid
from contextlib import closing


class ReviewRequired(ValueError):
    """Fixed, non-sensitive diagnosis supplied by reviewed adapter code."""


class AutomationSupervisor:
    def __init__(self, connect, policy, publish, clock=time.time):
        self.connect, self.policy, self.publish, self.clock = connect, policy, publish, clock
        self.adapters = {}
        with closing(connect()) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS automation_handovers (
                id TEXT PRIMARY KEY, state_json TEXT NOT NULL)''')
            db.commit()

    def register(self, adapter):
        if adapter.id in self.adapters:
            raise ValueError('Adapter already registered')
        self.adapters[adapter.id] = adapter
        with closing(self.connect()) as db:
            state = {'id': adapter.id, 'name': adapter.name, 'owner': 'original',
                     'status': 'discovered', 'attempts': 0, 'approved_revision': None,
                     'revision': adapter.revision, 'lease': None, 'retry_at': 0,
                     'evidence': {}, 'last_failure': None,
                     'plan': ['Inspect current progress and outputs',
                              'Test the reviewed candidate without publishing',
                              'Transfer one worker at a time after checks pass',
                              'Keep the original runner for rollback',
                              'Diagnose failure and retry within the attempt limit']}
            db.execute('INSERT OR IGNORE INTO automation_handovers VALUES (?,?)',
                       (adapter.id, json.dumps(state)))
            db.commit()

    def _load(self, db, ident):
        row = db.execute('SELECT state_json FROM automation_handovers WHERE id=?', (ident,)).fetchone()
        if not row:
            raise KeyError(ident)
        return json.loads(row[0])

    def _save(self, db, state):
        db.execute('UPDATE automation_handovers SET state_json=? WHERE id=?',
                   (json.dumps(state), state['id']))
        db.commit()

    def inventory(self):
        with closing(self.connect()) as db:
            records = [json.loads(row[0]) for row in db.execute('SELECT state_json FROM automation_handovers ORDER BY id')]
        for state in records:
            adapter = self.adapters.get(state['id'])
            state['adapter_available'] = bool(adapter)
            if adapter:
                # Adapter inspection returns operational counts, never credentials.
                state['observed'] = adapter.inspect()
                state['candidate_revision'] = adapter.revision
            state['autonomy_level'] = self.policy()
        return records

    def approve(self, ident, revision):
        adapter = self.adapters.get(ident)
        if not adapter or adapter.revision != revision:
            raise ValueError('Approve the exact installed adapter revision')
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._load(db, ident)
            if state['lease']:
                raise ValueError('Work is in flight; approval cannot change')
            state.update(approved_revision=revision, attempts=0, retry_at=0)
            self._save(db, state)
        self.publish('automation.approved', {'id': ident, 'revision': revision})
        return state

    def recover_stopped(self, ident, lease):
        """Owner/local timer calls only after verifying the prior worker stopped."""
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._load(db, ident)
            if not lease or state['lease'] != lease:
                raise ValueError('Recovery must identify the exact outstanding lease')
            state.update(lease=None, owner='original', status='recovered_original',
                         retry_at=self.clock() + 1800, last_failure='InterruptedWorker')
            self._save(db, state)
        self.publish('automation.recovered', {'id': ident, 'owner': 'original'})
        return state

    def run(self, ident):
        """Called by a registered local timer; one lease includes all side effects.

        A lease is deliberately not reclaimed on timeout: an uncertain worker may
        still be publishing. Recovery requires an operator to verify it has stopped.
        """
        adapter = self.adapters[ident]
        level = self.policy()
        lease = uuid.uuid4().hex
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._load(db, ident)
            if state['lease']:
                return {'status': 'busy', 'owner': state['owner']}
            if state['owner'] == 'kingdom' and level not in (3, 4, 5):
                return {'status': 'paused_by_autonomy', 'owner': state['owner']}
            adopted = (level in (3, 4, 5) and state['approved_revision'] == adapter.revision
                       and state['attempts'] < 3 and self.clock() >= state['retry_at'])
            # A revision change must never inherit an older candidate's approval.
            if state['owner'] == 'kingdom' and state['revision'] != adapter.revision:
                state.update(owner='original', status='revision_needs_approval')
            state['lease'] = lease
            self._save(db, state)
        event = 'automation.observed'
        try:
            if adopted and state['owner'] != 'kingdom':
                state['attempts'] += 1
                evidence = adapter.verify()
                if evidence.get('passed') is not True:
                    raise ValueError('Candidate checks failed')
                state.update(owner='kingdom', status='verified', revision=adapter.revision,
                             evidence=evidence, last_failure=None)
                # Persist the tested ownership decision before any candidate effect.
                with closing(self.connect()) as db:
                    self._save(db, state)
                event = 'automation.adopted'
            runner = adapter.run_candidate if state['owner'] == 'kingdom' else adapter.run_original
            runner()
            state['status'] = 'healthy' if state['owner'] == 'kingdom' else 'original_running'
            state['last_success'] = self.clock()
        except Exception as error:
            # Do not retry the original in this invocation: the failed candidate may
            # already have published. The next timer uses the same durable work DB.
            state.update(owner='original', status='rolled_back', retry_at=self.clock() + 1800,
                         last_failure=type(error).__name__)
            state['diagnosis'] = ('Reviewed source or deployment evidence changed. Retest and approve the corrected revision.'
                                  if isinstance(error, ReviewRequired) else
                                  'The checked worker failed. Retain progress, recheck its inputs and dependencies, then retry after cooldown.')
            event = 'automation.rolled_back'
            raise
        finally:
            state['lease'] = None
            with closing(self.connect()) as db:
                self._save(db, state)
            self.publish(event, {k: state[k] for k in ('id', 'owner', 'status', 'attempts', 'last_failure')})
        return state
