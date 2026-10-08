import sqlite3
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from backend.runtime.automation import AutomationSupervisor


class Adapter:
    id, name, revision = 'worker', 'Reviewed worker', 'rev1'
    def __init__(self):
        self.original = self.candidate = self.checks = 0
        self.pass_checks = True
        self.fail_run = False
    def inspect(self):
        return {'completed_skills': 12}
    def verify(self):
        self.checks += 1
        return {'passed': self.pass_checks}
    def run_original(self):
        self.original += 1
    def run_candidate(self):
        self.candidate += 1
        if self.fail_run:
            raise RuntimeError('secret must not enter state')


@pytest.fixture
def setup(tmp_path):
    level, now, events = [3], [1000], []
    connect = lambda: sqlite3.connect(tmp_path / 'automation.sqlite3', timeout=5)
    service = AutomationSupervisor(connect, lambda: level[0], lambda *args: events.append(args), lambda: now[0])
    adapter = Adapter()
    service.register(adapter)
    return service, adapter, level, now, events, connect


def test_original_remains_until_approved_and_verified(setup):
    s, a, *_ = setup
    s.run(a.id)
    assert (a.original, a.candidate, a.checks) == (1, 0, 0)
    s.approve(a.id, a.revision)
    assert s.run(a.id)['owner'] == 'kingdom'
    assert (a.original, a.candidate, a.checks) == (1, 1, 1)


@pytest.mark.parametrize('level', [0, 1, 2])
def test_lower_levels_do_not_adopt_and_pause_owned_work(setup, level):
    s, a, policy, *_ = setup
    s.approve(a.id, a.revision)
    policy[0] = level
    assert s.run(a.id)['owner'] == 'original'
    policy[0] = 3
    s.run(a.id)
    policy[0] = level
    assert s.run(a.id)['status'] == 'paused_by_autonomy'
    assert a.candidate == 1


def test_failed_checks_keep_original_and_bound_retries(setup):
    s, a, _, now, *_ = setup
    s.approve(a.id, a.revision)
    a.pass_checks = False
    for attempt in range(3):
        with pytest.raises(ValueError): s.run(a.id)
        assert s.inventory()[0]['owner'] == 'original'
        s.run(a.id)  # Cooldown uses original, never reruns failed candidate.
        now[0] += 1800
    s.run(a.id)
    assert a.checks == 3 and a.candidate == 0 and a.original == 4


def test_failure_rolls_back_without_duplicate_execution_and_can_recover(setup):
    s, a, _, now, _, connect = setup
    s.approve(a.id, a.revision)
    a.fail_run = True
    with pytest.raises(RuntimeError): s.run(a.id)
    assert a.original == 0  # Never rerun after uncertain side effects.
    record = s.inventory()[0]
    assert record['owner'] == 'original' and record['last_failure'] == 'RuntimeError'
    assert 'secret' not in str(record)
    s.run(a.id)
    a.fail_run = False
    now[0] += 1800
    restarted = AutomationSupervisor(connect, lambda: 3, lambda *args: None, lambda: now[0])
    restarted.register(a)
    assert restarted.run(a.id)['owner'] == 'kingdom'


def test_revision_change_requires_fresh_approval(setup):
    s, a, *_ = setup
    s.approve(a.id, a.revision); s.run(a.id)
    a.revision = 'rev2'
    assert s.run(a.id)['owner'] == 'original'
    assert a.candidate == 1
    with pytest.raises(ValueError): s.approve(a.id, 'rev1')


def test_concurrent_calls_cannot_publish_twice(setup):
    s, a, *_ = setup
    s.approve(a.id, a.revision)
    entered, release = Event(), Event()
    def run():
        entered.set()
        assert release.wait(5)
        a.candidate += 1
    a.run_candidate = run
    with ThreadPoolExecutor(2) as pool:
        future = pool.submit(s.run, a.id)
        assert entered.wait(5)
        assert s.run(a.id)['status'] == 'busy'
        with pytest.raises(ValueError): s.approve(a.id, a.revision)
        release.set(); future.result()
    assert a.candidate == 1


def test_crashed_lease_not_reclaimed_by_timeout(setup):
    s, a, _, now, _, connect = setup
    with connect() as db:
        state = s._load(db, a.id); state['lease'] = 'crashed'; s._save(db, state)
    now[0] += 999999
    assert s.run(a.id)['status'] == 'busy'
    with pytest.raises(ValueError): s.recover_stopped(a.id, 'wrong')
    s.recover_stopped(a.id, 'crashed')
    assert s.run(a.id)['owner'] == 'original'


def test_workshop_adapter_retains_progress_and_rejects_changed_sources(tmp_path):
    from backend.runtime.workshop_adapter import WorkshopAdapter
    (tmp_path / 'app').mkdir(); (tmp_path / 'skill-workshop').mkdir()
    source = tmp_path / 'app/skill_workshop.py'; source.write_text('# reviewed runner')
    manifest = {'tests_passed': 29, 'files': {'skill_workshop.py': hashlib.sha256(source.read_bytes()).hexdigest()}}
    core = ['backend/runtime/automation.py', 'backend/runtime/workshop_adapter.py', 'scripts/workshop_supervisor.py']
    for name in core:
        target = tmp_path / 'kingdom-automation-source' / name
        target.parent.mkdir(parents=True, exist_ok=True); target.write_text('# tested core')
    (tmp_path / 'app/workshop_supervisor.py').write_text('# tested core')
    manifest['supervisor_files'] = {name: hashlib.sha256(b'# tested core').hexdigest() for name in core}
    (tmp_path / 'app/automation-manifest.json').write_text(json.dumps(manifest))
    with sqlite3.connect(tmp_path / 'skill-workshop/workshop.sqlite3') as db:
        db.executescript("CREATE TABLE skills(slug TEXT); CREATE TABLE sessions(slug TEXT, mode TEXT, elapsed REAL,status TEXT); INSERT INTO sessions VALUES('json-format','improve',5400,'working');")
    runs = []
    adapter = WorkshopAdapter(tmp_path, lambda: runs.append('existing-reviewed-runner'))
    assert adapter.verify()['passed']
    assert adapter.inspect()['active_work'][0]['seconds'] == 5400
    adapter.run_candidate(); assert len(runs) == 1
    source.write_text('# changed without testing')
    with pytest.raises(ValueError, match='source changed'): adapter.run_candidate()
    assert len(runs) == 1


def test_inventory_api_requires_owner_and_rejects_unknown_adapter():
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.security.http_auth import owner_auth
    client = TestClient(app)
    assert client.get('/automations').status_code == 401
    client.headers['Authorization'] = 'Bearer ' + owner_auth.token
    response = client.get('/automations')
    assert response.status_code == 200
    assert isinstance(response.json()['automations'], list)
    assert client.post('/automations/unknown/approve', json={'revision': 'arbitrary'}).status_code == 409


def test_parallel_preview_uses_stable_autonomy_authority(tmp_path, monkeypatch):
    import io
    from backend.runtime import policy
    from backend.storage.db import Database
    token = tmp_path / 'token'; token.write_text('local-test-owner-token')
    monkeypatch.setenv('KINGDOM_POLICY_AUTHORITY_TOKEN_FILE', str(token))
    calls = []
    def respond(request, **kwargs):
        calls.append(request)
        return io.BytesIO(b'{"level": 0}')
    monkeypatch.setattr(policy, 'urlopen', respond)
    instance = policy.ExecutionPolicy(Database(tmp_path / 'runtime.db'))
    assert instance.get()['level'] == 0
    instance.set(0)
    assert calls[0].full_url == 'http://127.0.0.1:8012/runtime/policy'
    assert calls[1].method == 'PUT'
    assert calls[1].data == b'{"level": 0}'
    assert calls[0].get_header('Authorization') == 'Bearer local-test-owner-token'
    monkeypatch.setattr(policy, 'urlopen', lambda *args, **kwargs: io.BytesIO(b'{"level": true}'))
    with pytest.raises(RuntimeError): instance.get()
