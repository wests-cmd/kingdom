# Understanding what Kingdom is doing

This guide describes the **proposed plain-language status UI** in the [user-visibility PR](https://github.com/wests-cmd/kingdom/pulls). It is not a claim that the already published v1.2.6 installer contains the new screens. Wait for a new reviewed release and check your installed version.

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
