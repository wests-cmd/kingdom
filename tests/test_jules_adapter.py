import asyncio
import json
import os
import time
import unittest
import urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid5, NAMESPACE_URL

from fastapi.testclient import TestClient

from backend.integrations.jules import JulesService
from backend.integrations.jules_runner import JulesRunner
from backend.storage.db import Database
from backend.storage.repository import TaskRepository
from backend.runtime.work_backlog import WorkBacklog
from backend.runtime.missions import MissionService
from backend.runtime.tasks import TaskManager
from backend.runtime.project_tests import report
from backend.swarm.manager import execution_request
from backend.security.http_auth import owner_auth
import backend.runtime.computer_tools as computer_tools


class DummyEvents:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload):
        self.published.append((topic, payload))


class DummyEngine:
    def __init__(self, db, level=5):
        self.db = db
        self.level = level
        self.events = DummyEvents()
        self.tasks = TaskManager(TaskRepository(db))
        self.missions = MissionService(self, db)

    class ExecutionPolicy:
        def __init__(self, level):
            self._level = level

        def get(self):
            return {
                "level": self._level,
                "mission_budget": {
                    "max_steps": 10,
                    "max_parallel": 2,
                    "auto_advance": True,
                    "max_retries": 1,
                },
            }

    @property
    def execution_policy(self):
        return self.ExecutionPolicy(self.level)


class JulesAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "test_jules.db"
        self.secrets_root = self.root / "secrets"
        self.db = Database(self.db_path)
        self.engine = DummyEngine(self.db, level=5)
        self.clock_time = 1000.0
        self.service = JulesService(
            self.db,
            engine=self.engine,
            secrets_root=self.secrets_root,
            clock=lambda: self.clock_time,
        )

        self.backlog = WorkBacklog(
            self.db, engine=self.engine, clock=lambda: self.clock_time
        )
        self.backlog_item = self.backlog.register(
            project="kingdom",
            idempotency_key="task-123",
            title="Scoped feature task",
            description="Task to be assigned to Jules",
            enabled=False,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def enable_service(self):
        self.service.configure(api_key="test-secret-key-123", enabled=True)

    def dummy_opener(self, response_data, status_code=200):
        class DummyResp:
            def __init__(self, data, code):
                self._data = json.dumps(data).encode("utf-8")
                self.code = code

            def read(self, amt=None):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        class DummyOpener:
            def __init__(self):
                self.calls = []

            def open(self, req, timeout=30):
                self.calls.append(req)
                if status_code >= 400:
                    raise urllib.error.HTTPError(
                        req.full_url, status_code, "Error", {}, None
                    )
                return DummyResp(response_data, status_code)

        return DummyOpener()

    def test_secret_storage_key_separation(self):
        self.enable_service()
        key_file = self.secrets_root / "jules.key"
        self.assertTrue(key_file.exists())
        self.assertEqual(os.stat(key_file).st_mode & 0o777, 0o600)

        # Confirm vault_key is NOT in jules_settings data_json
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT data_json, secret FROM jules_settings WHERE id=1"
            ).fetchone()
        data_json = json.loads(row[0])
        self.assertNotIn("vault_key", data_json)
        self.assertNotIn("encrypted_key", data_json)
        self.assertIsNotNone(row[1])

        # Settings response never leaks secret bytes or key
        settings = self.service.settings()
        self.assertTrue(settings["has_credentials"])
        self.assertNotIn("api_key", settings)
        self.assertNotIn("vault_key", settings)

    def test_default_off_and_owner_authorization_required(self):
        settings = self.service.settings()
        self.assertFalse(settings["enabled"])
        self.assertFalse(settings["has_credentials"])

        restricted_engine = DummyEngine(self.db, level=4)
        restricted_service = JulesService(
            self.db, engine=restricted_engine, secrets_root=self.secrets_root
        )
        with self.assertRaises(ValueError):
            restricted_service.configure(api_key="key", enabled=True)

    def test_crash_during_submission_never_replays_post(self):
        self.enable_service()
        job = self.service.register_job(
            project="kingdom",
            backlog_id=self.backlog_item["id"],
            idempotency_key="idem-crash",
            source="sources/github/wests-cmd/kingdom",
            repository="wests-cmd/kingdom",
            revision="a" * 40,
            branch="feature/test",
            prompt="Implement bug fix",
        )

        failing_opener = self.dummy_opener({}, status_code=500)
        submitted = self.service.submit_job(job["id"], opener=failing_opener)

        self.assertEqual(submitted["phase"], "submission_unknown")
        self.assertIn("no automatic replay", submitted["reason"])

        with self.assertRaises(ValueError) as ctx:
            self.service.submit_job(job["id"], opener=failing_opener)
        self.assertIn("no automatic replay", str(ctx.exception))

    def test_allowlist_revocation_before_dispatch_cancels_job_without_network_call(self):
        """Protected regression test (1): Allowlist revocation before dispatch must NOT trigger HTTP requests."""
        self.enable_service()
        job = self.service.register_job(
            project="kingdom",
            backlog_id=self.backlog_item["id"],
            idempotency_key="idem-allowlist-revoke",
            source="sources/github/wests-cmd/kingdom",
            repository="wests-cmd/kingdom",
            revision="a" * 40,
            branch="feature/test",
            prompt="Implement feature",
        )

        # Revoke allowed_repositories before dispatching run_job
        self.service.configure(
            allowed_repositories=["other/repo"],
            allowed_sources=["sources/github/other/repo"],
        )

        opener = self.dummy_opener({"name": "sessions/sess-revoke"})
        res = self.service.run_job(job["id"], opener=opener)

        # Confirm 0 network calls were made to opener
        self.assertEqual(len(opener.calls), 0)
        self.assertEqual(res["phase"], "cancelled")
        self.assertIn("allowlist was revoked before dispatch", res["reason"])

    def test_level0_execution_policy_halts_dispatch_without_network_call(self):
        """Protected regression test (2): Policy level 0 must halt dispatch without sending POST."""
        self.enable_service()
        job = self.service.register_job(
            project="kingdom",
            backlog_id=self.backlog_item["id"],
            idempotency_key="idem-level0",
            source="sources/github/wests-cmd/kingdom",
            repository="wests-cmd/kingdom",
            revision="a" * 40,
            branch="feature/test",
            prompt="Implement feature",
        )

        # Set execution policy level to 0
        self.engine.level = 0

        opener = self.dummy_opener({"name": "sessions/sess-lvl0"})
        res = self.service.run_job(job["id"], opener=opener)

        # Confirm 0 network calls were made and job remains queued
        self.assertEqual(len(opener.calls), 0)
        self.assertEqual(res["phase"], "queued")

    def test_session_and_source_mismatch_are_rejected(self):
        self.enable_service()
        job = self.service.register_job(
            project="kingdom",
            backlog_id=self.backlog_item["id"],
            idempotency_key="idem-mismatch",
            source="sources/github/wests-cmd/kingdom",
            repository="wests-cmd/kingdom",
            revision="a" * 40,
            branch="feature/test",
            prompt="Implement feature",
        )

        opener = self.dummy_opener({"name": "sessions/sess-123", "state": "IN_PROGRESS"})
        self.service.submit_job(job["id"], opener=opener)

        mismatched_session_opener = self.dummy_opener(
            {"name": "sessions/sess-999", "state": "IN_PROGRESS"}
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.poll_job(job["id"], opener=mismatched_session_opener)
        self.assertIn("Jules session identity changed", str(ctx.exception))

        mismatched_source_opener = self.dummy_opener(
            {
                "name": "sessions/sess-123",
                "state": "IN_PROGRESS",
                "sourceContext": {"source": "sources/github/other/repo"},
            }
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.poll_job(job["id"], opener=mismatched_source_opener)
        self.assertIn("Jules source context changed", str(ctx.exception))

    def test_false_completion_true_boolean_without_mission_receipt_is_rejected(self):
        """Caller dictionary claiming tests_passed: True or accepted: True MUST be rejected."""
        self.enable_service()
        job = self.service.register_job(
            project="kingdom",
            backlog_id=self.backlog_item["id"],
            idempotency_key="idem-false-bool",
            source="sources/github/wests-cmd/kingdom",
            repository="wests-cmd/kingdom",
            revision="a" * 40,
            branch="feature/test",
            prompt="Implement feature",
        )

        self.service.submit_job(
            job["id"], opener=self.dummy_opener({"name": "sessions/sess-fb"})
        )
        self.service.poll_job(
            job["id"],
            opener=self.dummy_opener(
                {"name": "sessions/sess-fb", "state": "COMPLETED"}
            ),
        )

        # Attempting verification with caller dictionary {tests_passed: True} or {accepted: True}
        # WITHOUT a real Kingdom mission step receipt MUST fail!
        v1 = self.service.verify_job_completion(
            job["id"], {"tests_passed": True, "revision": "a" * 40}
        )
        self.assertFalse(v1["accepted"])
        self.assertEqual(v1["phase"], "review_required")

        v2 = self.service.verify_job_completion(
            job["id"], {"accepted": True, "revision": "a" * 40}
        )
        self.assertFalse(v2["accepted"])
        self.assertEqual(v2["phase"], "review_required")

        # Confirm backlog item was NEVER modified directly by JulesService!
        backlog_item = self.backlog.get("kingdom", self.backlog_item["id"])
        self.assertNotEqual(backlog_item["status"], "completed")

    def test_verification_with_unrelated_mission_or_mismatched_revision_is_rejected(self):
        """Protected regression test (3): Supplying unrelated mission or mismatched source revision must be REJECTED."""
        self.enable_service()

        job = self.service.register_job(
            project="kingdom",
            backlog_id=self.backlog_item["id"],
            idempotency_key="idem-mismatched-rev",
            source="sources/github/wests-cmd/kingdom",
            repository="wests-cmd/kingdom",
            revision="a" * 40,
            branch="feature/test",
            prompt="Implement feature",
        )

        self.service.submit_job(
            job["id"], opener=self.dummy_opener({"name": "sessions/sess-mm"})
        )
        self.service.poll_job(
            job["id"],
            opener=self.dummy_opener(
                {"name": "sessions/sess-mm", "state": "COMPLETED"}
            ),
        )

        # Supplying unrelated mission_id/version/step that differs from backlog item binding
        unrelated_res = self.service.verify_job_completion(
            job["id"],
            {
                "mission_id": "unrelated-mission-id",
                "mission_version": 1,
                "step_id": "step-1",
            },
        )
        self.assertFalse(unrelated_res["accepted"])
        self.assertEqual(unrelated_res["phase"], "review_required")

    def test_human_review_attestation_path(self):
        self.enable_service()
        job = self.service.register_job(
            project="kingdom",
            backlog_id=self.backlog_item["id"],
            idempotency_key="idem-human",
            source="sources/github/wests-cmd/kingdom",
            repository="wests-cmd/kingdom",
            revision="a" * 40,
            branch="feature/test",
            prompt="Implement feature",
        )

        self.service.submit_job(
            job["id"], opener=self.dummy_opener({"name": "sessions/sess-h"})
        )
        self.service.poll_job(
            job["id"],
            opener=self.dummy_opener(
                {"name": "sessions/sess-h", "state": "COMPLETED"}
            ),
        )

        # Neither an actor label nor human-review prose is a test attestation.
        for actor in ['unauthorized','owner']:
            res=self.service.verify_job_completion(job['id'],{'verification_type':'human_attestation','actor':actor,'notes':'Reviewed manually'})
            self.assertFalse(res['accepted'])
            self.assertEqual(res['phase'],'review_required')

    def test_true_verification_via_validated_acceptance_mission_receipt(self):
        self.enable_service()

        mission_id = "mission-jules-1"
        rev = "a" * 40
        mission_plan = {
            "title": "Verify Jules Patch",
            "objective": "Verify Jules engineering handoff candidate",
            "deliverables": ["verified test report"],
            "missing_requirements": [],
            "steps": [
                {
                    "id": "step-1",
                    "kind": "project_test",
                    "title": "Run unit tests",
                    "instructions": "Run unit tests",
                    "acceptance": "All tests pass",
                    "argv": ["python3", "-m", "pytest"],
                    "project_test": {
                        "project": "kingdom",
                        "source_revision": rev,
                        "runner": "pytest",
                        "minimum_tests": 1,
                    },
                }
            ],
        }

        mission_key = f"{mission_id}:1:step-1"
        task_id = str(uuid5(NAMESPACE_URL, "kingdom-mission:" + mission_key))

        with self.db.get_connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS missions (
                id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL
            )"""
            )
            mission_data = {
                "id": mission_id,
                "version": 1,
                "approved_version": 1,
                "status": "running",
                "plan": mission_plan,
                "steps": {
                    "step-1": {
                        "task_id": task_id,
                    }
                },
            }
            conn.execute(
                "INSERT INTO missions VALUES(?,?)",
                (mission_id, json.dumps(mission_data)),
            )
            conn.commit()

        output = {
            "exit_code": 0,
            "output_truncated": False,
            "output": "============================== 10 passed in 0.50s ==============================",
        }
        task_meta = {
            "tool": "process.run@1.0.0",
            "capability": "process.execute",
            "mission_id": mission_id,
            "mission_version": 1,
            "step_id": "step-1",
            "_mission_step_key": mission_key,
            "project_test": {
                "project": "kingdom",
                "source_revision": rev,
                "runner": "pytest",
                "minimum_tests": 1,
            },
            "max_attempts": 1,
            "tool_parameters": {"argv": ["python3", "-m", "pytest"]},
        }

        created_task = self.engine.tasks.create("Run unit tests", metadata=task_meta)
        self.assertEqual(created_task["id"], task_id)

        req_task = execution_request(created_task, "Run unit tests")
        receipt_meta = computer_tools.receipt(req_task, output)

        outcome = {
            "kind": "native_tool",
            "tool": "process.run@1.0.0",
            "output": output,
            "artifact": receipt_meta["artifact"],
            "sha256": receipt_meta["sha256"],
        }

        task_result = {
            "executed_by": "coder",
            "results": [
                {
                    "status": "completed",
                    "verification": {"state": "VERIFIED"},
                    "artifact": receipt_meta["artifact"],
                    "sha256": receipt_meta["sha256"],
                    "knight": "coder",
                    "outcome": outcome,
                }
            ],
            "plan": {
                "task_id": task_id,
                "subtasks": [{"prompt": "Run unit tests", "knight": "coder"}],
            },
        }

        self.engine.tasks.transition_task(task_id, "RUNNING")
        self.engine.tasks.complete(task_id, task_result)

        saved_task = self.engine.tasks.get(task_id)
        report_res = report(saved_task)
        self.assertTrue(report_res["tests_passed"], f"Report failed: {report_res}")

        # Register backlog item linked to mission
        backlog_item = self.backlog.register(
            project="kingdom",
            idempotency_key="task-mission-1",
            mission_id=mission_id,
            mission_version=1,
            acceptance_step="step-1",
            title="Mission bound backlog task",
            enabled=False,
        )

        job = self.service.register_job(
            project="kingdom",
            backlog_id=backlog_item["id"],
            idempotency_key="idem-mission-job",
            source="sources/github/wests-cmd/kingdom",
            repository="wests-cmd/kingdom",
            revision="a" * 40,
            branch="feature/test",
            prompt="Implement feature",
        )

        self.service.submit_job(
            job["id"], opener=self.dummy_opener({"name": "sessions/sess-m1"})
        )
        self.service.poll_job(
            job["id"],
            opener=self.dummy_opener(
                {"name": "sessions/sess-m1", "state": "COMPLETED"}
            ),
        )

        # Verify that backlog is completed when backlog tick runs (via reviewed advancement)
        self.backlog.settings(enabled=True, expected_revision=1)
        self.backlog.configure(
            project="kingdom",
            ident=backlog_item["id"],
            enabled=True,
            expected_revision=backlog_item["revision"],
        )
        self.service.engine.status = lambda: {"running": True}

        waiting=self.backlog.tick()
        self.assertNotEqual(waiting['status'],'completed','Old native test receipt must not complete a delegated patch job')

        # The canonical mission receipt above proves the reviewed command, not
        # the tested checkout. Add a provider-retained patch and a signed runner
        # fixture. Signing here is a unit-test seam, not a production test claim.
        import base64,hashlib
        from unittest.mock import patch
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from backend.runtime.patch_acceptance import canonical
        candidate_patch='diff --git a/example.py b/example.py\n'
        self.service.fetch_candidate(job['id'],opener=self.dummy_opener({'activities':[{'createTime':'2026-10-26','artifacts':[{'changeSet':{'source':job['source'],'gitPatch':{'baseCommitId':rev,'unidiffPatch':candidate_patch}}}]}]}))
        binding=dict(job_id=job['id'],project='kingdom',backlog_id=backlog_item['id'],mission_id=mission_id,mission_version=1,step_id='step-1',source=job['source'],base_revision=rev,patch_sha256=hashlib.sha256(candidate_patch.encode()).hexdigest())
        key=Ed25519PrivateKey.generate()
        payload=dict(format='kingdom.patch-test.v1',receipt_id='adapter-positive-test',reviewer_id='test-gate',issued_at=1000,expires_at=1200,binding=binding,execution=dict(run_id='test-run',image_sha256='c'*64,source_archive_sha256='d'*64,candidate_tree_sha256='e'*64,argv=['python3','-m','pytest'],test_count=10,failed_count=0,exit_code=0,network_isolated=True,read_only_source=True))
        attestation={'payload':payload,'signature':base64.b64encode(key.sign(canonical(payload))).decode()}
        reviewer={'test-gate':dict(public_key=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode(),enabled=True,projects=['kingdom'],sources=[job['source']])}
        trusted=patch('backend.runtime.patch_acceptance.reviewer_registry',return_value=reviewer)
        trusted.start();self.addCleanup(trusted.stop)
        verified=self.service.verify_job_completion(job['id'],{'attestation':attestation})
        self.assertTrue(
            verified["accepted"],
            f"Reason: {verified.get('reason')}, Diag: {verified.get('repair_diagnostics')}",
        )
        self.assertEqual(verified["phase"], "completed")
        self.assertEqual(verified["verification_type"], "independent_patch_test")

        tick_res = self.backlog.tick()
        self.assertEqual(tick_res["status"], "completed")

    def test_jules_runner_event_publishing_and_execution(self):
        """Test supervised JulesRunner background execution and event publishing."""
        self.enable_service()

        class ErrorService:
            def tick(self):
                raise RuntimeError("Provider connection reset")

        events = DummyEvents()
        runner = JulesRunner(lambda: ErrorService(), events.publish, interval=0.1)

        async def run_test():
            await runner.start()
            await asyncio.sleep(0.2)
            await runner.stop()

        asyncio.run(run_test())

        # Verify jules.runner_error event was published
        error_events = [e for e in events.published if e[0] == "jules.runner_error"]
        self.assertGreater(len(error_events), 0)
        self.assertEqual("RuntimeError", error_events[0][1]["error_type"])
        self.assertNotIn("Provider connection reset",str(error_events))

    def test_cross_instance_claim_and_cancel_during_post(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        self.enable_service()
        job=self.service.register_job(project='kingdom',backlog_id=self.backlog_item['id'],idempotency_key='cross-instance',source='sources/github/wests-cmd/kingdom',repository='wests-cmd/kingdom',revision='a'*40,branch='feature/test',prompt='Bounded test')
        second=JulesService(self.db,engine=self.engine,secrets_root=self.secrets_root,clock=lambda:self.clock_time)
        entered=threading.Event();release=threading.Event();calls=[]
        response=self.dummy_opener({'name':'sessions/cross-instance'})
        class BlockingOpener:
            def open(inner,*args,**kwargs):
                calls.append(1);entered.set()
                if not release.wait(10):raise TimeoutError('Test release did not arrive')
                return response.open(*args,**kwargs)
        with ThreadPoolExecutor(max_workers=1) as pool:
            submitted=pool.submit(self.service.submit_job,job['id'],BlockingOpener())
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(ValueError):second.submit_job(job['id'],BlockingOpener())
                second.cancel_job(job['id'])
            finally:release.set()
            result=submitted.result(timeout=10)
        self.assertEqual(len(calls),1)
        self.assertEqual(result['phase'],'cancelled')
        self.assertEqual(result['session'],'sessions/cross-instance')
        self.assertIn('remote',result['reason'].lower())

    def test_same_idempotency_key_cannot_change_backlog_or_prompt(self):
        self.enable_service()
        args=dict(project='kingdom',backlog_id=self.backlog_item['id'],idempotency_key='exact-intent',source='sources/github/wests-cmd/kingdom',repository='wests-cmd/kingdom',revision='a'*40,branch='feature/test',prompt='Original task')
        job=self.service.register_job(**args)
        self.assertEqual(self.service.register_job(**args)['id'],job['id'])
        for name,value in [('prompt','Different task'),('backlog_id','other-backlog'),('branch','other-branch'),('max_repair_budget',1)]:
            with self.assertRaises(ValueError):self.service.register_job(**{**args,name:value})
        self.clock_time=job['deadline_at']+1
        opener=self.dummy_opener({'name':'sessions/too-late'})
        with self.assertRaises(ValueError):self.service.submit_job(job['id'],opener=opener)

    def test_api_endpoints_integration(self):
        from backend.main import app
        from unittest.mock import patch
        headers={'Authorization':f'Bearer {owner_auth.token}','X-Kingdom-Request':'1'}
        # Never change the application's real/global integration configuration.
        with patch('backend.integrations.jules_api.service',return_value=self.service):
            client=TestClient(app)
            self.assertIn(client.get('/integrations/jules/settings').status_code,[401,403,503])
            r1=client.get('/integrations/jules/settings',headers=headers)
            self.assertEqual(r1.status_code,200)
            self.assertFalse(r1.json()['enabled'])
            r2=client.put('/integrations/jules/settings',json={'enabled':True,'api_key':'api-key-test-12345','allowed_repositories':['wests-cmd/kingdom'],'allowed_sources':['sources/github/wests-cmd/kingdom']},headers=headers)
            self.assertEqual(r2.status_code,200)
            self.assertTrue(r2.json()['enabled'])
            self.assertTrue(r2.json()['has_credentials'])
            self.assertNotIn('api-key-test-12345',r2.text)


if __name__ == "__main__":
    unittest.main()
