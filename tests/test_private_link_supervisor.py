import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location('private_links', Path(__file__).parents[1] / 'scripts/supervise-private-links.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def link():
    return {'name': 'approved-peer', 'argv': ['ssh', '-F', 'private-config', '-N',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes',
        '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3', '-o', 'ConnectTimeout=10',
        '-L', '127.0.0.1:8014:127.0.0.1:8012', 'owner@approved-host']}


class Child:
    pid = 123
    code = None
    terminated = False
    def poll(self): return self.code
    def terminate(self): self.terminated = True; self.code = 0
    def wait(self, timeout): return self.code


def test_repeated_steps_do_not_duplicate_live_child_and_stop_only_owned_child():
    children = []
    def spawn(*args, **kwargs):
        child = Child(); children.append(child); return child
    worker = module.Supervisor([link()], spawn=spawn, clock=lambda: 0)
    worker.step(); worker.step(); worker.step()
    assert len(children) == 1
    assert worker.receipt()['connection_verified'] is False
    worker.stop()
    assert children[0].terminated
    assert worker.receipt()['links'][0]['status'] == 'stopped'


def test_failure_uses_bounded_exponential_backoff_without_busy_retry():
    now = [0]
    attempts = []
    def spawn(*args, **kwargs):
        attempts.append(now[0]); raise OSError('sensitive host information')
    worker = module.Supervisor([link()], spawn=spawn, clock=lambda: now[0])
    for value in range(200):
        now[0] = value; worker.step()
    assert attempts[:6] == [0, 2, 6, 14, 30, 62]
    assert max(b-a for a, b in zip(attempts, attempts[1:])) == 60
    assert 'sensitive' not in json.dumps(worker.receipt())


def test_dead_child_reconnect_waits_instead_of_restarting_immediately():
    now = [0]
    children = []
    def spawn(*args, **kwargs):
        child = Child(); children.append(child); return child
    worker = module.Supervisor([link()], spawn=spawn, clock=lambda: now[0])
    worker.step(); children[0].code = 1
    worker.step(); worker.step()
    assert len(children) == 1
    now[0] = 2; worker.step()
    assert len(children) == 2


@pytest.mark.parametrize('old,new', [
    ('StrictHostKeyChecking=yes', 'StrictHostKeyChecking=no'),
    ('BatchMode=yes', 'BatchMode=no'),
    ('ExitOnForwardFailure=yes', 'ExitOnForwardFailure=no'),
    ('ServerAliveInterval=15', 'ProxyCommand=unsafe-command'),
    ('127.0.0.1:8014:127.0.0.1:8012', '0.0.0.0:8014:127.0.0.1:8012'),
    ('127.0.0.1:8014:127.0.0.1:8012', '8014:127.0.0.1:8012'),
    ('ssh', 'powershell')])
def test_unsafe_or_unbounded_config_rejected(old, new):
    value = link(); value['argv'] = [new if item == old else item for item in value['argv']]
    with pytest.raises(ValueError): module.validate_link(value)


def test_no_remote_commands_and_no_sensitive_arguments_in_receipt():
    value = link(); value['argv'] += ['execute something']
    with pytest.raises(ValueError): module.validate_link(value)
    worker = module.Supervisor([link()])
    text = json.dumps(worker.receipt())
    assert 'private-config' not in text and 'approved-host' not in text and 'argv' not in text


def test_lock_rejects_second_supervisor_and_release_cannot_delete_another_owner(tmp_path):
    path = tmp_path / 'supervisor.lock'
    first, second = module.ProcessLock(path), module.ProcessLock(path)
    first.acquire()
    with pytest.raises(RuntimeError, match='already running'): second.acquire()
    second.release()
    assert path.exists()
    first.release()
    assert not path.exists()


def test_receipt_writes_atomically(tmp_path):
    path = tmp_path / 'nested/status.json'
    module.write_receipt(path, {'status': 'safe'})
    assert json.loads(path.read_text()) == {'status': 'safe'}
    assert not path.with_suffix('.tmp').exists()


def test_model_forward_failure_cannot_take_down_dashboard_on_same_host():
    mixed=link()
    mixed['argv'][-1:-1]=['-R','127.0.0.1:11434:127.0.0.1:11434']
    children=[]
    def spawn(argv,**kwargs):
        if '-R' in argv:raise OSError('Remote model port occupied')
        child=Child();children.append(child);return child
    worker=module.Supervisor([mixed],spawn=spawn,clock=lambda:0)
    worker.step()
    assert len(children)==1
    assert sorted(item['status'] for item in worker.receipt()['links'])==['process_running','reconnecting']
