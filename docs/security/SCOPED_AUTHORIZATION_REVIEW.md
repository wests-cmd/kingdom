# Scoped authorization: review-required policy change

This PR is intentionally separated from Kingdom's fail-closed supply-chain checks.
It changes the legacy, secondary ScopedAuthorizationEngine so arbitrary request
metadata cannot stand in for HUMAN authorization.

Prior behavior: high-risk request was permitted when caller supplied
`context["approved_by_commander"] = True` or numeric governance level >=4,
even if no stored owner approval had been verified.

Proposed behavior: high-risk request always needs a trusted host-supplied
`approval_validator(AuthorizationRequest) -> bool` AND level >=4, and the
validator must verify an independently stored, precise actor/capability/operation/
resource approval. Missing validator or exception denies. Low-risk reads remain
unchanged. The callback is a seam to the EXISTING ApprovalEngine only, not an
independent new store. The host must not populate it from model/task output.

**Review block:** confirm all actual callers of this secondary class, prove the
integration with existing owner-authorized approval records before enabling
high-risk use, and run negative tests on direct/remote effects. This source-only
patch does not prove any joined-node permission behavior. No autonomous merge
or production deployment is authorized by this branch.
