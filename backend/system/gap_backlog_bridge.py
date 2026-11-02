"""Register incomplete capability work in Kingdom's existing backlog.

Never enables a job, grants permissions, or starts an executor.
"""
from __future__ import annotations
import hashlib
import re

VALID = re.compile(r'^[A-Za-z0-9_-]{1,80}$')


def register_missing_capabilities(register, backlog, *, project='kingdom', limit=20):
    """Idempotently create owner-reviewable notes for incomplete capabilities.

    register: existing GapRegister instance
    backlog: existing WorkBacklog instance
    """
    if not VALID.fullmatch(project):
        raise ValueError('Invalid project identifier')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Invalid batch limit')
    created = []
    for entry in register.list():
        if entry['status'] not in {'missing', 'partial', 'blocked'}:
            continue
        if len(created) >= limit:
            break
        ident = str(entry['id'])
        digest = hashlib.sha256(ident.encode('utf-8')).hexdigest()[:24]
        description = (
            f"Capability: {entry['capability']}\n"
            f"Missing work: {entry['missing_work']}\n"
            f"Evidence reference: {entry['test_evidence']}\n"
            "Review and attach an exact approved mission before enabling. "
            "This entry confers no execution or installation authority."
        )
        result = backlog.register(
            project=project, idempotency_key='gap_' + digest,
            title=('Capability gap: ' + entry['capability'])[:200],
            description=description[:12000],
            priority={'P0': 90, 'P1': 70, 'P2': 50, 'P3': 30}.get(entry['priority'], 30),
            task_type='repair', enabled=False,
        )
        created.append(result)
    return created
