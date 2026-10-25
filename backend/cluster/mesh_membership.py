"""Owner-selected membership authority. Membership conveys no tool grants."""
import hashlib
import json
import math
import threading
import time

from backend.cluster.identity import compute_fingerprint

APPROVED = {'APPROVED', 'CONNECTED', 'DISCONNECTED', 'RECONNECTING'}


class MeshMembership:
    def __init__(self, database, registry, identity, events, clock=time.time):
        self.db, self.registry, self.identity = database, registry, identity
        self.events, self.clock = events, clock
        self.lock = threading.RLock()
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS mesh_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')

    def _get(self, key, default=None):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT value FROM mesh_state WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def _set(self, key, value):
        with self.db.get_connection() as conn:
            conn.execute('INSERT INTO mesh_state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                         (key, json.dumps(value)))

    def config(self):
        return self._get('config', {})

    def configure(self, authority_id, local_endpoint, ca_pem=''):
        from backend.cluster.peer_endpoints import endpoint
        local_endpoint = endpoint(local_endpoint)
        if len(ca_pem) > 64000:
            raise ValueError('CA bundle exceeds its size limit')
        if ca_pem:
            import ssl
            ssl.create_default_context(cadata=ca_pem)
        if authority_id != self.identity.node_id:
            node = self.registry.get_node(authority_id)
            if not node or node.node_state not in APPROVED or not node.public_identity:
                raise ValueError('Select an explicitly approved membership authority')
            if not (node.connection_metadata or {}).get('kingdom_endpoint'):
                raise ValueError('Membership authority needs a saved endpoint')
        with self.lock:
            previous = self.config()
            if previous and previous['authority_id'] != authority_id:
                raise ValueError('Disable the previous mesh before changing its authority')
            self._set('config', {'authority_id': authority_id, 'local_endpoint': local_endpoint, 'ca_pem': ca_pem})
        self.events.publish('cluster.mesh_configured', {'authority_id': authority_id})
        return {'authority_id': authority_id, 'enabled': True}

    def disable(self):
        # Imported membership cannot outlive removal of its trust authority.
        with self.lock:
            authority = self.config().get('authority_id')
            if not authority:
                return
            for node in self.registry.list_nodes():
                if (node.connection_metadata or {}).get('mesh_authority') == authority and node.node_state in APPROVED:
                    self._revoke(node)
            self._set('config', {})
            self._set('received', None)
        self.events.publish('cluster.mesh_disabled', {'authority_id': authority})

    def _revoke(self, node):
        from backend.cluster.node_registry import NodeState
        self.registry.update_node_state(node.node_id, NodeState.REVOKED, reason='Owner-selected mesh membership removed')

    def export(self, requester):
        """Called only after native signed RPC verifies requester approval."""
        from backend.cluster.peer_endpoints import endpoint
        config = self.config()
        if config.get('authority_id') != self.identity.node_id:
            raise ValueError('This Knight is not the configured membership authority')
        members = [{'identity': self.identity.get_public_identity(), 'endpoint': config['local_endpoint'], 'expires_at': None}]
        for node in self.registry.list_nodes():
            if node.is_local or node.node_state not in APPROVED or (node.public_identity or {}).get('node_type') != 'commander':
                continue
            meta = node.connection_metadata or {}
            deadline = meta.get('membership_expires_at')
            if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline <= self.clock()):
                continue
            address = meta.get('kingdom_endpoint')
            if address:
                members.append({'identity': node.public_identity, 'endpoint': endpoint(address), 'expires_at': deadline})
        members.sort(key=lambda row: row['identity']['node_id'])
        if len(members) > 64 or requester not in {row['identity']['node_id'] for row in members}:
            raise ValueError('Requester is not an approved, reachable mesh member')
        digest = hashlib.sha256(json.dumps(members, sort_keys=True).encode()).hexdigest()
        with self.lock:
            old = self._get('published', {'generation': 0})
            generation = old['generation'] + (old.get('digest') != digest)
            self._set('published', {'generation': generation, 'digest': digest})
        now = self.clock()
        return {'authority_id': self.identity.node_id, 'generation': generation, 'issued_at': now,
                'expires_at': now + 90, 'members': members}

    def receive(self, sender, roster):
        """Apply only an independently verified mesh_roster_response payload."""
        from backend.cluster.peer_endpoints import endpoint
        config = self.config()
        if not config or sender != config['authority_id'] or roster.get('authority_id') != sender:
            raise ValueError('Roster does not belong to the owner-selected authority')
        now = self.clock()
        issued, expires = roster.get('issued_at'), roster.get('expires_at')
        if (type(issued) not in (int, float) or type(expires) not in (int, float)
                or not now - 120 <= issued <= now + 30 or not now < expires <= issued + 120):
            raise ValueError('Roster freshness window is invalid')
        generation = roster.get('generation')
        members = roster.get('members')
        if type(generation) is not int or generation < 1 or not isinstance(members, list) or not 1 <= len(members) <= 64:
            raise ValueError('Invalid bounded roster')
        prepared = {}
        for row in members:
            identity = row.get('identity', {})
            ident, key = identity.get('node_id'), identity.get('public_key_hex')
            if (not isinstance(ident, str) or not 1 <= len(ident) <= 100 or ident in prepared
                    or identity.get('node_type') != 'commander' or not isinstance(key, str) or len(key) != 64
                    or compute_fingerprint(bytes.fromhex(key)) != identity.get('fingerprint')):
                raise ValueError('Invalid or duplicate roster identity')
            deadline = row.get('expires_at')
            if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline <= now):
                raise ValueError('Temporary membership has expired')
            prepared[ident] = {'identity': identity, 'endpoint': endpoint(row['endpoint']), 'expires_at': deadline}
            existing = self.registry.get_node(ident)
            expected = self.identity.get_public_identity() if ident == self.identity.node_id else (existing.public_identity if existing else None)
            if expected and any(expected.get(k) != identity.get(k) for k in ('node_id', 'public_key_hex', 'fingerprint')):
                raise ValueError('Roster attempts to substitute a pinned identity')
        if self.identity.node_id not in prepared or sender not in prepared:
            raise ValueError('Roster omits this Knight or its authority')
        digest = hashlib.sha256(json.dumps(members, sort_keys=True).encode()).hexdigest()
        with self.lock:
            old = self._get('received')
            if old and (generation < old['generation'] or (generation == old['generation'] and digest != old['digest'])):
                raise ValueError('Stale or conflicting membership generation')
            # One write transaction preserves concurrent local revocations and
            # grants. Never replace a whole registry row read before this lock.
            with self.db.get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                for ident, row in prepared.items():
                    if ident == self.identity.node_id:
                        continue
                    current = conn.execute('SELECT node_state,connection_metadata_json FROM knights WHERE id=?', (ident,)).fetchone()
                    if current and current[0] not in APPROVED:
                        continue
                    if not current:
                        conn.execute('''INSERT INTO knights(id,role,status,node_state,capabilities_json,granted_capabilities_json,
                            health,is_local,last_heartbeat,public_identity_json,fingerprint,kingdom_id,connection_metadata_json,
                            created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (ident,'commander','APPROVED','APPROVED','[]','[]','unknown',0,0,json.dumps(row['identity']),
                             row['identity']['fingerprint'],self.identity.node_id,'{}',now,now))
                    meta = json.loads(current[1] or '{}') if current else {}
                    deadlines = [d for d in (meta.get('membership_expires_at'), row['expires_at']) if d is not None]
                    meta.update(kingdom_endpoint=row['endpoint'], mesh_authority=sender,
                                membership_expires_at=min(deadlines) if deadlines else None)
                    conn.execute('UPDATE knights SET connection_metadata_json=?,updated_at=? WHERE id=?', (json.dumps(meta),now,ident))
                for current in conn.execute('SELECT id,node_state,connection_metadata_json FROM knights').fetchall():
                    if (json.loads(current[2] or '{}').get('mesh_authority') == sender
                            and current[0] not in prepared and current[1] in APPROVED):
                        conn.execute("UPDATE knights SET node_state='REVOKED',status='REVOKED',health='unhealthy',updated_at=? WHERE id=?", (now,current[0]))
                conn.execute("INSERT INTO mesh_state VALUES('received',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                             (json.dumps({'generation':generation,'digest':digest,'received_at':now}),))
        if not old or generation != old['generation']:
            self.events.publish('cluster.mesh_membership_updated', {'authority_id': sender, 'generation': generation,
                                                                   'members': len(prepared)})
        return {'members': len(prepared), 'generation': generation}
