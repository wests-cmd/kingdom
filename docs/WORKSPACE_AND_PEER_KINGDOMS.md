# Workspace and peer Kingdoms

Built into Kingdom: computer and agent identities, automatic model placement,
responsive Easy/Advanced views, owner autonomy policy, and independent Kingdom
pairing/reconnection. These features work without Discord or Hermes.

Optional adapters: payment providers, model training, USB/AirLLM storage, and
Discord-specific skills. This update supplies no payment provider or account
and makes no transactions. Personal IPs, tokens, model names and SSH keys stay
in local configuration, outside repository defaults.

Automatic selection confirms installed models, filters configured context,
image/tool support and disabled connections, then uses shared computer capacity.
This is best eligible placement, not a measured model-quality leaderboard.
Explicit choices are preserved. Declare tool support in the connection editor
before automatic agent jobs use that model.

Level 5 is standing owner authorization for granted high-risk tools, including
financial capabilities if a financial adapter is separately connected. Lower
levels retain individual high-risk approval. Authentication, capability grants,
prompt checks, verification and OS boundaries remain. Updating does not select
level 5 or grant additional tools.

## Separate Kingdom installations

Create an invitation on B; paste its JSON and URL under Connect another Kingdom
on A. Approve A under B's Pending Approvals. Repeat in reverse. Each Kingdom
appears as a Knight in the other, with independent grants. Save the peer URL and
reconnect after interruption. HTTPS or an existing private loopback tunnel is
required. Reconnection checks pinned identity and signed RPC acceptance, and
refuses unapproved or revoked peers. It does not create a remote task executor
or automatically share all models.

New installations receive unique Kingdom IDs. Legacy installations sharing the
default ID need an owner-reviewed identity migration. Established keys and
pairings are never silently rotated.

103 backend tests passed across model placement, capacity, missions, agent
sessions, autonomy and federation. Frontend helper tests and build passed.
Peer pairing tests contact an actual HTTP server and verify Ed25519 signatures.
Two installed Kingdoms and automatic inter-Kingdom task execution have not been
demonstrated end to end by these tests.
