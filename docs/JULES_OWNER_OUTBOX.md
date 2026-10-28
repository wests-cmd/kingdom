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

## Separate protected patch gate

`scripts/jules-independent-gate.py` observes one existing session and fetches
source-bound patch artifacts through the official API. It applies only scoped
text changes to a fresh copy of a hashed source archive. Protected receipt tests
and unchanged backlog/programme tests run in a disposable, network-none container
with no credentials or host control socket. Candidate code cannot edit these
protected inputs. A real known-bad candidate must fail the receipt tests before
the controller is armed.

The gate retains the original deadline and counts prior reviewer corrections.
It can return bounded test diagnostics to the same remote session. It holds
unknown feedback POST outcomes instead of replaying them. Passing this test
subset means `scoped_tests_passed_review_required`, never native backlog
completion, automatic merge or deployment. Other source, integration, security
and release checks remain independent requirements. These are owner-installed
bootstrap services; the native adapter is a separately reviewed candidate.

Build a gate's base archive using `scripts/archive-verified-source.py`. It reads
and validates raw blobs at an exact commit, preserving their bytes regardless of
checkout line-ending settings. A platform-converted archive can be semantically
similar Python while failing the patch's exact source identity. The archive
SHA-256, raw commit and protected test hashes belong in the review checkpoint.

The existing backlog runner is outside the patch gate's default scope. A human
reviewer may explicitly include that one lifecycle file through the protected
`reviewed_extra_paths` configuration. This does not permit security or general
runtime rewrites. An expired assignment stays closed; a fresh review requires
its own explicit scope and must preserve prior repair history.
