"""Native Kingdom-to-Jules engineering handoff adapter.

Provides a narrow, owner-authorized adapter with encrypted write-only credentials,
explicit repository/source allowlists, durable job records bound to existing project/backlog
items, service-owned submit/observe lifecycle, and independent verification gates.

Remote completion is never acceptance. Model prose or test-count claims are untrusted.
"""

from pathlib import Path
import hashlib
import json
import os
import re
import threading
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from functools import wraps

from cryptography.fernet import Fernet
from backend.memory.portable_vault import clean_text, identifier

API = "https://jules.googleapis.com/v1alpha/"
TERMINAL_PHASES = {
    "completed",
    "failed",
    "submission_unknown",
    "expired_remote_may_continue",
    "cancelled",
}


def announces(kind='job'):
    def decorate(method):
        @wraps(method)
        def wrapped(self,*args,**kwargs):
            result=method(self,*args,**kwargs)
            self._announce(result,kind)
            return result
        return wrapped
    return decorate


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class JulesService:
    def __init__(
        self, database, engine=None, secrets_root="data/secrets", clock=time.time
    ):
        self.db = database
        self.engine = engine
        self.clock = clock
        self._lock = threading.RLock()
        self._announced = {}
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.ProxyHandler({})
        )
        self.secrets_root = Path(secrets_root)
        self._init_cipher()
        self._init_db()

    def _init_cipher(self):
        self.secrets_root.mkdir(parents=True, exist_ok=True)
        key_path = self.secrets_root / "jules.key"
        if not key_path.exists():
            try:
                fd = os.open(
                    key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                )
                with os.fdopen(fd, "wb") as handle:
                    handle.write(Fernet.generate_key())
            except FileExistsError:
                pass
        self.cipher = Fernet(key_path.read_bytes())

    def _init_db(self):
        with self.db.get_connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS jules_settings (
                id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                secret BLOB,
                revision INTEGER NOT NULL
            )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS jules_jobs (
                id TEXT PRIMARY KEY,
                project TEXT NOT NULL,
                backlog_id TEXT NOT NULL,
                idem TEXT NOT NULL,
                state_json TEXT NOT NULL,
                UNIQUE(project, idem)
            )"""
            )
            default_data = {
                "allowed_repositories": ["wests-cmd/kingdom"],
                "allowed_sources": ["sources/github/wests-cmd/kingdom"],
            }
            conn.execute(
                "INSERT OR IGNORE INTO jules_settings VALUES(1, 0, ?, NULL, 1)",
                (json.dumps(default_data),),
            )
            conn.commit()

    def settings(self):
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT enabled, data_json, secret, revision FROM jules_settings WHERE id=1"
            ).fetchone()
        if not row:
            return {
                "enabled": False,
                "revision": 1,
                "has_credentials": False,
                "allowed_repositories": [],
                "allowed_sources": [],
            }
        data = json.loads(row[1])
        return {
            "enabled": bool(row[0]),
            "revision": row[3],
            "has_credentials": bool(row[2]),
            "allowed_repositories": list(data.get("allowed_repositories", [])),
            "allowed_sources": list(data.get("allowed_sources", [])),
        }

    @announces('settings')
    def configure(
        self,
        enabled=None,
        allowed_repositories=None,
        allowed_sources=None,
        api_key=None,
        expected_revision=None,
    ):
        # Level 5 standing owner authorization required
        if (
            self.engine
            and hasattr(self.engine, "execution_policy")
            and self.engine.execution_policy.get()["level"] < 5
        ):
            raise ValueError(
                "Owner Level 5 standing authorization required for cloud adapter settings"
            )

        with self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT enabled, data_json, secret, revision FROM jules_settings WHERE id=1"
            ).fetchone()
            curr_enabled, curr_data_json, curr_secret, curr_rev = row
            if (
                expected_revision is not None
                and curr_rev != expected_revision
            ):
                raise ValueError("Settings revision mismatch; reload first")
            data = json.loads(curr_data_json)

            if allowed_repositories is not None:
                if (
                    not isinstance(allowed_repositories, list)
                    or not allowed_repositories
                ):
                    raise ValueError("At least one allowed repository required")
                data["allowed_repositories"] = allowed_repositories

            if allowed_sources is not None:
                if not isinstance(allowed_sources, list) or not allowed_sources:
                    raise ValueError("At least one allowed source required")
                data["allowed_sources"] = allowed_sources

            new_secret = curr_secret
            if api_key is not None:
                if not isinstance(api_key, str) or not api_key.strip():
                    raise ValueError("Valid API key string required")
                new_secret = self.cipher.encrypt(api_key.strip().encode("utf-8"))

            new_enabled = (
                int(enabled) if enabled is not None else curr_enabled
            )
            if new_enabled and not new_secret:
                raise ValueError(
                    "API credentials must be configured before enabling adapter"
                )

            changed = conn.execute(
                "UPDATE jules_settings SET enabled=?, data_json=?, secret=?, revision=revision+1 WHERE id=1 AND revision=?",
                (new_enabled, json.dumps(data), new_secret, curr_rev),
            ).rowcount
            if not changed:
                raise ValueError("Concurrent update detected; reload")
            conn.commit()
        return self.settings()

    def _get_decrypted_secret(self):
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT secret FROM jules_settings WHERE id=1"
            ).fetchone()
        if not row or not row[0]:
            raise ValueError("Jules API credentials not configured")
        return self.cipher.decrypt(row[0]).decode("utf-8")

    def _announce(self,state,kind='job'):
        if not self.engine or not hasattr(self.engine,'events') or not isinstance(state,dict):return
        ident=state.get('id','settings');version=state.get('record_version',state.get('revision',0))
        if self._announced.get((kind,ident),-1)>=version:return
        fields=('revision','enabled') if kind=='settings' else ('id','project','backlog_id','phase','accepted','record_version')
        self.engine.events.publish('jules.'+kind+'_changed',{key:state[key] for key in fields if key in state})
        if kind=='job' and state.get('backlog_woken_revision'):
            self.engine.events.publish('backlog.updated',{'id':state['backlog_id'],'project':state['project'],'status':'ready','revision':state['backlog_woken_revision']})
        self._announced[kind,ident]=version

    def _save_job(self, conn, state):
        state["updated_at"] = self.clock()
        state["record_version"] = state.get("record_version",0)+1
        conn.execute(
            "INSERT INTO jules_jobs VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state_json=excluded.state_json",
            (
                state["id"],
                state["project"],
                state["backlog_id"],
                state["idem"],
                json.dumps(state),
            ),
        )

    def get_job(self, job_id):
        identifier(job_id)
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT state_json FROM jules_jobs WHERE id=?", (job_id,)
            ).fetchone()
        if not row:
            raise KeyError(job_id)
        return json.loads(row[0])

    def list_jobs(self, project=None):
        with self.db.get_connection() as conn:
            if project:
                identifier(project)
                rows = conn.execute(
                    "SELECT state_json FROM jules_jobs WHERE project=? ORDER BY rowid DESC",
                    (project,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT state_json FROM jules_jobs ORDER BY rowid DESC"
                ).fetchall()
            return [json.loads(r[0]) for r in rows]

    @announces()
    def register_job(
        self,
        project,
        backlog_id,
        idempotency_key,
        source,
        repository,
        revision,
        branch,
        prompt,
        max_repair_budget=3,
        deadline_seconds=3600,
    ):
        identifier(project)
        identifier(backlog_id)
        identifier(idempotency_key)

        settings = self.settings()
        if not settings["enabled"]:
            raise ValueError("Jules adapter is disabled")

        if repository not in settings["allowed_repositories"]:
            raise ValueError(f"Repository {repository} is not in allowlist")
        if source not in settings["allowed_sources"]:
            raise ValueError(f"Source {source} is not in allowlist")

        if not re.fullmatch("[a-f0-9]{40}", revision):
            raise ValueError("Revision must be a 40-character hex SHA")
        if not re.fullmatch("[A-Za-z0-9_./-]{1,150}", branch) or ".." in branch:
            raise ValueError("Invalid branch name")
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 12000:
            raise ValueError("Prompt must be between 1 and 12000 characters")
        if type(max_repair_budget) is not int or not 0 <= max_repair_budget <= 10:
            raise ValueError("Max repair budget must be between 0 and 10")
        if (
            type(deadline_seconds) not in (int, float)
            or not 60 <= deadline_seconds <= 86400
        ):
            raise ValueError("Deadline seconds must be between 60 and 86400")

        with self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            # Check duplicate idempotency key
            existing = conn.execute(
                "SELECT state_json FROM jules_jobs WHERE project=? AND idem=?",
                (project, idempotency_key),
            ).fetchone()
            if existing:
                saved = json.loads(existing[0])
                expected={'source':source,'repository':repository,'revision':revision,'backlog_id':backlog_id,'branch':branch,'prompt':prompt,'max_repair_budget':max_repair_budget}
                if any(saved.get(k)!=value for k,value in expected.items()) or saved['deadline_at']-saved['created_at']!=deadline_seconds:
                    raise ValueError('Idempotency key belongs to different job parameters')
                return saved

            # Every cloud job must refer to an existing owner backlog record.
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='work_backlog'").fetchone():
                raise ValueError('Create the reviewed backlog record first')
            backlog_row=conn.execute('SELECT state_json FROM work_backlog WHERE project=? AND id=?',(project,backlog_id)).fetchone()
            if not backlog_row:raise ValueError('Backlog item is not registered in this project')
            backlog=json.loads(backlog_row[0])
            if backlog.get('enabled') or backlog.get('lease') or backlog.get('status')=='completed':
                raise ValueError('Delegate only a disabled, unleased, unfinished backlog record')

            if conn.execute('SELECT 1 FROM jules_jobs WHERE project=? AND backlog_id=?',(project,backlog_id)).fetchone():
                raise ValueError('Backlog item already has a Jules job; reuse its retained checkpoint')

            job_id = f"jules-{uuid.uuid4().hex[:12]}"
            now = self.clock()
            state = {
                "id": job_id,
                "project": project,
                "backlog_id": backlog_id,
                "idem": idempotency_key,
                "source": source,
                "repository": repository,
                "revision": revision,
                "branch": branch,
                "prompt": prompt,
                "phase": "queued",
                "session": None,
                "session_url": None,
                "remote_state": None,
                "accepted": False,
                "automatic_merge": False,
                "automatic_deployment": False,
                "repair_attempts": 0,
                "max_repair_budget": max_repair_budget,
                "repair_diagnostics": None,
                "consecutive_errors": 0,
                "backoff_until": 0,
                "deadline_at": now + deadline_seconds,
                "created_at": now,
                "updated_at": now,
                "reason": "Queued for submission to Jules provider",
            }
            self._save_job(conn, state)
            conn.commit()
        return state

    def request(self, path, body=None, opener=None):
        if not re.fullmatch(r"sessions(?:/[A-Za-z0-9_-]+(?:/activities\?pageSize=25(?:&pageToken=[A-Za-z0-9%_.~-]+)?)?)?", path):
            raise ValueError("Only fixed Jules session operations are allowed")
        secret = self._get_decrypted_secret()
        req = urllib.request.Request(
            API + path,
            data=None if body is None else json.dumps(body).encode("utf-8"),
            headers={
                "X-Goog-Api-Key": secret,
                "Content-Type": "application/json",
            },
        )
        active_opener = opener or self.opener
        with active_opener.open(req, timeout=30) as resp:
            data = resp.read(5242881)
        if len(data) > 5242880:
            raise ValueError("Bounded Jules response size exceeded")
        return json.loads(data.decode("utf-8"))

    @announces()
    def submit_job(self, job_id, opener=None):
        with self._lock:
            state = self.get_job(job_id)
            if state["phase"] == "cancelled":
                raise ValueError("Job is cancelled")
            if state["phase"] != "queued":
                if state["phase"] in {"submitting", "submission_unknown"}:
                    raise ValueError(
                        "Submission outcome needs reconciliation; no automatic replay"
                    )
                return state

            # Live execution policy / runtime level check prior to dispatch
            if (
                self.engine
                and hasattr(self.engine, "execution_policy")
                and self.engine.execution_policy.get()["level"] < 5
            ):
                return state

            settings = self.settings()
            if not settings["enabled"]:
                with self.db.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    state.update(
                        phase="cancelled",
                        reason="Adapter is disabled; queued job cancelled before dispatch",
                    )
                    self._save_job(conn, state)
                    conn.commit()
                return state

            # Live allowlist re-validation at dispatch time
            if (
                state["repository"] not in settings["allowed_repositories"]
                or state["source"] not in settings["allowed_sources"]
            ):
                with self.db.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    state.update(
                        phase="cancelled",
                        reason="Repository or source allowlist was revoked before dispatch",
                    )
                    self._save_job(conn, state)
                    conn.commit()
                return state

            self._current_authority(state)

            # Atomic cross-instance SQLite claiming
            now = self.clock()
            with self.db.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                rowcount = conn.execute(
                    """UPDATE jules_jobs
                       SET state_json = json_set(state_json, '$.phase', 'submitting', '$.reason', 'POST request dispatched to Jules API', '$.updated_at', ?, '$.record_version', COALESCE(json_extract(state_json, '$.record_version'),0)+1)
                       WHERE id = ? AND json_extract(state_json, '$.phase') = 'queued'""",
                    (now, job_id),
                ).rowcount
                conn.commit()

            if rowcount != 1:
                # Another process instance claimed or submitted the job concurrently
                return self.get_job(job_id)

            state = self.get_job(job_id)
            self._announce(state)

            body = {
                "title": f"Kingdom scoped engineering assignment: {state['backlog_id']}",
                "prompt": (
                    state["prompt"]
                    + "\nExpected source revision: "
                    + state["revision"]
                    + "\nVerify the exact checkout first. No merge, deployment, credentials or owner-device access. Return source/test evidence for independent review."
                ),
                "sourceContext": {
                    "source": state["source"],
                    "githubRepoContext": {"startingBranch": state["branch"]},
                },
                "requirePlanApproval": False,
                "automationMode": "AUTOMATION_MODE_UNSPECIFIED",
            }

            try:
                reply = self.request("sessions", body, opener=opener)
                session_name = reply.get("name")
                if not isinstance(session_name, str) or not re.fullmatch(
                    r"sessions/[A-Za-z0-9_-]+", session_name
                ):
                    raise ValueError("Unexpected Jules session identity format")
                session_url = (
                    "https://jules.google.com/session/"
                    + session_name.split("/")[1]
                )

                with self.db.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    current=json.loads(conn.execute('SELECT state_json FROM jules_jobs WHERE id=?',(job_id,)).fetchone()[0])
                    locally_cancelled=current['phase']=='cancelled'
                    state=current
                    state.update(
                        phase='cancelled' if locally_cancelled else 'watching',
                        session=session_name,session_url=session_url,
                        remote_state=reply.get('state','QUEUED'),
                        reason='Local cancellation retained; remote session may continue' if locally_cancelled else 'Jules session created; watching progress',
                    )
                    self._save_job(conn, state)
                    conn.commit()
            except Exception as error:
                status_code = (
                    error.code
                    if isinstance(error, urllib.error.HTTPError)
                    else None
                )
                with self.db.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    state.update(
                        phase="cancelled" if json.loads(conn.execute("SELECT state_json FROM jules_jobs WHERE id=?",(job_id,)).fetchone()[0])["phase"]=="cancelled" else "submission_unknown",
                        reason="Submission outcome needs reconciliation; no automatic replay",
                        http_status=status_code,
                    )
                    self._save_job(conn, state)
                    conn.commit()
            return state

    @announces()
    def poll_job(self, job_id, opener=None):
        with self._lock:
            state = self.get_job(job_id)
            if state["phase"] != "watching":
                return state

            # Live execution policy / runtime level check prior to polling
            if (
                self.engine
                and hasattr(self.engine, "execution_policy")
                and self.engine.execution_policy.get()["level"] < 5
            ):
                return state

            settings = self.settings()
            if not settings["enabled"]:
                return state

            # Live allowlist re-validation during observation
            if (
                state["repository"] not in settings["allowed_repositories"]
                or state["source"] not in settings["allowed_sources"]
            ):
                with self.db.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    state.update(
                        phase="review_required",
                        reason="Repository or source allowlist was revoked during observation",
                    )
                    self._save_job(conn, state)
                    conn.commit()
                return state

            now = self.clock()
            if now < state.get("backoff_until", 0):
                return state

            try:
                reply = self.request(state["session"], opener=opener)
                # Verify session and source identity consistency
                if reply.get("name") != state["session"]:
                    raise ValueError("Jules session identity changed")
                remote_source = (
                    reply.get("sourceContext", {}).get("source")
                    or state["source"]
                )
                if remote_source != state["source"]:
                    raise ValueError("Jules source context changed")

                remote_state = reply.get("state", "STATE_UNSPECIFIED")
                known_states = {
                    "STATE_UNSPECIFIED",
                    "QUEUED",
                    "PLANNING",
                    "AWAITING_PLAN_APPROVAL",
                    "AWAITING_USER_FEEDBACK",
                    "IN_PROGRESS",
                    "PAUSED",
                    "FAILED",
                    "COMPLETED",
                }
                if remote_state not in known_states:
                    raise ValueError(f"Unknown Jules lifecycle state: {remote_state}")

                if remote_state == "COMPLETED":
                    phase = "awaiting_independent_review"
                    reason = "Remote Jules session completed; awaiting independent local test verification"
                elif remote_state == "FAILED":
                    phase = "failed"
                    reason = "Remote Jules session reported failure"
                elif remote_state in {
                    "PAUSED",
                    "AWAITING_PLAN_APPROVAL",
                    "AWAITING_USER_FEEDBACK",
                }:
                    phase = "paused"
                    reason = f"Remote session paused in state {remote_state}"
                else:
                    phase = "watching"
                    reason = f"Remote session in progress: {remote_state}"

                state=self._poll_update(job_id,state['session'],dict(phase=phase,remote_state=remote_state,consecutive_errors=0,backoff_until=0,reason=reason))
            except urllib.error.HTTPError as error:
                if error.code in {429, 503}:
                    err_count = state.get("consecutive_errors", 0) + 1
                    delay = min(300, 15 * (2 ** min(err_count, 4)))
                    state=self._poll_update(job_id,state['session'],dict(consecutive_errors=err_count,backoff_until=now+delay,reason=f'Provider quota or transient backoff (HTTP {error.code})'))
                else:
                    raise
            return state

    def _poll_update(self,job_id,session,changes):
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            current=json.loads(conn.execute('SELECT state_json FROM jules_jobs WHERE id=?',(job_id,)).fetchone()[0])
            if current['phase']!='watching' or current.get('session')!=session:return current
            current.update(changes);self._save_job(conn,current);conn.commit()
            return current

    @announces()
    def run_job(self, job_id, opener=None):
        state = self.get_job(job_id)
        if state["phase"] in TERMINAL_PHASES:
            return state

        # Live policy check
        if (
            self.engine
            and hasattr(self.engine, "execution_policy")
            and self.engine.execution_policy.get()["level"] < 5
        ):
            return state

        if state["phase"] == "submitting":
            with self.db.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                state.update(
                    phase="submission_unknown",
                    reason="Interrupted POST; reconcile remote sessions before any new job",
                )
                self._save_job(conn, state)
                conn.commit()
            return state

        if self.clock() >= state["deadline_at"]:
            with self.db.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                state.update(
                    phase="expired_remote_may_continue",
                    reason="Local observation ended; remote work was not cancelled",
                )
                self._save_job(conn, state)
                conn.commit()
            return state

        if state["phase"] == "queued":
            state = self.submit_job(job_id, opener=opener)
        if state["phase"] == "watching":
            state = self.poll_job(job_id, opener=opener)
        return state

    def tick(self, opener=None):
        if not self.settings()["enabled"]:
            return {"status": "disabled", "processed": 0}

        if (
            self.engine
            and hasattr(self.engine, "execution_policy")
            and self.engine.execution_policy.get()["level"] < 5
        ):
            return {"status": "policy_halted", "processed": 0}

        active_jobs = [
            j for j in self.list_jobs()
            if j["phase"] in {"queued", "submitting", "watching"}
        ]
        processed = 0
        for job in active_jobs:
            try:
                self.run_job(job["id"], opener=opener)
                processed += 1
            except Exception as error:
                if self.engine and hasattr(self.engine,'events'):
                    self.engine.events.publish('jules.job_error',{'id':job['id'],'project':job['project'],'error_type':type(error).__name__})
        return {"status": "ok", "processed": processed}

    @announces()
    def cancel_job(self, job_id, reason="Cancelled by owner"):
        with self._lock,self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT state_json FROM jules_jobs WHERE id=?',(job_id,)).fetchone()
            if not row:raise KeyError(job_id)
            state=json.loads(row[0])
            if state['phase'] in {'completed','failed'}:return state
            remote_possible=state['phase']!='queued'
            state.update(phase='cancelled',reason=clean_text(str(reason))[:300]+(' ; local cancellation only; remote work may continue' if remote_possible else ''))
            self._save_job(conn,state);conn.commit()
            return state

    @announces()
    def fetch_candidate(self, job_id, opener=None):
        """Retain a provider-returned patch; callers cannot nominate its digest."""
        import urllib.parse
        with self._lock:
            state=self.get_job(job_id)
            if state['phase'] not in {'awaiting_independent_review','review_required'}:
                raise ValueError('Remote completion must precede candidate review')
            self._current_authority(state)
            page='';patches=[]
            for _ in range(12):
                suffix='/activities?pageSize=25'+('&pageToken='+urllib.parse.quote(page,safe='') if page else '')
                data=self.request(state['session']+suffix,opener=opener)
                for activity in data.get('activities',[]):
                    for artifact in activity.get('artifacts',[]):
                        change=artifact.get('changeSet',{});patch=change.get('gitPatch',{})
                        if change.get('source')==state['source'] and patch.get('unidiffPatch'):
                            patches.append((activity.get('createTime',''),patch))
                page=data.get('nextPageToken','')
                if not page:break
            if page or not patches:raise ValueError('Complete bounded provider patch unavailable')
            patch=max(patches,key=lambda value:value[0])[1]
            if patch.get('baseCommitId')!=state['revision']:raise ValueError('Candidate base differs from reviewed job')
            value=patch['unidiffPatch']
            if not isinstance(value,str) or not 1<=len(value.encode())<=2000000:raise ValueError('Candidate patch exceeds scope')
            candidate={'base_revision':state['revision'],'patch_sha256':hashlib.sha256(value.encode()).hexdigest()}
            with self.db.get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                current=json.loads(conn.execute('SELECT state_json FROM jules_jobs WHERE id=?',(job_id,)).fetchone()[0])
                if current['phase'] not in {'awaiting_independent_review','review_required'}:raise ValueError('Candidate job changed')
                if current.get('candidate') and current['candidate']!=candidate:raise ValueError('Retained candidate changed; create a bounded review revision')
                current.update(candidate=candidate)
                conn.execute('CREATE TABLE IF NOT EXISTS jules_candidate_patches (job_id TEXT PRIMARY KEY, patch TEXT NOT NULL)')
                conn.execute('INSERT OR REPLACE INTO jules_candidate_patches VALUES(?,?)',(job_id,value))
                self._save_job(conn,current);conn.commit()
            return current

    def _current_authority(self,state):
        settings=self.settings()
        if not settings['enabled'] or state['source'] not in settings['allowed_sources'] or state['repository'] not in settings['allowed_repositories']:
            raise ValueError('Jules job authority is disabled or revoked')
        if not self.engine or self.engine.execution_policy.get()['level']<5:
            raise ValueError('Cloud dispatch requires current level-5 standing authorization')
        if self.clock()>=state['deadline_at']:raise ValueError('Job review window expired')

    @announces()
    def verify_job_completion(self, job_id, verification_evidence):
        """Require both current mission acceptance and a protected exact-patch signature.

        Human-review flags are not an alternate path to automated test acceptance.
        A receipt is consumed atomically with acceptance; no backlog row is silently
        completed by this method.
        """
        from backend.runtime.patch_acceptance import reviewer_registry,verify_attestation,current_review_contract,expected_binding
        with self._lock,self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT state_json FROM jules_jobs WHERE id=?',(job_id,)).fetchone()
            if not row:raise KeyError(job_id)
            state=json.loads(row[0])
            if state['phase'] not in {'awaiting_independent_review','review_required'}:raise ValueError('Job is not awaiting review')
            try:
                self._current_authority(state)
                if not isinstance(verification_evidence,dict):raise ValueError('Structured signed attestation required')
                row=conn.execute('SELECT state_json FROM work_backlog WHERE project=? AND id=?',(state['project'],state['backlog_id'])).fetchone()
                backlog=json.loads(row[0]) if row else {};intent=backlog.get('intent',{})
                candidate=state.get('candidate')
                if not candidate or not intent.get('mission_id'):raise ValueError('Provider candidate and reviewed backlog mission required')
                review=current_review_contract(self.engine,state,backlog)
                state['review_contract']=review
                expected=expected_binding(state,backlog)
                proof=verify_attestation(verification_evidence.get('attestation'),expected,reviewer_registry(),now=self.clock())
                if proof['issued_at']<state['created_at']:raise ValueError('Independent run predates this job')
                if proof['execution']['test_count']<review['minimum_tests']:raise ValueError('Reviewed minimum test count not met')
                conn.execute('CREATE TABLE IF NOT EXISTS jules_accepted_receipts (receipt_id TEXT PRIMARY KEY,job_id TEXT NOT NULL UNIQUE,payload_json TEXT NOT NULL)')
                conn.execute('INSERT INTO jules_accepted_receipts VALUES(?,?,?)',(proof['receipt_id'],job_id,json.dumps(proof,sort_keys=True)))
                state.update(phase='completed',accepted=True,accepted_at=self.clock(),verification_type='independent_patch_test',evidence=proof,attestation=verification_evidence['attestation'],reason='Current approved external review contract and exact returned-patch verdict verified')
                if backlog.get('enabled') and backlog.get('status')=='waiting_external_review':
                    backlog.update(status='ready',reason='Independent patch review accepted; ready for normal mission advancement',revision=backlog['revision']+1)
                    conn.execute('UPDATE work_backlog SET state_json=? WHERE id=?',(json.dumps(backlog),backlog['id']))
                    state['backlog_woken_revision']=backlog['revision']

            except (ValueError,KeyError,TypeError,StopIteration,sqlite3.IntegrityError) as error:
                state.update(phase='review_required',accepted=False,reason='Independent exact-patch acceptance is missing or invalid',repair_diagnostics=type(error).__name__)
            self._save_job(conn,state);conn.commit()
            return state
