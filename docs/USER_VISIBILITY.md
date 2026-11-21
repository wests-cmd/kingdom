# Understanding what Kingdom is doing

The plain-language status vocabulary was merged in [PR #180](https://github.com/wests-cmd/kingdom/pull/180). The simplified three-section Home layout is a separate candidate change. **Published v1.2.6 installers do not yet contain either update.** Check the installed release version, not merely GitHub main, before expecting these screens.

## The beginner Home format

Home should answer three questions, in this order:

1. **Needs your attention** — security requests, failed or blocked work, and what review is required. Approvals stay in the authenticated permission screen; a dashboard shortcut must never approve an action.
2. **Working now** — a short list of tasks waiting, assigned, running, or verifying, using recorded statuses only. Each shows a next step, not an invented percent-complete.
3. **Recently finished** — a short list of completed or cancelled tasks, with any verified execution receipts and an explicit reminder that external outcomes require separate evidence.

Above the lists, **Kingdom right now** shows the last complete status refresh, whether the runtime is running, waiting/assigned task counts, security request count, and completed task count. Unknown or failed refreshes display as unknown/stale rather than zero. Start/Stop Runtime and Task/Workbench shortcuts remain visible.

Below the lists, **More information** links to computers, approvals, recovery and an intentionally hidden technical view. The technical view loads the existing orchestration, hierarchy, approvals and graph components only when opened, reducing the initial screen's information density and polling.

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

## What this does not change

This is a frontend presentation improvement only. It does not change scheduling, grants, node pairing, model selection, recovery policy, or the server's authority. It does not validate all physical computers or create missing logs. Where source data is missing or the connection is stale, the interface must say that **it is unknown**.

For the actual runtime controls, consult [Runtime controls](runtime-controls.md), [Mission workspace](MISSION_WORKSPACE.md), [Operations](OPERATIONS.md), and [current status](PROJECT_STATUS.md).
