"""Negative-fence regression: an agent cannot declare its own high-risk approval.

This tests the secondary ScopedAuthorizationEngine helper, NOT all Kingdom
effect-producing RPC paths or the installed multi-node authorization boundary.
"""
import unittest
from backend.security.identity_fabric import IdentityFabric, IdentityType
from backend.security.scoped_authorization import (
    AuthorizationRequest, ScopedAuthorizationEngine,
)


class ScopedAuthorizationProofTests(unittest.TestCase):
    def setUp(self):
        self.fabric = IdentityFabric()
        self.actor = self.fabric.register_identity(
            IdentityType.KNIGHT, "Unprivileged worker",
            capabilities=["filesystem.delete", "filesystem.read"],
            trust_level="TRUSTED",
        )
        self.fabric.activate_identity(self.actor.identity_id)

    def request(self, **changes):
        data = dict(actor_identity_id=self.actor.identity_id,
                    capability="filesystem.delete",
                    operation="Delete one reviewed temporary file",
                    resource="scratch/approved.txt",
                    context={"approved_by_commander": True})
        data.update(changes)
        return AuthorizationRequest(**data)

    def test_untrusted_approval_claim_does_not_grant_high_risk_at_any_level(self):
        engine = ScopedAuthorizationEngine(self.fabric)
        for level in (1, 3, 4, 5):
            with self.subTest(level=level):
                decision = engine.evaluate_authorization(self.request(), required_governance_level=level)
                self.assertFalse(decision.allowed)
                self.assertTrue(decision.requires_human_approval)

    def test_only_exact_host_verified_scope_succeeds(self):
        original = self.request()
        key = (original.actor_identity_id, original.capability,
               original.operation, original.resource)
        def verifier(req):
            return (req.actor_identity_id, req.capability, req.operation, req.resource) == key
        engine = ScopedAuthorizationEngine(self.fabric, approval_validator=verifier)
        self.assertTrue(engine.evaluate_authorization(original, required_governance_level=4).allowed)
        self.assertFalse(engine.evaluate_authorization(
            self.request(operation="Delete everything"), required_governance_level=5).allowed)
        self.assertFalse(engine.evaluate_authorization(
            self.request(resource="private/owner-token"), required_governance_level=5).allowed)
        self.assertFalse(engine.evaluate_authorization(original, required_governance_level=3).allowed)

    def test_verifier_error_fails_closed(self):
        def unavailable(req):
            raise OSError("Approval database unavailable")
        engine = ScopedAuthorizationEngine(self.fabric, approval_validator=unavailable)
        self.assertFalse(engine.evaluate_authorization(
            self.request(), required_governance_level=5).allowed)

    def test_revoked_identity_denied_even_if_verifier_accepts(self):
        engine = ScopedAuthorizationEngine(self.fabric, approval_validator=lambda _: True)
        self.fabric.revoke_identity(self.actor.identity_id, "Device revoked")
        self.assertFalse(engine.evaluate_authorization(
            self.request(), required_governance_level=5).allowed)

    def test_low_risk_read_remains_available(self):
        engine = ScopedAuthorizationEngine(self.fabric)
        result = engine.evaluate_authorization(self.request(
            capability="filesystem.read", operation="Read reviewed log",
            resource="logs/current.txt", context={}))
        self.assertTrue(result.allowed)
        self.assertFalse(result.requires_human_approval)


if __name__ == "__main__":
    unittest.main()
