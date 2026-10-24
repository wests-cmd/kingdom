# Chat planning and clarification

Work programmes now use the configured model service's chat protocol, not a Codex
agent or CLI. Choose a chat connection in the work-list panel. Automatic and pool
selection exclude connections whose configured model or profile identifier contains
`codex`; explicit selections do too. The connection is checked again after capacity
reservation. This identifies configured model names, not independently attested
upstream implementations behind a custom gateway.

The planning assistant can return one bounded `question` instead of an executable
proposal. Kingdom saves it as `awaiting_answer` and does not poll the model again
until the authenticated owner answers. The answer is saved with its question and
included as context on the next planning call. It grants no tools or approvals.
Automatic planning resumes when enabled; otherwise request the next plan manually.
Three clarification rounds are permitted per outcome. Provider/invalid-response
retries remain bounded separately. Unresolved work remains visible for review.

The answer endpoint is owner-authenticated and revision-bound:
`POST /work-programmes/{id}/items/{key}/answer` with `answer` and
`expected_revision`. A duplicate or stale response is rejected. Existing proposed
plans still require exact approval, component acceptance and separate integration
tests. Planning does not run those tests or prove completion.

This does not sign into ChatGPT or establish that a consumer ChatGPT session is an
API connection. No account credentials are extracted and there is no Codex fallback.
Connect an authorized, supported chat endpoint through existing model settings.
When no suitable endpoint is configured, planning fails visibly without execution.

Verification: clarification/restart/CAS/bounds tests; planner chat messages and
truncation tests; explicit/pooled/automatic Codex exclusion tests; existing programme
acceptance, HTTP ownership and runtime-loop tests. These test the implementation;
live provider execution and fleet deployment require separate receipts.
