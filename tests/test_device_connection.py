from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from fastapi.testclient import TestClient
from backend.main import app
from backend.api import engine
from backend.cluster.identity import KnightIdentity
from backend.cluster.mobile_pairing import mobile_pairing_manager as manager
from backend.cluster.node_registry import node_registry
from tests.auth_support import owner_client


def payload(challenge):
    identity = KnightIdentity('test-device-' + uuid4().hex, 'Acceptance device')
    message = f'{challenge["code"]}:{identity.node_id}:{challenge["kingdom_id"]}'.encode()
    return {'code': challenge['code'], 'device_id': identity.node_id,
            'device_name': 'Acceptance device', 'device_public_key_hex': identity.public_bytes.hex(),
            'signature': identity.sign_message(message).hex()}


def test_pairing_without_owner_and_session_never_grants_owner_access():
    owner = owner_client(app)
    visitor = TestClient(app)
    assert visitor.post('/mobile/challenge').status_code in {401, 403}
    challenge = owner.post('/mobile/challenge').json()
    body = payload(challenge)
    result = visitor.post('/mobile/pair', json=body)
    assert result.status_code == 200
    token = result.json()['session_token']
    device = TestClient(app, headers={'Authorization': 'Bearer ' + token})
    state = device.post('/mobile/session/status', json={}).json()
    assert state['device_state'] == 'PENDING_APPROVAL'
    assert state['capabilities'] == []
    assert device.get('/tasks').status_code == 401
    assert device.post('/mobile/challenge').status_code == 401
    assert visitor.post('/mobile/pair', json=body).status_code == 400
    assert owner.post(f'/mobile/{body["device_id"]}/approve').status_code == 200
    assert device.post('/mobile/session/status', json={}).json()['device_state'] == 'APPROVED'
    assert owner.post(f'/mobile/{body["device_id"]}/revoke').status_code == 200
    assert device.post('/mobile/session/status', json={}).status_code == 401


def test_pairing_rejects_malformed_expired_and_duplicate_identity():
    challenge = manager.create_pairing_challenge()
    body = payload(challenge)
    assert not manager.process_mobile_pairing({**body, 'signature': 'not-hex'})['success']
    manager._pairing_challenges[challenge['code']]['expires_at'] = 0
    assert not manager.process_mobile_pairing(body)['success']
    first = manager.create_pairing_challenge()
    duplicate = payload(first)
    assert manager.process_mobile_pairing(duplicate)['success']
    second = manager.create_pairing_challenge()
    assert not manager.process_mobile_pairing({**duplicate, 'code': second['code']})['success']


def test_pairing_code_is_consumed_atomically_and_not_logged():
    challenge = manager.create_pairing_challenge()
    body = payload(challenge)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(manager.process_mobile_pairing, [body, body]))
    assert sum(result['success'] for result in results) == 1
    for event in engine.events.history(200):
        if event['event_type'] == 'mobile.pairing_challenge_created':
            assert 'code' not in event['payload']


def test_events_filter_and_real_knight_identity_fields():
    client = owner_client(app)
    engine.events.publish('acceptance.match', {'value': 1})
    engine.events.publish('acceptance.other', {'value': 2})
    events = client.get('/events?event_type=acceptance.match').json()
    assert events and all(event['event_type'] == 'acceptance.match' for event in events)
    knights = client.get('/knights').json()['knights']
    assert knights and all(k['id'] and k['role'] and k['is_local'] and k['capabilities'] for k in knights)
