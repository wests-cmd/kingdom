## 2025-02-23 - Strict Actor Binding in ZeroTrust Approval Validation
**Vulnerability:** Approval IDs issued during high-risk action checks could be submitted by any actor or node to gain authorization in `ZeroTrust.authorize` because requesting actor matching was not enforced.
**Learning:** Human-in-the-loop approval workflows must validate not only approval status and capability scope, but also bound actor/node identity.
**Prevention:** Always verify that `approval_req["requesting_actor"] == actor_id` or `approval_req["requesting_node"] == actor_id` before honoring pre-approved decisions.

## 2025-02-23 - Robust Prompt Inspection Type Safety
**Vulnerability:** Calling `lowered = content.lower()` in `InjectionDetector` raised an unhandled `AttributeError` when non-string or `None` values were supplied, leading to runtime unhandled exceptions.
**Learning:** Security firewalls must defensively handle non-string inputs before invoking string manipulation methods.
**Prevention:** Always check for `None` and convert non-string types prior to inspection in prompt firewalls.
