import sys
from types import SimpleNamespace
import pytest
from backend.cluster.local_load import local_load_metrics


def test_reports_measured_load_using_bounded_cpu_sample(monkeypatch):
    intervals = []
    def cpu_percent(interval):
        intervals.append(interval)
        return 73.5
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(
        cpu_percent=cpu_percent, virtual_memory=lambda: SimpleNamespace(percent=61.25)))
    assert local_load_metrics() == {'cpu_percent': 73.5, 'memory_percent': 61.25,
                                  'power': {'status': 'unknown', 'battery_percent': None, 'plugged': None}}
    assert intervals == [0.1]


@pytest.mark.parametrize('percent,plugged', [(12, False), (85.5, True), (0, False), (100, True)])
def test_power_reports_battery_percentage_and_measured_plug_state(monkeypatch, percent, plugged):
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(
        cpu_percent=lambda interval: 10, virtual_memory=lambda: SimpleNamespace(percent=20),
        sensors_battery=lambda: SimpleNamespace(percent=percent, power_plugged=plugged)))
    assert local_load_metrics()['power'] == {
        'status': 'battery', 'battery_percent': percent, 'plugged': plugged}


def test_power_distinguishes_no_battery_from_unknown(monkeypatch):
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(
        cpu_percent=lambda interval: 10, virtual_memory=lambda: SimpleNamespace(percent=20),
        sensors_battery=lambda: None))
    assert local_load_metrics()['power'] == {
        'status': 'no_battery', 'battery_percent': None, 'plugged': None}


@pytest.mark.parametrize('failure', [OSError, RuntimeError, NotImplementedError])
def test_power_sensor_failure_preserves_load_without_assuming_ac(monkeypatch, failure):
    def broken():raise failure('unavailable')
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(
        cpu_percent=lambda interval: 10, virtual_memory=lambda: SimpleNamespace(percent=20),
        sensors_battery=broken))
    assert local_load_metrics() == {'cpu_percent': 10, 'memory_percent': 20,
                                  'power': {'status': 'unknown', 'battery_percent': None, 'plugged': None}}


@pytest.mark.parametrize('percent,plugged', [(-1, True), (101, True), (float('nan'), True),
                                           (float('inf'), True), (True, True), ('50', True),
                                           (50, None), (50, 1), (50, 'yes')])
def test_invalid_power_measurements_are_unknown(monkeypatch, percent, plugged):
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(
        cpu_percent=lambda interval: 10, virtual_memory=lambda: SimpleNamespace(percent=20),
        sensors_battery=lambda: SimpleNamespace(percent=percent, power_plugged=plugged)))
    assert local_load_metrics()['power'] == {
        'status': 'unknown', 'battery_percent': None, 'plugged': None}


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, 101, True, '0'])
def test_invalid_measurements_cannot_claim_idle_capacity(monkeypatch, value):
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(
        cpu_percent=lambda interval: value, virtual_memory=lambda: SimpleNamespace(percent=10)))
    assert local_load_metrics() == {}


def test_sampler_failure_is_unavailable_not_zero(monkeypatch):
    def broken(interval):
        raise OSError('unavailable')
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(cpu_percent=broken))
    assert local_load_metrics() == {}


def test_federation_heartbeat_signs_measured_load_with_inventory(monkeypatch):
    from backend.cluster import federation_api
    from backend.cluster.identity import KingdomIdentity
    from backend.cluster.transport import RPCMessage
    local = KingdomIdentity('KG-load-source')
    monkeypatch.setattr(federation_api.node_registry, 'get_node', lambda _: SimpleNamespace(
        public_identity={'node_type': 'commander'}, node_state='CONNECTED'))
    monkeypatch.setattr(federation_api.KingdomIdentity, 'get_or_create', lambda: local)
    monkeypatch.setattr(federation_api, 'local_load_metrics', lambda: {'cpu_percent': 73.5, 'memory_percent': 61.25})
    monkeypatch.setattr('backend.cluster.apprentice_inventory.local_inventory', lambda: {'version': 1, 'apprentices': []})
    proof = federation_api.export_heartbeat_proof('KG-peer')
    assert proof['payload']['load_metrics'] == {'cpu_percent': 73.5, 'memory_percent': 61.25}
    assert proof['payload']['apprentice_inventory'] == {'version': 1, 'apprentices': []}
    message = RPCMessage(proof['sender_id'], proof['target_id'], proof['msg_type'],
                         proof['payload'], proof['msg_id'], proof['timestamp'])
    signature = bytes.fromhex(proof['signature'])
    public = local.get_public_identity()['public_key_hex']
    assert local.verify_signature(public, message.get_canonical_bytes(), signature)
    message.payload['load_metrics']['cpu_percent'] = 0
    assert not local.verify_signature(public, message.get_canonical_bytes(), signature)


def test_new_unavailable_sample_clears_previously_idle_load(monkeypatch):
    import copy
    from backend.cluster.node_registry import node_registry, NodeInfo
    from backend.cluster.heartbeat import HeartbeatManager
    stored = NodeInfo(node_id='peer', node_state_val='CONNECTED', last_heartbeat=1,
        public_identity={'node_type': 'commander'}, granted_capabilities=['text.analyze@1.0.0'],
        connection_metadata={'load_metrics': {'cpu_percent': 1, 'memory_percent': 1}}).to_dict()
    monkeypatch.setattr(node_registry.repo, 'get', lambda _: copy.deepcopy(stored))
    monkeypatch.setattr(node_registry.repo, 'save', lambda data: stored.update(copy.deepcopy(data)))
    monkeypatch.setattr('backend.cluster.heartbeat.time.time', lambda: 100)
    assert HeartbeatManager().ping('peer', load_metrics={})['success']
    assert stored['last_heartbeat'] == 100
    assert stored['connection_metadata']['load_metrics'] == {}
