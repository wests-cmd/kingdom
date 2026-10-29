"""Read-only BlueZ/PAN observations. Never pair, trust or configure a device.

An observed OS route is not a Knight identity or a packet capture. The signed
RPC protocol remains authoritative on every path.
"""
import ipaddress
import json
import platform
import subprocess
import time
from urllib.parse import urlsplit


def _json_command(argv):
    result = subprocess.run(argv, capture_output=True, timeout=4, check=True)
    if len(result.stdout) > 262144:
        raise ValueError('Local Bluetooth observation exceeds its budget')
    return json.loads(result.stdout)


def bluez_snapshot(objects):
    """Parse actual ObjectManager data without exporting unrelated device names."""
    adapters, links = [], []
    for path, interfaces in objects.items():
        if 'org.bluez.Adapter1' in interfaces:
            props = interfaces['org.bluez.Adapter1']
            adapters.append({'path': path, 'address': props.get('Address', {}).get('data'),
                             'powered': props.get('Powered', {}).get('data') is True})
        network = interfaces.get('org.bluez.Network1', {})
        device = interfaces.get('org.bluez.Device1', {})
        interface = network.get('Interface', {}).get('data')
        if (network.get('Connected', {}).get('data') is True
                and device.get('Paired', {}).get('data') is True
                and isinstance(interface, str) and interface.startswith('bnep')):
            links.append({'interface': interface, 'device_address': device.get('Address', {}).get('data'),
                          'adapter': device.get('Adapter', {}).get('data')})
    powered = {a['path'] for a in adapters if a['powered']}
    return adapters, [link for link in links if link['adapter'] in powered]


def observe():
    result = {'platform': platform.system(), 'observed_at': time.time(), 'adapters': [],
              'pan_links': [], 'available': False, 'reason': 'Linux BlueZ observation is unavailable'}
    if result['platform'] != 'Linux':
        result['reason'] = 'This PAN observer requires Linux BlueZ; no radio state is assumed'
        return result
    try:
        raw = _json_command(['busctl', '--system', '--json=short', 'call', 'org.bluez', '/',
                             'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects'])
        objects = raw['data'][0]
        adapters, links = bluez_snapshot(objects)
        result.update(adapters=adapters, pan_links=links, available=bool(links),
                      reason=('Connected paired BlueZ PAN link observed' if links else
                              'No connected paired PAN link; normal owner pairing/PAN setup is required'))
    except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError):
        result['reason'] = 'BlueZ is unavailable or permission denied; no pairing or privileges were changed'
    return result


def validate_route(host, route, snapshot):
    """Require the OS-selected route to an active paired BlueZ Network1 link."""
    destination = ipaddress.ip_address(host)
    if destination.is_loopback or destination.is_multicast or destination.is_unspecified:
        raise ValueError('A loopback or non-unicast route cannot prove Bluetooth PAN')
    if not isinstance(route, list) or len(route) != 1:
        raise ValueError('One current OS route is required')
    entry = route[0]
    link = next((p for p in snapshot.get('pan_links', []) if p['interface'] == entry.get('dev')), None)
    if link is None:
        raise ValueError('The selected route is not a current paired Bluetooth PAN link')
    source = entry.get('prefsrc') or entry.get('src')
    if not source or ipaddress.ip_address(source).version != destination.version:
        raise ValueError('Bluetooth route has no matching local source address')
    return {'interface': link['interface'], 'device_address': link['device_address'],
            'local_address': source, 'observed_at': snapshot['observed_at'],
            'evidence': 'bluez_network1_and_os_route_observed'}


def route_observation(endpoint):
    host = str(ipaddress.ip_address(urlsplit(endpoint).hostname or ''))
    try:
        route = _json_command(['ip', '-j', 'route', 'get', host])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise ValueError('Bluetooth PAN route observation unavailable') from error
    return validate_route(host, route, observe())
