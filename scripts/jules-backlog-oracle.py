"""Protected host assertions for one positive backlog-advancement contract.

Candidate code executes only in the disposable API sandbox. This module never
imports it, its pytest plugins, or its test counts. These fixed scenarios are
bounded scheduler evidence, not general source correctness or release authority.
"""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import time


CONTRACT_ID = 'backlog-advancement-v1'
ALLOWED_PATHS = ['backend/runtime/work_backlog.py']
CASES = ('completed_dependency_then_restart', 'failure_does_not_block_ready',
         'waiting_work_does_not_starve_ready', 'owner_parallel_admission')
DISCLAIMER = 'Fixed positive backlog scenarios only; no general functional, arbitrary patch, Bluetooth, release or deployment acceptance.'

# A fixed rootless PID1 supervisor keeps only disposable /data tmpfs across an
# API-child crash. It never imports the candidate. Three starts is a hard bound.
SUPERVISOR = '''import subprocess,time
for attempt in range(3):
 p=subprocess.Popen(['python','-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8012','--no-access-log'])
 code=p.wait()
 if code==0:break
 time.sleep(.2)
'''
CHILD = '''from pathlib import Path
import json,os,signal,sys
children=Path('/proc/1/task/1/children').read_text().split()
# Docker --init inserts its tiny init before the fixed supervisor.
children+=sum([Path('/proc/'+value+'/task/'+value+'/children').read_text().split() for value in list(children)],[])
matches=[]
for value in children:
 args=Path('/proc/'+value+'/cmdline').read_bytes().split(b'\\0')
 if b'uvicorn' in args and b'backend.main:app' in args:matches.append(int(value))
assert len(matches)==1
pid=matches[0]
if sys.argv[1]=='restart':os.kill(pid,signal.SIGKILL)
else:assert sys.argv[1]=='observe'
print(json.dumps({'pid':pid}))
'''


def base_module():
    path = Path(__file__).with_name('jules-external-oracle.py')
    spec = importlib.util.spec_from_file_location('protected_external_oracle', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = base_module()  # This is a protected controller sibling, never candidate source.


def command():
    return ['-I', '-S', '-c', SUPERVISOR]


def suite_code(*, delay=0, fail=False):
    # Real stdlib unittest, fixed by the controller, with no candidate tests.
    return ('import unittest,time\nclass FixedSuite(unittest.TestCase):\n'
            ' def test_fixed(self):\n'
            f'  time.sleep({delay})\n  self.assertEqual(2+3,{6 if fail else 5})\n'
            "unittest.main(argv=['fixed'],verbosity=1)\n")


class BacklogOracle(base.ExternalOracle):
    def expected_command(self):
        if self.config.get('api_port', 8012) != 8012:
            raise ValueError('Positive contract uses its fixed sandbox loopback port')
        return command()

    def request(self, method, path, body=None):
        if time.time() >= self.config['deadline_at']:
            raise ValueError('Positive contract deadline exceeded')
        response = self.transport_fn(method, path,
            {'Authorization': 'Bearer '+self.config['test_auth_token'], 'X-Kingdom-Request': '1',
             'Content-Type': 'application/json'}, None if body is None else json.dumps(body))
        if response.get('truncated') is not False or response.get('status') not in (200, 201):
            raise ValueError('Fixed positive probe did not return a successful bounded response')
        raw = base64.b64decode(response.get('body', ''), validate=True)
        if len(raw) > 65536:
            raise ValueError('Fixed positive response exceeded its budget')
        return json.loads(raw)

    def wait(self, predicate, timeout=55):
        until = min(time.monotonic()+timeout, time.monotonic()+max(0, self.config['deadline_at']-time.time()))
        while time.monotonic() < until:
            if predicate():
                return
            time.sleep(.25)
        raise AssertionError('Fixed bounded progress assertion did not become true')

    def items(self):
        return {row['id']: row for row in self.request('GET', '/work-backlog')['items']}

    def tasks(self, missions):
        return [t for t in self.request('GET', '/tasks') if t.get('metadata', {}).get('mission_id') in missions]

    def register(self, name, *, depends=(), priority=50, delay=0, fail=False):
        plan = {'title': name, 'objective': 'Run fixed external backlog oracle suite', 'deliverables': ['fixed suite receipt'],
                'steps': [{'id': 'suite', 'title': name, 'kind': 'project_test',
                           'argv': ['/usr/local/bin/python3', '-I', '-c', suite_code(delay=delay, fail=fail)],
                           'project_test': {'project': 'kingdom', 'source_revision': self.config['revision'],
                                            'runner': 'unittest', 'minimum_tests': 1},
                           'acceptance': 'Current fixed nonempty governed process receipt'}]}
        mission = self.request('POST', '/missions', {'plan': plan})
        self.request('POST', '/missions/'+mission['id']+'/approve', {'version': mission['version']})
        item = self.request('POST', '/work-backlog/items', {'project': 'kingdom', 'idempotency_key': name,
            'title': name, 'mission_id': mission['id'], 'mission_version': mission['version'],
            'acceptance_step': 'suite', 'depends_on': list(depends), 'enabled': True, 'priority': priority})
        return item['id'], mission['id']

    def completed(self, *ids):
        state = self.items()
        return all(state[i]['status'] == 'completed' and state[i].get('evidence', {}).get('tests_run') == 1 for i in ids)

    def child(self, action):
        result = subprocess.run(['docker', 'exec', self._container_id, base.PROBE_PYTHON,
            '-I', '-S', '-c', CHILD, action], capture_output=True, timeout=10, check=True)
        value = json.loads(result.stdout)
        if type(value.get('pid')) is not int or value['pid'] <= 1:
            raise ValueError('Fixed API-child observation failed')
        return value['pid']

    def dependency_restart(self):
        first, a = self.register('oracle-dependent-first')
        second, b = self.register('oracle-dependent-second', depends=[first])
        self.wait(lambda: self.completed(first, second))
        before = sorted(t['id'] for t in self.tasks({a, b}))
        assert len(before) == len(set(before)) == 2
        previous = self.child('restart')
        self.wait(lambda: self._ready_after_restart(previous), timeout=25)
        # More than a full backlog cycle: no recreated mission task may appear.
        time.sleep(6)
        assert self.completed(first, second)
        assert sorted(t['id'] for t in self.tasks({a, b})) == before

    def _ready_after_restart(self, previous):
        try:
            return self.child('observe') != previous and self.request('GET', '/health/ready')['status'] == 'ready'
        except (ValueError, OSError, subprocess.SubprocessError):
            return False

    def failure_ready(self):
        bad, a = self.register('oracle-expected-failure', fail=True, priority=100)
        good, b = self.register('oracle-after-failure', priority=1)
        self.wait(lambda: self.items()[bad]['status'] == 'review_required' and self.completed(good))
        assert len(self.tasks({a, b})) == 2
        assert self.items()[bad].get('evidence') is None

    def waiting_ready(self):
        slow, a = self.register('oracle-waiting-high', delay=30, priority=100)
        self.wait(lambda: len(self.tasks({a})) == 1, timeout=15)
        other, b = self.register('oracle-unrelated-low', priority=1)
        # Baseline priority-only selection cannot dispatch b until slow finishes.
        self.wait(lambda: len(self.tasks({b})) == 1, timeout=14)
        assert self.items()[slow]['status'] != 'completed'
        self.wait(lambda: self.completed(slow, other))
        assert len(self.tasks({a, b})) == 2

    def admission(self):
        policy = self.request('PUT', '/runtime/policy', {'level': 4})
        assert policy['mission_budget']['max_parallel'] == 1
        slow, a = self.register('oracle-admission-first', delay=18, priority=100)
        # Level4 requires one exact owner approval for this fixed process.
        # Raising the level later must not be assumed to approve/requeue it.
        self.wait(lambda: len(self.tasks({a})) == 1 and
                  self.tasks({a})[0]['status'].lower() == 'waiting_approval', timeout=15)
        task = self.tasks({a})[0]
        approval_id = task['metadata']['approval_id']
        approval = next(row for row in self.request('GET', '/security/approvals')
                        if row['id'] == approval_id)
        assert approval['capability'] == 'process.execute'
        assert approval['operation'] == 'Execute task ' + task['id']
        assert approval['parameters']['task_id'] == task['id']
        expected = ['/usr/local/bin/python3', '-I', '-c', suite_code(delay=18)]
        assert approval['parameters']['metadata']['tool_parameters']['argv'] == expected
        self.request('POST', '/security/approvals/' + approval_id + '/approve', {})
        self.wait(lambda: self.tasks({a})[0]['status'].lower() == 'running', timeout=15)
        other, b = self.register('oracle-admission-second', priority=1)
        time.sleep(11)
        assert self.items()[other]['status'] == 'ready'
        assert not self.tasks({b})
        self.request('PUT', '/runtime/policy', {'level': 5})
        self.wait(lambda: self.completed(slow, other))
        assert len(self.tasks({a, b})) == 2

    def run_suite(self):
        self.inspect_candidate_container()
        if self.request('GET', '/tasks') or self.request('GET', '/work-backlog')['items']:
            raise ValueError('Positive contract requires fresh disposable state')
        self.request('PUT', '/workspace/apprentices/coder/tools', {'capabilities': ['process.execute']})
        self.request('PUT', '/runtime/policy', {'level': 5})
        self.request('POST', '/start')
        backlog = self.request('GET', '/work-backlog')
        self.request('POST', '/work-backlog/settings', {'enabled': True, 'expected_revision': backlog['revision']})
        results = []
        for name, operation in zip(CASES, (self.dependency_restart, self.failure_ready, self.waiting_ready, self.admission)):
            try:
                operation()
                results.append({'name': name, 'passed': True, 'detail': 'Fixed host progress assertions passed', 'status_code': 200})
            except (ValueError, AssertionError, OSError, KeyError, TypeError, subprocess.SubprocessError):
                results.append({'name': name, 'passed': False, 'detail': 'Fixed host progress assertion failed', 'status_code': None})
                # Uncertain failed scenario is not replayed or counted as success.
                break
        for name in CASES[len(results):]:
            results.append({'name': name, 'passed': False, 'detail': 'Not executed after prior failure', 'status_code': None})
        self.inspect_candidate_container()
        failed = sum(not r['passed'] for r in results)
        record = {'verdict': 'FAILED' if failed else 'PASSED', 'disclaimer': DISCLAIMER,
            'contract_id': CONTRACT_ID, 'source_revision': self.config['revision'],
            'candidate_patch_sha256': self.config['candidate_patch_sha256'], 'container_image_digest': self.config['image'],
            'source_tree_sha256': self.config['source_tree_sha256'], 'timestamp': time.time(),
            'trusted_test_counts': {'total': len(CASES), 'passed': len(CASES)-failed, 'failed': failed},
            'assertion_results': results}
        if time.time() >= self.config['deadline_at']:
            record['verdict'] = 'FAILED'
        return record, self.write_protected_verdict(record)
