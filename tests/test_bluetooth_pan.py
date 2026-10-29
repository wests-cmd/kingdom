"""OS-observation parsing/route guards; none of these claim physical transfer."""
import pytest
from backend.cluster.bluetooth_pan import bluez_snapshot, validate_route


def variant(value):
    return {'data': value}


def objects(*, paired=True, powered=True, connected=True):
    return {'/adapter': {'org.bluez.Adapter1': {'Address': variant('AA:BB:CC:DD:EE:FF'), 'Powered': variant(powered)}},
            '/device': {'org.bluez.Device1': {'Address': variant('11:22:33:44:55:66'), 'Paired': variant(paired), 'Adapter': variant('/adapter')},
                        'org.bluez.Network1': {'Connected': variant(connected), 'Interface': variant('bnep0')}}}


@pytest.mark.parametrize('field', ['paired', 'powered', 'connected'])
def test_unpaired_unpowered_disconnected_link_is_not_pan(field):
    adapters, links = bluez_snapshot(objects(**{field: False}))
    assert not links


def test_current_bluez_link_and_same_os_route_are_required():
    adapters, links = bluez_snapshot(objects())
    snapshot = {'adapters': adapters, 'pan_links': links, 'observed_at': 10}
    route = [{'dev': 'bnep0', 'prefsrc': '192.168.44.1'}]
    assert validate_route('192.168.44.2', route, snapshot)['interface'] == 'bnep0'
    with pytest.raises(ValueError):
        validate_route('192.168.44.2', [{'dev': 'wlan0', 'prefsrc': '192.168.44.1'}], snapshot)
    with pytest.raises(ValueError):
        validate_route('192.168.44.2', route, {**snapshot, 'pan_links': []})
    with pytest.raises(ValueError):
        validate_route('127.0.0.1', route, snapshot)
    with pytest.raises(ValueError):
        validate_route('192.168.44.2', [{'dev': 'bnep0'}], snapshot)


def test_owner_boundary_prevents_status_observation(monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from backend.security.http_auth import require_owner
    from backend.cluster.alternate_path_api import router
    import backend.cluster.bluetooth_pan as pan
    app = FastAPI(); app.include_router(router)
    def denied(): raise HTTPException(403, 'Owner required')
    app.dependency_overrides[require_owner] = denied
    monkeypatch.setattr(pan, 'observe', lambda: pytest.fail('Unauthorized hardware observation'))
    assert TestClient(app).get('/peer-paths/bluetooth/status').status_code == 403
