"""Conservative gates for Kingdom autonomous build proposals.

This module does not execute shell commands, write repo files, or grant approvals.
Wire it into existing Kingdom request/work-programme workers after authorization.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable

BLOCKED = frozenset({'.git', '.env', 'owner-token', 'id_rsa', 'id_ed25519', 'secrets.json'})
ALLOWED_ROOTS = frozenset({'backend', 'frontend', 'tests', 'docs', 'scripts', 'apps', 'desktop'})

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
