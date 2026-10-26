import importlib.util
from pathlib import Path
import time
import unittest

spec=importlib.util.spec_from_file_location('jules_gate',Path(__file__).parents[1]/'scripts/jules-independent-gate.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class GateTests(unittest.TestCase):
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
