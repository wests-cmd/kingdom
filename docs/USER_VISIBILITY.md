# Understanding what Kingdom is doing

The plain-language status vocabulary was merged in [PR #180](https://github.com/wests-cmd/kingdom/pull/180). The simplified three-section Home layout is a separate candidate change. **Published v1.2.6 installers do not yet contain either update.** Check the installed release version, not merely GitHub main, before expecting these screens.

## The beginner Home format

Home should answer three questions, in this order:

1. **Needs your attention** — security requests, failed or blocked work, and what review is required. Approvals stay in the authenticated permission screen; a dashboard shortcut must never approve an action.
2. **Working now** — a short list of tasks waiting, assigned, running, or verifying, using recorded statuses only. Each shows a next step, not an invented percent-complete.
3. **Recently finished** — a short list of completed or cancelled tasks, with any verified execution receipts and an explicit reminder that external outcomes require separate evidence.

Above the lists, **Kingdom right now** shows the last complete status refresh, whether the runtime is running, waiting/assigned task counts, security request count, and completed task count. Unknown or failed refreshes display as unknown/stale rather than zero. Start/Stop Runtime and Task/Workbench shortcuts remain visible.

Below the lists, **More information** links to computers, approvals, recovery and an intentionally hidden technical view. In Easy mode, the technical view loads the existing orchestration, hierarchy, approvals and graph components only when opened, reducing the initial screen's information density and polling. In Advanced mode those details open by default, and can still be collapsed.

The beginner Home must not print task prompts, internal source paths, sensitive metadata, or arbitrary model prose in a public status summary. Explicit task details retain the authorized technical view. Status colors never replace text labels; keyboard buttons, aria roles and responsive layouts remain required.

**No new execution authority:** this layout reads existing APIs. No permission, task transition, pairing, or verified-result behavior changes.

## Kingdom right now

At the top of the Dashboard, the status overview reads the existing Kingdom API. It shows the last successful refresh, explains whether the runtime is stopped, running, waiting for authorization, or in need of recovery, and offers the next safe action.

**Connection lost** means the dashboard failed to refresh. The numbers shown are the *last known* numbers, not evidence that a worker remains online.

The six task counts distinguish:
- **Waiting to start:** a request exists but execution has not started.
- **In progress or assigned:** a task may be executing or has an assigned worker lease. Assignment is not proof of execution.
- **Waiting for your approval:** action is held for review. Do not approve without checking what will happen.
- **Blocked or recovery needed:** the recorded problem needs attention.
- **Recorded as completed:** the task reached its completed status. Inspect its actual result and verification.
- **Failed:** Kingdom recorded a failure rather than a successful outcome.

These are counts of **recorded task states**, not estimates of remaining time or overall project percentage.

## Tasks: what it means, what to do next

Each task now has a short status explanation and a next action. Select **Show developer diagnostics** only if you need low-level details. Technical metadata remains available but is not required to interpret the ordinary status.

A model response can be useful, but it cannot prove that a file was installed, a program passed tests, a remote machine was updated, or a request succeeded outside Kingdom. Inspect recorded tool results and independent verification for that distinction.

## Security approvals

The approval panel shows **who is asking, the requested permission, the action, the reason, exact parameters, risk and expiry**. Approvals are never inferred from a successful model response. **Deny** is available if you do not recognize the request; use the existing authorization controls for reviewing later actions.

Do not share credentials or pairing codes in screenshots or reports.

## Activity history

The **Logs** screen translates recognized task and runtime event codes into readable explanations. Each entry retains its timestamp and optional technical details (source, event type and related task reference). An event is a recorded observation, not proof of the real-world effect it describes.

## Timeline and evidence report

On each recorded task, open **Timeline and what changed**. This now reads a bounded, owner-authenticated persisted-event endpoint `GET /tasks/{id}/timeline`; it returns only event type, ID and timestamp, not the event payload or model prompt. The UI loads it only when the task's details are expanded. A missing event means no linked event was recorded or retained; it does not imply that execution never happened. A failed query must display an error, not an empty successful timeline.

**What changed? Evidence report** lists only recorded, verified workspace writes, packages, checksum-verified build artifacts, command exit codes, or screenshot receipts when those fields exist. It is not a generated Git diff and cannot establish full test correctness. If no independently verified receipt is present, it says so rather than reporting successful changes.

## Computers, models and notifications

On Home, open **Computers & model health** to see actual host CPU-core count, host-wide available RAM and free disk, current/paired remote computer counts from inventory, and number of configured model profiles. These values are measured or recorded snapshots, **not** Kingdom's own process RAM/CPU use, a guarantee a remote peer is live, or proof that any model works. An explicit read-only **Check configured providers** button probes the Ollama backend and reports whether an OpenAI-compatible provider is configured; configuration is not connectivity or task-success proof. Model and cluster diagnostics remain separate.

**Notifications** is an in-app view of recent persisted event types. It surfaces failure, completion, approval-required, cancellation, recovery and scheduler-error events when recorded; it does not expose raw event payloads or task prompts in the notice cards. Older notices at first launch are treated as history rather than a flood of new alerts. A user can mark notices viewed for the open Home session. This is **not** phone push, email/SMS delivery, OS-level notifications, or durable per-user acknowledgement. Existing Governance remains the only place to approve a security request.

A future native notification gateway, per-user durable inbox and cross-device syncing would require dedicated permissions, storage and testing. Do not imply these are present.

## What this does not change

This is a frontend presentation improvement only. It does not change scheduling, grants, node pairing, model selection, recovery policy, or the server's authority. It does not validate all physical computers or create missing logs. Where source data is missing or the connection is stale, the interface must say that **it is unknown**.

For the actual runtime controls, consult [Runtime controls](runtime-controls.md), [Mission workspace](MISSION_WORKSPACE.md), [Operations](OPERATIONS.md), and [current status](PROJECT_STATUS.md).
