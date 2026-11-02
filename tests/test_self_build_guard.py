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

    def test_isolated_build_runner_scope_enforcement(self):
        from backend.runtime.self_build_guard import IsolatedBuildRunner
        runner = IsolatedBuildRunner()
        # Valid paths
        self.assertEqual(runner.validate_file_scope(["backend/runtime/health.py", "tests/test_health.py"]), [])
        # Out-of-tree / traversal
        errors = runner.validate_file_scope(["backend/../.env", "unauthorized_root/foo.py"])
        self.assertEqual(len(errors), 2)

    def test_run_build_and_repair_loop_success_after_repair(self):
        from backend.runtime.self_build_guard import IsolatedBuildRunner, run_build_and_repair_loop
        runner = IsolatedBuildRunner()
        job = BuildJob(job_id="job-repair", base_commit=SHA, approved=True)

        call_count = 0
        def test_suite():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False, "AssertionError: expected 200, got 500"
            return True, "All tests passed"

        def repair_gen(changes, failure_log):
            updated = dict(changes)
            updated["backend/runtime/health.py"] = "fixed_content"
            return updated

        res = run_build_and_repair_loop(
            runner, job,
            initial_changes={"backend/runtime/health.py": "broken_content"},
            test_suite=test_suite,
            repair_generator=repair_gen
        )
        self.assertEqual(res["final_state"], "reviewing")
        self.assertTrue(res["tests_passed"])
        self.assertEqual(len(res["repair_history"]), 1)

    def test_independent_review_catches_test_suppression(self):
        from backend.runtime.self_build_guard import review_build_candidate
        job = BuildJob(job_id="job-review", base_commit=SHA, state=BuildState.REVIEWING, tests_passed=True, approved=True)
        # Attempt to insert test skipping
        candidate_files = {"tests/test_bad.py": "@pytest.mark.skip(reason='bypass')"}
        res = review_build_candidate(job, candidate_files, original_base_commit=SHA)
        self.assertFalse(res["review_passed"])
        self.assertEqual(res["final_state"], "quarantined")
        self.assertTrue(any("test suppression" in r for r in res["rejection_reasons"]))
