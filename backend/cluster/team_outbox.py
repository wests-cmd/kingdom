"""Durable delivery state, not a transport or a grant of authority.

The runtime must check current authority and verify signed receipts outside this
storage boundary. An acknowledgement proves delivery only, never task success.
No network, model, or user callback runs inside a SQLite transaction.
"""
import json
import hashlib
import uuid
import re
import time

from backend.cluster.team_policy import TeamMessage, TeamPolicy, utc_seconds


class TeamOutbox:
    def __init__(self, database, policy=None, publish=None, *, clock=time.time):
        self.db = database
        policy_data = policy.model_dump(mode='python') if isinstance(policy, TeamPolicy) else policy
        self.policy = TeamPolicy.model_validate(policy_data if policy_data is not None else {})
        self.publish = publish or (lambda *args: None)
        self.clock = clock
        with self.db.get_connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS team_outbox(
                message_id TEXT PRIMARY KEY, digest TEXT NOT NULL,
                lane TEXT NOT NULL, encoded_size INTEGER NOT NULL,
                state_json TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS team_inbox(
                message_id TEXT PRIMARY KEY, digest TEXT NOT NULL,
                state_json TEXT NOT NULL)''')
            conn.commit()

    def enqueue(self, message):
        message = TeamMessage.model_validate(message.model_dump(mode='python')
                                             if isinstance(message, TeamMessage) else message)
        encoded = message.canonical_bytes()
        digest = hashlib.sha256(encoded).hexdigest()
        snapshot = json.loads(encoded)
        message_id = snapshot['message_id']
        state = {'message_id': message_id, 'digest': digest,
                 'message': snapshot, 'state': 'queued',
                 'sender_id': snapshot['sender_id'], 'recipient_id': snapshot['recipient_id'],
                 'task_id': snapshot['task_id'], 'kind': snapshot['kind'],
                 'claim_token': None, 'generation': 0, 'receipt_id': None}
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            prior = conn.execute('SELECT digest,state_json FROM team_outbox WHERE message_id=?',
                                 (message_id,)).fetchone()
            if prior:
                if prior['digest'] != digest:
                    raise ValueError('Message ID belongs to different content')
                return json.loads(prior['state_json'])
            message.assert_current(self.clock())
            lane = 'control' if snapshot['kind'] in {'stop', 'revocation', 'recovery'} else 'routine'
            if self._ledger_count(conn) >= self.policy.receipt_entries:
                raise BufferError('Delivery ledger full; retain duplicate protection and request maintenance')
            pending = [row for row in conn.execute('SELECT encoded_size,state_json FROM team_outbox WHERE lane=?', (lane,))
                       if json.loads(row['state_json'])['state'] not in {'acknowledged', 'expired'}]
            entry_limit = self.policy.control_entries if lane == 'control' else self.policy.routine_entries
            byte_limit = self.policy.control_bytes if lane == 'control' else self.policy.routine_bytes
            if len(pending) >= entry_limit or sum(row['encoded_size'] for row in pending) + len(encoded) > byte_limit:
                raise BufferError('Pending outbox full; no saved evidence was pruned')
            conn.execute('INSERT INTO team_outbox VALUES(?,?,?,?,?)',
                         (message_id, digest, lane, len(encoded), json.dumps(state)))
            conn.commit()
        self.publish('team.message_queued', {'message_id': message_id})
        return state

    def get(self, message_id):
        with self.db.get_connection() as conn:
            return self._load(conn, message_id)

    @staticmethod
    def _load(conn, message_id):
        row = conn.execute('SELECT state_json FROM team_outbox WHERE message_id=?', (message_id,)).fetchone()
        if row is None:
            raise KeyError(message_id)
        return json.loads(row['state_json'])

    @staticmethod
    def _save(conn, state):
        conn.execute('UPDATE team_outbox SET state_json=? WHERE message_id=?',
                     (json.dumps(state), state['message_id']))

    @staticmethod
    def _ledger_count(conn):
        return (conn.execute('SELECT count(*) FROM team_outbox').fetchone()[0]
                + conn.execute('SELECT count(*) FROM team_inbox').fetchone()[0])

    def claim_next(self):
        """Claim the oldest queued control item, otherwise oldest routine item."""
        return self.claim()

    def claim(self, message_id=None):
        """Claim local preparation only. No I/O is permitted before mark_sending."""
        expired = []
        selected = None
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if message_id is None:
                rows = conn.execute("SELECT state_json FROM team_outbox ORDER BY CASE lane WHEN 'control' THEN 0 ELSE 1 END,rowid").fetchall()
                candidates = [json.loads(row['state_json']) for row in rows]
            else:
                candidates = [self._load(conn, message_id)]
            now = utc_seconds(self.clock())
            for state in candidates:
                if state['state'] != 'queued':
                    continue
                message = TeamMessage.model_validate(state['message'])
                if now >= message.expires_at:
                    state.update(state='expired', claim_token=None)
                    self._save(conn, state)
                    expired.append(state['message_id'])
                    continue
                if now < message.created_at:
                    continue  # Clock rollback holds work; it never renews TTL.
                message.assert_current(now)
                state.update(state='claimed', claim_token=uuid.uuid4().hex,
                             generation=state['generation'] + 1)
                self._save(conn, state)
                selected = state
                break
            conn.commit()
        for ident in expired:
            self.publish('team.message_expired', {'message_id': ident})
        if selected:
            self.publish('team.message_claimed', {'message_id': selected['message_id']})
        return selected

    def mark_sending(self, message_id, claim_token):
        """Persist the send boundary before bytes; repeated starts are denied."""
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            state = self._load(conn, message_id)
            if state['state'] != 'claimed' or state['claim_token'] != claim_token:
                raise PermissionError('Current unsent claim required')
            TeamMessage.model_validate(state['message']).assert_current(self.clock())
            state['state'] = 'sending'
            self._save(conn, state)
            conn.commit()
        self.publish('team.message_sending', {'message_id': message_id})
        return state

    def recover(self):
        """Fence unsent claims; retain uncertain sends without automatically replaying.

        A dispatcher must mark_sending before any external operation. If an old
        dispatcher races recovery, its token either loses before send or its
        already-marked send is held as unknown, never admitted a second time.
        """
        changed, incoming = [], []
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            for row in conn.execute('SELECT state_json FROM team_outbox').fetchall():
                state = json.loads(row['state_json'])
                if state['state'] == 'claimed':
                    state.update(state='queued', claim_token=None,
                                 generation=state['generation'] + 1)
                elif state['state'] == 'sending':
                    state['state'] = 'outcome_unknown'
                else:
                    continue
                self._save(conn, state)
                changed.append(state)
            for row in conn.execute('SELECT state_json FROM team_inbox').fetchall():
                state = json.loads(row['state_json'])
                if state['state'] != 'processing':
                    continue
                state['state'] = 'outcome_unknown'
                conn.execute('UPDATE team_inbox SET state_json=? WHERE message_id=?',
                             (json.dumps(state), state['message_id']))
                incoming.append(state['message_id'])
            conn.commit()
        for state in changed:
            self.publish('team.message_recovered', {'message_id': state['message_id'], 'state': state['state']})
        for message_id in incoming:
            self.publish('team.incoming_held', {'message_id': message_id})
        return {'requeued': sum(s['state'] == 'queued' for s in changed),
                'held': sum(s['state'] == 'outcome_unknown' for s in changed) + len(incoming)}

    def acknowledge(self, message_id, *, claim_token, recipient_id, digest, receipt_id):
        """Retain a controller-verified receipt; this method verifies no signature.

        The caller must first authenticate the peer and verify the signed,
        current-authority receipt. Stored acceptance is transport-only.
        """
        if not isinstance(receipt_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', receipt_id):
            raise ValueError('Bounded receipt identity required')
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            state = self._load(conn, message_id)
            if (state['state'] not in {'sending', 'outcome_unknown', 'acknowledged'}
                    or state['claim_token'] != claim_token or state['recipient_id'] != recipient_id
                    or state['digest'] != digest):
                raise PermissionError('Receipt does not bind the current send and recipient')
            if state['state'] == 'acknowledged':
                if state['receipt_id'] != receipt_id:
                    raise ValueError('Delivery already has a different receipt')
                return state
            state.update(state='acknowledged', receipt_id=receipt_id, message=None)
            self._save(conn, state)
            conn.commit()
        self.publish('team.message_acknowledged', {'message_id': message_id, 'receipt_id': receipt_id})
        return state

    def reserve_incoming(self, message):
        """Reserve once before effects, after the caller's current receive authorization.

        Only the first reservation permits processing. After uncertainty the
        runtime must reconcile evidence; this ledger never assumes an effect
        was absent and never automatically repeats it.
        """
        message = TeamMessage.model_validate(message.model_dump(mode='python')
                                             if isinstance(message, TeamMessage) else message)
        encoded = message.canonical_bytes()
        digest = hashlib.sha256(encoded).hexdigest()
        snapshot = json.loads(encoded)
        message_id = snapshot['message_id']
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            prior = conn.execute('SELECT digest,state_json FROM team_inbox WHERE message_id=?',
                                 (message_id,)).fetchone()
            if prior:
                if prior['digest'] != digest:
                    raise ValueError('Received message ID belongs to different content')
                state = json.loads(prior['state_json'])
                return {**state, 'effect_token': None, 'should_process': False}
            message.assert_current(self.clock())
            if self._ledger_count(conn) >= self.policy.receipt_entries:
                raise BufferError('Delivery ledger full; retain duplicate protection and request maintenance')
            state = {'message_id': message_id, 'digest': digest,
                     'sender_id': snapshot['sender_id'], 'recipient_id': snapshot['recipient_id'],
                     'task_id': snapshot['task_id'], 'state': 'processing',
                     'effect_token': uuid.uuid4().hex, 'receipt_id': None}
            conn.execute('INSERT INTO team_inbox VALUES(?,?,?)',
                         (message_id, digest, json.dumps(state)))
            conn.commit()
        self.publish('team.incoming_reserved', {'message_id': message_id})
        return {**state, 'should_process': True}

    def incoming_status(self, message_id):
        """A reconciliation observation, not permission to repeat an effect."""
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT state_json FROM team_inbox WHERE message_id=?', (message_id,)).fetchone()
        if row is None:
            raise KeyError(message_id)
        state = json.loads(row['state_json'])
        return {**state, 'effect_token': None, 'should_process': False}

    def complete_incoming(self, message_id, effect_token, receipt_id):
        """Record the first worker's completed effect without executing anything."""
        if not isinstance(receipt_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', receipt_id):
            raise ValueError('Bounded receipt identity required')
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT state_json FROM team_inbox WHERE message_id=?', (message_id,)).fetchone()
            if row is None:
                raise KeyError(message_id)
            state = json.loads(row['state_json'])
            if state['effect_token'] != effect_token:
                raise PermissionError('Current effect reservation required')
            if state['state'] == 'completed':
                if state['receipt_id'] != receipt_id:
                    raise ValueError('Effect already has a different receipt')
                return {**state, 'effect_token': None, 'should_process': False}
            state.update(state='completed', receipt_id=receipt_id)
            conn.execute('UPDATE team_inbox SET state_json=? WHERE message_id=?',
                         (json.dumps(state), message_id))
            conn.commit()
        self.publish('team.incoming_completed', {'message_id': message_id, 'receipt_id': receipt_id})
        return {**state, 'effect_token': None, 'should_process': False}

    def status(self):
        with self.db.get_connection() as conn:
            outgoing = [json.loads(row[0])['state'] for row in conn.execute('SELECT state_json FROM team_outbox')]
            incoming = [json.loads(row[0])['state'] for row in conn.execute('SELECT state_json FROM team_inbox')]
        return {'pending_count': sum(state not in {'acknowledged', 'expired'} for state in outgoing),
                'incoming_pending_count': sum(state != 'completed' for state in incoming),
                'incoming_unknown_count': incoming.count('outcome_unknown'),
                'receipt_count': len(outgoing) + len(incoming)}
