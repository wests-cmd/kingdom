import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('regression_supervisor',Path(__file__).parents[1]/'scripts/scoped-regression-supervisor.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

GOOD='''import unittest
import copy
from backend.cluster.shared_groups import remap
class MappingTest(unittest.TestCase):
    def test_mapping(self):
        groups=[{'id':'one','name':'Team','flags':['review'],'members':['a'],'captain':'a'}]
        original=copy.deepcopy(groups)
        actual=remap(groups,'a','local')
        expected=[{'id':'one','name':'Team','flags':['review'],'members':['local'],'captain':'local'}]
        self.assertEqual(actual,expected)
        self.assertEqual(groups,original)
if __name__ == '__main__':
    unittest.main()
'''


class CandidateBoundaryTests(unittest.TestCase):
    def test_actual_function_call_and_assertions_are_required(self):
        self.assertEqual(module.validate_candidate(GOOD),1)
        for bad in (GOOD.replace("actual=remap(groups,'a','local')",'actual=groups'),
                    GOOD.replace('from backend.cluster.shared_groups import remap',''),
                    GOOD.replace('self.assertEqual(actual,expected)','actual').replace('self.assertEqual(groups,original)','groups')):
            with self.assertRaises(ValueError):module.validate_candidate(bad)

    def test_host_access_and_dynamic_code_are_rejected(self):
        for bad in ('import os\n'+GOOD,GOOD.replace('actual=remap(groups,\'a\',\'local\')','actual=__import__("os")'),
                    GOOD.replace('actual=remap(groups,\'a\',\'local\')','self.__class__=dict'),
                    GOOD.replace('def test_mapping(self):','def test_mapping(self, x=open("secret")):'),
                    GOOD.replace('class MappingTest(unittest.TestCase):','@run()\nclass MappingTest(unittest.TestCase):')):
            with self.subTest(source=bad[:80]),self.assertRaises(ValueError):module.validate_candidate(bad)

    def test_bad_syntax_has_precise_fixed_diagnostic(self):
        with self.assertRaisesRegex(ValueError,'Python syntax error at line'):
            module.validate_candidate(GOOD.replace('self.assertEqual(groups,original)','self.assertEqual(groups,original}'))

    def test_oversize_input_is_rejected(self):
        with self.assertRaises(ValueError):module.validate_candidate(GOOD+' '*6001)

    def test_published_status_excludes_private_state_and_uses_revision(self):
        import tempfile,json
        with tempfile.TemporaryDirectory() as directory:
            supervisor=object.__new__(module.Supervisor)
            supervisor.file=Path(directory)/'state.json';supervisor.name='bounded-test'
            supervisor.config={'publish_status':True}
            supervisor.state={'phase':'review_required','request_id':'known','secret':'never-publish'}
            calls=[]
            def api(path,body=None):calls.append((path,body));return {'revision':3}
            supervisor.api=api;supervisor.publish()
            self.assertEqual(calls[-1][1]['expected_revision'],3)
            self.assertNotIn('never-publish',json.dumps(calls))
            supervisor.publish();self.assertEqual(len(calls),2)

    def test_changed_protected_source_cannot_start_a_container(self):
        import tempfile,time
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            supervisor=object.__new__(module.Supervisor);supervisor.root=Path(directory)
            source=Path(directory)/'inputs/backend/cluster';source.mkdir(parents=True)
            (source/'shared_groups.py').write_text('changed')
            supervisor.config={'deadline_at':time.time()+60,'source_root':str(Path(directory)/'inputs'),
                'source_hashes':{'backend/cluster/shared_groups.py':'0'*64}}
            with patch.object(module.subprocess,'run') as execute:
                with self.assertRaisesRegex(RuntimeError,'Protected verification source changed'):supervisor.verify(GOOD)
                execute.assert_not_called()

    def test_terminal_assignment_never_resumes_execution(self):
        supervisor=object.__new__(module.Supervisor)
        supervisor.state={'phase':'review_required'}
        supervisor.api=lambda *args:(_ for _ in ()).throw(AssertionError('No API execution for terminal work'))
        supervisor.run()

    def test_provider_failure_does_not_consume_a_code_repair(self):
        import time
        supervisor=object.__new__(module.Supervisor)
        supervisor.state={'phase':'watching','request_id':'known','repairs':0}
        supervisor.config={'deadline_at':time.time()+60,'expected_identity':'pinned'}
        answers={'/nodes/identity':{'node_id':'pinned'},
                 '/requests/known':{'id':'known','status':'waiting_review','agent_session_id':'agent'},
                 '/orchestration':{'background':{'active_request_ids':[]}},
                 '/agent-sessions/agent':{'status':'needs_review','error_class':'HTTPStatusError'}}
        supervisor.api=lambda path:answers[path]
        supervisor.save=lambda **values:supervisor.state.update(values)
        supervisor.repair=lambda *args:(_ for _ in ()).throw(AssertionError('No code repair for provider failure'))
        supervisor.run()
        self.assertEqual(supervisor.state['phase'],'review_required')
        self.assertEqual(supervisor.state['repairs'],0)


if __name__=='__main__':unittest.main()
