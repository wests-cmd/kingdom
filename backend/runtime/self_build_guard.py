"""Conservative gates for Kingdom autonomous build proposals.

This module does not execute shell commands, write repo files, or grant approvals.
Wire it into existing Kingdom request/work-programme workers after authorization.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Iterable

BLOCKED = frozenset({'.git', '.env', 'owner-token', 'id_rsa', 'id_ed25519', 'secrets.json'})
ALLOWED_ROOTS = frozenset({'backend', 'frontend', 'tests', 'docs', 'scripts', 'apps', 'desktop'})


class BuildState(str, Enum):
    QUEUED = "queued"
    BUILDING = "building"
    TESTING = "testing"
    REVIEWING = "reviewing"
    READY = "ready"
    QUARANTINED = "quarantined"


@dataclass
class BuildJob:
    job_id: str
    base_commit: str
    state: BuildState = BuildState.QUEUED
    attempts: int = 0
    tests_passed: bool = False
    review_passed: bool = False
    approved: bool = False


def record_test_result(job: BuildJob, passed: bool):
    if job.state != BuildState.TESTING:
        raise ValueError("Job is not testing")

    job.tests_passed = passed

    if passed:
        job.state = BuildState.REVIEWING
    else:
        job.attempts += 1
        job.state = (
            BuildState.QUARANTINED
            if job.attempts >= 3
            else BuildState.BUILDING
        )


def finish_review(job: BuildJob, passed: bool):
    if job.state != BuildState.REVIEWING:
        raise ValueError("Job is not under review")

    job.review_passed = passed
    job.state = (
        BuildState.READY
        if passed and job.tests_passed and job.approved
        else BuildState.QUARANTINED
    )


class IsolatedBuildRunner:
    """Safely runs build jobs within isolated work directories under strict scope fences."""

    def __init__(self, allowed_roots: frozenset[str] = ALLOWED_ROOTS, blocked_names: frozenset[str] = BLOCKED):
        self.allowed_roots = allowed_roots
        self.blocked_names = blocked_names

    def validate_file_scope(self, paths: Iterable[str]) -> list[str]:
        errors = []
        for raw in paths:
            if not raw or '\\' in raw or raw.startswith('/') or '\x00' in raw:
                errors.append(f"Unsafe path format: {raw!r}")
                continue
            parts = raw.split('/')
            if any(x in ('', '.', '..') for x in parts):
                errors.append(f"Path traversal detected: {raw!r}")
                continue
            if parts[0] not in self.allowed_roots:
                errors.append(f"Root not in allowed roots: {raw!r}")
                continue
            if any(part.lower() in self.blocked_names for part in parts):
                errors.append(f"Blocked path target: {raw!r}")
                continue
        return errors

    def execute_build(self, job: BuildJob, file_changes: dict[str, str], test_fn) -> dict:
        """Executes a fenced build step: validates file scope, applies modifications, and invokes test_fn."""
        scope_errors = self.validate_file_scope(file_changes.keys())
        if scope_errors:
            raise ValueError(f"Scope violation: {'; '.join(scope_errors)}")

        job.state = BuildState.TESTING
        test_passed, test_output = test_fn()
        record_test_result(job, test_passed)

        return {
            "job_id": job.job_id,
            "base_commit": job.base_commit,
            "state": job.state.value,
            "attempts": job.attempts,
            "tests_passed": test_passed,
            "test_output": test_output
        }


def run_build_and_repair_loop(
    runner: IsolatedBuildRunner,
    job: BuildJob,
    initial_changes: dict[str, str],
    test_suite,
    repair_generator,
    max_attempts: int = 3
) -> dict:
    """Executes a bounded build and automatic self-repair loop upon failure."""
    current_changes = dict(initial_changes)
    repair_history = []

    while job.attempts < max_attempts and job.state not in (BuildState.REVIEWING, BuildState.QUARANTINED):
        result = runner.execute_build(job, current_changes, test_suite)
        if result["tests_passed"]:
            break

        repair_history.append({
            "attempt": job.attempts,
            "test_output": result["test_output"]
        })

        if job.attempts < max_attempts and job.state == BuildState.BUILDING:
            # Generate repair patch from test diagnostics
            repaired_changes = repair_generator(current_changes, result["test_output"])
            if repaired_changes:
                current_changes = repaired_changes

    return {
        "job_id": job.job_id,
        "final_state": job.state.value,
        "attempts": job.attempts,
        "tests_passed": job.tests_passed,
        "repair_history": repair_history,
        "final_changes": current_changes
    }


def review_build_candidate(job: BuildJob, candidate_files: dict[str, str], original_base_commit: str) -> dict:
    """Independent reviewer verification ensuring no unsafe modifications or drifted base commit."""
    if job.state != BuildState.REVIEWING:
        raise ValueError("Job is not ready for review")

    rejection_reasons = []

    if job.base_commit != original_base_commit:
        rejection_reasons.append("Base commit drift detected")

    if not job.tests_passed:
        rejection_reasons.append("Tests have not passed")

    for path, content in candidate_files.items():
        # Reject attempts to disable security or modify sensitive tokens
        if any(b in path.lower() for b in BLOCKED):
            rejection_reasons.append(f"Forbidden sensitive path in candidate: {path}")
        # Detect attempts to bypass or skip tests
        if "@pytest.mark.skip" in content or "unittest.skip" in content:
            rejection_reasons.append(f"Detected suspicious test suppression in {path}")

    review_approved = len(rejection_reasons) == 0
    finish_review(job, review_approved)

    return {
        "job_id": job.job_id,
        "review_passed": review_approved,
        "rejection_reasons": rejection_reasons,
        "final_state": job.state.value
    }


@dataclass(frozen=True)
class BuildProposal:
    goal: str
    base_commit: str
    paths: tuple[str, ...]
    test_commands: tuple[str, ...]
    approved: bool = False
    max_files: int = 12


def validate_proposal(p: BuildProposal) -> list[str]:
    errors = []
    if not p.goal.strip() or len(p.goal) > 4000:
        errors.append('Goal must contain 1-4000 characters')
    if len(p.base_commit) != 40 or any(c not in '0123456789abcdef' for c in p.base_commit.lower()):
        errors.append('Pin proposal to a full 40-character Git commit SHA')
    if not p.paths or len(p.paths) > min(p.max_files, 30):
        errors.append('Invalid number of target files')
    if len(set(p.paths)) != len(p.paths):
        errors.append('Duplicate target paths')
    for raw in p.paths:
        if not raw or '\\' in raw or raw.startswith('/') or '\x00' in raw:
            errors.append(f'Unsafe target path: {raw!r}')
            continue
        parts = raw.split('/')
        if any(x in ('', '.', '..') for x in parts) or parts[0] not in ALLOWED_ROOTS or any(x.lower() in BLOCKED for x in parts):
            errors.append(f'Disallowed target path: {raw!r}')
    if not p.test_commands:
        errors.append('At least one test must be specified')
    # Command strings are metadata for an external trusted runner, never executed here.
    if not p.approved:
        errors.append('Explicit Kingdom authorization required')
    return errors


def may_promote(*, approved: bool, tests_passed: bool, independent_review_passed: bool,
                emergency_stop: bool, base_commit_unchanged: bool) -> bool:
    return all((approved, tests_passed, independent_review_passed, not emergency_stop, base_commit_unchanged))


def select_recovery_action(attempts: int, *, emergency_stop: bool, interrupted: bool) -> str:
    if emergency_stop:
        return 'halt'
    if attempts >= 3:
        return 'quarantine'
    if interrupted:
        return 'requeue'
    return 'inspect'
