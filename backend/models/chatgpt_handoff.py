"""Operator-only move of one Kingdom OAuth session between approved hosts.

No HTTP route or model tool exposes this module. Transfer bundles are secrets;
use an authenticated private channel and give the recipient the digest separately.
"""
import hashlib
import hmac
import json
import secrets
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.models.chatgpt_plan import ChatGPTPlanError, REQUIRED_SCOPES

MAX_BUNDLE = 160 * 1024


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class PublicAccount(Strict):
    id: str = Field(pattern=r'^[a-f0-9]{32}$')
    client_id: str = Field(pattern=r'^oaiapp_[A-Za-z0-9_-]{1,190}$')
    subject: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=320)
    connected: bool
    expires_at: float = Field(allow_inf_nan=False)
    scopes: list[str] = Field(max_length=30)
    refresh_available: bool
    refresh_state: str = Field(max_length=40)
    session_generation: str = Field(pattern=r'^[a-f0-9]{32}$')
    revision: int = Field(ge=1)


class Credentials(Strict):
    access_token: str = Field(min_length=1, max_length=32000)
    refresh_token: str = Field(min_length=1, max_length=32000)
    id_token: str = Field(min_length=1, max_length=64000)
    earliest_refresh_at: float | None = Field(default=None, allow_inf_nan=False)


class Bundle(Strict):
    format: str = Field(pattern=r'^kingdom.chatgpt-host-move.v1$')
    transfer_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    source_host: str = Field(min_length=1, max_length=300)
    target_host: str = Field(min_length=1, max_length=300)
    created_at: float = Field(allow_inf_nan=False)
    expires_at: float = Field(allow_inf_nan=False)
    account: PublicAccount
    credentials: Credentials
    acknowledgement_key: str = Field(pattern=r'^[a-f0-9]{64}$')
    activation_public_key: str = Field(pattern=r'^[a-f0-9]{64}$')


class Receipt(Strict):
    kind: str = Field(pattern=r'^(imported|activate)$')
    transfer_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    bundle_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_host: str = Field(min_length=1, max_length=300)
    target_host: str = Field(min_length=1, max_length=300)
    proof: str = Field(min_length=64, max_length=128, pattern=r'^[a-f0-9]+$')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def validate(model, value):
    try:
        if len(canonical(value)) > MAX_BUNDLE:
            raise ValueError()
        return model.model_validate(value).model_dump(exclude_none=True)
    except (ValueError, TypeError, ValidationError) as error:
        raise ChatGPTPlanError('handoff_invalid') from error


def bundle_digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def receipt_fields(kind, record):
    return {key: value for key, value in dict(kind=kind, transfer_id=record['transfer_id'],
        bundle_sha256=record['bundle_sha256'], source_host=record['source_host'],
        target_host=record['target_host']).items()}


class ChatGPTHostHandoff:
    """Four durable steps; uncertain outcomes remain fenced, never auto-rollback."""

    def __init__(self, connection):
        self.connection = connection
        with connection.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS chatgpt_host_handoffs(transfer_id TEXT PRIMARY KEY, state_json TEXT NOT NULL, secret BLOB)')
            conn.commit()

    def _row(self, conn, transfer_id):
        row = conn.execute('SELECT state_json,secret FROM chatgpt_host_handoffs WHERE transfer_id=?', (transfer_id,)).fetchone()
        if not row:
            raise ChatGPTPlanError('handoff_unknown')
        try:
            return json.loads(row[0]), json.loads(self.connection.cipher.decrypt(row[1])) if row[1] else None
        except Exception as error:
            raise ChatGPTPlanError('credential_store_unavailable') from error

    def status(self, transfer_id):
        """Public recovery checkpoint; no credential or private signing material."""
        with self.connection.db.get_connection() as conn:
            state, _ = self._row(conn, transfer_id)
        return {key:state[key] for key in ('transfer_id','source_host','target_host','bundle_sha256','phase','acknowledgement','activation') if key in state}

    def _store(self, conn, state, secret=None):
        encrypted = self.connection.cipher.encrypt(canonical(secret)) if secret is not None else None
        conn.execute('INSERT INTO chatgpt_host_handoffs VALUES(?,?,?) ON CONFLICT(transfer_id) DO UPDATE SET state_json=excluded.state_json,secret=excluded.secret',
            (state['transfer_id'], json.dumps(state), encrypted))

    def _meta(self, conn):
        return json.loads(conn.execute('SELECT value_json FROM chatgpt_plan_meta WHERE id=1').fetchone()[0])

    def _write_meta(self, conn, meta, **changes):
        meta.update(changes)
        meta['revision'] += 1
        conn.execute('UPDATE chatgpt_plan_meta SET value_json=? WHERE id=1', (json.dumps(meta),))

    def _no_pending(self, conn):
        row = conn.execute('SELECT expires,phase FROM chatgpt_plan_pending WHERE id=1').fetchone()
        if row and (row[0] > self.connection.clock() or row[1] == 'exchanging'):
            raise ChatGPTPlanError('handoff_sign_in_pending')

    def _publish(self, ident, phase):
        self.connection.publish('chatgpt_plan.host_handoff', {'transfer_id':ident, 'phase':phase})

    def prepare(self, *, target_host_id):
        c = self.connection
        now = c.clock()
        with c.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            meta = self._meta(conn)
            self._no_pending(conn)
            if (not isinstance(target_host_id, str) or not 1 <= len(target_host_id) <= 300
                    or target_host_id == meta['host_id']):
                raise ChatGPTPlanError('handoff_host_invalid')
            public, secret = c._account(meta.get('active_account'))
            if (not public.get('connected') or public.get('refresh_state') != 'idle'
                    or public.get('expires_at', 0) <= now+60 or not secret
                    or not REQUIRED_SCOPES <= set(public['scopes'])):
                raise ChatGPTPlanError('handoff_account_unavailable')
            signing = Ed25519PrivateKey.generate()
            seed = signing.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()).hex()
            key = signing.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
            parcel = validate(Bundle, dict(format='kingdom.chatgpt-host-move.v1', transfer_id=uuid4().hex,
                source_host=meta['host_id'], target_host=target_host_id, created_at=now,
                expires_at=min(now+300, public['expires_at']), account=public, credentials=secret,
                acknowledgement_key=secrets.token_hex(32), activation_public_key=key))
            state = dict(transfer_id=parcel['transfer_id'], source_host=parcel['source_host'], target_host=target_host_id,
                bundle_sha256=bundle_digest(parcel), phase='exported', account_id=public['id'])
            public.update(refresh_state='handoff_exported', session_generation=uuid4().hex, revision=public['revision']+1)
            conn.execute('UPDATE chatgpt_plan_accounts SET public_json=? WHERE id=?', (json.dumps(public), public['id']))
            state['account_version'] = public['revision']
            self._store(conn, state, {'bundle':parcel, 'signing_seed':seed})
            self._write_meta(conn, meta, enabled=False)
            conn.commit()
        self._publish(state['transfer_id'], 'exported')
        return parcel

    def import_bundle(self, value, *, expected_sha256):
        parcel = validate(Bundle, value)
        if not isinstance(expected_sha256, str) or not hmac.compare_digest(bundle_digest(parcel), expected_sha256):
            raise ChatGPTPlanError('handoff_digest_mismatch')
        c = self.connection
        public, secret = parcel['account'], parcel['credentials']
        now = c.clock()
        if (parcel['source_host'] == parcel['target_host'] or not now-300 <= parcel['created_at'] <= now+30
                or not now < parcel['expires_at'] <= parcel['created_at']+300
                or public['expires_at'] <= now+60 or not public['connected'] or public['refresh_state'] != 'idle'
                or not public['refresh_available'] or not REQUIRED_SCOPES <= set(public['scopes'])):
            raise ChatGPTPlanError('handoff_expired_or_unavailable')
        # Standard discovery/JWKS validation is intentionally outside the SQLite
        # transaction. Every local conflict is rechecked immediately before commit.
        claims = c._identity(secret['id_token'], public['client_id'], subject=public['subject'])
        expected_id = hashlib.sha256((public['client_id']+'\0'+claims['sub']).encode()).hexdigest()[:32]
        if public['id'] != expected_id:
            raise ChatGPTPlanError('identity_invalid')
        state = dict(transfer_id=parcel['transfer_id'], source_host=parcel['source_host'], target_host=parcel['target_host'],
            bundle_sha256=expected_sha256, phase='pending', account_id=public['id'],
            activation_public_key=parcel['activation_public_key'])
        unsigned = receipt_fields('imported', state)
        ack = {**unsigned, 'proof':hmac.new(bytes.fromhex(parcel['acknowledgement_key']), canonical(unsigned), hashlib.sha256).hexdigest()}
        with c.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            now = c.clock()
            if (not now-300 <= parcel['created_at'] <= now+30
                    or not now < parcel['expires_at'] <= parcel['created_at']+300
                    or public['expires_at'] <= now+60 or claims['exp'] <= now):
                raise ChatGPTPlanError('handoff_expired_or_unavailable')
            meta = self._meta(conn)
            if meta['host_id'] != parcel['target_host']:
                raise ChatGPTPlanError('handoff_host_invalid')
            self._no_pending(conn)
            existing = conn.execute('SELECT state_json FROM chatgpt_host_handoffs WHERE transfer_id=?', (state['transfer_id'],)).fetchone()
            if existing:
                saved = json.loads(existing[0])
                if saved.get('bundle_sha256') == expected_sha256 and saved.get('phase') in ('pending','active'):
                    return saved['acknowledgement']
                raise ChatGPTPlanError('handoff_conflict')
            if conn.execute('SELECT 1 FROM chatgpt_plan_accounts LIMIT 1').fetchone() or meta.get('active_account'):
                raise ChatGPTPlanError('handoff_target_not_empty')
            public = {**public, 'refresh_state':'handoff_pending', 'session_generation':uuid4().hex, 'revision':public['revision']+1}
            conn.execute('INSERT INTO chatgpt_plan_accounts VALUES(?,?,?)',
                (public['id'], json.dumps(public), c.cipher.encrypt(canonical(secret))))
            state.update(account_version=public['revision'], acknowledgement=ack)
            self._store(conn, state)
            self._write_meta(conn, meta, active_account=public['id'], enabled=False, model=None, last_error=None)
            conn.commit()
        self._publish(state['transfer_id'], 'pending')
        return ack

    def export_existing(self, transfer_id):
        """Explicit operator recovery of the SAME still-fenced export, no renewal."""
        with self.connection.db.get_connection() as conn:
            state, secret = self._row(conn, transfer_id)
            if state['phase'] != 'exported' or not secret or secret['bundle']['expires_at'] <= self.connection.clock():
                raise ChatGPTPlanError('handoff_expired_or_unavailable')
            public, _ = self.connection._account(state['account_id'])
            if public['refresh_state'] != 'handoff_exported' or public['revision'] != state['account_version']:
                raise ChatGPTPlanError('handoff_conflict')
            return secret['bundle']

    def complete(self, value):
        ack = validate(Receipt, value)
        if ack['kind'] != 'imported':
            raise ChatGPTPlanError('handoff_invalid')
        c = self.connection
        with c.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            state, secret = self._row(conn, ack['transfer_id'])
            if state['phase'] == 'completed' and state.get('acknowledgement') == ack:
                return state['activation']
            if state['phase'] != 'exported' or not secret or receipt_fields('imported', state) != {k:v for k,v in ack.items() if k != 'proof'}:
                raise ChatGPTPlanError('handoff_conflict')
            expected = hmac.new(bytes.fromhex(secret['bundle']['acknowledgement_key']), canonical(receipt_fields('imported', state)), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, ack['proof']):
                raise ChatGPTPlanError('handoff_proof_invalid')
            public, _ = c._account(state['account_id'])
            if public['refresh_state'] != 'handoff_exported' or public['revision'] != state['account_version']:
                raise ChatGPTPlanError('handoff_conflict')
            unsigned = receipt_fields('activate', state)
            key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(secret['signing_seed']))
            activation = {**unsigned, 'proof':key.sign(canonical(unsigned)).hex()}
            public.update(connected=False, refresh_available=False, refresh_state='handoff_moved', revision=public['revision']+1)
            conn.execute('UPDATE chatgpt_plan_accounts SET public_json=?,secret=NULL WHERE id=?', (json.dumps(public), public['id']))
            state.update(phase='completed', acknowledgement=ack, activation=activation)
            self._store(conn, state)  # Erase the exported duplicate credential record too.
            meta = self._meta(conn)
            if meta.get('active_account') == public['id']:
                self._write_meta(conn, meta, active_account=None, enabled=False, model=None)
            conn.commit()
        self._publish(state['transfer_id'], 'completed')
        return activation

    def activate(self, value):
        receipt = validate(Receipt, value)
        if receipt['kind'] != 'activate':
            raise ChatGPTPlanError('handoff_invalid')
        c = self.connection
        with c.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            state, _ = self._row(conn, receipt['transfer_id'])
            unsigned = receipt_fields('activate', state)
            if unsigned != {k:v for k,v in receipt.items() if k != 'proof'}:
                raise ChatGPTPlanError('handoff_conflict')
            try:
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(state['activation_public_key'])).verify(bytes.fromhex(receipt['proof']), canonical(unsigned))
            except (ValueError, InvalidSignature) as error:
                raise ChatGPTPlanError('handoff_proof_invalid') from error
            if state['phase'] == 'active' and state.get('activation') == receipt:
                return {'activated':True, 'enabled':False, 'transfer_id':state['transfer_id']}
            if state['phase'] != 'pending':
                raise ChatGPTPlanError('handoff_conflict')
            meta = self._meta(conn)
            self._no_pending(conn)
            public, secret = c._account(state['account_id'])
            if (meta['host_id'] != state['target_host'] or meta['enabled'] or meta['active_account'] != public['id']
                    or public['refresh_state'] != 'handoff_pending' or public['revision'] != state['account_version']
                    or public['expires_at'] <= c.clock()+60 or not secret):
                raise ChatGPTPlanError('handoff_conflict')
            public.update(refresh_state='idle', revision=public['revision']+1)
            conn.execute('UPDATE chatgpt_plan_accounts SET public_json=? WHERE id=?', (json.dumps(public), public['id']))
            state.update(phase='active', activation=receipt)
            self._store(conn, state)
            self._write_meta(conn, meta, enabled=False, model=None)
            conn.commit()
        self._publish(state['transfer_id'], 'active')
        return {'activated':True, 'enabled':False, 'transfer_id':state['transfer_id']}
