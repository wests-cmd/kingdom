# Scoped authorization: review-required trust-boundary change

This draft hardens the **secondary** `ScopedAuthorizationEngine` without replacing
Kingdom's production `ZeroTrust`/execution policy or inventing a second approval
database. It is not itself authorization for production rollout.

## Problem and change

Previously a high-risk request could pass by providing
`context["approved_by_commander"] = True` or choosing a numeric governance
level >= 4. Neither establishes actual authenticated owner approval.

The secondary helper now accepts only the **existing durable**
`ApprovalEngine` supplied by trusted host code. For high-risk requests it
atomically consumes one stored, unexpired approval matching **all** of:

- authenticated actor identity ID;
- capability and operation;
- exact `parameters = {"resource": request.resource, "data_scope": request.data_scope}`.

The untrusted `approval_id` in request context is only a lookup handle. It is
not proof; the database's exact record and one-time consume are proof of the
reviewed authorization. Missing approval, no approval engine, revoked/unknown
identity, mismatch, reuse, expiration or storage failure all deny. A numeric
`required_governance_level` and `approved_by_commander` do not override this
requirement. Restricted-scope checks run **before** consuming an approval.

An exact human approval can authorize at any level in this secondary helper;
the runtime's distinct authenticated **level 5 standing owner authorization**
continues through `ZeroTrust`/the owner's persisted `ExecutionPolicy`. This
helper does not mint, infer or override that standing authorization.

## Review and verification limits

- Source regression covers forged claims, levels, exact persistent approval,
  single consumption, operation/resource/actor/scope drift, expiration,
  revocation, unavailable approval storage, and low-risk reads in
  `tests/test_scoped_authorization_proof.py`.
- The code does **not** independently authenticate the transport actor;
  the caller must bind `actor_identity_id` to an authenticated OS/RPC identity.
  Do not pass arbitrary model or network values as identity or policy input.
- Audit every actual constructor/caller and any data-scope policy caller before
  promotion. This secondary helper is **not** the installed RPC execution path.
  Passing source tests and CI does not show the remote effect path enforces it.
- Do not merge until independently verifying real controller/worker high-risk
  execution, positive approved actions, false-approval rejection, replay,
  revocation/restart, and existing standing-owner policy behavior.
- Issue #172's eight installed-system security commissioning gates remain
  separate and unverified until supported by real-machine evidence.

Do not auto-merge this draft, bypass repository review, or claim it fixes every
authorization path. Treat this as a candidate hardening change only.
