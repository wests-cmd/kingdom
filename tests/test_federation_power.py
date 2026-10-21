"""Signed RPC power reports cross the real authentication and validation boundaries."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException


@pytest.fixture
def signed_rpc(monkeypatch, tmp_path):
    # Keep runtime initialization and the durable replay ledger in test storage.
    import backend.storage.db as storage
    from backend.storage.db import Database

    isolated_db = Database(tmp_path / 'rpc.db')
    # Earlier collection may have bound this singleton in repositories. Update
    # its path before changing cwd so those references share initialized storage.
    monkeypatch.setattr(storage.db, 'db_path', isolated_db.db_path)
    monkeypatch.chdir(tmp_path)
    import backend.api as api
    from backend.cluster.identity import KingdomIdentity
    from backend.cluster.transport import RPCSecureTransport, node_registry

    receiver = KingdomIdentity('KG-power-receiver')
    sender = KingdomIdentity('KG-power-sender')
    monkeypatch.setattr(api.KingdomIdentity, 'get_or_create', lambda: receiver)
    peer = SimpleNamespace(kingdom_id=receiver.node_id, node_state='CONNECTED',
                           public_identity=sender.get_public_identity())
    monkeypatch.setattr(node_registry, 'get_node', lambda node_id: peer if node_id == sender.node_id else None)
    ping = Mock(return_value={'success': True})
    monkeypatch.setattr(api.heartbeat_manager, 'ping', ping)
    monkeypatch.setattr('backend.cluster.apprentice_inventory.local_inventory',
                        lambda: {'version': 1, 'apprentices': []})
    monkeypatch.setattr('backend.cluster.local_load.local_load_metrics', lambda: {})

    def sign(metrics, msg_type='heartbeat'):
        return RPCSecureTransport(sender).create_signed_message(receiver.node_id, msg_type, {
            'node_id': sender.node_id, 'load_metrics': deepcopy(metrics),
            'apprentice_inventory': {'version': 1, 'apprentices': []}})

    def receive(message):
        return api.handle_cluster_rpc(api.RPCMessageRequest(**message))

    return sign, receive, ping, sender.node_id


@pytest.mark.parametrize('msg_type', ['heartbeat', 'inventory_snapshot'])
@pytest.mark.parametrize('power', [
    {'status': 'battery', 'battery_percent': 12.5, 'plugged': False},
    {'status': 'battery', 'battery_percent': 100, 'plugged': True},
    {'status': 'unknown', 'battery_percent': None, 'plugged': None},
    {'status': 'no_battery', 'battery_percent': None, 'plugged': None},
])
def test_signed_power_survives_to_heartbeat_manager(signed_rpc, msg_type, power):
    sign, receive, ping, sender_id = signed_rpc
    metrics = {'cpu_percent': 27.5, 'memory_percent': 41, 'power': power}
    assert receive(sign(metrics, msg_type))['status'] == 'ok'
    ping.assert_called_once_with(sender_id, load_metrics=metrics,
                                apprentice_inventory={'version': 1, 'apprentices': []})


@pytest.mark.parametrize('power', [None, [], {},
    {'status': 'battery', 'battery_percent': -1, 'plugged': False},
    {'status': 'battery', 'battery_percent': 101, 'plugged': True},
    {'status': 'battery', 'battery_percent': True, 'plugged': True},
    {'status': 'battery', 'battery_percent': '50', 'plugged': True},
    {'status': 'battery', 'battery_percent': 50, 'plugged': 1},
    {'status': 'unknown', 'battery_percent': 50, 'plugged': None},
    {'status': 'no_battery', 'battery_percent': None, 'plugged': True},
    {'status': 'charging', 'battery_percent': 50, 'plugged': True},
    {'status': 'unknown', 'battery_percent': None, 'plugged': None, 'extra': True},
])
def test_signed_malformed_power_is_rejected_before_ping(signed_rpc, power):
    sign, receive, ping, _ = signed_rpc
    with pytest.raises(HTTPException) as error:
        receive(sign({'cpu_percent': 20, 'memory_percent': 30, 'power': power}))
    assert error.value.status_code == 400
    ping.assert_not_called()


def test_legacy_signed_load_remains_supported(signed_rpc):
    sign, receive, ping, sender_id = signed_rpc
    metrics = {'cpu_percent': 20, 'memory_percent': 30}
    assert receive(sign(metrics))['status'] == 'ok'
    assert ping.call_args.args == (sender_id,)
    assert ping.call_args.kwargs['load_metrics'] == metrics


def test_tampering_power_after_signing_fails_authentication(signed_rpc):
    sign, receive, ping, _ = signed_rpc
    message = sign({'cpu_percent': 20, 'memory_percent': 30,
                    'power': {'status': 'battery', 'battery_percent': 12, 'plugged': False}})
    message['payload']['load_metrics']['power']['plugged'] = True
    with pytest.raises(HTTPException) as error:
        receive(message)
    assert error.value.status_code == 403
    assert error.value.detail == 'Invalid cryptographic signature.'
    ping.assert_not_called()
