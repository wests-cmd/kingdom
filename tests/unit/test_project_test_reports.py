import os
import tempfile
import unittest

from backend.runtime.project_tests import report, validate_metadata
from backend.runtime.computer_tools import receipt


class ProjectTestReports(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(os.chdir, self.old)
        self.task = {'id': 'test-job', 'prompt': 'Run exact suite', 'status': 'completed', 'metadata': {
            'tool': 'process.run@1.0.0', 'capability': 'process.execute', 'max_attempts': 1,
            'project_test': {'project': 'threadmap', 'source_revision': 'a' * 40,
                             'runner': 'unittest', 'minimum_tests': 2}}}

    def evidence(self, text='Ran 2 tests in 0.01s\n\nOK\n', exit_code=0, truncated=False):
        output = {'output': text, 'exit_code': exit_code, 'output_truncated': truncated}
        from backend.swarm.manager import execution_request
        child = execution_request(self.task, self.task['prompt'])
        outcome = {'kind': 'native_tool', 'tool': 'process.run@1.0.0', 'output': output, **receipt(child, output)}
        self.task['result'] = {'plan': {'task_id': self.task['id'], 'subtasks': [{'prompt': self.task['prompt'], 'knight': 'coder'}]},
                               'results': [{'knight': 'coder', 'status': 'completed', 'outcome': outcome, 'verification': {'state': 'VERIFIED'}}]}

    def test_nonempty_report_is_repeatable_after_serialization(self):
        import json
        self.evidence()
        first = report(self.task)
        self.assertTrue(first['tests_passed'])
        self.assertEqual(first, report(json.loads(json.dumps(self.task))))

    def test_successful_process_without_tests_is_not_passing(self):
        for text in ['done', 'Ran 0 tests in 0.01s\n\nOK\n', 'Ran 1 test in 0.01s\n\nOK\n',
                     'Ran 2 tests in 0.01s\n\nOK (skipped=2)\n']:
            self.evidence(text)
            self.assertFalse(report(self.task)['tests_passed'])

    def test_failure_and_truncation(self):
        self.evidence(exit_code=1)
        self.assertEqual(report(self.task)['state'], 'process_failed')
        self.evidence(truncated=True)
        self.assertEqual(report(self.task)['state'], 'summary_unavailable')

    def test_tampered_or_missing_receipt_fails(self):
        self.evidence()
        outcome = self.task['result']['results'][0]['outcome']
        outcome['output']['output'] = 'Ran 999 tests in 0.01s\n\nOK\n'
        self.assertEqual(report(self.task)['state'], 'evidence_invalid')
        os.unlink(outcome['artifact'])
        self.assertEqual(report(self.task)['state'], 'evidence_invalid')

    def test_cancelled_and_recovery_states_do_not_claim_success(self):
        self.evidence()
        for status in ['cancelled', 'RECOVERY_REQUIRED', 'WAITING_APPROVAL', 'running']:
            self.task['status'] = status
            self.assertFalse(report(self.task)['tests_passed'])
            self.assertEqual(report(self.task)['state'], status.lower())

    def test_no_automatic_retry_or_different_tool(self):
        for change in [{'max_attempts': 2}, {'tool': 'harness.run@1.0.0'}, {'capability': 'filesystem.read'}]:
            metadata = dict(self.task['metadata'], **change)
            with self.assertRaises(ValueError): validate_metadata(metadata)

    def test_pytest_final_summary(self):
        self.task['metadata']['project_test']['runner'] = 'pytest'
        for text, passed in [('== 3 passed, 1 skipped in 0.04s ==', True),
                             ('== 1 failed, 3 passed in 0.04s ==', False),
                             ('== 3 passed in 0.04s ==\nextra', False)]:
            self.evidence(text)
            self.assertEqual(report(self.task)['tests_passed'], passed)

    def test_multiple_outcomes_are_not_merged_as_one_suite(self):
        self.evidence()
        self.task['result']['results'] *= 2
        self.assertEqual(report(self.task)['state'], 'evidence_missing')

    def test_durable_cancel_and_restart_recovery_do_not_execute_again(self):
        from backend.storage.db import Database
        from backend.storage.repository import TaskRepository
        from backend.runtime.tasks import TaskManager
        repository = TaskRepository(Database('task-state.sqlite3'))
        manager = TaskManager(repository)
        task = manager.create('Reviewed project suite', self.task['metadata'])
        manager.cancel(task['id'])
        restarted = TaskManager(repository)
        self.assertIsNone(restarted.claim_next())
        self.assertEqual(report(restarted.get(task['id']))['state'], 'cancelled')
        running = restarted.create('Another reviewed suite', self.task['metadata'])
        restarted.claim_next()
        # Exercise the same durable transition used by RuntimeEngine startup.
        restarted.transition_task(running['id'], 'RECOVERY_REQUIRED')
        again = TaskManager(repository)
        self.assertIsNone(again.claim_next())
        self.assertEqual(report(again.get(running['id']))['state'], 'recovery_required')

    def test_actual_swarm_process_receipt_and_wrong_child_rejection(self):
        import asyncio
        import sys
        from types import SimpleNamespace
        from backend.swarm.manager import SwarmManager
        from backend.runtime.execution import execute_request
        # Only authority/registry boundaries are test doubles. Swarm _run,
        # process tool, subprocess, receipt writing and verification are real.
        self.task['metadata']['tool_parameters'] = {'argv': [sys.executable, '-c',
            'import unittest; s=unittest.TestSuite([unittest.FunctionTestCase(lambda: None),unittest.FunctionTestCase(lambda: None)]); unittest.TextTestRunner().run(s)']}
        knight = SimpleNamespace(execute=lambda request: {'status': 'completed',
            'knight': 'coder', 'outcome': execute_request(request, ['process.execute'])})
        swarm = SwarmManager.__new__(SwarmManager)
        swarm.registry = SimpleNamespace(get=lambda name: knight, begin=lambda name: None, finish=lambda name: None)
        swarm.security = SimpleNamespace(authorize=lambda **kwargs: {'authorized': True},
                                         nodes=SimpleNamespace(get_node=lambda name: {'token': 'test-only'}))
        swarm._publish = lambda *args: None
        item = asyncio.run(swarm._run('coder', self.task['prompt'], self.task))
        self.task['result'] = {'plan': {'task_id': self.task['id'],
            'subtasks': [{'prompt': self.task['prompt'], 'knight': 'coder'}]}, 'results': [item]}
        self.assertTrue(report(self.task)['tests_passed'])
        self.task['prompt'] = 'Different child prompt'
        self.assertEqual(report(self.task)['state'], 'evidence_invalid')
        self.task['result']['plan']['subtasks'][0]['prompt'] = self.task['prompt']
        self.assertEqual(report(self.task)['state'], 'evidence_invalid')


def test_project_job_api_uses_existing_cancel_and_auth():
    from backend.main import app
    from tests.auth_support import owner_client
    from fastapi.testclient import TestClient
    client = owner_client(app)
    metadata = {'tool': 'process.run@1.0.0', 'capability': 'process.execute',
                'max_attempts': 1, 'tool_parameters': {'argv': ['python', '-m', 'unittest']},
                'project_test': {'project': 'centipede', 'runner': 'unittest',
                                 'source_revision': 'b' * 40}}
    created = client.post('/tasks', json={'prompt': 'Reviewed local unit suite', 'metadata': metadata})
    assert created.status_code == 201
    ident = created.json()['id']
    assert client.get(f'/tasks/{ident}/test-report').json()['tests_passed'] is False
    assert TestClient(app).get(f'/tasks/{ident}/test-report').status_code == 401
    assert client.post(f'/tasks/{ident}/cancel').status_code == 200
    assert client.get(f'/tasks/{ident}/test-report').json()['state'] == 'cancelled'
    metadata['max_attempts'] = 2
    assert client.post('/tasks', json={'prompt': 'Invalid retry', 'metadata': metadata}).status_code == 400
