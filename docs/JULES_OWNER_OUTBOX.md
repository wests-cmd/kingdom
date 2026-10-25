# Owner-installed Jules repository outbox

`scripts/jules-repo-job.py` is a finite controller adapter for the explicitly
approved `wests-cmd/kingdom` source. It is not a general model tool or a second
authorization authority. Default installations do not start it.

The owner supplies a protected configuration with exact repository/source,
branch, expected source revision, bounded public-repository task, absolute local
observation deadline, encrypted credential file and existing Fernet vault key.
The optional owner token is used only to publish bounded status to the local
project vault. Keep these files outside every agent workspace.

The controller checkpoints `submitting` before one session POST. If the response
is lost, or the controller restarts during submission, it holds
`submission_unknown`; it never creates a second session automatically. Known
sessions can be observed again after restart. GET failures back off. No cookie
scraping or browser session credential is used.

The caller's task is standing authorization for ordinary repository edits in
Jules's existing isolated repository environment, not host access or additional
grants. This adapter sends `requirePlanApproval: false` only for that fixed
owner-approved task and disables PR automation. It exposes no merge, deployment,
credential change or plan-approval API. Remote completion becomes
`awaiting_independent_review`, never accepted work. Source attestation and actual
independent test/review gates still have to be integrated into the native backlog.

The local deadline bounds observation, not Jules's remote execution. Expiration
is explicitly `expired_remote_may_continue`; the adapter does not pretend a
timeout cancelled remote work. Reconcile the existing session before any new
assignment.

The DT1 deployment uses a separate trusted control container, a pinned existing
image, no Docker socket, read-only root and credential mounts, fixed process and
memory limits, and one writable protected job checkpoint. The execution agent
receives neither the API key nor the controller's filesystem.

References checked October 25, 2026:
- https://developers.google.com/jules/api
- https://developers.google.com/jules/api/reference/rest/v1alpha/sessions
- https://jules.google/docs/api/reference/sources/

This is a bootstrap outbox, not a claim that the full backlog is autonomous.
