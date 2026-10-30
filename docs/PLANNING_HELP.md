# Planning help and retained lessons

This source feature adds bounded assistance to held work programmes. It does not
establish that a published installer, DT1 or another Knight has been updated.
It does not complete the general autonomous coding backlog.

## What happens

```text
owner-enabled programme needs planning or error advice
  retain a bounded, redacted question and its original work binding
  use a currently verified local lesson if one matches
  otherwise ask the explicitly connected ChatGPT planning model
  validate a returned planning proposal through the normal native contract
  keep review, execution and acceptance separate
  after bound acceptance passes, permit explicit selection for local export
```

Assistance and the ChatGPT connection start disabled. The existing configured
planner continues to own normal planning; assistance handles held outcomes.
Verified lessons are reused before cloud advice, without another model call.
Independent adopted outcomes can plan while an unrelated outcome waits for an
answer. Dependent outcomes and section integration still wait for their gates.

## Connect on the owning Knight

In **Model profiles → Planning help and local learning**:

1. Choose **Continue with ChatGPT** and open the supplied sign-in link on that
   same Knight. The callback listens only on its `127.0.0.1`; opening the link
   on a different computer cannot complete that connection.
2. Complete the account's normal consent. Load the available models, choose a
   planning model, and choose **Use for advice**. Codex models are excluded.
3. Enable backlog help separately. Only programmes already enabled by the owner
   are harvested automatically; this does not adopt or enable every backlog note.

The default cloud allowance is eight help calls per UTC day, with at most two
sends for one question and one in-flight coordinator call. Owner-authenticated
`POST /assistance/settings` can set a daily limit from 1 to 32 with its current
settings revision. These limits do not reset exhausted planning/execution budgets.
The account's own eligibility, quotas and provider availability still apply.
There is no automatic paid API-key fallback.

**Pause backlog help** stops new automatic help sends. **Cancel this question**
fences its worker. Cancellation before the final provider-send check prevents
delivery; cancellation after transmission cannot retract information already
sent. **Disconnect ChatGPT** removes local credentials first, then attempts
bounded remote revocation. If remote revocation is unconfirmed, disconnect the
application in the account's settings as well.

## Safety and recovery

- Public OAuth uses PKCE, state, nonce and verified signed identity claims.
  Credentials are encrypted with the existing local vault key; they are not
  exported to tasks, logs or training data. No browser cookies or another
  application's credentials are used.
- Immediately before cloud delivery, recheck the sending claim, lease,
  cancellation, programme state, sanitized prompt/context, owner policy and
  selected account/model/session. A changed connection or task holds the send.
- Token and response requests have finite total deadlines and byte budgets.
  Only a completed response counts as advice. Provider text grants no authority.
- Interrupted sending becomes `outcome_unknown` after recovery and is not
  automatically resent. Claimed-but-unsent work can be queued again. Inspect
  the saved outcome instead of deleting its database row or resetting counters.
- Requests are retained in SQLite, capped at 1,024 entries. A full store requires
  retention review; evidence is not silently deleted. The UI shows the first
  100 records; automatic verification checks the full bounded store.
- Questions and answers receive bounded secret-pattern redaction. This is not
  universal detection of private information. The planner context uses declared
  work and setup facts; failed-work advice omits raw process logs and environments.

Runtime startup owns the assistance runner; browser polling does not perform
model calls. UI records stay collapsed until opened and refresh on open, events
and at the existing ten-minute interval.

## Lessons are not trained models

An answer remains unverified until current acceptance evidence binds its exact
question, answer digest, project, source context, original work and mission.
Verification is rechecked when lessons are reused or exported. An owner must
explicitly select each example for training export. The download is bounded
JSONL with provenance and redaction, not a model update or automatic upload.
Retained error advice is not yet bound to a repair mission and therefore cannot
qualify as a verified training example through this coordinator.

## Verification and remaining work

```bash
python -m pytest tests/test_chatgpt_plan.py tests/test_consultations.py tests/test_consultation_coordinator.py tests/test_programme_assistance.py -q
npm --prefix frontend run build
python scripts/check_docs.py
```

Provider tests use an actual loopback HTTP fixture with signed OAuth identities,
refresh, response streaming, interruption, revocation and deadline cases. They do
not consume a real account or prove live provider consent or fleet connectivity.
Coordinator tests exercise SQLite and native programme/acceptance handling; their
teacher replies are fixtures, not proof of a cloud model's planning quality.

Remaining gates include live owner consent, reviewed per-Knight deployment,
cross-Knight sharing of a planning connection, general failed-test-to-repair
execution, and independent review of the exact repaired patch before release.
No general repair, training, GitHub push or release is authorized by advice alone.

Protocol references: [public token sharing](https://developers.openai.com/siwc/token-sharing-open-source),
[sign-in](https://developers.openai.com/siwc/sign-in),
[models and inference](https://developers.openai.com/siwc/models-and-inference),
[token reference](https://developers.openai.com/siwc/token-reference),
[preview limitations](https://developers.openai.com/siwc/preview-limitations).
