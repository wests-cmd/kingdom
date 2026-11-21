"""Regression for the secondary scoped authorization helper.

This exercises durable ApprovalEngine consumption. It does NOT prove RPC identity
binding, OS permission enforcement, or installed-multi-node acceptance.
"""
import tempfile
import unittest
from pathlib import Path

from backend.security.approval_engine import ApprovalEngine
from backend.security.identity_fabric import IdentityFabric, IdentityType
from backend.security.scoped_authorization import (
    AuthorizationRequest, ScopedAuthorizationEngine,
)
from backend.storage.db import Database


class ScopedAuthorizationProofTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.approvals = ApprovalEngine(database=Database(Path(tmp.name) / "approvals.sqlite"))
        self.fabric = IdentityFabric()
        self.actor = self.fabric.register_identity(
            IdentityType.KNIGHT, "Approved worker",
            capabilities=["filesystem.delete", "filesystem.read"],
            trust_level="TRUSTED",
        )
        self.fabric.activate_identity(self.actor.identity_id)

    def request(self, **changes):
        data = dict(
            actor_identity_id=self.actor.identity_id,
            capability="filesystem.delete",
            operation="Delete one reviewed temporary file",
            resource="scratch/approved.txt",
            context={"approved_by_commander": True},
        )
        data.update(changes)
        return AuthorizationRequest(**data)

    def approve_exact(self, *, resource="scratch/approved.txt", data_scope="general"):
        created = self.approvals.create_request(
            capability="filesystem.delete",
            operation="Delete one reviewed temporary file",
            requesting_actor=self.actor.identity_id,
            parameters={"resource": resource, "data_scope": data_scope},
            ttl_seconds=120,
        )
        self.approvals.approve(created["id"], approver="owner")
        return created["id"]

    def test_forged_claim_and_numeric_level_cannot_self_authorize(self):
        for level in (1, 3, 4, 5, 999):
            with self.subTest(level=level):
                result = ScopedAuthorizationEngine(self.fabric, self.approvals).evaluate_authorization(
                    self.request(), required_governance_level=level)
                self.assertFalse(result.allowed)
                self.assertTrue(result.requires_human_approval)

    def test_missing_store_denies_even_with_approval_pointer(self):
        approval_id = self.approve_exact()
        request = self.request(context={"approval_id": approval_id, "approved_by_commander": True})
        self.assertFalse(ScopedAuthorizationEngine(self.fabric).evaluate_authorization(
            request, required_governance_level=5).allowed)

    def test_exact_persisted_approval_is_consumed_once_even_at_level_three(self):
        approval_id = self.approve_exact()
        request = self.request(context={"approval_id": approval_id, "approved_by_commander": True})
        engine = ScopedAuthorizationEngine(self.fabric, self.approvals)
        self.assertTrue(engine.evaluate_authorization(
            request, required_governance_level=3).allowed)
        self.assertEqual(self.approvals.get_request(approval_id)["status"], "consumed")
        self.assertFalse(engine.evaluate_authorization(
            request, required_governance_level=5).allowed)

    def test_mismatched_operation_actor_resource_and_scope_do_not_spend_approval(self):
        approval_id = self.approve_exact()
        engine = ScopedAuthorizationEngine(self.fabric, self.approvals)
        other = self.fabric.register_identity(
            IdentityType.KNIGHT, "Another worker",
            capabilities=["filesystem.delete"], trust_level="TRUSTED")
        self.fabric.activate_identity(other.identity_id)
        for changes in (
            {"operation": "Delete every file"},
            {"resource": "private/owner-token"},
            {"data_scope": "restricted"},
            {"actor_identity_id": other.identity_id},
        ):
            with self.subTest(changes=changes):
                req = self.request(context={"approval_id": approval_id}, **changes)
                self.assertFalse(engine.evaluate_authorization(req).allowed)
                self.assertEqual(self.approvals.get_request(approval_id)["status"], "approved")
        self.assertTrue(engine.evaluate_authorization(
            self.request(context={"approval_id": approval_id})).allowed)

    def test_scope_denial_does_not_spend_approval(self):
        approval_id = self.approve_exact(data_scope="finance")
        self.actor.trust_level = "UNVERIFIED"
        request = self.request(data_scope="finance",
            context={"approval_id": approval_id, "restricted_data_scopes": ["finance"]})
        engine = ScopedAuthorizationEngine(self.fabric, self.approvals)
        self.assertFalse(engine.evaluate_authorization(request).allowed)
        self.assertEqual(self.approvals.get_request(approval_id)["status"], "approved")
        self.actor.trust_level = "TRUSTED"
        self.assertTrue(engine.evaluate_authorization(request).allowed)

    def test_expired_approval_is_rejected(self):
        approval_id = self.approve_exact()
        record = self.approvals.get_request(approval_id)
        record["expires_at"] = "2000-01-01T00:00:00+00:00"
        self.approvals._save(record)
        engine = ScopedAuthorizationEngine(self.fabric, self.approvals)
        self.assertFalse(engine.evaluate_authorization(
            self.request(context={"approval_id": approval_id})).allowed)

    def test_revoked_identity_denied_without_spending_approval(self):
        approval_id = self.approve_exact()
        engine = ScopedAuthorizationEngine(self.fabric, self.approvals)
        self.fabric.revoke_identity(self.actor.identity_id, "Owner revocation")
        result = engine.evaluate_authorization(
            self.request(context={"approval_id": approval_id}))
        self.assertFalse(result.allowed)
        self.assertEqual(self.approvals.get_request(approval_id)["status"], "approved")

    def test_storage_failure_denies(self):
        class BrokenApprovals:
            def consume(self, *args, **kwargs):
                raise OSError("approval database unavailable")

        engine = ScopedAuthorizationEngine(self.fabric, BrokenApprovals())
        self.assertFalse(engine.evaluate_authorization(
            self.request(context={"approval_id": "appr_unavailable"})).allowed)

    def test_low_risk_read_remains_available_without_approval(self):
        engine = ScopedAuthorizationEngine(self.fabric)
        result = engine.evaluate_authorization(self.request(
            capability="filesystem.read", operation="Read reviewed log",
            resource="logs/current.txt", context={}))
        self.assertTrue(result.allowed)
        self.assertFalse(result.requires_human_approval)


if __name__ == "__main__":
    unittest.main()
