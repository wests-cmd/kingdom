"""Durable team delivery through public storage/fencing interfaces, no network."""
from backend.cluster.team_outbox import TeamOutbox
from backend.cluster.team_policy import TeamMessage, TeamPolicy
from backend.storage.db import Database
import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pydantic import ValidationError
import time

MESSAGE_TIME = int(time.time())


def message(ident='message-one', **changes):
    values = dict(message_id=ident, task_id='task-one', sender_id='knight-a',
                  recipient_id='knight-b', policy_revision=1, kind='progress',
                  created_at=MESSAGE_TIME, expires_at=MESSAGE_TIME + 3600,
                  payload={'stage': 'testing'})
    values.update(changes)
    return TeamMessage(**values)


def test_expired_send_cannot_restart_but_its_exact_late_ack_survives(tmp_path):
    now = [100]
    database = Database(tmp_path / 'ttl.db')
    queue = TeamOutbox(database, clock=lambda: now[0])
    value = message(created_at=100, expires_at=110)
    queue.enqueue(value)
    claim = queue.claim(value.message_id)
    now[0] = 110
    with pytest.raises(ValueError):
        queue.mark_sending(value.message_id, claim['claim_token'])
    restarted = TeamOutbox(database, clock=lambda: now[0])
    restarted.recover()
    assert restarted.claim(value.message_id) is None
    assert restarted.get(value.message_id)['state'] == 'expired'
    with pytest.raises(ValueError):
        restarted.enqueue(message('new-expired', created_at=100, expires_at=110))
    with pytest.raises(ValueError):
        restarted.reserve_incoming(message('incoming-expired', created_at=100, expires_at=110))
    now[0] = 100
    sent = message('already-sent', created_at=100, expires_at=110)
    queue.enqueue(sent)
    claim = queue.claim(sent.message_id)
    queue.mark_sending(sent.message_id, claim['claim_token'])
    now[0] = 120
    restarted.recover()
    ack = restarted.acknowledge(sent.message_id, claim_token=claim['claim_token'],
        recipient_id=sent.recipient_id, digest=sent.digest(), receipt_id='late-receipt')
    assert ack['state'] == 'acknowledged'
    assert restarted.enqueue(sent) == ack


def test_expired_head_is_retained_without_starving_live_work(tmp_path):
    now = [100]
    database = Database(tmp_path / 'ttl.db')
    queue = TeamOutbox(database, clock=lambda: now[0])
    queue.enqueue(message('old', created_at=100, expires_at=110))
    queue.enqueue(message('live', created_at=100, expires_at=200))
    now[0] = 110
    restarted = TeamOutbox(database, clock=lambda: now[0])
    assert restarted.claim_next()['message_id'] == 'live'
    assert restarted.get('old')['state'] == 'expired'
    assert restarted.get('old')['message']['expires_at'] == 110
    assert restarted.status()['receipt_count'] == 2
    assert restarted.status()['pending_count'] == 1


def test_clock_rollback_holds_claim_and_expiry_keeps_receiver_deduplication(tmp_path):
    now = [100]
    queue = TeamOutbox(Database(tmp_path / 'ttl.db'), clock=lambda: now[0])
    value = message(created_at=100, expires_at=110)
    queue.enqueue(value)
    received = queue.reserve_incoming(value)
    now[0] = 99
    assert queue.claim_next() is None
    assert queue.get(value.message_id)['state'] == 'queued'
    now[0] = 110
    assert queue.complete_incoming(value.message_id, received['effect_token'], 'received-late')['state'] == 'completed'
    assert queue.reserve_incoming(value)['should_process'] is False


def test_queued_message_survives_restart_and_duplicate_enqueue_is_one_record(tmp_path):
    database = Database(tmp_path / 'team.db')
    queue = TeamOutbox(database)
    queued = queue.enqueue(message())
    assert queued['state'] == 'queued'
    restarted = TeamOutbox(database)
    assert restarted.get('message-one') == queued
    assert restarted.enqueue(message()) == queued
    assert restarted.status()['pending_count'] == 1


def test_recovery_fences_unsent_claim_before_another_worker_can_send(tmp_path):
    database = Database(tmp_path / 'team.db')
    queue = TeamOutbox(database)
    queue.enqueue(message())
    old = queue.claim('message-one')
    assert old['state'] == 'claimed'
    assert TeamOutbox(database).claim('message-one') is None
    restarted = TeamOutbox(database)
    restarted.recover()
    replacement = restarted.claim('message-one')
    assert replacement['claim_token'] != old['claim_token']
    with pytest.raises(PermissionError):
        queue.mark_sending('message-one', old['claim_token'])
    assert restarted.mark_sending('message-one', replacement['claim_token'])['state'] == 'sending'


def test_uncertain_send_is_held_after_restart_and_exact_late_ack_is_retained(tmp_path):
    database = Database(tmp_path / 'team.db')
    queue = TeamOutbox(database)
    original = message()
    queue.enqueue(original)
    claim = queue.claim(original.message_id)
    queue.mark_sending(original.message_id, claim['claim_token'])
    restarted = TeamOutbox(database)
    assert restarted.recover() == {'requeued': 0, 'held': 1}
    assert restarted.claim(original.message_id) is None
    assert restarted.enqueue(original)['state'] == 'outcome_unknown'
    receipt = dict(claim_token=claim['claim_token'], recipient_id='knight-b',
                   digest=original.digest(), receipt_id='signed-receipt-one')
    accepted = restarted.acknowledge(original.message_id, **receipt)
    assert accepted['state'] == 'acknowledged'
    assert accepted['message'] is None  # compact body, preserve replay protection
    assert accepted['receipt_id'] == 'signed-receipt-one'
    assert restarted.status()['pending_count'] == 0
    assert TeamOutbox(database).acknowledge(original.message_id, **receipt) == accepted
    assert TeamOutbox(database).claim(original.message_id) is None


def delivered(queue, value):
    claim = queue.claim(value.message_id)
    queue.mark_sending(value.message_id, claim['claim_token'])
    return queue.acknowledge(value.message_id, claim_token=claim['claim_token'],
                             recipient_id=value.recipient_id, digest=value.digest(),
                             receipt_id='receipt-' + value.message_id)


def test_pending_capacity_frees_after_ack_but_receipt_limit_never_prunes_deduplication(tmp_path):
    queue = TeamOutbox(Database(tmp_path / 'team.db'), TeamPolicy(routine_entries=1, receipt_entries=2))
    first, second = message(), message('message-two')
    queue.enqueue(first)
    with pytest.raises(BufferError):
        queue.enqueue(second)
    delivered(queue, first)
    assert queue.enqueue(second)['state'] == 'queued'
    delivered(queue, second)
    with pytest.raises(BufferError):
        queue.enqueue(message('message-three'))
    assert queue.enqueue(first)['state'] == 'acknowledged'
    assert queue.status()['pending_count'] == 0


def test_receiver_reserves_effect_once_and_keeps_unknown_effect_across_restart(tmp_path):
    database = Database(tmp_path / 'receiver.db')
    receiver = TeamOutbox(database)
    value = message()
    first = receiver.reserve_incoming(value)
    assert first['should_process'] is True
    assert first['effect_token']
    duplicate = TeamOutbox(database).reserve_incoming(value)
    assert duplicate['should_process'] is False and duplicate['effect_token'] is None
    restarted = TeamOutbox(database)
    restarted.recover()
    assert restarted.incoming_status(value.message_id)['state'] == 'outcome_unknown'
    assert restarted.reserve_incoming(value)['should_process'] is False
    saved = receiver.complete_incoming(value.message_id, first['effect_token'], 'receiver-receipt')
    assert saved['state'] == 'completed'
    final = TeamOutbox(database).reserve_incoming(value)
    assert final['should_process'] is False and final['receipt_id'] == 'receiver-receipt'
    assert final['digest'] == value.digest()
    with pytest.raises(ValueError):
        receiver.reserve_incoming(message(payload={'stage': 'different'}))


def test_unvalidated_policy_copy_is_rejected_before_admission(tmp_path):
    bad = TeamPolicy().model_copy(update={'receipt_entries': False})
    with pytest.raises(ValidationError):
        TeamOutbox(Database(tmp_path / 'team.db'), bad)


def test_restart_worker_can_claim_control_before_routine_without_volatile_id_list(tmp_path):
    database = Database(tmp_path / 'team.db')
    queue = TeamOutbox(database)
    queue.enqueue(message())
    queue.enqueue(message('stop-one', kind='stop', payload={'reason': 'owner stop'}))
    restarted = TeamOutbox(database)
    assert restarted.claim_next()['message_id'] == 'stop-one'
    assert restarted.claim_next()['message_id'] == 'message-one'
    assert restarted.claim_next() is None


def test_reserved_control_lane_remains_bounded_when_routine_lane_is_full(tmp_path):
    queue = TeamOutbox(Database(tmp_path / 'team.db'), TeamPolicy(routine_entries=1, control_entries=1))
    queue.enqueue(message())
    with pytest.raises(BufferError):
        queue.enqueue(message('routine-two'))
    assert queue.enqueue(message('stop-one', kind='stop', payload={'reason': 'stop'}))['state'] == 'queued'
    with pytest.raises(BufferError):
        queue.enqueue(message('stop-two', kind='stop', payload={'reason': 'stop'}))
    assert queue.status()['pending_count'] == 2


@pytest.mark.parametrize('kind,payload,policy', [
    ('progress', {'stage': 'one'}, TeamPolicy(routine_bytes=10)),
    ('stop', {'reason': 'stop'}, TeamPolicy(control_bytes=10)),
])
def test_byte_capacity_denies_oversized_admission_without_creating_record(tmp_path, kind, payload, policy):
    queue = TeamOutbox(Database(tmp_path / 'team.db'), policy)
    with pytest.raises(BufferError):
        queue.enqueue(message(kind=kind, payload=payload))
    with pytest.raises(KeyError):
        queue.get('message-one')


def test_changed_payload_or_envelope_never_reuses_an_existing_delivery_id(tmp_path):
    queue = TeamOutbox(Database(tmp_path / 'team.db'))
    first = queue.enqueue(message())
    for changed in (message(payload={'stage': 'other'}), message(recipient_id='other-knight'),
                    message(policy_revision=2), message(task_id='other-task')):
        with pytest.raises(ValueError):
            queue.enqueue(changed)
    assert queue.get('message-one') == first


@pytest.mark.parametrize('invalid', [
    {'claim_token': 'old-claim'}, {'recipient_id': 'other-knight'}, {'digest': '0' * 64},
])
def test_mismatched_ack_does_not_complete_the_delivery(tmp_path, invalid):
    queue = TeamOutbox(Database(tmp_path / 'team.db'))
    value = message()
    queue.enqueue(value)
    claim = queue.claim(value.message_id)
    queue.mark_sending(value.message_id, claim['claim_token'])
    receipt = dict(claim_token=claim['claim_token'], recipient_id=value.recipient_id,
                   digest=value.digest(), receipt_id='receipt-one')
    with pytest.raises(PermissionError):
        queue.acknowledge(value.message_id, **{**receipt, **invalid})
    assert queue.get(value.message_id)['state'] == 'sending'


def test_repeated_start_is_rejected_and_changed_receipts_cannot_replace_history(tmp_path):
    queue = TeamOutbox(Database(tmp_path / 'team.db'))
    value = message()
    queue.enqueue(value)
    claim = queue.claim(value.message_id)
    queue.mark_sending(value.message_id, claim['claim_token'])
    with pytest.raises(PermissionError):
        queue.mark_sending(value.message_id, claim['claim_token'])
    receipt = dict(claim_token=claim['claim_token'], recipient_id=value.recipient_id,
                   digest=value.digest(), receipt_id='receipt-one')
    queue.acknowledge(value.message_id, **receipt)
    with pytest.raises(ValueError):
        queue.acknowledge(value.message_id, **{**receipt, 'receipt_id': 'other-receipt'})
    assert queue.get(value.message_id)['receipt_id'] == 'receipt-one'


def test_two_instances_cannot_claim_or_reserve_an_effect_twice(tmp_path):
    database = Database(tmp_path / 'team.db')
    queues = [TeamOutbox(database), TeamOutbox(database)]
    value = message()
    queues[0].enqueue(value)
    barrier = Barrier(2)

    def claim(queue):
        barrier.wait()
        return queue.claim_next()

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, queues))
    assert sum(result is not None for result in claims) == 1
    barrier = Barrier(2)

    def reserve(queue):
        barrier.wait()
        return queue.reserve_incoming(value)

    with ThreadPoolExecutor(max_workers=2) as pool:
        effects = list(pool.map(reserve, queues))
    assert sum(result['should_process'] for result in effects) == 1
    winner = next(result for result in effects if result['should_process'])
    with pytest.raises(PermissionError):
        queues[1].complete_incoming(value.message_id, 'stale-effect-token', 'receipt-one')
    assert queues[0].complete_incoming(value.message_id, winner['effect_token'], 'receipt-one')['state'] == 'completed'


def test_receiver_and_sender_share_ledger_cap_without_losing_completed_receipt(tmp_path):
    database = Database(tmp_path / 'team.db')
    queue = TeamOutbox(database, TeamPolicy(receipt_entries=1))
    value = message()
    reserved = queue.reserve_incoming(value)
    queue.complete_incoming(value.message_id, reserved['effect_token'], 'incoming-receipt')
    with pytest.raises(BufferError):
        queue.reserve_incoming(message('other-incoming'))
    with pytest.raises(BufferError):
        queue.enqueue(message('outgoing'))
    assert TeamOutbox(database, TeamPolicy(receipt_entries=1)).reserve_incoming(value)['receipt_id'] == 'incoming-receipt'


def test_status_reports_held_incoming_effects_without_exposing_payload_or_claim_tokens(tmp_path):
    queue = TeamOutbox(Database(tmp_path / 'team.db'))
    value = message(payload={'stage': 'PRIVATE'})
    reserved = queue.reserve_incoming(value)
    assert queue.status()['incoming_pending_count'] == 1
    queue.recover()
    held = queue.status()
    assert held['incoming_unknown_count'] == 1 and held['receipt_count'] == 1
    assert reserved['effect_token'] not in str(held)
    assert 'PRIVATE' not in str(held)
    queue.complete_incoming(value.message_id, reserved['effect_token'], 'receipt-one')
    assert queue.status()['incoming_pending_count'] == 0


def test_event_failure_after_send_boundary_cannot_turn_committed_send_back_into_retry(tmp_path):
    database = Database(tmp_path / 'team.db')

    def unavailable(event, data):
        if event == 'team.message_sending':
            raise OSError('Event sink interrupted after storage commit')

    queue = TeamOutbox(database, publish=unavailable)
    queue.enqueue(message())
    claim = queue.claim_next()
    with pytest.raises(OSError):
        queue.mark_sending('message-one', claim['claim_token'])
    restarted = TeamOutbox(database)
    restarted.recover()
    assert restarted.get('message-one')['state'] == 'outcome_unknown'
    assert restarted.claim_next() is None


def test_caller_mutation_does_not_change_persisted_message_or_audit_event(tmp_path):
    events = []
    queue = TeamOutbox(Database(tmp_path / 'team.db'), publish=lambda *event: events.append(event))
    value = message()
    queue.enqueue(value)
    value.payload['stage'] = 'PRIVATE'
    observed = queue.get('message-one')
    observed['message']['payload']['stage'] = 'CHANGED'
    assert queue.get('message-one')['message']['payload']['stage'] == 'testing'
    assert all('PRIVATE' not in str(event) and 'testing' not in str(event) for event in events)
