# Durable owner-scoped coding admission

An owner can authorize up to twelve existing, disabled, unowned backlog notes as a bounded Jules batch. The native Jules runner admits one eligible coding job without requiring another browser or Codex turn. The existing encrypted credential and repository/source allowlists remain authoritative. No batch is created by default, and a model response cannot configure it.

## Control API

Owner authentication is required for all endpoints:

- `GET /integrations/jules/backlog-queues` lists retained batches.
- `POST /integrations/jules/backlog-queues` creates an idempotent batch. Supply project, idempotency_key, allowed repository and source, exact base revision, branch, one-to-twelve items (backlog_id and expected_revision), and deadline_seconds (120–86400).
- `POST /integrations/jules/backlog-queues/{id}/settings` changes future admission using enabled and expected_binding from the saved batch. Pausing does not cancel an already claimed/registered job; use existing job cancellation or the emergency stop for that operation. An expired batch cannot be re-enabled or renewed by repeating its idempotency key.

The existing runner calls batch admission before normal job submission and monitoring. There is one automatic admission slot across batches. Already active Jules jobs consume it. A provider-completed candidate awaiting verification continues to occupy the slot. Unknown submission outcomes, cancellation after a remote session exists, and expired remote work also retain it; local cancellation is not proof that a remote worker stopped.

A job cancelled before remote submission frees the slot for unrelated eligible work. Its dependent notes remain held until their actual backlog prerequisites have completed. Exact base revisions are not silently rebased, and partial results or model claims do not satisfy dependencies.

## Crash and authority behavior

Admission and job registration commit in one SQLite write transaction, using a durable task key. A restart after the registration commit rejoins the same job instead of creating another cloud session. A restart before registration uses only the remaining original batch window, never a fresh extended deadline. A changed or adopted note requires review, while independent notes may proceed. Concurrent queue instances serialize admission in SQLite. Expired batches leave no abandoned admission reservation. Current prerequisite acceptance is independently rechecked at admission and before provider submission.

Current level five, enabled Jules settings, existing repository/source allowlists and the batch deadline are checked on each admission cycle. Existing provider dispatch/repair and exact-patch verification checks continue unchanged. A batch admission error produces a bounded event and does not stop existing jobs from being polled.

## What this does not prove

This is coding admission, not general permission to execute arbitrary plans or to accept a patch. Independent acceptance still requires the current reviewed mission, exact returned patch, trusted reviewer and test contract. Missing review infrastructure remains a real blocker. This feature does not automatically merge, deploy, enable a tool, train a model, publish, or spend funds. It does not make every historical backlog note executable.

## Verification

`python -m pytest tests/test_jules_backlog_queue.py tests/test_jules_adapter.py tests/test_backlog_ready_progress.py -q`

Tests exercise the real SQLite backlog, encrypted Jules service and admission scheduler. Only provider HTTP transport and authenticated API service selection are substituted. They cover restart, post-registration crash, concurrent admission, dependencies, safe cancellation, uncertain remote cancellation, provider completion without acceptance, pause, revocation, expiry, deadline preservation, changed ownership, owner authentication and extra-authority rejection.


## Routine feedback without new authority

Paused remote sessions continue to be observed, with a thirty-second pause backoff. When the latest fully retrieved agent message ends with the exact routine question “Would you like me to proceed with submitting these changes for review?”, the runtime may send one fixed reminder to return the original patch and test evidence. That reminder explicitly forbids PR creation, merge, deployment, release, spending, permission changes and weakened checks. It is not an approval of the candidate or a free-form answer to a model question.

The activity and question digest are claimed durably before the message POST. A lost acknowledgement or interrupted process cannot automatically resend that reminder. There are at most three such attempts per job, inside the original policy, allowlist and deadline. Other questions, including permission or publication requests, remain paused. No model may fabricate human answers. This is a narrow workflow repair, not a claim that arbitrary questions are handled autonomously.
