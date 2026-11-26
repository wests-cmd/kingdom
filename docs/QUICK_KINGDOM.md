# Quick Kingdom (v1.2.9 source candidate)

This is an independently implemented interaction pattern inspired by [Atticus](https://github.com/SaarthurR/atticus-mac/tree/2239807b857abb82302c785afd34e7799257186c), MIT © 2026 SaarthurR. No Atticus source, assets, telemetry or shell replay has been copied.

## Use

- On a GUI-enabled Kingdom desktop, press Ctrl+Shift+Space (Cmd+Shift+Space on macOS) or choose **Quick Kingdom** from the tray. If the OS reserves the shortcut, use the tray. Headless profiles do not open a window.
- The compact window uses the existing local owner authentication and the same saved conversation/project selection as Talk & work when it opens. The scope is displayed; if you change the project in another open window, close and reopen Quick Kingdom to load it.
- Type a message, or use existing optional voice controls. Review and send the transcript yourself. Browser speech is not guaranteed offline; no microphone starts automatically.
- Instant commands in automatic mode: `/help`, `/status`, `/time`, `/priorities`, `/work`, `/harnesses`. No model is called. Unknown slash commands are rejected. Harness names are configuration only, not proof of readiness.
- Under Instant commands and personal shortcuts, explicitly save a short name for an existing read-only command, e.g. `/focus` for `/status`. Up to 32 per project. No arbitrary shell, learned execution, or permission escalation. Edits/removal cannot redirect an already saved request.
- Agent work still uses existing scoped tools, grants and background budgets. Closing Quick Kingdom does not stop server-owned work. Cancel a retained request explicitly if needed.

## Architecture and verification

`desktop/quick-assistant.js` owns one compact native window and the global shortcut; it denies external navigation and popups, has no privileged preload, and releases the shortcut at quit. `frontend/src/components/UnifiedConversation.jsx` is shared by both views. `backend/runtime/intent_router.py` only selects allowlisted read-only intents. The existing authenticated `request_api.py` / `request_service.py` handles identity, scope, persistence and evidence; no separate executor or conversation store was added.

Acceptance gates: backend request regression cases, Node window lifecycle tests, production UI build, and the packaged native smoke test submitting /status from the compact renderer and reading its exact saved request from the main renderer. Physical OS shortcut/Wayland support and installed speech operation are not certified by these tests.

## Deliberate limits and next work

This is the first interaction slice, not a port of Atticus. Typed verified action learning, explicit harness execution in chat, capability-based escalation, local speech, screen-region capture and annotations, multi-platform accessibility controls and Commander delegation remain separate engineering work. No raw shell replay, automatic application input, unapproved cloud calls, background recording, or additional model privileges are introduced. The published v1.2.8 installers do not contain this feature; publish a new reviewed version rather than replace immutable assets.
