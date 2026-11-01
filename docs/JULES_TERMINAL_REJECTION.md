# Exact returned-candidate rejection and terminal reconciliation

Owner rejection is a negative decision, not independent test acceptance. A candidate that does not implement its assignment must not be marked passed merely to release the coding admission slot.

## Owner API

`POST /integrations/jules/jobs/{id}/reject-candidate` requires normal owner authentication and these strict fields:

- `expected_job_binding`: job_id, project, backlog_id, repository, source, base_revision, branch, session and patch_sha256, copied from the current retained job/candidate.
- `expected_record_version`: the current job record version.
- `reason`: `outcome_not_implemented`, `outside_assignment_scope`, or `owner_rejected`.

Extra authority fields are rejected. The service verifies the retained provider patch bytes against the expected digest, then independently reads the existing bound provider session. The response must explicitly match session and source and report `COMPLETED`. Missing source, unknown/active states, provider failure or changed job bindings cannot release the slot.

This endpoint performs only a GET through the existing enabled provider adapter and unchanged repository/source allowlists. It never sends a message, assumes remote cancellation, creates another session, installs a grant, or extends the job deadline. An explicit owner can reject and reconcile an exact completed candidate after its old execution/review window ends, including at autonomy zero; that is local negative control plus a read-only terminal observation, not renewed execution authority.

Only retained candidates in review, locally cancelled, or expired states are eligible. In-flight/uncertain repair sends and scope reminders remain held even if a current provider GET reports completion: an older unconfirmed POST might still take effect. Submit/repair-in-flight states are not eligible.

After the GET, the original record version and full binding are rechecked atomically. A concurrent cancellation, repair or candidate change wins rather than being overwritten. Successful rejection stores a durable `jules_candidate_rejections` audit row and `rejection` evidence on the job, sets `phase=rejected` and `accepted=false`, and publishes a bounded `jules.candidate_rejected` event. Raw provider replies, messages, credentials and job contents are not copied into the rejection audit; only matched observation fields and a response digest are retained.

An identical request is idempotent and performs no second provider call. Rejected jobs remain terminal under cancel/run/late repair callbacks. The backlog queue releases a rejected slot only when the exact job/candidate evidence matches its atomically retained rejection audit row. Unrelated eligible work may proceed; dependent work still waits for actual verified prerequisite acceptance. No backlog note or dependency is completed by rejection.

## Separate positive acceptance

The ordinary `/failure` and `/verify` APIs still require current governed independent-review missions, protected reviewer signatures and exact returned-patch binding. A scope rejection, preparation error, owner reason, provider completion or generated release notes cannot substitute for that test evidence. Missing or expired review authorization must be reported rather than renewed implicitly.

## Verification

`python -m pytest tests/test_jules_terminal_rejection.py tests/test_jules_backlog_queue.py tests/test_jules_adapter.py -q`

Real-store/API tests cover exact binding and patch corruption, expired-window rejection without renewal, owner authentication, active/unknown/mismatched provider refusal, cancellation during observation, uncertain outbound messages, concurrent observers, atomic rollback, idempotency, stale expiry writes, admission of unrelated next work, and preservation of incomplete prerequisites. Only external provider transport and API service selection are substituted.
