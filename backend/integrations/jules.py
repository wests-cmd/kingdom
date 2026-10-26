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
import time
import urllib.error
import urllib.request
import uuid

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

    def _save_job(self, conn, state):
        state["updated_at"] = self.clock()
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
                if (
                    saved["source"] != source
                    or saved["repository"] != repository
                    or saved["revision"] != revision
                ):
                    raise ValueError(
                        "Idempotency key belongs to a job with different parameters"
                    )
                return saved

            # Check backlog ID binding
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='work_backlog'"
            ).fetchone():
                backlog_row = conn.execute(
                    "SELECT state_json FROM work_backlog WHERE project=? AND id=?",
                    (project, backlog_id),
                ).fetchone()
                if not backlog_row:
                    raise ValueError(
                        f"Backlog item {backlog_id} not found in project {project}"
                    )

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
        if not re.fullmatch(r"sessions(?:/[A-Za-z0-9_-]+)?", path):
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
            data = resp.read(262145)
        if len(data) > 262144:
            raise ValueError("Bounded Jules response size exceeded")
        return json.loads(data.decode("utf-8"))

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
                and self.engine.execution_policy.get()["level"] == 0
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

            # Atomic cross-instance SQLite claiming
            now = self.clock()
            with self.db.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                rowcount = conn.execute(
                    """UPDATE jules_jobs
                       SET state_json = json_set(state_json, '$.phase', 'submitting', '$.reason', 'POST request dispatched to Jules API', '$.updated_at', ?)
                       WHERE id = ? AND json_extract(state_json, '$.phase') = 'queued'""",
                    (now, job_id),
                ).rowcount
                conn.commit()

            if rowcount != 1:
                # Another process instance claimed or submitted the job concurrently
                return self.get_job(job_id)

            state = self.get_job(job_id)

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
                    state.update(
                        phase="watching",
                        session=session_name,
                        session_url=session_url,
                        remote_state=reply.get("state", "QUEUED"),
                        reason="Jules session created; watching progress",
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
                        phase="submission_unknown",
                        reason="Submission outcome needs reconciliation; no automatic replay",
                        http_status=status_code,
                    )
                    self._save_job(conn, state)
                    conn.commit()
            return state

    def poll_job(self, job_id, opener=None):
        with self._lock:
            state = self.get_job(job_id)
            if state["phase"] != "watching":
                return state

            # Live execution policy / runtime level check prior to polling
            if (
                self.engine
                and hasattr(self.engine, "execution_policy")
                and self.engine.execution_policy.get()["level"] == 0
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

                with self.db.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    state.update(
                        phase=phase,
                        remote_state=remote_state,
                        consecutive_errors=0,
                        backoff_until=0,
                        reason=reason,
                    )
                    self._save_job(conn, state)
                    conn.commit()
            except urllib.error.HTTPError as error:
                if error.code in {429, 503}:
                    err_count = state.get("consecutive_errors", 0) + 1
                    delay = min(300, 15 * (2 ** min(err_count, 4)))
                    with self.db.get_connection() as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        state.update(
                            consecutive_errors=err_count,
                            backoff_until=now + delay,
                            reason=f"Provider quota or transient backoff (HTTP {error.code})",
                        )
                        self._save_job(conn, state)
                        conn.commit()
                else:
                    raise
            return state

    def run_job(self, job_id, opener=None):
        state = self.get_job(job_id)
        if state["phase"] in TERMINAL_PHASES:
            return state

        # Live policy check
        if (
            self.engine
            and hasattr(self.engine, "execution_policy")
            and self.engine.execution_policy.get()["level"] == 0
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
            and self.engine.execution_policy.get()["level"] == 0
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
            except Exception:
                pass
        return {"status": "ok", "processed": processed}

    def cancel_job(self, job_id, reason="Cancelled by owner"):
        with self._lock:
            state = self.get_job(job_id)
            if state["phase"] in {"completed", "failed"}:
                return state

            if state["phase"] in {"queued", "submitting"}:
                new_phase = "cancelled"
                new_reason = reason
            elif state["phase"] == "watching":
                new_phase = "cancelled"
                new_reason = (
                    "Local observation cancelled; remote work was not cancelled"
                )
            else:
                new_phase = "cancelled"
                new_reason = reason

            with self.db.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                state.update(phase=new_phase, reason=new_reason)
                self._save_job(conn, state)
                conn.commit()
            return state

    def verify_job_completion(self, job_id, verification_evidence):
        """Independent Verification Gate for returned Jules work.

        Model prose, markdown comments, or claims of test passes are untrusted.
        Completion requires a separate source/artifact-bound receipt proving
        passing execution of independent tests via Kingdom's mission acceptance
        machinery, OR an explicit human owner attestation path (attesting human review
        without claiming test pass receipt).
        """
        with self._lock:
            state = self.get_job(job_id)
            if state["phase"] not in {
                "awaiting_independent_review",
                "paused",
                "review_required",
            }:
                raise ValueError(
                    f"Job in phase '{state['phase']}' cannot undergo independent verification"
                )

            if not isinstance(verification_evidence, dict):
                raise ValueError(
                    "Verification evidence must be a structured dictionary"
                )

            receipt = None
            verification_error = None
            is_human_attestation = (
                verification_evidence.get("verification_type") == "human_attestation"
                or verification_evidence.get("human_attestation") is True
            )

            if is_human_attestation:
                if verification_evidence.get("actor") != "owner":
                    raise ValueError(
                        "Human review attestation requires authenticated owner identity"
                    )
                receipt = {
                    "verification_type": "human_attestation",
                    "actor": "owner",
                    "notes": clean_text(
                        str(verification_evidence.get("notes", "Owner human review attestation"))
                    )[:2000],
                    "accepted": True,
                }
            else:
                # Retrieve registered backlog item to enforce strict binding
                backlog_binding = None
                with self.db.get_connection() as conn:
                    if conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='work_backlog'"
                    ).fetchone():
                        row = conn.execute(
                            "SELECT state_json FROM work_backlog WHERE project=? AND id=?",
                            (state["project"], state["backlog_id"]),
                        ).fetchone()
                        if row:
                            backlog_binding = json.loads(row[0]).get("intent", {})

                if not backlog_binding or not backlog_binding.get("mission_id"):
                    verification_error = "Registered backlog item has no executable mission binding"
                    receipt = None
                else:
                    b_mission_id = backlog_binding["mission_id"]
                    b_version = backlog_binding["mission_version"]
                    b_step_id = backlog_binding["acceptance_step"]

                    # Check that evidence matches registered backlog mission binding
                    ev_mission = verification_evidence.get("mission_id")
                    ev_version = verification_evidence.get("mission_version", verification_evidence.get("version"))
                    ev_step = verification_evidence.get("step_id", verification_evidence.get("acceptance_step"))

                    if ev_mission and ev_mission != b_mission_id:
                        verification_error = f"Verification mission_id ({ev_mission}) does not match backlog mission binding ({b_mission_id})"
                    elif ev_version and ev_version != b_version:
                        verification_error = f"Verification mission_version ({ev_version}) does not match backlog mission binding ({b_version})"
                    elif ev_step and ev_step != b_step_id:
                        verification_error = f"Verification acceptance_step ({ev_step}) does not match backlog mission binding ({b_step_id})"
                    else:
                        try:
                            from backend.runtime.mission_acceptance import validated_acceptance
                            if not self.engine:
                                raise ValueError("Runtime engine unavailable for mission acceptance")
                            receipt = validated_acceptance(self.engine, b_mission_id, b_version, b_step_id)
                            # Verify source revision & artifact binding against job's revision
                            task = self.engine.tasks.get(receipt.get("task_id", ""))
                            task_rev = (task or {}).get("metadata", {}).get("project_test", {}).get("source_revision")
                            if task_rev and task_rev != state["revision"]:
                                receipt = None
                                verification_error = f"Task receipt source revision ({task_rev}) does not match job revision ({state['revision']})"
                        except Exception as error:
                            verification_error = str(error)
                            receipt = None

            passed = receipt is not None and receipt.get("accepted") is True
            evidence_revision = verification_evidence.get("revision")
            if (
                evidence_revision
                and evidence_revision != state["revision"]
                and not is_human_attestation
            ):
                passed = False
                verification_error = "Verification evidence revision mismatch with job source"

            with self.db.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if passed:
                    state.update(
                        phase="completed",
                        accepted=True,
                        verification_type=receipt.get("verification_type", "validated_acceptance"),
                        reason=(
                            "Owner attested human review; not verified test receipt"
                            if is_human_attestation
                            else "Independent verification gate passed with verified mission task receipt"
                        ),
                        evidence=receipt,
                    )
                    self._save_job(conn, state)
                else:
                    attempts = state.get("repair_attempts", 0) + 1
                    max_budget = state.get("max_repair_budget", 3)
                    diagnostics = clean_text(
                        str(
                            verification_evidence.get(
                                "diagnostics",
                                verification_error or "Independent test verification failed or missing task receipt",
                            )
                        )
                    )[:2000]

                    if attempts <= max_budget:
                        state.update(
                            phase="review_required",
                            repair_attempts=attempts,
                            repair_diagnostics=diagnostics,
                            reason=f"Independent verification failed ({diagnostics}); candidate returned with diagnostics (attempt {attempts}/{max_budget})",
                        )
                    else:
                        state.update(
                            phase="failed",
                            repair_attempts=attempts,
                            repair_diagnostics=diagnostics,
                            reason=f"Independent verification failed and repair budget ({max_budget}) exhausted: {diagnostics}",
                        )
                    self._save_job(conn, state)
                conn.commit()
            return state
