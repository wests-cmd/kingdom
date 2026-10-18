"""Bounded peer-reported inventories. Identity attestation never grants tool access."""
import re
import time

MAX_AGENTS = 128
FRESH_SECONDS = 45
STATES = {'ready', 'idle', 'running', 'working', 'busy', 'offline', 'blocked', 'paused', 'unknown', 'needs_review'}


def validate_inventory(report):
    if not isinstance(report, dict) or type(report.get('version')) is not int or report['version'] != 1:
        raise ValueError('Unsupported Apprentice inventory version')
    rows = report.get('apprentices')
    if not isinstance(rows, list) or len(rows) > MAX_AGENTS:
        raise ValueError('Invalid Apprentice inventory size')
    clean, seen = [], set()
    for row in rows:
        if not isinstance(row, dict): raise ValueError('Invalid Apprentice record')
        ident = row.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}', ident) or ident in seen:
            raise ValueError('Invalid or duplicate Apprentice identity')
        seen.add(ident)
        name, role = row.get('display_name', ident), row.get('role', 'unknown')
        if any(not isinstance(text, str) or not 1 <= len(text) <= 100 or any(ord(c) < 32 for c in text) for text in (name, role)):
            raise ValueError('Invalid Apprentice label')
        status = row.get('status', 'unknown')
        active = row.get('active', 0)
        if not isinstance(status, str) or status not in STATES or type(active) is not int or not 0 <= active <= 100:
            raise ValueError('Invalid Apprentice activity')
        clean.append({'id': ident, 'display_name': name, 'role': role, 'status': status, 'active': active})
    result={'version': 1, 'apprentices': clean}
    services=report.get('services')
    if services is not None:
        if not isinstance(services,dict) or services.get('state') not in {'observed','unsupported','unavailable'} or not isinstance(services.get('services'),list) or len(services['services'])>128:
            raise ValueError('Invalid service inventory')
        rows=[]
        for item in services['services']:
            if not isinstance(item,dict) or item.get('state')!='running' or any(not isinstance(item.get(key),str) or not 1<=len(item[key])<=160 or any(ord(c)<32 for c in item[key]) for key in ('id','name')):
                raise ValueError('Invalid observed service')
            rows.append({key:item[key] for key in ('id','name','state')})
        result['services']={'state':services['state'],'services':rows,'truncated':services.get('truncated') is True}
    return result


def local_inventory():
    from backend.api import knights
    from backend.runtime.service_discovery import discover_local_services
    return validate_inventory({'version': 1,'services':discover_local_services(), 'apprentices': [
        {key: row[key] for key in ('id', 'display_name', 'role', 'status', 'active') if key in row}
        for row in knights()['knights']]})


def aggregate_inventories(local, peers, now=None):
    now = time.time() if now is None else now
    remote, reports, seen = [], [], set()
    for node in peers:
        ident = node.get('node_id') or node.get('id')
        if not ident or ident in seen: continue
        seen.add(ident)
        saved = (node.get('connection_metadata') or {}).get('apprentice_inventory')
        state = 'missing'
        if isinstance(saved, dict):
            received = saved.get('received_at', 0)
            heartbeat = node.get('last_heartbeat', 0)
            state = 'stale'
            if node.get('node_state') == 'CONNECTED' and type(received) in (int,float) and type(heartbeat) in (int,float) and 0 <= now - received <= FRESH_SECONDS and 0 <= now - heartbeat <= FRESH_SECONDS:
                try: report = validate_inventory(saved.get('report'))
                except ValueError: state = 'invalid'
                else:
                    state = 'current'
                    remote.extend({**row, 'kingdom_id': ident, 'scoped_id': ident + '/' + row['id'],
                                   'host': node.get('hostname') or ident, 'entity_type': 'knight_apprentice',
                                   'provenance': 'signed_peer_report'} for row in report['apprentices'])
        reports.append({'kingdom_id': ident, 'state': state, 'received_at': saved.get('received_at') if isinstance(saved,dict) else None,
                        'services':report.get('services') if state=='current' else None})
    return {'local_count': len(local), 'remote_count': len(remote), 'total_current': len(local) + len(remote),
            'complete': all(r['state'] == 'current' for r in reports), 'reports': reports, 'remote_apprentices': remote,
            'notice': 'Remote workers are identity-attested peer reports, not independent proof of running models or successful execution.'}
