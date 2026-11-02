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
