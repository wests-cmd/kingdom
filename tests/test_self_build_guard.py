import unittest
from backend.runtime.self_build_guard import (
    BuildProposal,
    validate_proposal,
    may_promote,
    select_recovery_action,
    BuildJob,
    BuildState,
    record_test_result,
    finish_review,
)
SHA='a'*40

def proposal(**changes):
    args=dict(goal='Fix onboarding',base_commit=SHA,paths=('frontend/src/App.jsx',),test_commands=('pytest',),approved=True)
    args.update(changes)
    return BuildProposal(**args)

class Tests(unittest.TestCase):
    def test_valid(self): self.assertEqual(validate_proposal(proposal()),[])
    def test_needs_approval(self): self.assertIn('Explicit Kingdom authorization required',validate_proposal(proposal(approved=False)))
    def test_requires_pinned_base(self): self.assertTrue(validate_proposal(proposal(base_commit='main')))
    def test_traversal(self): self.assertTrue(validate_proposal(proposal(paths=('frontend/../.env',))))
    def test_secrets(self): self.assertTrue(validate_proposal(proposal(paths=('backend/secrets.json',))))
    def test_absolute(self): self.assertTrue(validate_proposal(proposal(paths=('/tmp/evil',))))
    def test_duplicate(self): self.assertTrue(validate_proposal(proposal(paths=('tests/a.py','tests/a.py'))))
    def test_no_tests(self): self.assertTrue(validate_proposal(proposal(test_commands=())))
    def test_promote_all_gates(self): self.assertTrue(may_promote(approved=True,tests_passed=True,independent_review_passed=True,emergency_stop=False,base_commit_unchanged=True))
    def test_stop_blocks(self): self.assertFalse(may_promote(approved=True,tests_passed=True,independent_review_passed=True,emergency_stop=True,base_commit_unchanged=True))
    def test_stale_commit_blocks(self): self.assertFalse(may_promote(approved=True,tests_passed=True,independent_review_passed=True,emergency_stop=False,base_commit_unchanged=False))
    def test_recovery(self): self.assertEqual(select_recovery_action(3,emergency_stop=False,interrupted=True),'quarantine')
    def test_interrupt(self): self.assertEqual(select_recovery_action(1,emergency_stop=False,interrupted=True),'requeue')

    def test_build_job_lifecycle_success(self):
        job = BuildJob(job_id="job-1", base_commit=SHA, approved=True)
        self.assertEqual(job.state, BuildState.QUEUED)
        job.state = BuildState.TESTING
        record_test_result(job, passed=True)
        self.assertEqual(job.state, BuildState.REVIEWING)
        self.assertTrue(job.tests_passed)
        finish_review(job, passed=True)
        self.assertEqual(job.state, BuildState.READY)
        self.assertTrue(job.review_passed)

    def test_build_job_test_failure_retry_and_quarantine(self):
        job = BuildJob(job_id="job-2", base_commit=SHA, approved=True)
        job.state = BuildState.TESTING
        record_test_result(job, passed=False)
        self.assertEqual(job.state, BuildState.BUILDING)
        self.assertEqual(job.attempts, 1)

        job.state = BuildState.TESTING
        record_test_result(job, passed=False)
        self.assertEqual(job.state, BuildState.BUILDING)
        self.assertEqual(job.attempts, 2)

        job.state = BuildState.TESTING
        record_test_result(job, passed=False)
        self.assertEqual(job.state, BuildState.QUARANTINED)
        self.assertEqual(job.attempts, 3)

    def test_build_job_review_failure_quarantines(self):
        job = BuildJob(job_id="job-3", base_commit=SHA, approved=True)
        job.state = BuildState.TESTING
        record_test_result(job, passed=True)
        finish_review(job, passed=False)
        self.assertEqual(job.state, BuildState.QUARANTINED)
