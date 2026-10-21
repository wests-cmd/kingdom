# Owner reference architecture: one harness, many front doors

Source: five owner-supplied screenshots, October 16, 2026. They are design
references, not evidence that their advertised integrations or speedups work.
Their calls to follow accounts, purchase hosting or install particular products
are not project requirements. This backlog supplements ADAPTIVE_CLUSTER_CORE.md.

## Product direction

Kingdom owns the shared request, routing, memory, tool, scheduling and evidence
layer. Centipede hosts and supervises it and supplies desktop/server access.
Web, desktop, phone, optional voice, Discord and optional knowledge-editor
interfaces submit to the same backend. Switching interface or model must not
lose a project, duplicate a job or create a separate authority plane.

Use existing owned computers first. Paid VPS hosting, a specific provider,
Obsidian, Hermes, Claude, Telegram and Discord are optional adapters. A new user
must be able to use the built-in interface without installing those products.

## Request tiers

1. Rules and saved data: deterministic answers to explicit status, time,
   preferences and known project state. No model invocation. Include freshness
   and timezone where relevant; ask when required context is missing.
2. Quick model work: select a healthy small model that meets context and declared
   modality/tool requirements. Use scoped retrieval when requested. Summarizing
   current news still needs fresh sources; a small model is not a news service.
3. Real tool work: create a durable bounded job for Kingdom's native agent or an
   optional installed harness; place model and tools separately, execute, test,
   retain evidence and report limitations. A long prompt alone is not proof of
   complex work, and a short prompt can request a dangerous or difficult task.

Current: model availability/capacity selection, native agent sessions, harness
connections, task receipts and scoped retrieval exist. The current complexity
router classifies by text length. It is not a reliable implementation of these
three semantic tiers. Deterministic-first routing remains a delivery item.

## Ordered implementation backlog

- [ ] R01 Unified request bridge: persist request ID, project/scope, origin,
  reply destination, selected tier, budget, cancellation and evidence pointers.
  Acceptance: submitting the same idempotency key through two front doors
  creates one job; reconnecting shows the same result, not a repeated action.
- [ ] R02 Deterministic-first router: explicit read-only intents for clock,
  runtime/node status and saved project priorities; unresolved input falls
  through to model/job tiers with a visible reason. Acceptance: count provider
  calls and prove zero inference for these intents, including ambiguous and
  stale-data cases. Preserve explicit model/harness selections.
- [ ] R03 Responsive background execution: audit async routes for blocking file,
  database, subprocess and network operations. Bound concurrent I/O, reserve
  model/computer capacity, and move CPU-heavy work to process/remote workers.
  Acceptance: delayed independent I/O overlaps while health/cancel stays
  responsive; CPU tasks respect resource limits; shutdown and timeout preserve
  checkpoints. Async is not shared RAM or CPU acceleration. Do not promise a
  tenfold speedup from ten artificial sleeps.
- [ ] R04 Portable project vault: readable Markdown notes, reports and receipt
  references with stable IDs; retain transactional SQLite state and derived
  search/vector indexes. No secrets in exported notes. Acceptance: export,
  import and rebuild indexes without losing provenance; enforce project scopes,
  concurrent edits, deletion and revocation. Shared memory does not mean every
  model can read every project. Existing SQLite graph/retrieval is a foundation,
  not a completed shared Markdown vault.
- [ ] R05 Unified conversation/results: text answer first, bounded chunks, files
  and detailed receipts afterward, with job progress and recovery in the same
  conversation. Acceptance: a simple question produces a concise answer rather
  than a research source dump; reconnect resumes without losing the request.
- [ ] R06 Scheduled and proactive work: persisted schedule, bounded review loop,
  quiet unchanged state, cancellation, budget and restart recovery. Acceptance:
  survive host reboot, prevent duplicate side effects, and report actual work
  separately from idle time. Optional peer reviews cannot validate themselves.
- [ ] R07 Optional voice front door: replaceable speech-to-text and speech output
  adapters, push-to-talk and text fallback. Whisper/Kokoro in the references are
  examples to evaluate, not mandatory dependencies or currently installed
  features. Acceptance: local hardware benchmark, microphone choice, privacy,
  interrupt/stop and equivalent text/voice job identity.
- [ ] R08 Optional connectors and reusable skills: mail/calendar/files/repository
  adapters with declared scopes, secret storage, availability and independently
  verified tests. Promote reviewed repeated workflows into versioned portable
  skills with rollback. Do not promise accounts, free tiers or app access from
  a screenshot. Discord-specific packaging stays optional.
- [ ] R09 Measured adaptation: route using observed latency, verified success,
  cost and load; show why a model/computer was selected. Evaluate new knowledge,
  skills and tuning separately with held-out checks and rollback. Memory/RAG is
  not model-weight training, and model modification is never a prerequisite for
  using Kingdom.

## Centipede delivery responsibility

Centipede's matching backlog is docs/KINGDOM_REFERENCE_REQUIREMENTS.md in the
Centipede repository. Its service health, boot, reconnection and desktop shell
must support these contracts without embedding personal IPs or credentials.
The existing OptiPlex persistent Kingdom service is verified; this roadmap does
not authorize another disk write or reinstall.

## Parsec-inspired experience acceptance (unimplemented)

Official-source review: [PARSEC_EXPERIENCE_REVIEW.md](PARSEC_EXPERIENCE_REVIEW.md).
These are proposed delivery items, not shipped remote-desktop capabilities.

- [ ] P01 Computer cards and distinct actions: show verified identity, online
  freshness and real capabilities; separate Connect, Observe and Control.
  Acceptance: an offline or unsupported host cannot appear controllable;
  connection alone grants neither screen observation nor input authority.
- [ ] P02 Scoped session authority: explicit host-approved observation/input
  grants bind user, computer, capability, expiry and session. Acceptance:
  unapproved input fails at the host; revocation stops active and queued input;
  expired/replayed grants fail after reconnect; clipboard/files/shell and agent
  jobs require independent authority. Record redacted grant/revoke evidence.
- [ ] P03 Measured quality: report timestamped transport RTT, supported
  capture/encode/decode timings, achieved frame rate/bitrate and lost frames.
  Acceptance: controlled network degradation changes real metrics and warnings;
  unavailable measurements are marked unavailable; RTT is not advertised as
  end-to-end input latency. Benchmark DT1's actual GPU/driver/capture path before
  claiming hardware encoding, supported codecs, resolution or frame rate.
- [ ] P04 Reconnect without privilege growth: bounded retry with visible cause,
  host identity recheck and grant revalidation. Acceptance: network interruption,
  host restart, expiry and revocation never replay input, duplicate a job, or
  restore control without valid authority. Keep observation/control/job state
  distinct and offer cancel/disconnect throughout recovery.
- [ ] P05 Beginner and advanced settings: understandable defaults, quality
  tradeoffs and reset, with supported expert options behind Advanced.
  Acceptance: effective settings and restart requirements are visible; invalid
  options recover safely; no unsupported DT1 GPU or Linux-host promises. Test
  on real endpoints before marking any streaming capability implemented.
