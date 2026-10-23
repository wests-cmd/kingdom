"""Owner-visible orchestration evidence, without model transcripts or secrets."""
import json
import time
from fastapi import APIRouter, Depends
from backend.security.http_auth import require_owner

router = APIRouter(prefix='/orchestration', dependencies=[Depends(require_owner)])


@router.get('/activity')
def activity():
    from backend.runtime.fleet_activity import local_activity
    return local_activity()


def job_view(request, agent=None, tasks=()):
    agent = agent or {}
    related = [t for t in tasks if request.get('agent_session_id') and t.get('metadata', {}).get('agent_session_id') == request['agent_session_id']]
    assigned = {t['assigned_knight'] for t in related if t.get('assigned_knight')}
    for task in related:
        result = task.get('result') or {}
        if result.get('verification', {}).get('state') == 'VERIFIED' and result.get('executed_by'):
            assigned.add(result['executed_by'])
        for record in result.get('results', []):
            if record.get('verification', {}).get('state') == 'VERIFIED' and record.get('knight'):
                assigned.add(record['knight'])
    assignments = sorted(assigned)
    verified = sum((t.get('result') or {}).get('verification', {}).get('state') == 'VERIFIED' or
                   any(r.get('verification', {}).get('state') == 'VERIFIED' for r in (t.get('result') or {}).get('results', [])) for t in related)
    return {'id': request['id'], 'project': request.get('project_scope'), 'objective': request.get('prompt', '')[:500],
            'status': request.get('status'), 'agent_status': agent.get('status'),
            'display_status': agent.get('status') if request.get('status') == 'running' else request.get('status'),
            'reason': agent.get('error') or request.get('error') or '',
            'model_profile': agent.get('selected_profile') or request.get('model_profile'),
            'model': agent.get('selected_model'), 'computer': agent.get('selected_computer'),
            'assigned_workers': assignments, 'tool_count': agent.get('tool_count', 0),
            'verified_tools': verified, 'updated_at': request.get('updated_at'),
            'completion_scope': 'Response completed; inspect independent tests before accepting an implementation' if request.get('status') == 'completed' else None}


@router.get('')
def overview():
    from backend.api import engine, knights
    from backend.storage.db import db
    from backend.runtime.agent_api import service as agents
    from backend.runtime.request_api import background, service as requests_service
    from backend.models.profiles import ModelProfiles
    from backend.cluster.hierarchy import CommandHierarchy
    from backend.cluster.node_registry import node_registry
    requests_service()  # Create the request table on a fresh installation.
    hierarchy = CommandHierarchy(db, node_registry, engine.events.publish).export(knights()['knights'])
    profiles = {p['id']: p for p in ModelProfiles(db).list()}
    with db.get_connection() as conn:
        requests = [json.loads(row[0]) for row in conn.execute('SELECT state_json FROM conversation_requests ORDER BY rowid DESC LIMIT 100')]
    tasks = engine.tasks.list()
    jobs = []
    for request in requests:
        try: agent = agents().get(request['agent_session_id']) if request.get('agent_session_id') else None
        except KeyError: agent = None
        job = job_view(request, agent, tasks)
        profile = profiles.get(job['model_profile'], {})
        job['computer'] = profile.get('computer_id') or job['computer']
        job['model'] = job['model'] or profile.get('model')
        if request.get('background_owner') == 'server' and request['status'] == 'running' and request['id'] not in background.active:
            job.update(status='waiting_review', display_status='interrupted', reason='Server execution interrupted; inspect retained agent and tool checkpoints before continuing')
        jobs.append(job)
    peers = hierarchy['knights']
    now = time.time()
    inventory = hierarchy['inventory']
    return {'observed_at': now, 'commander': hierarchy['commander'], 'knights': peers,
            'inventory': inventory,
            'apprentices': hierarchy['apprentices'], 'jobs': jobs,
            'counts': {'knights': 1 + len(peers), 'paired_knights': len(peers), 'local_apprentices': len(hierarchy['apprentices']),
                       'current_apprentices': inventory['total_current'], 'remote_apprentices': inventory['remote_count'],
                       'connected_peers': sum(n.get('node_state') == 'CONNECTED' and now - n.get('last_heartbeat', 0) < 45 for n in peers)},
            'background': background.status(), 'coverage': inventory['notice']}
