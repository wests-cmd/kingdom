# Chat planning and clarification

## ChatGPT specifically

New lists in the interface default to `planner_mode: chatgpt`. This prepares and
persists an external planning request; it does not call a configured model, Codex,
or any fallback. The interface exposes the request for the owner to copy into
ChatGPT and an input for its JSON response. This is an explicit **manual handoff**,
not a completed ChatGPT connection or unattended planner.

The owner-authenticated, revision-bound `chatgpt-response` endpoint validates an
external response using the same mission, exact-source and independent integration
acceptance rules as configured planning. It may save a clarification question or
a proposal awaiting review. It cannot approve or execute. Its origin is declared by
the owner, not cryptographically attested as ChatGPT. Pending requests survive
restart and do not cause local inference. Existing lists retain their configured
planner; API creation remains backward-compatible unless `planner_mode` is explicit.

Official connection route: a ChatGPT custom MCP plugin can call Kingdom tools
through a supported MCP server, subject to account/workspace permissions and server
authentication. Kingdom's existing `MCPServer` Python helper is not that transport
or an authenticated ChatGPT connection. It must not be exposed as though it were.
An authenticated, scoped MCP transport plus a real ChatGPT round trip remains to
implement and verify. MCP's documented direction is ChatGPT calling server tools;
these docs do not establish an unattended Kingdom-to-ChatGPT inference API.

Sources checked October 24, 2026:
- https://developers.openai.com/api/docs/guides/custom-mcp-server
- https://developers.openai.com/plugins/quickstart

## Configured chat models (separate option)

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
