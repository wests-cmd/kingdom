# Kingdom operates the computer

Kingdom's own agent can observe a Windows app's visible accessibility controls,
send a click, printable text or a supported key, then inspect the visible result.
Codex is not a runtime dependency or an execution worker for this loop. This is
native interaction with an application, not a hidden ChatGPT API or a transfer
of browser cookies.

## Use it

1. Install Kingdom's normal Windows requirements. `pywinauto==0.6.9` is a
   Windows-only dependency; it is not installed on headless Linux servers.
2. Select the target app on the interactive Windows desktop. Use its exact
   current window title. A locked, unavailable, disconnected or inaccessible
   desktop is a blocker. Kingdom never unlocks Windows or bypasses its prompts.
3. In **Talk & work**, choose **Agent work**, select the intended model, expand
   **Let Kingdom use a Windows app**, and enter that exact title. State a bounded
   task and what visible result will prove it succeeded.
4. Grant `computer.observe` and `computer.control` only to the intended Apprentice
   through existing owner governance. Selecting a title does not grant either
   capability. Existing autonomy policy and approval requirements remain active.
5. Send the request. Its background job can continue after the browser closes
   while the Kingdom server and interactive Windows session stay available.
   Follow the request, agent job and individual tool receipts. Stop/review any
   failure before continuing; a typed command or model claim is not completion.

For API clients, `POST /requests` accepts `desktop_window_title` with `mode=agent`
or `mode=auto`; use `/requests/{id}/background` to start bounded continuation.
Text-only `mode=quick` rejects desktop requests. Direct saved agent sessions also
accept the same optional title. `/agent-sessions/desktop-readiness` reports
platform, optional dependency, foreground availability and current Apprentice
grants; it performs no input and changes no permission.

## Boundaries enforced by the controller

- Desktop tools are absent unless the authenticated owner selects a window.
- The first desktop action must be observation. The model cannot supply a
  different title; Kingdom injects the selected one into each tool task.
- Input is pinned to the observed HWND as well as the exact title. Freshness is
  limited to 30 seconds, checked both at model dispatch and when input executes.
- Every verified input requires a subsequent observation. A response saying
  "done" before that inspection is retained as `needs_review`.
- Optional `desktop_expected_text` binds completion to exact text in the actual
  observed controls. Model prose cannot satisfy it. Desktop jobs always require
  a real observation; reading a screen does not force an unnecessary click.
- Observation runs in a child process with a 12-second timeout, bounded depth,
  at most 100 visited controls, 15,000 text characters and 200,000 output bytes.
- Offscreen controls and controls with unknown password status are skipped.
  Password names/values are redacted. Parent DocumentRange text is never read.
- UI/browser text is untrusted reference data. It cannot authorize another app,
  capability, purchase, process, download, or expansion of the owner's task.
- Native input verifies the foreground window again for each action. It does
  not activate another app, dismiss security prompts, elevate, or log in as the
  owner. New windows and changing titles stop the strict title-bound workflow.

Background requests continue at most six productive two-turn chunks within one
shared 310-second deadline. They continue only the same ready agent with no
errors or pending tools/approvals. Actual failures are not blindly replayed.

## Current limits

This first adapter uses accessibility text; it does not provide general visual
understanding, native Linux/Android control, unrestricted keyboard shortcuts,
scrolling or reliable operation of apps whose controls are not accessible. It
does not establish a persistent ChatGPT account session. An app must already be
open and available to the Windows session, and its UI may require the owner to
sign in or select it. Follow-up titles/windows need a newly reviewed target.

Local model competence is separate from tool availability. Tests of validation,
receipts and routing cannot prove a model can complete arbitrary desktop work.
Use real application evidence before claiming an end-to-end integration.

The owner selected the disposable Windows test app. A real local-model agent
then executed `desktop_observe` through Kingdom and received actual controls
(task `ee44d255-2883-5936-991f-ef12d4c7e747`). The first model response was rejected
for parallel calls; after scoped review feedback, observation succeeded. The
subsequent input was not accepted. The local model exceeded the 30-second
observation freshness window during inference; no typing or autonomous ChatGPT
operation is claimed. Faster action inference or verified UI revalidation is
required before this can be described as reliable desktop control.

References:
- https://pywinauto.readthedocs.io/en/latest/code/pywinauto.controls.uia_controls.html
- https://pywinauto.readthedocs.io/en/latest/code/pywinauto.application.html
