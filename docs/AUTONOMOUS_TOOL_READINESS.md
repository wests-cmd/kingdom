# Execution prerequisites and required tool evidence

Programme planning now supplies the current controller's Node/Git availability
and existing worker tool grants. Missing inventory is explicitly unknown. These
facts help identify prerequisites; they do not attest remote environments,
model quality, source checkouts or completed work, and grant no capabilities.

For a validated OpenAI-compatible model endpoint, an owner may configure
`tool_choice_mode: required_pending` through the model-profile API. The default
remains `auto`. Native Ollama rejects this mode because it does not support the
required tool-choice contract.

An agent session records whether its owner-selected required tools still lack
verified execution evidence. An opted-in endpoint receives `tool_choice:
required` while that evidence is pending; it returns to `auto` afterward so the
model can finish. Explicit `none` or named choices are not overwritten. The
internal evidence hint is not sent to the provider. Unsupported endpoints fail
normally; there is no automatic downgrade or prose-to-command conversion.

This constrains response format, not authority or correctness. Tool arguments,
available tools, task grants, approvals and receipts undergo the same checks.
A model can still choose the wrong tool, produce bad code or exhaust its budget.
Required tools are not a substitute for independent acceptance tests.

These changes alone do not establish autonomous completion of an arbitrary
backlog, repair, release, training or trading. A real end-to-end task must still
pass source-bound independent acceptance before those claims are made.

Candidate connections may set `auto_select: false`. Automatic chat/generation,
readiness selection and deliberative planner routing then exclude them. An
explicit profile or deliberately selected pool can still test the candidate;
existing disabled, capacity and grant checks remain authoritative. This prevents
a protocol experiment from silently becoming the default production worker.
