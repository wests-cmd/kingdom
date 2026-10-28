"""Protected finite local worker for the fixed external negative-fence contract.

Run with python -I as an operator. The trusted producer launches disposable
containers. This worker installs no keys, grants, images or network rules.
"""
import argparse
import base64
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import sys
import time
import urllib.request
import uuid


BINDING = {'job_id', 'project', 'backlog_id', 'mission_id', 'mission_version', 'step_id',
           'source', 'base_revision', 'patch_sha256', 'contract_sha256'}
DELIVERY_PROTOCOL = 'kingdom.idempotent-verdict.v1'
SCRIPTS = ['jules-native-review-worker.py', 'jules-external-review.py',
           'jules-source-preparation.py', 'jules-external-oracle.py', 'archive-verified-source.py']
CONFIG = {'api_port', 'owner_token', 'signing_key', 'repository_directory', 'image',
          'state_directory', 'reviewer_id', 'project', 'source', 'contract_id',
          'contract_sha256', 'allowed_paths', 'deadline_at', 'max_reviews'}


def protected(path, private=False):
    path = Path(path).absolute()
    if os.name != 'posix' or path.resolve() != path:
        raise ValueError('Protected POSIX operator paths without symlinks required')
    for entry in [path, *path.parents]:
        value = entry.stat()
        if value.st_uid != 0 or value.st_mode & 0o022:
            raise ValueError('Root-owned non-writable operator inputs required')
    if private and path.stat().st_mode & 0o077:
        raise ValueError('Operator secret/config/state directory must be private')
    return path


def producer():
    for name in SCRIPTS:
        protected(Path(__file__).with_name(name))
    path = Path(__file__).with_name('jules-external-review.py')
    spec = importlib.util.spec_from_file_location('protected_external_review', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class Worker:
    # DI is constructor-only for unit tests; configuration cannot select code.
    def __init__(self, config_path, *, transport=None, execute=None, contract_digest=None,
                 recover=None, lock_factory=None, protect=protected, clock=time.time):
        self.protect, self.clock = protect, clock
        path = protect(config_path, private=True)
        if path.stat().st_size > 65536:
            raise ValueError('Bounded protected configuration required')
        self.config = json.loads(path.read_text(encoding='utf-8'))
        c = self.config
        if set(c) != CONFIG:
            raise ValueError('Only the fixed native worker configuration fields are allowed')
        if (type(c['api_port']) is not int or not 1 <= c['api_port'] <= 65535
                or c['project'] != 'kingdom' or c['source'] != 'sources/github/wests-cmd/kingdom'
                or not re.fullmatch('[a-z][a-z0-9_-]{0,100}', c['contract_id'])
                or not re.fullmatch('[a-f0-9]{64}', c['contract_sha256'])
                or not re.fullmatch('[A-Za-z0-9_.-]{1,120}', c['reviewer_id'])
                or not re.fullmatch('sha256:[a-f0-9]{64}', c['image'])
                or type(c['max_reviews']) is not int or not 1 <= c['max_reviews'] <= 20
                or type(c['deadline_at']) not in (int, float) or not math.isfinite(c['deadline_at'])
                or c['deadline_at'] > clock() + 86400):
            raise ValueError('Finite exact owner project, contract, image and budget required')
        if not isinstance(c['allowed_paths'], list) or not 1 <= len(c['allowed_paths']) <= 100:
            raise ValueError('A bounded exact operator file allowlist is required')
        for value in c['allowed_paths']:
            if (not isinstance(value, str) or not value or len(value) > 500
                    or PurePosixPath(value).is_absolute() or '..' in PurePosixPath(value).parts
                    or '\\' in value or ':' in value or any(p.lower() == '.git' for p in PurePosixPath(value).parts)):
                raise ValueError('Unsafe operator file scope')
        self.root = protect(c['state_directory'], private=True)
        if not self.root.is_dir():
            raise ValueError('Existing protected state directory required')
        protect(c['signing_key'], private=True)
        protect(c['repository_directory'])
        token_path = protect(c['owner_token'], private=True)
        if not 20 <= token_path.stat().st_size <= 501:
            raise ValueError('Bounded copied owner token required')
        self.token = token_path.read_text(encoding='utf-8').strip()
        if not 20 <= len(self.token) <= 500 or any(ch.isspace() for ch in self.token):
            raise ValueError('Invalid copied owner token')
        module = producer() if execute is None or contract_digest is None or recover is None else None
        self.execute = execute or module.execute
        self.recover = recover or module.recover_candidates
        self.lock_factory = lock_factory or self._tick_lock
        actual_digest = contract_digest() if contract_digest is not None else module.contract_digest()
        if actual_digest != c['contract_sha256']:
            raise ValueError('Installed trusted producer differs from the reviewed contract')
        self.transport = transport or self._request
        self.database = self.root / 'worker.sqlite'
        if self.database.exists() or self.database.is_symlink():
            protect(self.database, private=True)
        with self.connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,binding_json TEXT NOT NULL,state_json TEXT NOT NULL)')
        self.database.chmod(0o600)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.database, timeout=5)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _request(self, method, path, body=None):
        if not ((method == 'GET' and path == '/integrations/jules/jobs?project=kingdom')
                or re.fullmatch(r'/integrations/jules/jobs/jules-[a-f0-9]{12}(?:/review-material)?', path) and method == 'GET'
                or re.fullmatch(r'/integrations/jules/jobs/jules-[a-f0-9]{12}/(?:candidate|verify|failure)', path) and method == 'POST'):
            raise ValueError('Only fixed local review operations are permitted')
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{self.config['api_port']}" + path,
            data=data, method=method, headers={'Authorization': 'Bearer ' + self.token,
                'Content-Type': 'application/json', 'X-Kingdom-Request': '1'})
        opener = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=10) as response:
            value = response.read(5_242_881)
        if len(value) > 5_242_880:
            raise ValueError('Local review response exceeds its budget')
        return json.loads(value)

    def records(self):
        with self.connection() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT state_json FROM reviews ORDER BY rowid')]

    def save(self, state):
        with self.connection() as conn:
            conn.execute('UPDATE reviews SET state_json=? WHERE id=?', (json.dumps(state), state['id']))

    @contextmanager
    def _tick_lock(self):
        import fcntl
        path = self.root / 'worker.lock'
        if path.exists() or path.is_symlink():
            self.protect(path, private=True)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        acquired = False
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                pass
            yield acquired
        finally:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def reserve_attempt(self, state):
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            used = sum(json.loads(row[0]).get('attempts', 0) for row in conn.execute('SELECT state_json FROM reviews'))
            if used >= self.config['max_reviews'] or state.get('attempts', 0) >= 2:
                return False
            state['attempts'] = state.get('attempts', 0) + 1
            state['attempt_directory'] = 'review-' + state['id'] + '-attempt-' + str(state['attempts'])
            state['phase'] = 'executing'
            conn.execute('UPDATE reviews SET state_json=? WHERE id=?', (json.dumps(state), state['id']))
        return True

    def material(self, job):
        if (job.get('project') != self.config['project'] or job.get('source') != self.config['source']
                or not re.fullmatch('jules-[a-f0-9]{12}', job.get('id', ''))):
            raise ValueError('Job is outside the fixed owner scope')
        prefix = '/integrations/jules/jobs/' + job['id']
        if not job.get('candidate'):
            self.transport('POST', prefix + '/candidate', {})  # Read provider artifact; never submit work.
        value = self.transport('GET', prefix + '/review-material')
        if (set(value) != {'binding', 'patch', 'review_contract', 'deadline_at', 'delivery_protocol'}
                or value['delivery_protocol'] != DELIVERY_PROTOCOL):
            raise ValueError('Exact retained review material required')
        binding, contract = value['binding'], value['review_contract']
        if (not isinstance(binding, dict) or set(binding) != BINDING
                or binding['job_id'] != job['id'] or binding['project'] != self.config['project']
                or binding['source'] != self.config['source']
                or binding['contract_sha256'] != self.config['contract_sha256']
                or contract.get('contract_id') != self.config['contract_id']
                or contract.get('contract_sha256') != self.config['contract_sha256']
                or contract.get('project') != binding['project'] or contract.get('source') != binding['source']
                or contract.get('base_revision') != binding['base_revision']
                or type(contract.get('minimum_tests')) is not int or not 1 <= contract['minimum_tests'] <= 7
                or type(binding['mission_version']) is not int or binding['mission_version'] < 1
                or not re.fullmatch('[a-f0-9]{40}', binding['base_revision'])
                or not isinstance(value['patch'], str) or not 0 < len(value['patch'].encode()) <= 2_000_000
                or hashlib.sha256(value['patch'].encode()).hexdigest() != binding['patch_sha256']
                or type(value['deadline_at']) not in (int, float) or not math.isfinite(value['deadline_at'])
                or self.clock() >= min(value['deadline_at'], self.config['deadline_at'])):
            raise ValueError('Retained artifact, source, deadline or fixed negative-fence contract changed')
        return value

    def claim(self, binding):
        encoded = json.dumps(binding, sort_keys=True, separators=(',', ':'))
        ident = hashlib.sha256(encoded.encode()).hexdigest()
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT 1 FROM reviews WHERE id=?', (ident,)).fetchone():
                return None
            if sum(json.loads(row[0]).get('attempts', 0) for row in conn.execute('SELECT state_json FROM reviews')) >= self.config['max_reviews']:
                return None
            state = {'id': ident, 'binding': binding, 'phase': 'executing', 'attempts': 0, 'created_at': self.clock()}
            conn.execute('INSERT INTO reviews VALUES(?,?,?)', (ident, encoded, json.dumps(state)))
        return state

    @staticmethod
    def consumed(job, receipt_id, binding):
        values = [job.get('evidence'), job.get('repair_verdict')]
        values += [entry.get('verdict') for entry in job.get('repair_history', [])[:20] if isinstance(entry, dict)]
        return any(isinstance(value, dict) and value.get('receipt_id') == receipt_id
                   and value.get('binding') == binding for value in values)

    def reconcile(self, state):
        job = self.transport('GET', '/integrations/jules/jobs/' + state['binding']['job_id'])
        if self.consumed(job, state['receipt_id'], state['binding']):
            state.update(phase='delivered', delivery_reconciled=True)
            self.save(state)
        elif (state.get('delivery_protocol') == DELIVERY_PROTOCOL
                and self.clock() < min(self.config['deadline_at'], state['attestation']['payload']['expires_at'])
                and job.get('phase') == 'awaiting_independent_review'):
            if state.get('delivery_attempts', 0) >= 3:
                state.update(phase='delivery_held', reason='Bounded idempotent owner verdict delivery exhausted; review required')
                self.save(state)
                return state
            value = self.material(job)  # Fresh owner acknowledgement of receipt-idempotent semantics.
            if value['binding'] == state['binding']:
                self.deliver_reserved(state)
        return state

    def review(self, material, state):
        state['delivery_protocol'] = material['delivery_protocol']
        if not self.reserve_attempt(state):
            state.update(phase='execution_held', reason='Finite isolated test attempt budget exhausted')
            self.save(state)
            return
        folder = self.root / state['attempt_directory']
        folder.mkdir(mode=0o700)  # Fresh only: uncertain executions never repeat.
        patch = folder / 'candidate.patch'
        fd = os.open(patch, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(material['patch'].encode()); handle.flush(); os.fsync(handle.fileno())
        config = {key: self.config[key] for key in ('reviewer_id', 'signing_key', 'repository_directory', 'image', 'allowed_paths')}
        config.update(binding=material['binding'], patch_file=str(patch),
            deadline_at=min(material['deadline_at'], self.config['deadline_at'], self.clock() + 3600))
        path = folder / 'run-config.json'
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(config, handle); handle.flush(); os.fsync(handle.fileno())
        output = Path(self.execute(path))
        self.deliver_output(state, folder, output)

    def deliver_output(self, state, folder, output):
        self.protect(output, private=True)
        if (output.resolve().parent.parent != folder.resolve() or output.name != 'attestation.json'
                or not (output.parent / 'cleanup-complete').is_file() or output.stat().st_size > 65536):
            raise ValueError('Completed protected producer output and candidate cleanup required')
        self.protect(output.parent / 'cleanup-complete')
        envelope = json.loads(output.read_text(encoding='utf-8'))
        proof = envelope['payload']; execution = proof['execution']
        if (proof['binding'] != state['binding'] or proof['reviewer_id'] != self.config['reviewer_id']
                or proof.get('format') != 'kingdom.patch-test.v2'
                or not re.fullmatch('external-[a-f0-9]{32}', proof.get('receipt_id', ''))
                or len(base64.b64decode(envelope['signature'], validate=True)) != 64
                or type(execution.get('test_count')) is not int or execution['test_count'] != 7
                or type(execution.get('failed_count')) is not int or not 0 <= execution['failed_count'] <= 7
                or type(execution.get('exit_code')) is not int or execution['exit_code'] not in {0, 1}
                or execution.get('network_isolated') is not True or execution.get('read_only_source') is not True
                or execution.get('verdict_origin') != 'external_controller'
                or proof['expires_at'] <= self.clock() or self.clock() >= self.config['deadline_at']):
            raise ValueError('No current fixed-contract execution evidence')
        passed = execution['exit_code'] == 0 and execution['failed_count'] == 0
        if not passed and (execution['failed_count'] == 0 or execution['exit_code'] != 1):
            raise ValueError('Inconsistent producer verdict')
        state.update(phase='delivery_reserved', receipt_id=proof['receipt_id'],
                     route='verify' if passed else 'failure', attestation=envelope,
                     scope='Seven fixed API negative fences only; no general functional correctness claim')
        self.deliver_reserved(state)

    def deliver_reserved(self, state):
        if (state.get('delivery_protocol') != DELIVERY_PROTOCOL or state.get('route') not in {'verify', 'failure'}
                or state.get('delivery_attempts', 0) >= 3
                or self.clock() >= min(self.config['deadline_at'], state['attestation']['payload']['expires_at'])):
            raise ValueError('Current bounded idempotent owner-verdict delivery required')
        state.update(phase='delivery_reserved', delivery_attempts=state.get('delivery_attempts', 0) + 1)
        self.save(state)  # Claim each identical receipt delivery before POST; never rerun tests here.
        try:
            job = self.transport('POST', '/integrations/jules/jobs/' + state['binding']['job_id'] + '/' + state['route'], {'attestation': state['attestation']})
            state['phase'] = 'delivered' if self.consumed(job, state['receipt_id'], state['binding']) else 'delivery_unknown'
        except Exception:
            state['phase'] = 'delivery_unknown'
        self.save(state)

    def recover_executions(self):
        for state in self.records():
            if state['phase'] not in {'executing', 'cleanup_held'}:
                continue
            try:
                folder = self.root / state['attempt_directory'] if state.get('attempt_directory') else None
                if folder and folder.exists():
                    self.protect(folder, private=True)
                    self.recover(folder)  # Trusted cleanup first, even when a signed result was retained.
                    if self.clock() >= self.config['deadline_at']:
                        state.update(phase='execution_held', reason='Scope expired after required candidate cleanup; no retry or delivery')
                        self.save(state)
                        continue
                    results = list(folder.glob('external-*/attestation.json'))
                    if len(results) > 1:
                        raise ValueError('Ambiguous retained producer outputs')
                    if results:
                        self.deliver_output(state, folder, results[0])
                        continue
                if self.clock() >= self.config['deadline_at']:
                    state.update(phase='execution_held', reason='Scope expired; no retry or delivery')
                    self.save(state)
                    continue
                if state.get('attempts', 0) >= 2:
                    state.update(phase='execution_held', reason='One isolated retry exhausted; operator review required')
                    self.save(state)
                    continue
                job = self.transport('GET', '/integrations/jules/jobs/' + state['binding']['job_id'])
                if job.get('phase') != 'awaiting_independent_review':
                    state.update(phase='execution_held', reason='Job no longer awaits this isolated test')
                    self.save(state)
                    continue
                value = self.material(job)
                if value['binding'] != state['binding']:
                    state.update(phase='execution_held', reason='Retained binding changed; old attempt is not replayed')
                    self.save(state)
                    continue
                self.review(value, state)
            except Exception:
                state.update(phase='cleanup_held', reason='Trusted cleanup or retained verdict needs reconciliation; no new candidate launched')
                self.save(state)
                return False
        return True

    def tick(self):
        with self.lock_factory() as acquired:
            if not acquired:
                return {'status': 'another_worker_active', 'reviews': []}
            return self._tick()

    def _tick(self):
        if not self.recover_executions():
            return {'status': 'cleanup_required', 'reviews': self.records()}
        if self.clock() >= self.config['deadline_at']:
            return {'status': 'scope_expired', 'reviews': self.records()}
        for state in self.records():
            if state['phase'] in {'delivery_reserved', 'delivery_unknown'}:
                try:
                    self.reconcile(state)
                except Exception:
                    pass  # A read failure cannot authorize a repeated verdict POST.
        retained = self.records()
        if sum(s.get('attempts', 0) for s in retained) >= self.config['max_reviews']:
            pending = any(s['phase'] in {'delivery_reserved', 'delivery_unknown'} for s in retained)
            return {'status': 'reconciliation_pending' if pending else 'scope_budget_exhausted', 'reviews': retained}
        jobs = self.transport('GET', '/integrations/jules/jobs?project=kingdom')
        if not isinstance(jobs, list):
            raise ValueError('Expected a bounded local job list')
        for job in jobs[:50]:
            if not isinstance(job, dict) or job.get('phase') != 'awaiting_independent_review':
                continue
            try:
                value = self.material(job)
                state = self.claim(value['binding'])
                if state is not None:
                    try:
                        self.review(value, state)
                    except Exception:
                        state.update(phase='delivery_unknown' if state['phase'] == 'delivery_reserved' else 'executing',
                                     reason='No completed trusted delivery; do not automatically rerun or repost')
                        self.save(state)
                        return {'status': 'cleanup_required', 'reviews': self.records()}
            except (ValueError, KeyError, TypeError, OSError):
                continue
        return {'status': 'bounded_review_cycle', 'reviews': self.records()}


if __name__ == '__main__':
    if not sys.flags.isolated:
        raise SystemExit('Launch the protected worker with Python -I')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--watch', action='store_true', help='Finite supervision until the protected deadline; no renewal')
    args = parser.parse_args()
    worker = Worker(args.config)
    while True:
        try:
            result = worker.tick()
        except (OSError, ValueError, sqlite3.Error):
            # GET/state availability can recover inside the original window.
            # Claim/delivery reservations still prohibit any uncertain replay.
            print(json.dumps({'status': 'local_api_or_state_unavailable_no_replay'}), flush=True)
            if not args.watch:
                raise SystemExit(2)
            if time.time() >= worker.config['deadline_at']:
                break
            time.sleep(min(10, max(0, worker.config['deadline_at'] - time.time())))
            continue
        print(json.dumps({'status': result['status'], 'review_count': len(result['reviews']),
                          'reserved_attempts': sum(r.get('attempts', 0) for r in result['reviews'])}), flush=True)
        if not args.watch or result['status'] in {'scope_expired', 'scope_budget_exhausted'} or time.time() >= worker.config['deadline_at']:
            break
        time.sleep(min(10, max(0, worker.config['deadline_at'] - time.time())))
