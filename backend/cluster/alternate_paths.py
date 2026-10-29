"""Opt-in IP paths for signed control probes; radio setup stays outside Kingdom.

No task, management or artifact RPC is retried or routed by this module. PAN
probes require a current paired BlueZ link and matching OS route/source address.
"""
import asyncio
import hashlib
import ipaddress
import json
import math
import time
from urllib.parse import urlsplit

import httpx

from backend.memory.portable_vault import identifier
from backend.cluster.federation_api import check_identity
from backend.cluster.transport import RPCSecureTransport


def local_endpoint(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in {'', '/'}):
        raise ValueError('Use an IP base URL without credentials, query or path')
    address = ipaddress.ip_address(parsed.hostname or '')  # Never resolve untrusted DNS.
    networks = ('127.0.0.0/8', '::1/128', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7')
    if not any(address in ipaddress.ip_network(n) for n in networks):
        raise ValueError('Use an explicit loopback, private LAN or private PAN address')
    if parsed.scheme == 'http' and not address.is_loopback:
        raise ValueError('Non-loopback paths require normal verified HTTPS')
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('Invalid port')
    return value.rstrip('/')


class AlternatePaths:
    def __init__(self, database, registry, identity, events):
        self.db, self.registry, self.identity, self.events = database, registry, identity, events
        self.slots = asyncio.Semaphore(2)
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS alternate_paths(peer TEXT PRIMARY KEY,state_json TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS path_probes(id TEXT PRIMARY KEY,peer TEXT NOT NULL,digest TEXT NOT NULL,state_json TEXT NOT NULL)')
            conn.commit()

    def peer(self, ident):
        node = self.registry.get_node(identifier(ident))
        if (not node or node.node_state not in {'APPROVED', 'CONNECTED', 'DISCONNECTED', 'RECONNECTING'}
                or not node.public_identity or node.public_identity.get('node_type') != 'commander'
                or node.fingerprint != node.public_identity.get('fingerprint')
                or node.node_id == self.identity.node_id):
            raise ValueError('Use an existing approved pinned peer identity')
        deadline = (node.connection_metadata or {}).get('membership_expires_at')
        if deadline is not None and (type(deadline) not in (int, float)
                                     or not math.isfinite(deadline) or deadline <= time.time()):
            raise ValueError('Temporary peer membership expired or is invalid')
        return node

    def get(self, ident):
        self.peer(ident)
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT state_json FROM alternate_paths WHERE peer=?', (ident,)).fetchone()
        return json.loads(row[0]) if row else {'peer': ident, 'revision': 0, 'paths': []}

    def configure(self, ident, paths, expected_revision):
        node = self.peer(ident)
        if type(expected_revision) is not int or not isinstance(paths, list) or len(paths) > 2:
            raise ValueError('Use at most two paths and a current revision')
        names, urls, clean = set(), set(), []
        for path in paths:
            if not isinstance(path, dict) or set(path) != {'name', 'endpoint', 'transport_hint'}:
                raise ValueError('Supply only name, endpoint and transport_hint')
            name = identifier(path['name'])
            url = local_endpoint(path['endpoint'])
            if name in names or url in urls or path['transport_hint'] not in {'lan', 'bluetooth_pan'}:
                raise ValueError('Use distinct names and endpoints with a LAN or PAN hint')
            names.add(name); urls.add(url)
            clean.append({'name': name, 'endpoint': url, 'transport_hint': path['transport_hint'],
                          'transport_evidence': 'owner_configured_not_radio_observed'})
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT state_json FROM alternate_paths WHERE peer=?', (ident,)).fetchone()
            revision = json.loads(row[0])['revision'] if row else 0
            if revision != expected_revision:
                raise ValueError('Path configuration changed')
            state = {'peer': ident, 'fingerprint': node.fingerprint, 'revision': revision + 1, 'paths': clean}
            conn.execute('INSERT INTO alternate_paths VALUES(?,?) ON CONFLICT(peer) DO UPDATE SET state_json=excluded.state_json', (ident, json.dumps(state)))
            conn.commit()
        self.events.publish('cluster.paths_configured', {'peer': ident, 'revision': state['revision'], 'count': len(clean)})
        return state

    def _reserve(self, peer, key, path, revision):
        identifier(key)
        ident = hashlib.sha256(f'{peer}:{key}'.encode()).hexdigest()
        digest = hashlib.sha256(json.dumps([path, revision], sort_keys=True).encode()).hexdigest()
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            prior = conn.execute('SELECT digest,state_json FROM path_probes WHERE id=?', (ident,)).fetchone()
            if prior:
                if prior[0] != digest:
                    raise ValueError('Probe key belongs to another path configuration')
                return ident, json.loads(prior[1])
            if conn.execute('SELECT count(*) FROM path_probes').fetchone()[0] >= 10000:
                raise ValueError('Probe ledger full; retain deduplication and request owner maintenance')
            state = {'id': ident, 'peer': peer, 'path': path['name'], 'status': 'outcome_unknown',
                     'reason': 'Reserved before transmission; interrupted sends are never automatically repeated',
                     'transport_hint': path['transport_hint'], 'transport_evidence': path['transport_evidence']}
            conn.execute('INSERT INTO path_probes VALUES(?,?,?,?)', (ident, peer, digest, json.dumps(state)))
            conn.commit()
        return ident, None

    def _finish(self, ident, state):
        with self.db.get_connection() as conn:
            conn.execute('UPDATE path_probes SET state_json=? WHERE id=?', (json.dumps(state), ident))
            conn.commit()
        self.events.publish('cluster.path_probe', {'peer': state['peer'], 'path': state['path'], 'status': state['status']})
        return state

    @staticmethod
    async def _json(client, method, url, payload=None):
        async with client.stream(method, url, json=payload) as response:
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError('Redirects are not alternate peer paths')
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 65536:
                    raise ValueError('Peer control response exceeds its budget')
            value = json.loads(body)
            if not isinstance(value, dict):
                raise ValueError('Expected a signed peer response object')
            return value

    async def probe(self, peer, key, path_name):
        # Bound independent control requests, not duplicate execution across paths.
        async with self.slots:
            node = await asyncio.to_thread(self.peer, peer)
            config = await asyncio.to_thread(self.get, peer)
            if config.get('fingerprint') != node.fingerprint:
                raise ValueError('Peer identity changed; owner must review its path configuration')
            path = next((p for p in config['paths'] if p['name'] == path_name), None)
            if path is None:
                raise ValueError('Use an explicitly owner-configured path')
            ident, cached = await asyncio.to_thread(self._reserve, peer, key, path, config['revision'])
            if cached is not None:
                return cached
            state = {'id': ident, 'peer': peer, 'path': path_name, 'status': 'not_sent',
                     'transport_hint': path['transport_hint'], 'transport_evidence': path['transport_evidence']}
            started, sent = time.monotonic(), False
            try:
                pan = None
                options = {}
                if path['transport_hint'] == 'bluetooth_pan':
                    from backend.cluster.bluetooth_pan import route_observation
                    pan = await asyncio.to_thread(route_observation, path['endpoint'])
                    options['transport'] = httpx.AsyncHTTPTransport(local_address=pan['local_address'], retries=0, trust_env=False)
                    state['transport_evidence'] = pan['evidence']
                    state['route_observation'] = pan
                async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False, **options) as client:
                    advertised = await self._json(client, 'GET', path['endpoint'] + '/nodes/identity')
                    check_identity(advertised, node.public_identity, self.identity)
                    # Revalidate locally after network delay; remote policy also remains authoritative.
                    current = await asyncio.to_thread(self.peer, peer)
                    if current.fingerprint != config['fingerprint'] or await asyncio.to_thread(self.get, peer) != config:
                        raise ValueError('Peer or owner path configuration changed')
                    if pan is not None:
                        current_route = await asyncio.to_thread(route_observation, path['endpoint'])
                        if any(current_route[k] != pan[k] for k in ('interface', 'device_address', 'local_address')):
                            raise ValueError('Bluetooth PAN route changed before transmission')
                    transport = RPCSecureTransport(self.identity)
                    message = transport.create_signed_message(peer, 'heartbeat', {'node_id': self.identity.node_id})
                    sent = True
                    result = await self._json(client, 'POST', path['endpoint'] + '/nodes/rpc', message)
                    verified = await asyncio.to_thread(transport.verify_and_unwrap_message, result.get('inventory_proof'), expected_target_id=self.identity.node_id)
                    if (not verified.get('valid') or verified.get('sender_id') != peer
                            or verified.get('msg_type') != 'inventory_snapshot'
                            or verified.get('payload', {}).get('node_id') != peer
                            or verified.get('payload', {}).get('request_id') != message['msg_id']
                            or result.get('status') != 'ok' or result.get('ping', {}).get('success') is not True):
                        raise ValueError('No current pinned signed control receipt')
                    await asyncio.to_thread(self.peer, peer)  # A receipt cannot restore revoked authority.
                    state.update(status='verified_control_exchange', request_id=message['msg_id'],
                                 response_id=verified['msg_id'], elapsed_ms=round((time.monotonic()-started)*1000, 2),
                                 observed_at=time.time(),
                                 scope='Signed control exchange; route observations are not packet capture, task execution or artifact transfer proof')
            except (httpx.HTTPError, ValueError, TypeError, KeyError, OSError):
                state.update(status='outcome_unknown' if sent else 'not_sent',
                             reason='No verified outcome; this key is retained and will not be retransmitted')
            except asyncio.CancelledError:
                state.update(status='outcome_unknown', reason='Cancelled; retained key prevents uncertain retransmission')
                await asyncio.to_thread(self._finish, ident, state)
                raise
            return await asyncio.to_thread(self._finish, ident, state)
