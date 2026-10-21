"""Optional Stripe payment intents with durable identity and exact authorization.

No account, card collection, funds transfer or credentials are invented here.
Only owner-configured Stripe accounts are supported. No production simulator.
"""
import hashlib
import json
import re
import time
from uuid import uuid4

import httpx

from backend.models.profiles import ModelProfiles


class PaymentService:
    def __init__(self, database, engine, vault_root='data/secrets'):
        self.db, self.engine = database, engine
        self.cipher = ModelProfiles(database, root=vault_root).cipher
        with database.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS payment_settings (id INTEGER PRIMARY KEY, config TEXT NOT NULL, secret BLOB)')
            conn.execute('CREATE TABLE IF NOT EXISTS payment_requests (id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, body TEXT NOT NULL, state TEXT NOT NULL)')
            conn.commit()

    def settings(self, private=False):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT config,secret FROM payment_settings WHERE id=1').fetchone()
        if not row:
            return {'provider': 'stripe', 'enabled': False, 'mode': 'test', 'has_credentials': False,
                    'currency': 'usd', 'max_amount_minor': 1000}
        result = json.loads(row['config'])
        result['has_credentials'] = bool(row['secret'])
        if private:
            result['api_key'] = self.cipher.decrypt(row['secret']).decode() if row['secret'] else ''
        return result

    def configure(self, enabled, mode, currency, max_amount_minor, api_key=None):
        if type(enabled) is not bool or mode not in {'test', 'live'} or not re.fullmatch('[a-z]{3}', currency):
            raise ValueError('Choose test/live mode and a three-letter currency')
        if type(max_amount_minor) is not int or not 1 <= max_amount_minor <= 100000000:
            raise ValueError('Set a positive maximum amount in currency minor units')
        previous = self.settings(private=True)
        key = previous.get('api_key', '') if api_key is None else api_key
        if key and (not isinstance(key, str) or not key.startswith(('sk_' + mode + '_', 'rk_' + mode + '_'))):
            raise ValueError('Credential does not match selected Stripe mode')
        if enabled and not key:
            raise ValueError('Connect your provider credential before enabling payments')
        revision = uuid4().hex
        config = {'provider': 'stripe', 'enabled': enabled, 'mode': mode, 'currency': currency,
                  'max_amount_minor': max_amount_minor, 'revision': revision}
        with self.db.get_connection() as conn:
            conn.execute('INSERT INTO payment_settings VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET config=excluded.config,secret=excluded.secret',
                         (json.dumps(config), self.cipher.encrypt(key.encode()) if key else None))
            conn.commit()
        self.engine.events.publish('payments.configuration_changed', {'enabled': enabled, 'mode': mode})
        return self.settings()

    def prepare(self, request_key, amount_minor, currency, purpose, payment_method=None, confirm=False):
        if not re.fullmatch('[A-Za-z0-9_-]{8,100}', request_key):
            raise ValueError('Use a stable request key of 8–100 characters')
        if type(amount_minor) is not int or amount_minor <= 0 or not re.fullmatch('[a-z]{3}', currency):
            raise ValueError('Use a positive integer amount in currency minor units')
        if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 300:
            raise ValueError('A payment purpose is required')
        if type(confirm) is not bool or (payment_method and not re.fullmatch('pm_[A-Za-z0-9_]{1,200}', payment_method)):
            raise ValueError('Use a provider payment-method ID, never raw card details')
        if confirm and not payment_method:
            raise ValueError('Confirmation needs an existing provider payment-method ID')
        config = self.settings()
        body = {'amount_minor': amount_minor, 'currency': currency, 'purpose': purpose,
                'payment_method': payment_method, 'confirm': confirm,
                'configuration_revision': config.get('revision'), 'mode': config['mode']}
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT body,state FROM payment_requests WHERE request_key=?', (request_key,)).fetchone()
            if row:
                if json.loads(row['body']) != body:
                    raise ValueError('Request key already belongs to different payment details or configuration')
                return json.loads(row['state'])
            state = {'id': uuid4().hex, 'status': 'prepared', 'amount_minor': amount_minor,
                     'currency': currency, 'purpose': purpose, 'mode': config['mode'],
                     'confirm_requested': confirm, 'created_at': time.time(), 'approval_id': None}
            conn.execute('INSERT INTO payment_requests VALUES(?,?,?,?)',
                         (state['id'], request_key, json.dumps(body, sort_keys=True), json.dumps(state)))
            conn.commit()
        self.engine.events.publish('payments.prepared', {'id': state['id'], 'mode': state['mode']})
        return state

    def get(self, ident):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT state FROM payment_requests WHERE id=?', (ident,)).fetchone()
        if not row:
            raise KeyError('Payment request not found')
        return json.loads(row['state'])

    def list(self):
        with self.db.get_connection() as conn:
            return [json.loads(row['state']) for row in conn.execute('SELECT state FROM payment_requests ORDER BY rowid DESC LIMIT 100')]

    def save(self, state):
        with self.db.get_connection() as conn:
            conn.execute('UPDATE payment_requests SET state=? WHERE id=?', (json.dumps(state), state['id']))
            conn.commit()

    async def execute(self, ident):
        # Durable claim protects against simultaneous requests and process restarts.
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT body,state FROM payment_requests WHERE id=?', (ident,)).fetchone()
            if not row:
                raise KeyError('Payment request not found')
            body, state = json.loads(row['body']), json.loads(row['state'])
            if state['status'] not in {'prepared', 'waiting_approval'}:
                return state
            config = self.settings(private=True)
            if not config['enabled'] or not config.get('api_key'):
                raise ValueError('Payment provider is not connected and enabled')
            if body['configuration_revision'] != config['revision']:
                raise ValueError('Provider settings changed; prepare a new reviewed request')
            if body['currency'] != config['currency'] or body['amount_minor'] > config['max_amount_minor']:
                raise ValueError('Payment exceeds the owner-configured currency or amount limit')
            level = self.engine.execution_policy.get()['level']
            if level == 0:
                raise ValueError('Runtime policy is paused')
            digest = hashlib.sha256(row['body'].encode()).hexdigest()
            state.update(status='authorizing')
            conn.execute('UPDATE payment_requests SET state=? WHERE id=?', (json.dumps(state), ident))
            conn.commit()
        # Approval persistence uses the same database; do not hold a write lock.
        auth = self.engine.security.authorize(actor_id='owner', capability='finance.execute',
            operation='Execute payment ' + ident,
            token=self.engine.security.nodes.get_node('owner')['token'],
            approval_id=state.get('approval_id'), parameters={'payment_id': ident, 'details_sha256': digest},
            require_human_approval=level == 2)
        if not auth['authorized']:
            state.update(status='waiting_approval', approval_id=auth.get('approval_id'))
        else:
            state.update(status='submitting', submitted_at=time.time())
        self.save(state)
        if state['status'] != 'submitting':
            return state
        form = {'amount': str(body['amount_minor']), 'currency': body['currency'],
                'description': body['purpose'], 'confirm': str(body['confirm']).lower(),
                'metadata[kingdom_request]': ident}
        if body['payment_method']:
            form['payment_method'] = body['payment_method']
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                response = await client.post('https://api.stripe.com/v1/payment_intents', data=form,
                    auth=(config['api_key'], ''), headers={'Idempotency-Key': 'kingdom-payment-' + ident})
                response.raise_for_status()
                result = response.json()
            if not str(result.get('id', '')).startswith('pi_') or result.get('amount') != body['amount_minor'] or result.get('currency') != body['currency'] or result.get('livemode') is not (config['mode'] == 'live'):
                raise ValueError('Provider result differs from the authorized payment')
            # Do not return client_secret, card details or provider error payloads.
            state.update(status='provider_recorded', provider_id=result['id'],
                         provider_status=result.get('status'), completed_at=time.time(),
                         money_moved=result.get('status') == 'succeeded' and config['mode'] == 'live')
        except Exception:
            # Timeout is not proof of failure: never blindly repeat a charge.
            state.update(status='reconciliation_required', error='Provider outcome uncertain; inspect Stripe using this Kingdom request ID before any new payment.')
        self.save(state)
        self.engine.events.publish('payments.result', {'id': ident, 'status': state['status'], 'mode': config['mode']})
        return state
