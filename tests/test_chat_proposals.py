from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from backend.storage.db import Database
from backend.runtime.chat_proposals import ChatProposals, ChatTask


def setup(tmp_path, provider='ollama', endpoint='http://127.0.0.1:11434'):
    requests = []
    def create(body):
        requests.append(body)
        return {'id': body['idempotency_key']}
    db = Database(tmp_path / 'test.db')
    profiles = SimpleNamespace(get=lambda _: {'provider': provider, 'endpoint': endpoint})
    queue = SimpleNamespace(create=create)
    events = []
    service = ChatProposals(db, profiles, queue, lambda *args: events.append(args))
    return service, requests, events


def task(**extra):
    return ChatTask(**{'project_scope':'projects/demo', 'objective':'Fix the boundary',
                      'acceptance':'Preserve input and pass independent tests',
                      'exported_context':'def chunks(text): ...', 'local_profile':'local-review', **extra})


def test_proposal_survives_restart_and_never_becomes_execution(tmp_path):
    service, requests, events = setup(tmp_path)
    state = service.create(task())
    assert not requests and state['status'] == 'awaiting_chat'
    assert state['codex_worker'] is False and 'def chunks' in state['prompt']
    received = service.submit(state['id'], 'Use a strict type check.')
    assert received['status'] == 'awaiting_local_review'
    restarted = ChatProposals(service.db, service.profiles, service.requests, service.publish)
    assert restarted.get(state['id']) == received
    review = restarted.queue_review(state['id'])
    assert review['status'] == 'local_review_queued'
    assert requests[0]['mode'] == 'quick' and requests[0]['model_profile'] == 'local-review'
    assert requests[0]['allow_process'] is False
    assert events[-1][1]['status'] == 'local_review_queued'


@pytest.mark.parametrize('provider,endpoint', [('openai_compatible','https://api.openai.com/v1'), ('ollama','https://example.org')])
def test_cloud_cannot_silently_become_reviewer(tmp_path, provider, endpoint):
    service, requests, _ = setup(tmp_path, provider, endpoint)
    with pytest.raises(ValueError, match='local Ollama'):
        service.create(task())
    assert not requests


def test_duplicate_and_conflicting_replies_are_durable(tmp_path):
    service, requests, _ = setup(tmp_path)
    ident = service.create(task())['id']
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda _: service.submit(ident, 'same proposal'), range(2)))
    assert replies[0] == replies[1]
    with pytest.raises(ValueError, match='immutable'):
        service.submit(ident, 'different code')
    assert not requests
    assert service.queue_review(ident)['request_id'] == service.queue_review(ident)['request_id']


def test_empty_unbound_and_oversized_proposals_rejected(tmp_path):
    service, _, _ = setup(tmp_path)
    ident = service.create(task())['id']
    for text in ['', ' ', 'x' * 12001]:
        with pytest.raises(ValueError):
            service.submit(ident, text)
    with pytest.raises(ValueError):
        service.queue_review(ident)
    with pytest.raises(KeyError):
        service.submit('unknown', 'code')


@pytest.mark.parametrize('scope', ['../private', 'projects/a/../../secret', '/projects/a', 'projects/a\\b'])
def test_external_chat_cannot_choose_an_escaping_workspace(scope):
    with pytest.raises(ValidationError):
        ChatTask(project_scope=scope, objective='a', acceptance='b', local_profile='local')


def test_profile_rechecked_before_dispatch(tmp_path):
    service, requests, _ = setup(tmp_path)
    ident = service.create(task())['id']
    service.submit(ident, 'code')
    service.profiles.get = lambda _: {'provider': 'openai_compatible', 'endpoint': 'https://cloud.example'}
    with pytest.raises(ValueError):
        service.queue_review(ident)
    assert not requests


def test_inbox_control_plane_requires_owner():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.runtime.chat_proposal_api import router
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        for method, path, data in [
            ('GET', '/chat-proposals/unknown', None),
            ('POST', '/chat-proposals', task().model_dump()),
            ('POST', '/chat-proposals/unknown/reply', {'text': 'proposal'}),
            ('POST', '/chat-proposals/unknown/review', {}),
        ]:
            response = client.request(method, path, json=data, headers={'X-Kingdom-Request': '1'})
            assert response.status_code == 401


def test_review_never_silently_compacts_away_proposed_code(tmp_path):
    service, requests, _ = setup(tmp_path)
    ident = service.create(task(exported_context='x' * 10000))['id']
    service.submit(ident, 'candidate ' * 1000)
    service.profiles.get = lambda _: {'provider':'ollama', 'endpoint':'http://localhost:11434', 'context_characters':4000}
    with pytest.raises(ValueError, match='split the task'):
        service.queue_review(ident)
    assert not requests
