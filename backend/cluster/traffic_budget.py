"""Host-runtime traffic accounting. Reservations grant no execution authority.

The host owns this database. Callers supply an already authenticated principal;
messages cannot choose a parent host or authorize their own control traffic.
"""
import hashlib
import json
import re
import time

from backend.cluster.team_policy import TeamMessage, TeamPolicy, utc_seconds


class BudgetExceeded(PermissionError):
    """Queue the operation: this host's current allowance is exhausted."""


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('Use a bounded principal or attempt identifier')
    return value


class TrafficBudget:
    def __init__(self, database, host_id, *, policy=None, clock=time.time, publish=None):
        self.db, self.host_id = database, _identifier(host_id)
        self.policy = TeamPolicy.model_validate(policy if policy is not None else TeamPolicy())
        self.clock, self.publish = clock, publish or (lambda *args: None)
        with self.db.get_connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS team_traffic_windows(
                host TEXT PRIMARY KEY, started REAL NOT NULL, seconds INTEGER NOT NULL,
                routine_used INTEGER NOT NULL, control_used INTEGER NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS team_traffic_attempts(
                host TEXT NOT NULL, attempt TEXT NOT NULL, context TEXT NOT NULL,
                receipt TEXT NOT NULL, PRIMARY KEY(host,attempt))''')
            conn.execute('''CREATE TABLE IF NOT EXISTS team_traffic_actors(
                actor TEXT PRIMARY KEY, host TEXT NOT NULL, active INTEGER NOT NULL)''')
            conn.commit()

    def _host_allowed(self, conn):
        if conn.execute('SELECT 1 FROM team_traffic_actors WHERE actor=?', (self.host_id,)).fetchone():
            raise PermissionError('A container must use its recorded physical host budget')

    def bind_actor(self, actor_id):
        """Trusted host configuration only: accounting placement, never a grant."""
        actor = _identifier(actor_id)
        if actor == self.host_id:
            raise ValueError('The host is already its own budget principal')
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._host_allowed(conn)
            if (conn.execute('SELECT 1 FROM team_traffic_windows WHERE host=?', (actor,)).fetchone()
                    or conn.execute('SELECT 1 FROM team_traffic_actors WHERE host=?', (actor,)).fetchone()):
                raise PermissionError('An established physical host cannot become a child budget')
            row = conn.execute('SELECT host,active FROM team_traffic_actors WHERE actor=?', (actor,)).fetchone()
            if row:
                if row['host'] != self.host_id:
                    raise PermissionError('Actor already belongs to another host budget')
                if row['active']:
                    return {'actor_id': actor, 'host_id': self.host_id}
                conn.execute('UPDATE team_traffic_actors SET active=1 WHERE actor=?', (actor,))
            else:
                conn.execute('INSERT INTO team_traffic_actors VALUES(?,?,1)', (actor, self.host_id))
            conn.commit()
        self.publish('team.traffic_actor_bound', {'actor_id': actor, 'host_id': self.host_id})
        return {'actor_id': actor, 'host_id': self.host_id}

    def unbind_actor(self, actor_id):
        """Revoke budget placement; cached attempts do not restore it."""
        actor = _identifier(actor_id)
        with self.db.get_connection() as conn:
            self._host_allowed(conn)
            changed = conn.execute('UPDATE team_traffic_actors SET active=0 WHERE actor=? AND host=? AND active=1', (actor, self.host_id)).rowcount
            conn.commit()
        if changed:
            self.publish('team.traffic_actor_unbound', {'actor_id': actor, 'host_id': self.host_id})
        return {'actor_id': actor, 'bound': False}

    def _now(self):
        value = self.clock()
        # Above the supported UTC year9999 range, float granularity can make
        # started + window_seconds == started and refill every reservation.
        return utc_seconds(value)

    def _window(self, conn, now):
        row = conn.execute('SELECT * FROM team_traffic_windows WHERE host=?', (self.host_id,)).fetchone()
        changed = row is None or now >= row['started'] + row['seconds']
        if changed:
            seconds = self.policy.window_seconds
            started = (now // seconds) * seconds
            conn.execute('''INSERT INTO team_traffic_windows VALUES(?,?,?,0,0)
                ON CONFLICT(host) DO UPDATE SET started=excluded.started,seconds=excluded.seconds,
                routine_used=0,control_used=0''', (self.host_id, started, seconds))
            row = conn.execute('SELECT * FROM team_traffic_windows WHERE host=?', (self.host_id,)).fetchone()
        return row, changed

    def reserve(self, attempt_id, message, *, authenticated_actor, byte_count=None, control_authorized=False):
        attempt_id = _identifier(attempt_id)
        actor = _identifier(authenticated_actor)
        if not isinstance(message, TeamMessage):
            raise ValueError('A validated TeamMessage is required')
        canonical = message.canonical_bytes()
        snapshot = TeamMessage.model_validate_json(canonical)
        if snapshot.sender_id != actor:
            raise PermissionError('Message sender must be the authenticated principal')
        size = len(canonical) if byte_count is None else byte_count
        if type(size) is not int or size < len(canonical):
            raise ValueError('Reservation must cover the serialized message bytes')
        if type(control_authorized) is not bool:
            raise ValueError('Use an explicit trusted control authorization verdict')
        lane = 'control' if snapshot.kind in {'stop', 'revocation', 'recovery'} else 'routine'
        if lane == 'control' and not control_authorized:
            raise PermissionError('An independent control authorization verdict is required')
        digest = hashlib.sha256(canonical).hexdigest()
        context = json.dumps({'actor': actor, 'bytes': size, 'digest': digest, 'kind': snapshot.kind}, sort_keys=True)
        now = self._now()
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._host_allowed(conn)
            binding = conn.execute('SELECT host,active FROM team_traffic_actors WHERE actor=?', (actor,)).fetchone()
            if actor != self.host_id and (not binding or binding['host'] != self.host_id or not binding['active']):
                raise PermissionError('Actor has no current binding to this host budget')
            old = conn.execute('SELECT context,receipt FROM team_traffic_attempts WHERE host=? AND attempt=?', (self.host_id, attempt_id)).fetchone()
            if old:
                if old['context'] != context:
                    raise ValueError('Attempt identifier belongs to different traffic')
                return json.loads(old['receipt'])
            snapshot.assert_current(now)
            count = conn.execute('SELECT count(*) FROM team_traffic_attempts WHERE host=?', (self.host_id,)).fetchone()[0]
            if count >= self.policy.receipt_entries:
                raise BudgetExceeded('Traffic reservation ledger full; retain replay protection and request maintenance')
            window, window_changed = self._window(conn, now)
            used = window['control_used'] if lane == 'control' else window['routine_used']
            limit = self.policy.wifi_control_bytes if lane == 'control' else self.policy.wifi_routine_bytes
            if used + size > limit:
                raise BudgetExceeded('Traffic allowance exhausted; retain queued work')
            receipt = {'attempt_id': attempt_id, 'host_id': self.host_id, 'actor_id': actor,
                       'message_id': snapshot.message_id, 'message_digest': digest,
                       'byte_count': size, 'kind': snapshot.kind, 'lane': lane,
                       'window_started': window['started'], 'window_ends': window['started'] + window['seconds'],
                       'reserved_at': now}
            column = 'control_used' if lane == 'control' else 'routine_used'
            conn.execute(f'UPDATE team_traffic_windows SET {column}={column}+? WHERE host=?', (size, self.host_id))
            conn.execute('INSERT INTO team_traffic_attempts VALUES(?,?,?,?)', (self.host_id, attempt_id, context, json.dumps(receipt)))
            conn.commit()
        if window_changed:
            self.publish('team.traffic_window', {'host_id': self.host_id, 'window_started': window['started']})
        self.publish('team.traffic_reserved', {'host_id': self.host_id, 'attempt_id': attempt_id, 'lane': lane, 'bytes': size})
        return receipt

    def status(self):
        now = self._now()
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self._host_allowed(conn)
            window, changed = self._window(conn, now)
            conn.commit()
        if changed:
            self.publish('team.traffic_window', {'host_id': self.host_id, 'window_started': window['started']})
        return {'host_id': self.host_id, 'window_started': window['started'],
                'window_ends': window['started'] + window['seconds'],
                'routine': {'limit': self.policy.wifi_routine_bytes, 'used': window['routine_used'],
                            'remaining': max(0, self.policy.wifi_routine_bytes - window['routine_used'])},
                'control': {'limit': self.policy.wifi_control_bytes, 'used': window['control_used'],
                            'remaining': max(0, self.policy.wifi_control_bytes - window['control_used'])}}
