"""Public message contract: payload data cannot declare execution authority."""
import pytest
from pydantic import ValidationError

from backend.cluster.team_policy import TeamMessage, TeamPolicy


def message(**changes):
    return TeamMessage(**{
        'message_id': 'message-1', 'task_id': 'task-1', 'sender_id': 'knight-a',
        'recipient_id': 'knight-b', 'policy_revision': 1, 'kind': 'progress',
        'created_at': 100, 'expires_at': 200, 'payload': {'percent': 25}, **changes})


def test_message_lifetime_is_explicit_bounded_and_immutable_under_revalidation():
    item = message()
    assert item.assert_current(100) is item
    assert item.assert_current(199.9) is item
    for now in (99, 200, float('nan'), float('inf'), True):
        with pytest.raises(ValueError):
            item.assert_current(now)
    for changes in ({'created_at': -1}, {'expires_at': float('inf')},
                    {'expires_at': 100}, {'expires_at': 86501},
                    {'created_at': True}, {'expires_at': 253402300800}, {'expires_at': 10**1000}):
        with pytest.raises(ValidationError):
            message(**changes)
    assert TeamMessage.model_validate_json(item.canonical_bytes()).expires_at == 200


def test_message_rejects_authority_fields():
    with pytest.raises(ValidationError):
        TeamMessage(message_id='message-1', task_id='task-1', sender_id='knight-a',
                    recipient_id='knight-b', policy_revision=1, kind='progress',
                    payload={'percent': 25}, actor='owner', control_authorized=True)


@pytest.mark.parametrize(('kind', 'payload'), [
    ('stop', {'reason': 'owner stop', 'file_data': 'not control'}),
    ('revocation', {'node_id': 'knight-b', 'revision': 2, 'data': 'not control'}),
    ('recovery', {'operation_id': 'message-1', 'state': 'query', 'data': 'not control'}),
])
def test_control_reserve_messages_cannot_carry_routine_data(kind, payload):
    with pytest.raises(ValidationError):
        message(kind=kind, payload=payload)


@pytest.mark.parametrize('changes', [{'group_id': 'team-1'}, {'group_revision': 2}])
def test_group_delivery_requires_both_identity_and_revision(changes):
    with pytest.raises(ValidationError):
        message(**changes)


@pytest.mark.parametrize('payload', [
    {'text': 'a' * 16385},
    {'text': '\u2603' * 6000},  # UTF-8 bytes, not just character count.
    {'value': float('nan')},
    {'value': float('inf')},
    {'value': (1, 2)},
    {'value': b'not JSON'},
])
def test_message_rejects_oversized_or_non_json_payloads(payload):
    with pytest.raises(ValidationError):
        message(payload=payload)


def test_canonical_message_detaches_input_and_rejects_later_unsafe_mutation():
    payload = {'values': [1, 2]}
    item = message(payload=payload)
    payload['values'].append(3)
    assert item.payload == {'values': [1, 2]}
    item.payload['invalid'] = b'not JSON'
    with pytest.raises(ValidationError):
        item.canonical_bytes()


def test_identical_json_key_order_is_one_message_but_changed_scope_is_not():
    first = message(payload={'a': 1, 'b': 2})
    reordered = message(payload={'b': 2, 'a': 1})
    assert first.canonical_bytes() == reordered.canonical_bytes()
    assert first.digest() == reordered.digest()
    assert first.digest() != message(payload={'a': 1, 'b': 2}, policy_revision=2).digest()


@pytest.mark.parametrize(('kind', 'payload'), [
    ('stop', {'reason': 'owner requested stop'}),
    ('revocation', {'node_id': 'knight-b', 'revision': 2}),
    ('recovery', {'operation_id': 'message-1', 'state': 'query'}),
])
def test_small_valid_control_messages_remain_serializable(kind, payload):
    assert message(kind=kind, payload=payload).canonical_bytes()


@pytest.mark.parametrize('changes', [
    {'policy_revision': 2**63},
    {'group_id': 'team-1', 'group_revision': 2**63},
    {'kind': 'revocation', 'payload': {'node_id': 'knight-b', 'revision': 2**63}},
])
def test_revisions_fit_durable_sqlite_counters(changes):
    with pytest.raises(ValidationError):
        message(**changes)


def test_copied_policy_is_revalidated_before_it_can_control_resources():
    invalid = TeamPolicy().model_copy(update={'wifi_routine_bytes': True, 'routine_entries': 0})
    with pytest.raises(ValidationError):
        TeamPolicy.model_validate(invalid)
