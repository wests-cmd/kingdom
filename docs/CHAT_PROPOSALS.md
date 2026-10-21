# External chat proposals, local Kingdom review

ChatGPT Chat can supply code suggestions without being a Codex worker. This
inbox also accepts suggestions from other chat services. Kingdom retains project
scope, task identity, the immutable response hash, and a separate local review.
It does not treat generated text as execution or as passing tests.

The assisted screen is available under **Talk & work** in Easy view and under
**Routing** in Advanced view. It retains the last proposal identity on this
browser so a refresh can restore the saved server-side proposal.

## Current working surface

All endpoints below require the existing Kingdom owner authentication. Never give
an external chat the Kingdom owner token. The inbox is not a public MCP server.

1. `POST /chat-proposals` with `project_scope`, `objective`, `acceptance`, an
   explicit local Ollama `local_profile`, and optional `exported_context`.
   The returned `prompt` contains only these deliberately selected fields, not
   automatic file reads, personal vault data, credentials or conversation history.
2. Send that prompt through the chat service's visible interface. This version
   requires an operator/browser bridge for that step; it does not have an
   unattended browser worker. Opening ChatGPT does not establish such a worker.
3. `POST /chat-proposals/{id}/reply` with `{"text":"..."}`. The first reply is
   immutable; identical retries are safe. Use a new task for a corrected proposal.
4. `POST /chat-proposals/{id}/review` creates an idempotent local text-review
   request. The profile is checked again before queuing; remote/cloud profiles
   are rejected. Run the returned `request_id` using the existing request API.
5. Read the request's result, errors and evidence. `local_review_queued` is an
   inbox state, not a completed review or accepted implementation. A local text
   assessment has no tools and cannot edit files, run commands or promote code.
6. A separate governed coding task must inspect current source, compare the
   proposal with the actual need, and apply only the useful changes inside an
   isolated workspace. Independently run unchanged acceptance/regression tests
   before accepting or publishing. Existing tool grants remain authoritative.

Review failure retains the proposal and request checkpoint. No cloud or Codex
fallback is selected. There is no claim of general autonomous coding readiness.

## Applying reviewed code without regenerating it

Existing Kingdom missions can inspect a file, syntax-check the exact proposal,
write those exact bytes with a `write_file` step, then read the result back.
Use the reviewed candidate as literal step instructions; do not have a small
model reserialize an already accepted code file into another JSON tool argument.
That can introduce escaped-newline errors. An owner-approved mission retains
normal grants and execution receipts. Its verified write is still separate from
correctness: compare candidate and written hashes, preserve tests, and run the
independent acceptance suite against the actual written file. Reinspect current
source before preparing a mission; a draft does not lock the destination file.

The inbox does not automatically approve these missions, treat a local model's
text as acceptance, or publish code. The local reviewer has produced incorrect
or unfinished assessments in real trials; keep independent checks mandatory.

## Connecting ChatGPT itself

Official ChatGPT supports custom MCP integrations. A future unattended
integration should expose only a selected task's prompt and proposal submission,
with separate scoped authentication, revocation and explicit export controls.
Do not expose this owner-authenticated control plane, its owner token, arbitrary
file reads, filesystem writes, or process tools directly to an external chat.
Configure and test the actual account connection before labelling it connected.

The current UI smoke test is an operator-assisted chat round trip, not that
persistent integration. No OpenAI API key or Codex worker is needed for this
inbox, and no paid provider request is initiated by it.

References checked 2026-10-18:
- https://developers.openai.com/api/docs/guides/custom-mcp-server
- https://developers.openai.com/siwc/quickstart
