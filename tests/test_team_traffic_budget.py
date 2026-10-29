"""Traffic accounting through public APIs and real SQLite, never network mocks."""
import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from backend.cluster.traffic_budget import TrafficBudget, BudgetExceeded
from backend.cluster.team_policy import TeamMessage, TeamPolicy
from backend.storage.db import Database


def message(ident='message-one', sender='host-a', kind='progress', payload=None, **changes):
    return TeamMessage(message_id=ident, task_id='task-one', sender_id=sender,
        recipient_id='host-b', policy_revision=1, kind=kind,
        payload=payload if payload is not None else {'text': 'private working detail'},
        **{'created_at': 0, 'expires_at': 86400, **changes})


def test_expiry_denies_new_spend_but_preserves_historical_reservation(tmp_path):
    now = [100]
    database = Database(tmp_path / 'budget.db')
    budget = TrafficBudget(database, 'host-a', clock=lambda: now[0])
    value = message(created_at=100, expires_at=110)
    receipt = budget.reserve('old-attempt', value, authenticated_actor='host-a')
    now[0] = 110
    restarted = TrafficBudget(database, 'host-a', clock=lambda: now[0])
    assert restarted.reserve('old-attempt', value, authenticated_actor='host-a') == receipt
    with pytest.raises(ValueError):
        restarted.reserve('new-attempt', value, authenticated_actor='host-a')
    now[0] = 99
    with pytest.raises(ValueError):
        restarted.reserve('future-attempt', value, authenticated_actor='host-a')
    assert restarted.status()['routine']['used'] == receipt['byte_count']


def test_reservation_survives_restart_without_double_charge(tmp_path):
    database = Database(tmp_path / 'budget.db')
    budget = TrafficBudget(database, 'host-a', clock=lambda: 100)
    first = budget.reserve('attempt-one', message(), authenticated_actor='host-a', byte_count=1024)
    restarted = TrafficBudget(Database(tmp_path / 'budget.db'), 'host-a', clock=lambda: 100)
    duplicate = restarted.reserve('attempt-one', message(), authenticated_actor='host-a', byte_count=1024)
    assert duplicate == first
    assert restarted.status()['routine']['used'] == 1024
    assert 'private working detail' not in str(first)


def test_routine_exhaustion_queues_without_borrowing_control_allowance(tmp_path):
    policy = TeamPolicy(wifi_routine_bytes=1024, wifi_control_bytes=1024)
    budget = TrafficBudget(Database(tmp_path / 'budget.db'), 'host-a', policy=policy, clock=lambda: 100)
    budget.reserve('attempt-one', message(), authenticated_actor='host-a', byte_count=1024)
    with pytest.raises(BudgetExceeded):
        budget.reserve('attempt-two', message('message-two'), authenticated_actor='host-a')
    assert budget.status()['routine']['remaining'] == 0
    assert budget.status()['control']['remaining'] == 1024


def test_control_reserve_requires_independent_authorization_and_has_its_own_cap(tmp_path):
    budget = TrafficBudget(Database(tmp_path / 'budget.db'), 'host-a',
        policy=TeamPolicy(wifi_routine_bytes=1024, wifi_control_bytes=1024), clock=lambda: 100)
    stop = message('stop-one', kind='stop', payload={'reason': 'owner requested stop'})
    with pytest.raises(PermissionError):
        budget.reserve('unauthorized-stop', stop, authenticated_actor='host-a', byte_count=1024)
    budget.reserve('routine-full', message(), authenticated_actor='host-a', byte_count=1024)
    receipt = budget.reserve('authorized-stop', stop, authenticated_actor='host-a', byte_count=1024,
                             control_authorized=True)
    assert receipt['lane'] == 'control'
    assert budget.status()['control']['remaining'] == 0
    with pytest.raises(BudgetExceeded):
        budget.reserve('another-stop', message('stop-two', kind='stop', payload={'reason': 'stop'}),
                       authenticated_actor='host-a', control_authorized=True)


def test_clock_rollback_and_restart_do_not_refill_but_a_new_window_does(tmp_path):
    now = [100]
    database = Database(tmp_path / 'budget.db')
    policy = TeamPolicy(wifi_routine_bytes=1024)
    budget = TrafficBudget(database, 'host-a', policy=policy, clock=lambda: now[0])
    old = budget.reserve('old-attempt', message(), authenticated_actor='host-a', byte_count=1024)
    now[0] = 10
    restarted = TrafficBudget(database, 'host-a', policy=policy, clock=lambda: now[0])
    assert restarted.status()['routine']['remaining'] == 0
    now[0] = 120
    assert restarted.status()['routine']['remaining'] == 1024
    assert restarted.reserve('old-attempt', message(), authenticated_actor='host-a', byte_count=1024) == old
    assert restarted.status()['routine']['used'] == 0
    restarted.reserve('new-attempt', message('new-message'), authenticated_actor='host-a', byte_count=1024)
    now[0] = 100000
    assert restarted.status()['routine']['remaining'] == 1024
    restarted.reserve('future-attempt', message('future-message', created_at=100000, expires_at=100100), authenticated_actor='host-a', byte_count=1024)
    now[0] = 130
    assert restarted.status()['routine']['remaining'] == 0


def test_authenticated_containers_share_parent_allowance_and_revocation_beats_cache(tmp_path):
    database = Database(tmp_path / 'budget.db')
    budget = TrafficBudget(database, 'host-a', policy=TeamPolicy(wifi_routine_bytes=1024), clock=lambda: 100)
    child = message('child-message', sender='container-a')
    with pytest.raises(PermissionError):
        budget.reserve('child-attempt', child, authenticated_actor='container-a', byte_count=512)


    budget.bind_actor('container-a')
    budget.reserve('host-attempt', message(), authenticated_actor='host-a', byte_count=512)
    budget.reserve('child-attempt', child, authenticated_actor='container-a', byte_count=512)
    assert budget.status()['routine']['used'] == 1024
    other = TrafficBudget(database, 'host-z', clock=lambda: 100)
    with pytest.raises(PermissionError):
        other.bind_actor('container-a')
    with pytest.raises(PermissionError):
        other.reserve('child-attempt', child, authenticated_actor='container-a', byte_count=512)
    budget.unbind_actor('container-a')
    with pytest.raises(PermissionError):
        budget.reserve('child-attempt', child, authenticated_actor='container-a', byte_count=512)


def test_bound_or_revoked_container_cannot_claim_a_new_physical_host_budget(tmp_path):
    database = Database(tmp_path / 'budget.db')
    host = TrafficBudget(database, 'host-a', clock=lambda: 100)
    host.bind_actor('container-a')
    impostor = TrafficBudget(database, 'container-a', clock=lambda: 100)
    with pytest.raises(PermissionError):
        impostor.reserve('extra-quota', message(sender='container-a'), authenticated_actor='container-a')
    host.unbind_actor('container-a')
    with pytest.raises(PermissionError):
        impostor.reserve('revoked-extra-quota', message(sender='container-a'), authenticated_actor='container-a')


def test_full_reservation_ledger_holds_admission_without_deleting_duplicate_protection(tmp_path):
    database = Database(tmp_path / 'budget.db')
    budget = TrafficBudget(database, 'host-a', policy=TeamPolicy(receipt_entries=2), clock=lambda: 100)
    first = budget.reserve('one', message('one'), authenticated_actor='host-a')
    budget.reserve('two', message('two'), authenticated_actor='host-a')
    with pytest.raises(BudgetExceeded):
        budget.reserve('three', message('three'), authenticated_actor='host-a')
    assert budget.reserve('one', message('one'), authenticated_actor='host-a') == first


def test_two_instances_cannot_overspend_one_host_allowance_concurrently(tmp_path):
    database = Database(tmp_path / 'budget.db')
    policy = TeamPolicy(wifi_routine_bytes=1024)
    ledgers = [TrafficBudget(database, 'host-a', policy=policy, clock=lambda: 100) for _ in range(2)]
    ready = Barrier(4)

    def reserve(index):
        ready.wait(timeout=5)
        try:
            ledgers[index % 2].reserve(f'attempt-{index}', message(f'message-{index}'),
                                     authenticated_actor='host-a', byte_count=512)
            return 'reserved'
        except BudgetExceeded:
            return 'held'

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(reserve, range(4)))
    assert outcomes.count('reserved') == 2
    assert outcomes.count('held') == 2
    assert ledgers[0].status()['routine']['used'] == 1024


def test_concurrent_duplicate_attempt_is_charged_once(tmp_path):
    database = Database(tmp_path / 'budget.db')
    ledgers = [TrafficBudget(database, 'host-a', clock=lambda: 100) for _ in range(2)]
    ready = Barrier(4)

    def reserve(index):
        ready.wait(timeout=5)
        return ledgers[index % 2].reserve('same-attempt', message(), authenticated_actor='host-a', byte_count=512)

    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(reserve, range(4)))
    assert all(receipt == receipts[0] for receipt in receipts)
    assert ledgers[1].status()['routine']['used'] == 512


def test_attempt_identifier_cannot_be_reused_for_changed_bytes_payload_or_principal(tmp_path):
    budget = TrafficBudget(Database(tmp_path / 'budget.db'), 'host-a', clock=lambda: 100)
    budget.reserve('attempt', message(), authenticated_actor='host-a', byte_count=1024)
    with pytest.raises(ValueError):
        budget.reserve('attempt', message(), authenticated_actor='host-a', byte_count=1025)
    with pytest.raises(ValueError):
        budget.reserve('attempt', message(payload={'text': 'changed'}), authenticated_actor='host-a', byte_count=1024)
    budget.bind_actor('container-a')
    with pytest.raises(ValueError):
        budget.reserve('attempt', message(sender='container-a'), authenticated_actor='container-a', byte_count=1024)
    with pytest.raises(PermissionError):
        budget.reserve('attempt', message(), authenticated_actor='unregistered', byte_count=1024)
    assert budget.status()['routine']['used'] == 1024


@pytest.mark.parametrize('count', [True, False, -1, 0, 1.0, float('nan'), float('inf')])
def test_byte_reservation_rejects_invalid_or_underreported_counts(tmp_path, count):
    budget = TrafficBudget(Database(tmp_path / 'budget.db'), 'host-a', clock=lambda: 100)
    with pytest.raises(ValueError):
        budget.reserve('attempt', message(), authenticated_actor='host-a', byte_count=count)
    assert budget.status()['routine']['used'] == 0


@pytest.mark.parametrize('now', [True, -1, float('nan'), float('inf'), 1e308, 10**1000])
def test_invalid_clock_never_grants_an_allowance(tmp_path, now):
    budget = TrafficBudget(Database(tmp_path / 'budget.db'), 'host-a', clock=lambda: now)
    with pytest.raises(ValueError):
        budget.reserve('attempt', message(), authenticated_actor='host-a')
    with pytest.raises(ValueError):
        budget.status()


def test_control_urgency_flag_cannot_move_routine_data_into_reserved_lane(tmp_path):
    budget = TrafficBudget(Database(tmp_path / 'budget.db'), 'host-a',
        policy=TeamPolicy(wifi_routine_bytes=512), clock=lambda: 100)
    budget.reserve('one', message(), authenticated_actor='host-a', byte_count=512)
    with pytest.raises(BudgetExceeded):
        budget.reserve('two', message('two'), authenticated_actor='host-a', control_authorized=True)
    assert budget.status()['control']['used'] == 0


def test_new_window_duration_does_not_erase_the_current_window_spend(tmp_path):
    now = [100]
    database = Database(tmp_path / 'budget.db')
    first = TrafficBudget(database, 'host-a', policy=TeamPolicy(wifi_routine_bytes=512, window_seconds=60), clock=lambda: now[0])
    first.reserve('one', message(), authenticated_actor='host-a', byte_count=512)
    changed = TrafficBudget(database, 'host-a', policy=TeamPolicy(wifi_routine_bytes=512, window_seconds=1), clock=lambda: now[0])
    now[0] = 110
    assert changed.status()['routine']['remaining'] == 0
    now[0] = 120
    assert changed.status()['routine']['remaining'] == 512


@pytest.mark.parametrize('field,value', [('wifi_routine_bytes', True), ('wifi_control_bytes', 0), ('window_seconds', 0)])
def test_constructor_revalidates_copied_policy_instances(tmp_path, field, value):
    copied = TeamPolicy().model_copy(update={field: value})
    with pytest.raises(ValueError):
        TrafficBudget(Database(tmp_path / 'budget.db'), 'host-a', policy=copied)
