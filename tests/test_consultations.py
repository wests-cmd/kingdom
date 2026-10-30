"""Public durable consultation seams; no cloud or model calls."""
import concurrent.futures
import json

import pytest

from backend.runtime.consultations import ConsultationStore
from backend.storage.db import Database


@pytest.fixture
def runtime(tmp_path):
    clock = [1000.0]
    database = Database(tmp_path / 'consultations.db')
    events = []
    store = ConsultationStore(database, clock=lambda: clock[0], publish=lambda *args: events.append(args))
    return database, clock, events, store


def request(store, **changes):
    values = dict(project='kingdom', parent_work_id='work-a', context_revision='a' * 40,
                  kind='error', question='How should this failed test be repaired?',
                  context={'summary': 'Expected two groups; observed one', 'tool': 'pytest'})
    values.update(changes)
    return store.request(**values)


def test_environment_secrets_database_userinfo_and_cookie_headers_are_not_retained(runtime):
    _, _, _, store = runtime
    row = request(store, question='DB_PASSWORD=neverKeepThis\nCookie: sid=firstSecret; other=secondSecret\n'
                  'postgresql://user:thirdSecret@localhost/db\n-----BEGIN PRIVATE KEY-----\nfourthSecret')
    encoded = json.dumps(store.get(row['id']))
    for secret in ['neverKeepThis', 'firstSecret', 'secondSecret', 'thirdSecret', 'fourthSecret']:
        assert secret not in encoded


@pytest.mark.parametrize('secret', ['password="correct horse battery staple"',
    "secret='first line\nsecond secret line'", 'DB_PASSWORD="escaped\\\" quote secret"',
    'password=correct horse battery staple'])
def test_complete_multiword_and_multiline_secret_values_are_redacted(runtime, secret):
    _, _, _, store = runtime
    saved = request(store, question=secret+'\nExplain the failure.')
    encoded = json.dumps(store.get(saved['id']))
    for word in ['correct', 'horse', 'battery', 'staple', 'first line', 'second secret line', 'escaped', 'quote secret']:
        assert word not in encoded
    assert 'Explain the failure.' in saved['question']


def answer(store, **changes):
    row = request(store, **changes)
    claim = store.claim('worker-a', row['id'])
    store.mark_sending(row['id'], claim['claim_token'])
    return store.finish(row['id'], claim['claim_token'], 'Keep separate groups and rerun the fixed test.', 'chatgpt-plan')


def test_question_is_durable_and_same_request_does_not_duplicate(runtime):
    database, clock, events, store = runtime
    first = request(store)
    restored = ConsultationStore(database, clock=lambda: clock[0])
    assert request(restored)['id'] == first['id']
    assert len(restored.list()) == 1
    assert restored.get(first['id'])['status'] == 'queued'
    assert events[-1][0] == 'consultation.queued'


def test_crash_fences_claim_and_holds_started_cloud_request(runtime):
    database, clock, _, store = runtime
    row = request(store)
    first = store.claim('worker-a', row['id'])
    recovered = ConsultationStore(database, clock=lambda: clock[0])
    recovered.recover_startup()
    second = recovered.claim('worker-b', row['id'])
    assert second['generation'] > first['generation']
    with pytest.raises(PermissionError):
        store.mark_sending(row['id'], first['claim_token'])
    recovered.mark_sending(row['id'], second['claim_token'])
    assert recovered.get(row['id'])['attempts'] == 1
    recovered.recover_startup()
    assert recovered.get(row['id'])['status'] == 'outcome_unknown'
    assert recovered.claim('worker-c', row['id']) is None
    with pytest.raises(PermissionError):
        recovered.finish(row['id'], second['claim_token'], 'Late answer', 'chatgpt-plan')


def test_two_workers_only_claim_once_and_network_has_not_started(runtime):
    database, clock, _, store = runtime
    row = request(store)
    def claim(worker):
        return ConsultationStore(database, clock=lambda: clock[0]).claim(worker, row['id'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, ['worker-a', 'worker-b']))
    assert sum(c is not None for c in claims) == 1
    assert store.get(row['id'])['attempts'] == 0


def test_claim_expiry_and_cancellation_prevent_send_and_late_completion(runtime):
    _, clock, _, store = runtime
    row = request(store)
    claim = store.claim('worker-a', row['id'], lease_seconds=10)
    clock[0] += 10
    with pytest.raises(PermissionError):
        store.mark_sending(row['id'], claim['claim_token'])
    store.cancel(row['id'])
    assert store.claim('worker-b', row['id']) is None
    with pytest.raises(PermissionError):
        store.finish(row['id'], claim['claim_token'], 'Late result', 'chatgpt-plan')


class Evidence:
    """Trusted acceptance-system boundary, not model-supplied verification."""
    def __init__(self):
        self.revoked = False
        self.override = {}

    def __call__(self, row, evidence_id):
        return {'evidence_id': evidence_id, 'tests_passed': True, 'revoked': self.revoked,
                'project': row['project'], 'parent_work_id': row['parent_work_id'],
                'context_revision': row['context_revision'], 'question_id': row['id'],
                'answer_sha256': row['answer_sha256'], 'kind': 'project_test', **self.override}


def test_only_tested_guidance_is_reused_and_it_never_grants_authority(runtime):
    _, _, _, store = runtime
    row = answer(store)
    query = dict(project='kingdom', context_revision='a'*40, kind='error',
                 question=row['question'], context=row['context'])
    assert store.lookup_verified(**query) is None
    with pytest.raises(PermissionError):
        store.record_verification(row['id'], 'receipt-a')
    evidence = Evidence(); store.verifier = evidence
    store.record_verification(row['id'], 'receipt-a')
    found = store.lookup_verified(**query)
    assert found['id'] == row['id']
    assert found['authority'] == 'untrusted_advice'
    assert found['verification']['evidence_id'] == 'receipt-a'
    # A new task may reuse the same guidance, but retains its own work ID/tests.
    second = request(store, parent_work_id='work-b')
    assert second['id'] != row['id']
    assert store.lookup_verified(**query)['parent_work_id'] == 'work-a'
    assert store.lookup_verified(**{**query, 'project': 'centipede'}) is None
    assert store.lookup_verified(**{**query, 'context_revision': 'b'*40}) is None
    assert store.lookup_verified(**{**query, 'context': {'summary': 'A different error'}}) is None
    evidence.revoked = True
    assert store.lookup_verified(**query) is None


@pytest.mark.parametrize('override', [
    {'tests_passed': False}, {'tests_passed': 1}, {'revoked': True},
    {'question_id': 'another'}, {'answer_sha256': '0'*64},
    {'parent_work_id': 'different'}, {'context_revision': 'b'*40}, {'project': 'centipede'},
    {'evidence_id': 'another'}, {'kind': 'model_opinion'}])
def test_unrelated_or_untrusted_evidence_cannot_promote_advice(runtime, override):
    _, _, _, store = runtime
    row = answer(store)
    evidence = Evidence(); evidence.override = override; store.verifier = evidence
    with pytest.raises(PermissionError):
        store.record_verification(row['id'], 'receipt-a')
    assert store.get(row['id'])['verification'] is None


def test_training_export_requires_selection_and_current_bound_evidence(runtime):
    _, _, _, store = runtime
    row = answer(store)
    store.verifier = Evidence()
    store.record_verification(row['id'], 'receipt-a')
    assert store.export_training(project='kingdom') == ''
    store.select_for_training(row['id'], True)
    line = json.loads(store.export_training(project='kingdom'))
    assert line['messages'] == [{'role': 'user', 'content': row['question']},
                                {'role': 'assistant', 'content': row['answer']}]
    assert line['provenance']['evidence_id'] == 'receipt-a'
    assert line['provenance']['context_revision'] == 'a'*40
    assert 'claim_token' not in str(line)
    store.verifier.revoked = True
    assert store.export_training(project='kingdom') == ''
