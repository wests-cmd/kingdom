"""Durable advisory questions and evidence-backed reusable lessons.

This store grants no execution authority. Callers authenticate, recheck access
and supply an independently authoritative evidence verifier. A saved answer is
untrusted advice; selecting training data never starts training.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from uuid import NAMESPACE_URL, uuid4, uuid5


CONTEXT_FIELDS = frozenset({'source_revision', 'runtime_version', 'tool', 'error_code',
                            'summary', 'expected', 'observed', 'constraints', 'source_paths'})
POLICY_VERSION = 'consultation.v1'
_ID = re.compile(r'^[A-Za-z0-9_.:-]{1,160}$')
_PROJECT = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
_SECRET = re.compile(
    r'(?i)(\b(?:[A-Za-z][A-Za-z0-9_]*_)?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|'
    r'password|passwd|secret|authorization|cookie)\b["\']?\s*[:=]\s*["\']?)'
    r'([^\r\n,;"\'}]+)')
_QUOTED_SECRET = re.compile(
    r'(?is)(\b(?:[A-Za-z][A-Za-z0-9_]*_)?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|'
    r'id[_-]?token|password|passwd|secret|authorization|cookie)\b["\']?\s*[:=]\s*)'
    r'(["\'])(?:\\.|(?!\2).)*\2')
_BEARER = re.compile(r'(?i)\bBearer\s+[^\s,;"\'}]+')
_KEY = re.compile(r'\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b')
_PEM = re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)', re.S)
_URL_CREDENTIAL = re.compile(r'(?i)([a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@')
_COOKIE = re.compile(r'(?im)\b(?:set-cookie|cookie)\s*:\s*[^\r\n]+')


def redact_text(value, *, maximum=6000):
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise ValueError('Supply bounded nonempty text')
    value = _PEM.sub('[REDACTED PRIVATE KEY]', value)
    value = _COOKIE.sub('Cookie: [REDACTED]', value)
    value = _URL_CREDENTIAL.sub(r'\1[REDACTED]@', value)
    value = _QUOTED_SECRET.sub(lambda m: m[1]+m[2]+'[REDACTED]'+m[2], value)
    value = _SECRET.sub(r'\1[REDACTED]', value)
    value = _BEARER.sub('Bearer [REDACTED]', value)
    value = _KEY.sub('[REDACTED]', value)
    if len(value.encode('utf-8')) > maximum * 2:
        raise ValueError('Text exceeds byte budget')
    return value


def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('Supply a bounded identifier')
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class ConsultationStore:
    def __init__(self, database, *, verifier=None, publish=None, clock=time.time, max_entries=1024):
        if type(max_entries) is not int or not 1 <= max_entries <= 1024:
            raise ValueError('Consultation storage limit must be 1–1024')
        self.db, self.verifier, self.publish, self.clock = database, verifier, publish, clock
        self.max_entries = max_entries
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS consultations '
                         '(id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, state_json TEXT NOT NULL)')
            conn.commit()

    def _now(self):
        value = self.clock()
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 253402300799:
            raise ValueError('A finite UTC clock is required')
        return value

    def _event(self, row):
        if self.publish:
            self.publish('consultation.' + row['status'], {'id': row['id'], 'project': row['project'],
                         'parent_work_id': row['parent_work_id'], 'revision': row['revision']})

    @staticmethod
    def _load(conn, ident):
        value = conn.execute('SELECT state_json FROM consultations WHERE id=?', (_identifier(ident),)).fetchone()
        if not value:
            raise KeyError(ident)
        return json.loads(value[0])

    @staticmethod
    def _save(conn, row):
        row['revision'] += 1
        conn.execute('UPDATE consultations SET state_json=? WHERE id=?', (json.dumps(row), row['id']))

    @staticmethod
    def _request(project, parent_work_id, context_revision, kind, question, context):
        if not isinstance(project, str) or not _PROJECT.fullmatch(project):
            raise ValueError('Supply a project')
        _identifier(parent_work_id); _identifier(context_revision)
        if kind not in {'planning', 'question', 'error'}:
            raise ValueError('Choose planning, question or error advice')
        question = redact_text(question, maximum=16000).strip()
        if not question:
            raise ValueError('Supply a question')
        if not isinstance(context, dict) or set(context) - CONTEXT_FIELDS:
            raise ValueError('Only explicit bounded context fields are permitted')
        cleaned = {}
        for key, value in context.items():
            if isinstance(value, list):
                if len(value) > 16:
                    raise ValueError('Context list exceeds budget')
                cleaned[key] = [redact_text(v, maximum=2000) for v in value]
            else:
                cleaned[key] = redact_text(value, maximum=6000)
        if len(json.dumps(cleaned, ensure_ascii=False).encode()) > 24000:
            raise ValueError('Context exceeds byte budget')
        return dict(project=project, parent_work_id=parent_work_id, context_revision=context_revision,
                    kind=kind, question=question, question_sha256=_digest(question), context=cleaned,
                    context_sha256=_digest(cleaned))

    def request(self, project, parent_work_id, context_revision, kind, question, context=None):
        values = self._request(project, parent_work_id, context_revision, kind, question, context or {})
        key = _digest([project, parent_work_id, context_revision, kind, values['question_sha256']])
        ident = uuid5(NAMESPACE_URL, 'kingdom-consultation:' + key).hex
        created = False
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            saved = conn.execute('SELECT state_json FROM consultations WHERE request_key=?', (key,)).fetchone()
            if saved:
                row = json.loads(saved[0])
                if row['context_sha256'] != values['context_sha256']:
                    raise ValueError('Question context changed; use its new revision')
            else:
                if conn.execute('SELECT COUNT(*) FROM consultations').fetchone()[0] >= self.max_entries:
                    raise ValueError('Consultation storage is full; retain evidence and review retention')
                now = self._now()
                row = dict(values, id=ident, status='queued', revision=1, generation=0, attempts=0,
                           created_at=now, updated_at=now, answer=None, answer_sha256=None,
                           provider=None, verification=None, training_selected=False,
                           policy_version=POLICY_VERSION, authority='untrusted_advice')
                conn.execute('INSERT INTO consultations VALUES(?,?,?)', (ident, key, json.dumps(row)))
                created = True
            conn.commit()
        if created:
            self._event(row)
        return row

    def get(self, ident):
        with self.db.get_connection() as conn:
            return self._load(conn, ident)

    def list(self, project=None, *, limit=100):
        if type(limit) is not int or not 1 <= limit <= 1024:
            raise ValueError('Choose a bounded limit')
        if project is not None and (not isinstance(project, str) or not _PROJECT.fullmatch(project)):
            raise ValueError('Supply a project')
        with self.db.get_connection() as conn:
            rows = [json.loads(v[0]) for v in conn.execute('SELECT state_json FROM consultations ORDER BY rowid')]
        return [r for r in rows if project is None or r['project'] == project][:limit]

    def claim(self, worker_id, question_id=None, *, lease_seconds=120):
        _identifier(worker_id)
        if type(lease_seconds) not in (int, float) or not math.isfinite(lease_seconds) or not 1 <= lease_seconds <= 300:
            raise ValueError('Use a finite lease of 1–300 seconds')
        now = self._now()
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            rows = ([self._load(conn, question_id)] if question_id is not None else
                    [json.loads(v[0]) for v in conn.execute('SELECT state_json FROM consultations ORDER BY rowid')])
            for row in rows:
                if (row['status'] != 'queued' or row['attempts'] >= 2
                        or now < row['created_at'] or now < row.get('retry_at', 0)):
                    continue
                row.update(status='claimed', claim_token=uuid4().hex, worker_id=worker_id,
                           generation=row['generation'] + 1, claimed_at=now,
                           lease_expires_at=now + lease_seconds, updated_at=now)
                self._save(conn, row); conn.commit()
                break
            else:
                return None
        self._event(row)
        return row

    @staticmethod
    def _fence(row, token, statuses):
        if (not isinstance(token, str) or row.get('claim_token') != token or row['status'] not in statuses):
            raise PermissionError('Consultation claim is stale or not available for this transition')

    def mark_sending(self, ident, token):
        now = self._now()
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE'); row = self._load(conn, ident)
            self._fence(row, token, {'claimed'})
            if not row['claimed_at'] <= now < row['lease_expires_at'] or row['attempts'] >= 2:
                raise PermissionError('Consultation lease expired or its attempt budget is exhausted')
            row.update(status='sending', attempts=row['attempts'] + 1, updated_at=now)
            self._save(conn, row); conn.commit()
        self._event(row)
        return row

    def finish(self, ident, token, answer, provider):
        answer = redact_text(answer, maximum=16000).strip()
        _identifier(provider)
        if not answer:
            raise ValueError('A completed answer must contain text')
        now = self._now()
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE'); row = self._load(conn, ident)
            self._fence(row, token, {'sending'})
            row.update(status='answered', answer=answer, answer_sha256=_digest(answer), provider=provider,
                       updated_at=now, answered_at=now)
            row.pop('claim_token', None)
            self._save(conn, row); conn.commit()
        self._event(row)
        return row

    def _terminal(self, ident, status, *, token=None, reason='operator_cancelled'):
        _identifier(reason)
        now = self._now()
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE'); row = self._load(conn, ident)
            if token is not None:
                self._fence(row, token, {'claimed', 'sending'})
            row.update(status=status, error_code=reason, updated_at=now, training_selected=False)
            row.pop('claim_token', None)
            self._save(conn, row); conn.commit()
        self._event(row)
        return row

    def mark_unknown(self, ident, token, reason='provider_outcome_unknown'):
        return self._terminal(ident, 'outcome_unknown', token=token, reason=reason)

    def mark_failed(self, ident, token=None, reason='provider_failed'):
        return self._terminal(ident, 'failed', token=token, reason=reason)

    def cancel(self, ident):
        return self._terminal(ident, 'cancelled')

    def fail_not_sent(self, ident, token, reason='provider_unavailable'):
        """Trusted transport only: never use this for an ambiguous sent request."""
        _identifier(reason)
        now = self._now()
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE'); row = self._load(conn, ident)
            self._fence(row, token, {'claimed', 'sending'})
            row.update(status='queued' if row['attempts'] < 2 else 'failed', error_code=reason,
                       retry_at=now + min(300, 10 * 2 ** row['attempts']), updated_at=now)
            row.pop('claim_token', None)
            self._save(conn, row); conn.commit()
        self._event(row)
        return row

    def recover_startup(self):
        changed = []
        now = self._now()
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            rows = [json.loads(v[0]) for v in conn.execute('SELECT state_json FROM consultations')]
            for row in rows:
                if row['status'] not in {'claimed', 'sending'}:
                    continue
                row.update(status='queued' if row['status'] == 'claimed' else 'outcome_unknown',
                           generation=row['generation'] + 1, updated_at=now,
                           error_code='runtime_interrupted')
                row.pop('claim_token', None)
                self._save(conn, row); changed.append(row)
            conn.commit()
        for row in changed:
            self._event(row)
        return changed

    def _evidence(self, row, evidence_id):
        """Revalidate current external evidence; never accept a caller's Boolean."""
        _identifier(evidence_id)
        if self.verifier is None or row['status'] != 'answered' or not row.get('answer_sha256'):
            raise PermissionError('A completed answer and authoritative verifier are required')
        try:
            evidence = self.verifier(json.loads(json.dumps(row)), evidence_id)
            expected = {'evidence_id': evidence_id, 'project': row['project'],
                        'parent_work_id': row['parent_work_id'], 'context_revision': row['context_revision'],
                        'question_id': row['id'], 'answer_sha256': row['answer_sha256']}
            if (not isinstance(evidence, dict) or evidence.get('tests_passed') is not True
                    or evidence.get('revoked') is not False
                    or evidence.get('kind') not in {'project_test', 'independent_review', 'function_check'}
                    or any(evidence.get(k) != value for k, value in expected.items())):
                raise PermissionError('Acceptance does not cover this exact question and answer')
            return {**expected, 'kind': evidence['kind'], 'checked_at': self._now(),
                    'policy_version': POLICY_VERSION}
        except PermissionError:
            raise
        except Exception as error:
            # Provider errors can contain credentials, private paths or logs.
            raise PermissionError('Acceptance is unavailable or no longer valid') from None

    def record_verification(self, ident, evidence_id):
        observed = self.get(ident)
        evidence = self._evidence(observed, evidence_id)
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE'); row = self._load(conn, ident)
            if row['revision'] != observed['revision'] or row['status'] != 'answered':
                raise ValueError('Answer changed during acceptance verification')
            row.update(verification=evidence, updated_at=self._now())
            self._save(conn, row); conn.commit()
        self._event(row)
        return row

    def lookup_verified(self, project, context_revision, kind, question, context=None):
        wanted = self._request(project, 'lookup', context_revision, kind, question,
                               {} if context is None else context)
        # Match source/context, not the new task's ID. The original evidence is
        # always verified against its original parent, never transferred to a new
        # mission. The new task must still validate its plan and execution.
        for row in reversed(self.list(project, limit=1024)):
            if (row['status'] != 'answered' or not row.get('verification')
                    or any(row[k] != wanted[k] for k in ('context_revision', 'kind', 'question_sha256', 'context_sha256'))):
                continue
            try:
                evidence = self._evidence(row, row['verification']['evidence_id'])
                current = self.get(row['id'])
                if current['revision'] != row['revision']:
                    continue
                return {**row, 'verification': evidence, 'reuse_scope': 'advice_only',
                        'source_consultation_id': row['id']}
            except (PermissionError, KeyError, ValueError):
                continue
        return None

    def select_for_training(self, ident, selected):
        if type(selected) is not bool:
            raise ValueError('Training selection must be explicit')
        observed = self.get(ident)
        if selected:
            if not observed.get('verification'):
                raise PermissionError('Only currently verified guidance can be selected')
            self._evidence(observed, observed['verification']['evidence_id'])
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE'); row = self._load(conn, ident)
            if row['revision'] != observed['revision']:
                raise ValueError('Lesson changed during selection')
            row.update(training_selected=selected, updated_at=self._now())
            self._save(conn, row); conn.commit()
        self._event(row)
        return row

    def export_training(self, *, project, limit=100, maximum_bytes=1_000_000):
        """Sanitized local JSONL candidates; neither uploads nor starts training."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('Choose a bounded export limit')
        if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= 1_000_000:
            raise ValueError('Choose an export byte budget of at most one megabyte')
        lines, used = [], 0
        for row in self.list(project, limit=1024):
            if not row['training_selected'] or not row.get('verification'):
                continue
            try:
                evidence = self._evidence(row, row['verification']['evidence_id'])
                current = self.get(row['id'])
                if current['revision'] != row['revision'] or not current['training_selected']:
                    continue
                record = {'messages': [
                    {'role': 'user', 'content': redact_text(row['question'], maximum=16000)},
                    {'role': 'assistant', 'content': redact_text(row['answer'], maximum=16000)}],
                    'context': {k: [redact_text(s, maximum=2000) for s in v] if isinstance(v, list)
                                else redact_text(v) for k, v in row['context'].items()},
                    'provenance': {**evidence, 'provider': row['provider'],
                                   'authority': 'training_candidate_only'}}
                line = json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n'
                cost = len(line.encode())
                if used + cost > maximum_bytes:
                    break
                lines.append(line); used += cost
                if len(lines) >= limit:
                    break
            except (PermissionError, KeyError, ValueError):
                continue
        return ''.join(lines)
