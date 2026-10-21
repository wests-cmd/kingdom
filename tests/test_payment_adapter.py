import asyncio
import json
import pytest
import httpx
from backend.integrations.payments import PaymentService
from backend.runtime.engine import RuntimeEngine
from backend.runtime.policy import ExecutionPolicy
from backend.security.approval_engine import ApprovalEngine
from backend.storage.db import Database


@pytest.fixture
def payment(tmp_path):
    database = Database(tmp_path/'payment.db')
    engine = RuntimeEngine()
    engine.execution_policy = ExecutionPolicy(database)
    engine.security.approvals = ApprovalEngine(database=database)
    return PaymentService(database, engine, tmp_path/'vault')


def configured(payment, level=5):
    payment.configure(True, 'test', 'usd', 1000, 'sk_test_fixture_only')
    payment.engine.set_autonomy(level)
    return payment.prepare('fixture-payment-1', 500, 'usd', 'Fixture only')


def test_disconnected_default_and_secrets_are_write_only(payment):
    assert payment.settings()['enabled'] is False
    result = payment.configure(True, 'test', 'usd', 1000, 'sk_test_fixture_only')
    assert result['has_credentials'] is True and 'api_key' not in result
    assert b'sk_test_fixture_only' not in payment.db.db_path.read_bytes()
    with pytest.raises(ValueError, match='match'):
        payment.configure(True, 'live', 'usd', 1000, 'sk_test_fixture_only')


def test_durable_request_identity_rejects_changed_details(payment):
    record = configured(payment)
    assert payment.prepare('fixture-payment-1', 500, 'usd', 'Fixture only')['id'] == record['id']
    with pytest.raises(ValueError, match='different'):
        payment.prepare('fixture-payment-1', 501, 'usd', 'Fixture only')
    restored = PaymentService(payment.db, payment.engine, payment.db.db_path.parent/'vault')
    assert restored.get(record['id'])['amount_minor'] == 500


@pytest.mark.asyncio
async def test_owner_limit_blocks_before_network(payment):
    configured(payment)
    record = payment.prepare('too-large-fixture', 1001, 'usd', 'Fixture only')
    with pytest.raises(ValueError, match='limit'):
        await payment.execute(record['id'])
    assert payment.get(record['id'])['status'] == 'prepared'


@pytest.mark.asyncio
async def test_l4_requests_exact_approval_without_provider_calls(payment):
    record = configured(payment, 4)
    result = await payment.execute(record['id'])
    assert result['status'] == 'waiting_approval'
    approval = payment.engine.security.approvals.get_request(result['approval_id'])
    assert approval['parameters']['payment_id'] == record['id']


@pytest.mark.asyncio
async def test_provider_record_is_filtered_and_never_repeated(payment, monkeypatch):
    record = configured(payment)
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={'id':'pi_fixture','amount':500,'currency':'usd',
            'livemode':False,'status':'requires_payment_method','client_secret':'must-not-escape'})
    real_client = httpx.AsyncClient
    monkeypatch.setattr('backend.integrations.payments.httpx.AsyncClient',
        lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    result = await payment.execute(record['id'])
    assert result['status'] == 'provider_recorded' and result['money_moved'] is False
    assert 'must-not-escape' not in json.dumps(result)
    assert calls[0].headers['Idempotency-Key'] == 'kingdom-payment-' + record['id']
    await payment.execute(record['id'])
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_unknown_provider_outcome_requires_reconciliation_not_retry(payment, monkeypatch):
    record = configured(payment)
    calls = []
    def respond(request):
        calls.append(request)
        raise httpx.ReadTimeout('private-provider-detail', request=request)
    real_client = httpx.AsyncClient
    monkeypatch.setattr('backend.integrations.payments.httpx.AsyncClient',
        lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    assert (await payment.execute(record['id']))['status'] == 'reconciliation_required'
    await payment.execute(record['id'])
    assert len(calls) == 1
    assert 'private-provider-detail' not in json.dumps(payment.get(record['id']))


@pytest.mark.asyncio
async def test_concurrent_execution_claims_once(payment, monkeypatch):
    record = configured(payment)
    calls = []
    async def respond(request):
        calls.append(request)
        await asyncio.sleep(.02)
        return httpx.Response(200, json={'id':'pi_fixture','amount':500,'currency':'usd','livemode':False,'status':'requires_payment_method'})
    real_client = httpx.AsyncClient
    monkeypatch.setattr('backend.integrations.payments.httpx.AsyncClient',
        lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    await asyncio.gather(payment.execute(record['id']), payment.execute(record['id']))
    assert len(calls) == 1
