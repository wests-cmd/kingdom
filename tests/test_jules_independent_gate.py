import importlib.util
from pathlib import Path
import time
import unittest
from tempfile import TemporaryDirectory

spec=importlib.util.spec_from_file_location('jules_gate',Path(__file__).parents[1]/'scripts/jules-independent-gate.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class GateTests(unittest.TestCase):
    def test_signing_cannot_reuse_unrelated_or_missing_passing_run(self):
        gate=object.__new__(module.Gate)
        gate.last_test_sha='a'*64;gate.last_test_evidence={'test_count':10}
        with self.assertRaises(ValueError):gate.attest('b'*64)
        gate.last_test_evidence=None
        with self.assertRaises(ValueError):gate.attest('a'*64)

    def test_junit_requires_actual_nonempty_consistent_passing_cases(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)/'report.xml'
            p.write_text('<testsuites><testsuite tests="2" failures="0" errors="0"><testcase name="a"/><testcase name="b"/></testsuite></testsuites>')
            self.assertEqual(module.read_passing_junit(p),2)
            for value in ['<testsuites/>','<testsuite tests="0"/>','<testsuite tests="5"><testcase/></testsuite>',
                '<testsuite tests="1"><testcase><failure/></testcase></testsuite>',
                '<testsuite tests="1"><testcase><error/></testcase></testsuite>',
                '<testsuite tests="1"><testcase><skipped/></testcase></testsuite>',
                '<!DOCTYPE testsuite><testsuite tests="1"><testcase/></testsuite>']:
                p.write_text(value)
                with self.subTest(value=value),self.assertRaises(ValueError):module.read_passing_junit(p)

    def test_private_extraction_directories_are_traversable_by_test_user(self):
        with TemporaryDirectory() as folder:
            source=Path(folder)/'source';nested=source/'tests'/'nested'
            nested.mkdir(parents=True)
            for directory in [source,source/'tests',nested]:directory.chmod(0o700)
            module.prepare_test_directories(source)
            if __import__('os').name!='nt':
                for directory in [source,source/'tests',nested]:
                    self.assertEqual(directory.stat().st_mode & 0o777,0o755)

    def gate(self,phase='waiting'):
        gate=object.__new__(module.Gate)
        gate.c={'deadline_at':time.time()+60,'session':'sessions/123','max_repairs':2,'already_rejected':[]}
        gate.state={'phase':phase,'repairs':2,'accepted':False}
        gate.save=lambda **kw:gate.state.update(**kw,accepted=False)
        return gate

    def test_patch_scope_cannot_change_security_or_general_runtime(self):
        for path in ['backend/integrations/jules.py','backend/runtime/jules_api.py','backend/main.py','tests/test_jules_adapter.py','docs/JULES_API.md']:
            self.assertTrue(module.allowed_path(path),path)
        for path in ['../secret','backend/security/http_auth.py','backend/runtime/engine.py','.github/workflows/release.yml','/etc/passwd','tests/../../x']:
            self.assertFalse(module.allowed_path(path),path)

    def test_terminal_gate_never_starts_more_work(self):
        gate=self.gate('review_required')
        gate.api=lambda *args:(_ for _ in ()).throw(AssertionError('No network'))
        gate.run()

    def test_lifecycle_extension_requires_explicit_review_and_cannot_expand_security_scope(self):
        path='backend/runtime/work_backlog_runner.py'
        self.assertFalse(module.allowed_path(path))
        self.assertTrue(module.allowed_path(path,[path]))
        self.assertFalse(module.allowed_path('backend/security/http_auth.py',['backend/security/http_auth.py']))

    def test_unknown_feedback_post_is_not_replayed(self):
        gate=self.gate('repair_sending')
        gate.api=lambda *args:(_ for _ in ()).throw(AssertionError('No replay'))
        gate.run();self.assertEqual(gate.state['phase'],'review_required')

    def test_wrong_session_or_paused_worker_holds(self):
        for reply in [{'name':'sessions/wrong','state':'COMPLETED'},{'name':'sessions/123','state':'PAUSED'}]:
            gate=self.gate();gate.api=lambda *args:reply
            gate.run();self.assertEqual(gate.state['phase'],'review_required')

    def test_passing_subset_does_not_accept_or_complete_the_backlog(self):
        gate=self.gate();gate.api=lambda *args:{'name':'sessions/123','state':'COMPLETED'}
        gate.patch=lambda:'candidate-data';gate.test=lambda *args:(0,'10 passed')
        gate.run()
        self.assertEqual(gate.state['phase'],'scoped_tests_passed_review_required')
        self.assertFalse(gate.state['accepted'])

    def test_exhausted_repair_budget_never_sends_feedback(self):
        gate=self.gate();calls=[]
        gate.api=lambda *args:(calls.append(args) or {'name':'sessions/123','state':'COMPLETED'})
        gate.patch=lambda:'candidate-data';gate.test=lambda *args:(1,'2 failed')
        gate.run()
        self.assertEqual(calls,[()]);self.assertEqual(gate.state['repairs'],2)
        self.assertEqual(gate.state['phase'],'review_required')


if __name__=='__main__':unittest.main()
