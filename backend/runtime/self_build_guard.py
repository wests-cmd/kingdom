"""Conservative gates for Kingdom autonomous build proposals.

This module does not execute shell commands, write repo files, or grant approvals.
Wire it into existing Kingdom request/work-programme workers after authorization.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

BLOCKED = frozenset({'.git', '.env', 'owner-token', 'id_rsa', 'id_ed25519', 'secrets.json'})
ALLOWED_ROOTS = frozenset({'backend', 'frontend', 'tests', 'docs', 'scripts', 'apps', 'desktop'})
WINDOWS_RESERVED = re.compile(r'^(con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\.|$)', re.I)
# Trust-policy changes belong to a separately reviewed engineering path.
PROTECTED_PREFIXES = ('backend/security/', 'backend/cluster/task_leasing.py',
                      'backend/runtime/policy.py', 'backend/runtime/self_build_guard.py')

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
    if not isinstance(p.goal, str) or not p.goal.strip() or len(p.goal) > 4000:
        errors.append('Goal must contain 1-4000 characters')
    if not isinstance(p.base_commit, str) or not re.fullmatch(r'[a-fA-F0-9]{40}', p.base_commit):
        errors.append('Pin proposal to a full 40-character Git commit SHA')
    if type(p.max_files) is not int or not 1 <= p.max_files <= 30:
        errors.append('Invalid file budget')
    if (not isinstance(p.paths, tuple) or not p.paths or
            type(p.max_files) is not int or len(p.paths) > min(p.max_files, 30)):
        errors.append('Invalid number of target files')
    paths = p.paths if isinstance(p.paths, tuple) else ()
    seen = set()
    for raw in paths:
        if (not isinstance(raw, str) or not raw or len(raw) > 500 or
                '\\' in raw or raw.startswith('/') or any(ord(c) < 32 or c in ':*?"<>|' for c in raw)):
            errors.append('Unsafe target path')
            continue
        folded = raw.casefold()
        if folded in seen:
            errors.append('Duplicate target paths')
        seen.add(folded)
        parts = raw.split('/')
        if (any(x in ('', '.', '..') or x.endswith(('.', ' ')) or WINDOWS_RESERVED.match(x)
                or x.casefold() in BLOCKED for x in parts)
                or parts[0] not in ALLOWED_ROOTS):
            errors.append('Disallowed target path')
        if any(folded == prefix.rstrip('/') or folded.startswith(prefix) for prefix in PROTECTED_PREFIXES):
            errors.append('Protected trust-policy path requires separate review')
    if (not isinstance(p.test_commands, tuple) or not p.test_commands or len(p.test_commands) > 20
            or any(not isinstance(cmd, str) or not cmd.strip() or len(cmd) > 2000
                   or '\x00' in cmd for cmd in p.test_commands)):
        errors.append('At least one bounded nonempty test must be specified')
    # Commands are metadata for an external trusted runner, never executed here.
    if p.approved is not True:
        errors.append('Explicit Kingdom authorization required')
    return errors


def may_promote(*, approved: bool, tests_passed: bool, independent_review_passed: bool,
                emergency_stop: bool, base_commit_unchanged: bool) -> bool:
    return (approved is True and tests_passed is True and independent_review_passed is True
            and emergency_stop is False and base_commit_unchanged is True)


def select_recovery_action(attempts: int, *, emergency_stop: bool, interrupted: bool) -> str:
    if emergency_stop:
        return 'halt'
    if attempts >= 3:
        return 'quarantine'
    if interrupted:
        return 'requeue'
    return 'inspect'
