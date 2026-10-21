from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from backend.storage.db import Database
from backend.runtime.durable_automation import DurableAutomations
from backend.runtime.request_service import RequestService


def test_schedule_restart_checkpoint_and_missed_interval_coalescing(tmp_path):
    database = Database(tmp_path/'schedule.db')
    service = DurableAutomations(database, clock=lambda: 100)
    schedule = service.create('project', 'safe note', 60)
    restarted = DurableAutomations(database, clock=lambda: 100)
    receipts = restarted.tick()
    assert len(receipts) == 1
    assert restarted.tick() == []
    state = restarted.get('project', schedule['id'])
    assert state['checkpoint']['run_key'] == receipts[0]['run_key']
    assert state['next_due'] == 160
    late = DurableAutomations(database, clock=lambda: 1000)
    assert len(late.tick()) == 1
    assert late.get('project', schedule['id'])['next_due'] == 1060
    assert len(late.receipts('project', schedule['id'])) == 2


def test_competing_real_database_workers_commit_effect_once(tmp_path):
    database = Database(tmp_path/'schedule.db')
    services = [DurableAutomations(database, clock=lambda: 100) for _ in range(2)]
    services[0].create('p', 'note', 60)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda service: service.tick(), services))
    assert sum(len(result) for result in results) == 1
    with database.get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM durable_schedule_notes').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM durable_schedule_runs').fetchone()[0] == 1


def test_receipt_failure_rolls_back_effect_and_restart_retries_without_duplicates(tmp_path):
    database = Database(tmp_path/'schedule.db')
    service = DurableAutomations(database, clock=lambda: 100)
    schedule = service.create('p', 'note', 60)
    with database.get_connection() as conn:
        conn.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON durable_schedule_runs BEGIN SELECT RAISE(ABORT, 'disk receipt failure'); END")
        conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        service.tick()
    with database.get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM durable_schedule_notes').fetchone()[0] == 0
        conn.execute('DROP TRIGGER fail_receipt')
        conn.commit()
    restarted = DurableAutomations(database, clock=lambda: 100)
    assert len(restarted.tick()) == 1
    assert restarted.tick() == []
    assert len(restarted.receipts('p', schedule['id'])) == 1


def test_pause_resume_cancel_revision_and_project_isolation(tmp_path):
    service = DurableAutomations(Database(tmp_path/'schedule.db'), clock=lambda: 100)
    schedule = service.create('p', 'note', 60)
    paused = service.change_status('p', schedule['id'], 'paused', schedule['revision'])
    assert service.tick() == []
    with pytest.raises(ValueError):
        service.change_status('p', schedule['id'], 'active', schedule['revision'])
    with pytest.raises(KeyError):
        service.change_status('other', schedule['id'], 'active', paused['revision'])
    active = service.change_status('p', schedule['id'], 'active', paused['revision'])
    cancelled = service.change_status('p', schedule['id'], 'cancelled', active['revision'])
    assert service.tick() == []
    with pytest.raises(ValueError):
        service.change_status('p', schedule['id'], 'active', cancelled['revision'])


def test_work_schedule_defaults_paused_then_enqueues_real_bridge_without_running(tmp_path):
    database = Database(tmp_path/'work.db')
    bridge = RequestService(database, None, None, None)
    service = DurableAutomations(database, clock=lambda: 100, enqueue_request=bridge.create, cancel_request=bridge.cancel)
    schedule = service.create_work('p', 'Inspect the project', 60, model_profile='local-reviewed', allow_process=False)
    assert schedule['status'] == 'paused' and schedule['autorun'] is False
    assert service.tick() == [] and service.deliver() == []
    service.change_status('p', schedule['id'], 'active', schedule['revision'])
    service.tick()
    delivered = service.deliver()
    assert len(delivered) == 1
    request = bridge.get(delivered[0]['request_id'])
    assert request['status'] == 'queued' and request['model_profile'] == 'local-reviewed'
    assert request['allow_process'] is False and request['project_scope'] == 'projects/p'
    assert request['session_scope'] == 'automation-p'
    assert request['idempotency_key'].startswith('schedule:'+schedule['id']+':')
    assert service.deliver() == []
    assert service.get('p', schedule['id'])['checkpoint']['request_id'] == request['id']


def test_interrupted_bridge_delivery_replays_saved_key_not_existing_job(tmp_path):
    database = Database(tmp_path/'work.db')
    bridge = RequestService(database, None, None, None)
    def interrupt_after_commit(body):
        bridge.create(body)
        raise RuntimeError('connection lost after durable create')
    service = DurableAutomations(database, clock=lambda: 100, enqueue_request=interrupt_after_commit)
    schedule = service.create_work('p', 'Review results', 60, enabled=True)
    service.tick()
    assert service.deliver() == []
    existing = bridge.list('automation-p', 'projects/p')
    assert len(existing) == 1 and existing[0]['status'] == 'queued'
    restarted = DurableAutomations(database, clock=lambda: 100, enqueue_request=bridge.create)
    receipt = restarted.deliver()[0]
    assert receipt['request_id'] == existing[0]['id']
    assert len(bridge.list('automation-p', 'projects/p')) == 1
    assert len(restarted.receipts('p', schedule['id'])) == 1


def test_cancel_or_pause_before_delivery_prevents_bridge_create(tmp_path):
    database = Database(tmp_path/'work.db')
    bridge = RequestService(database, None, None, None)
    service = DurableAutomations(database, clock=lambda: 100, enqueue_request=bridge.create)
    for status in ('paused','cancelled'):
        schedule = service.create_work('p', 'Review evidence', 60, enabled=True)
        service.tick()
        current = service.get('p', schedule['id'])
        service.change_status('p', schedule['id'], status, current['revision'])
    assert service.deliver() == []
    assert bridge.list('automation-p', 'projects/p') == []


def test_concurrent_outbox_delivery_creates_only_one_real_request(tmp_path):
    database = Database(tmp_path/'work.db')
    bridge = RequestService(database, None, None, None)
    services = [DurableAutomations(database, clock=lambda: 100, enqueue_request=bridge.create) for _ in range(2)]
    services[0].create_work('p', 'Review evidence', 60, enabled=True)
    services[0].tick()
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda service: service.deliver(), services))
    assert len(bridge.list('automation-p', 'projects/p')) == 1
