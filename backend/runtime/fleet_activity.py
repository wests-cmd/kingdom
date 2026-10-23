"""Bounded metadata only. Pairing never authorizes copying prompts or transcripts."""
import json
import re
import sqlite3
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_JOBS = 20
IDENTITY = r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$'
STATUSES = {'created', 'validating', 'waiting_authorization', 'waiting_approval', 'authorized',
            'queued', 'leased', 'running', 'verifying', 'succeeded', 'completed', 'failed',
            'cancelled', 'cancel_requested', 'expired', 'blocked', 'recovery_required',
            'unknown', 'needs_review', 'waiting_review', 'ready', 'thinking', 'waiting_tools', 'budget_exhausted'}


class JobSummary(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    id: str = Field(pattern=IDENTITY)
    kind: Literal['request', 'agent', 'task']
    status: str = Field(max_length=32)
    tool: str | None = Field(default=None, pattern=r'^[a-z][a-z0-9_.-]{0,63}@\d+\.\d+\.\d+$', max_length=90)
    model: str | None = Field(default=None, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,99}$')
    worker: str | None = Field(default=None, pattern=IDENTITY)
    updated_at: float | None = Field(default=None, ge=0)


class ActivityReport(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    state: Literal['observed', 'unavailable']
    jobs: list[JobSummary] = Field(max_length=MAX_JOBS)
    observed_at: float = Field(ge=0)
    truncated: bool = False


def validate_activity(value):
    report = ActivityReport.model_validate(value).model_dump()
    seen = set()
    for job in report['jobs']:
        identity = (job['kind'], job['id'])
        if job['status'] not in STATUSES or identity in seen:
            raise ValueError('Invalid or duplicate job summary')
        seen.add(identity)
        # Reject rather than forward recognizable credentials in permitted labels.
        for field in ('id', 'model', 'worker', 'tool'):
            if job[field] is not None and safe_label(job[field], field) is None:
                raise ValueError('Unsafe job label')
    if report['state'] != 'observed' and report['jobs']:
        raise ValueError('Unavailable activity cannot contain current jobs')
    return report


def safe_label(value, field):
    if not isinstance(value, str) or re.search(r'(?i)(?:api[_-]?key|password|secret|authorization|bearer|github_pat_|ghp_|^sk-)', value):
        return None
    pattern = {'model': r'[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,99}',
               'worker': IDENTITY[1:-1], 'id': IDENTITY[1:-1], 'tool': r'[a-z][a-z0-9_.-]{0,63}@\d+\.\d+\.\d+'}[field]
    return value if re.fullmatch(pattern, value) else None


def local_activity(database=None, now=None):
    """Read existing records only; never initialize request/agent execution services."""
    if database is None:
        from backend.storage.db import db
        database = db
    observed = time.time() if now is None else now
    jobs = []
    truncated = False
    try:
        with database.get_connection() as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            # Do not send source text, objective, answer, arguments, error or config.
            for table, kind in (('conversation_requests', 'request'), ('agent_sessions', 'agent')):
                if table not in tables:
                    continue
                rows = conn.execute(f"SELECT state_json FROM {table} ORDER BY CAST(json_extract(state_json, '$.updated_at') AS REAL) DESC, rowid DESC LIMIT 21").fetchall()
                truncated |= len(rows) > MAX_JOBS
                for row in rows[:MAX_JOBS]:
                    state = json.loads(row[0])
                    if not isinstance(state, dict):
                        raise ValueError('Malformed saved work')
                    status = str(state.get('status', 'unknown')).lower()
                    jobs.append({'id': state['id'], 'kind': kind, 'status': status if status in STATUSES else 'unknown',
                                 'model': safe_label(state.get('selected_model'), 'model'),
                                 'updated_at': state.get('updated_at')})
            if 'tasks' in tables:
                rows = conn.execute('SELECT id,status,metadata_json,assigned_knight,updated_at FROM tasks ORDER BY updated_at DESC LIMIT 21').fetchall()
                truncated |= len(rows) > MAX_JOBS
                for row in rows[:MAX_JOBS]:
                    metadata = json.loads(row['metadata_json'] or '{}')
                    if not isinstance(metadata, dict):
                        raise ValueError('Malformed saved task metadata')
                    status = str(row['status']).lower()
                    jobs.append({'id': row['id'], 'kind': 'task', 'status': status if status in STATUSES else 'unknown',
                                 'tool': safe_label(metadata.get('tool'), 'tool'),
                                 'worker': safe_label(row['assigned_knight'], 'worker'),
                                 'updated_at': row['updated_at']})
        # Most recent bounded metadata across all local work records, not counts of
        # every task or proof of successful execution. Source clocks are descriptive.
        jobs.sort(key=lambda job: (job.get('updated_at') or 0, job['kind'], job['id']), reverse=True)
        truncated |= len(jobs) > MAX_JOBS
        return validate_activity({'state': 'observed', 'jobs': jobs[:MAX_JOBS],
                                  'observed_at': observed, 'truncated': truncated})
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError):
        return {'state': 'unavailable', 'jobs': [], 'observed_at': observed, 'truncated': False}
