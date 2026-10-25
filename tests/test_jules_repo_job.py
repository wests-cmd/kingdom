import importlib.util
from pathlib import Path
import time
import unittest

spec=importlib.util.spec_from_file_location('jules_job',Path(__file__).parents[1]/'scripts/jules-repo-job.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def config():
    return {'repository':'wests-cmd/kingdom','source':'sources/github/wests-cmd/kingdom',
            'revision':'a'*40,'branch':'codex/test','prompt':'Implement the scoped fix','deadline_at':time.time()+60}


class JulesJobTests(unittest.TestCase):
    def job(self):
        job=object.__new__(module.Job);job.config=config();job.state={'phase':'queued'}
        job.save=lambda **values:job.state.update(values)
        return job

    def test_scope_and_source_are_fixed(self):
        module.validate(config())
        for change in ({'repository':'other/private'},{'source':'sources/other'}, {'revision':'main'}, {'branch':'../other'}):
            with self.subTest(change=change),self.assertRaises(ValueError):module.validate({**config(),**change})

    def test_unknown_submission_is_never_repeated(self):
        job=self.job();calls=[]
        def fail(*args):calls.append(args);raise TimeoutError('private-secret-never-retain')
        job.request=fail;job.submit();job.submit();job.run()
        self.assertEqual(len(calls),1)
        self.assertEqual(job.state['phase'],'submission_unknown')
        self.assertNotIn('private-secret',str(job.state))

    def test_crash_during_submit_holds_without_a_network_call(self):
        job=self.job();job.state['phase']='submitting'
        job.request=lambda *args:(_ for _ in ()).throw(AssertionError('No replay'))
        job.run();self.assertEqual(job.state['phase'],'submission_unknown')

    def test_session_create_has_no_automatic_pr_merge_or_deployment(self):
        job=self.job();calls=[]
        job.request=lambda *args:(calls.append(args) or {'name':'sessions/123'})
        job.submit()
        body=calls[0][1]
        self.assertEqual(body['automationMode'],'AUTOMATION_MODE_UNSPECIFIED')
        self.assertEqual(body['sourceContext']['source'],job.config['source'])
        self.assertIn(job.config['revision'],body['prompt'])
        self.assertEqual(job.state['session'],'sessions/123')

    def test_remote_completion_is_not_local_acceptance(self):
        job=self.job();job.state={'phase':'watching','session':'sessions/123'}
        job.request=lambda *args:{'name':'sessions/123','state':'COMPLETED'}
        job.poll()
        self.assertEqual(job.state['phase'],'awaiting_independent_review')
        self.assertFalse(job.state['accepted'])
        self.assertFalse(job.state['automatic_merge'])

    def test_wrong_session_and_unknown_status_are_rejected(self):
        for response in ({'name':'sessions/other','state':'COMPLETED'}, {'name':'sessions/123','state':'MADE_UP'}):
            job=self.job();job.state={'phase':'watching','session':'sessions/123'}
            job.request=lambda *args:response
            with self.assertRaises(ValueError):job.poll()

    def test_expired_observer_does_not_claim_to_cancel_remote_work(self):
        job=self.job();job.config['deadline_at']=time.time()-1
        job.run();self.assertEqual(job.state['phase'],'expired_remote_may_continue')


if __name__=='__main__':unittest.main()
