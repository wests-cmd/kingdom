"""Dispatch only after existing signed RPC authentication and replay checks."""
import os
from pathlib import Path


def dispatch(sender_id, operation, payload, *, registry=None, engine=None, database=None):
    if not isinstance(payload, dict):
        raise ValueError('Management arguments must be an object')
    if registry is None:
        from backend.cluster.node_registry import node_registry
        registry = node_registry
    node = registry.get_node(sender_id)
    grant = 'knight.manage.execute' if operation in {'inspect', 'service_action'} else 'knight.update.execute'
    if (not node or node.node_state not in {'APPROVED', 'CONNECTED'}
            or grant not in (node.granted_capabilities or [])):
        raise PermissionError('Peer needs the explicit owner-granted Knight management capability')
    if operation == 'inspect':
        from backend.runtime.service_discovery import discover_local_services
        return discover_local_services()
    if operation == 'service_action':
        from backend.runtime.service_nodes import ServiceNodes
        if engine is None:
            from backend.api import engine
        if database is None:
            from backend.storage.db import db
            database = db
        services = ServiceNodes(engine, database)
        # Remote peers can only manage explicitly registered LOCAL user units.
        target = services.config(payload.get('service_node', ''))
        if target.mode != 'local':
            raise PermissionError('Peer management cannot relay onward through SSH')
        return services.action(payload['service_node'], payload.get('unit'), payload.get('action'), requested_by_peer=sender_id)
    if operation not in {'stage_update', 'activate_update', 'update_status'}:
        raise ValueError('Unknown Knight management operation')
    profile_path = os.environ.get('KINGDOM_KNIGHT_UPDATE_PROFILE')
    if not profile_path:
        raise ValueError('This Knight has no owner-installed update adapter')
    from backend.runtime.knight_updates import load_profile, stage, schedule_command, record_receipt, read_receipt
    profile = load_profile(profile_path)
    if operation == 'stage_update':
        result = stage(profile['releases_root'], payload.get('archive_b64'), payload.get('sha256', ''))
        record_receipt(profile['state_root'], result)
    elif operation == 'activate_update':
        if engine is None:
            from backend.api import engine
        release = payload.get('release', '')
        argv = schedule_command(profile_path, release)
        task = engine.submit_task('Update this Knight from verified release ' + release, {
            # Local operator configured this adapter; the peer is provenance,
            # not an invented security principal. Normal exact approvals apply.
            'actor': 'owner', 'tool': 'process.run@1.0.0',
            'tool_parameters': {'argv': argv, 'timeout_seconds': 30},
            'requested_by_peer': sender_id,
            'verification_scope': 'Scheduling exit is not completion; inspect update_status receipt.'})
        result = {'status': 'governed_task_submitted', 'release': release, 'task': task, 'verified': False}
    else:
        import json
        import re
        release = payload.get('release', '')
        if not re.fullmatch(r'[0-9a-f]{64}', release):
            raise ValueError('Invalid release digest')
        return read_receipt(profile['state_root'], release)
    from backend.events.event_bus import event_bus
    event_bus.publish('cluster.knight_management', {'sender_id': sender_id, 'operation': operation,
                                                  'release': result.get('release'), 'status': result.get('status')})
    return result
