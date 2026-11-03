# Move a Kingdom ChatGPT session to a remote Knight

This is an operator-only credential **move**, not a shared refresh-token copy.
There is no HTTP endpoint, model tool, automatic enrollment or permission grant.
The destination stays disabled until the owner selects a model using the normal
ChatGPT connection settings. Kingdom execution policies and grants are unchanged.

The [official self-hosted VM procedure](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms)
requires the same tool/client, a distinct stable destination host ID, a secure
transfer channel, and destination ownership of later token refreshes. This
implementation follows that procedure. It does not read Codex credentials,
browser cookies, API keys or billing settings. Host-specific revocation and
usage attribution for transferred sessions are not currently provided by OpenAI.

## Prerequisites

- Both stores belong to this same Kingdom application and the selected user and
  workspace. Use only an existing owner-approved private management channel and
  pinned destination identity. A host ID alone is not authentication.
- The source has a valid signed-in account, an unexpired access/ID token and a
  retained refresh token. Its planner and any service or other process that can
  use that account must be quiescent before starting. Run only the reviewed
  handoff-capable code on both sides throughout the move. Do not run an older
  connection implementation against these stores while a handoff is pending.
- The destination already has its own persistent host ID, has no saved account,
  and has no pending OAuth flow. Never copy the source's host ID or vault key.
- Keep at least five minutes available for the operation. An exported bundle has
  a fixed maximum five-minute import window, which retries cannot extend.
- Source and destination must reach OpenAI's official discovery/JWKS endpoint
  for normal ID-token verification; there is no offline trust override.

## Four explicit steps

Run `scripts/chatgpt-host-handoff.py` with absolute `--database` and `--secrets`
paths pointing at each installation's actual database and existing secret root.
The command is not a daemon and does not install itself or grant OS access.

1. **Source: `prepare --target-host-id HOST_ID --secret-stdout`.** Atomically
   disables source planning, changes the selected account's generation and fences
   refresh/access/sign-out/new sign-in for that account. It emits a strict secret
   JSON bundle only to non-terminal stdout. Stderr contains only its transfer ID
   and digest. Send the bundle directly over the existing pinned private SSH
   channel; pass its expected digest separately to the recipient. Do not send it
   through chat, command arguments, logs, clipboard history or shared storage.
2. **Destination: `import --expected-sha256 DIGEST`.** Reads the bounded bundle
   from private stdin, validates its digest, host binding, expiry, OAuth identity,
   audience, subject, account ID and required scopes. It reencrypts credentials
   using the destination's existing key, retains that host ID, and leaves the
   imported account fenced and disabled. It emits a bound acknowledgement.
3. **Source: `complete`.** Reads that acknowledgement from stdin and validates
   its one-time HMAC proof. Atomically removes the local account's secret and
   exported duplicate credential record, retains a disconnected tombstone,
   and signs the destination activation receipt with an ephemeral key whose
   private material was never sent to the destination. It does **not** call
   remote revocation: that would revoke the transferred session too.
4. **Destination: `activate`.** Reads and verifies the signed activation receipt.
   Only then releases its refresh fence. Planning remains disabled, with no model
   selected. The owner can now list the account's actual models and configure one
   through the existing authenticated settings. Configuration does not expand
   tool or execution authority.

Acknowledgements and activation receipts contain no OAuth tokens, account email,
vault key or private signing key. They are nevertheless task-bound control
receipts and should be kept with the protected operator record, not published.

## Interrupted operations

`status --transfer-id ID` returns the durable phase, bound hosts, digest and any
retained acknowledgement/activation receipt. It never returns OAuth credentials.
An explicit `export-existing --transfer-id ID --secret-stdout` can recover the
**same** still-valid source bundle over the private channel, without extending
the original import deadline. Repeating an exact known import, source completion
or target activation rejoins its existing record; it does not create a second
account, rotate a token, or reset a deadline.

Unknown outcomes stay fenced. Never unpause both sides, restore a pre-move
credential database, or reuse a copied refresh token on a second Knight. There
is deliberately no automatic abort/unfence command. If the move cannot be
reconciled, the operator must first secure/revoke the affected renewable session
through the owner/provider and then perform a fresh supported sign-in. Logical
database deletion does not claim secure erasure of historical encrypted SQLite
pages or owner backups. Those backups remain protected recovery material.

To connect both Laptop 2 and DT1, use separately authorized renewable sessions or
keep one refresh-owning planning service and send it scoped advice requests.
Do not copy this same renewable session to both computers.

## Verification and deployment boundary

`python -m pytest tests/test_chatgpt_host_handoff.py tests/test_chatgpt_plan.py -q`
exercises real stores, real encryption and signed fixture OAuth/JWKS validation,
with only provider HTTP routing substituted. The tests cover fencing, proof and
identity tampering, expiry, restart/idempotency, sign-out/refresh races, terminal
export refusal and authority preservation. These tests do not claim a live
credential move or production Knight integration has run. A reviewed deployment
and read-back of each destination's actual state remain required.
