# Discord, portable skill maps and reviewed providers

Discord is an optional adapter over Kingdom's existing identities, permissions,
SQLite records, task engine, Knights and independent result verifier. It is disabled
by default. Installing the desktop application does not connect a Discord account.

## Configure Discord

1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications).
   Record its application ID and Ed25519 public key. Create its bot token and keep
   it in the process environment or your deployment's secret store.
2. Set the variables shown in `configs/discord.env.example`. Kingdom does not
   automatically load that example file. Never commit your populated secrets.
   Set `KINGDOM_DISCORD_GUILD_ID` to restrict commands to your test server.
3. Restart the backend with these variables. Incomplete enabled configuration fails
   closed. The ordinary owner HTTP authentication remains required everywhere
   except the signature-protected `POST /discord/interactions` endpoint.
4. Supply a public HTTPS reverse proxy that forwards **only**
   `/discord/interactions` to Kingdom. Apply request-size and rate limits at the
   proxy. Set this URL as the application's Interactions Endpoint URL. Discord
   validates it with a signed PING. Do not publish the owner dashboard or its
   access code. A private Tailscale Serve address cannot receive Discord callbacks.
   This feature does not enable Funnel, change your firewall or create a public relay.
5. Run `python -m backend.integrations.discord_ai_map.commands --register` in
   the configured environment. This explicitly registers Kingdom's slash commands;
   it does not delete unrelated application commands. Install the application in
   the selected server with the application-command scope. A private test guild
   makes rollout and troubleshooting easier.
6. Run `/kingdom` in Discord. In the owner dashboard choose **Skill maps & Discord**,
   paste the private five-minute code and select the permissions to grant. The
   challenge is single-use and stored only as a hash. No grant is selected by default.

Server membership and Discord administrator privileges confer no Kingdom authority.
Links and grants persist across restarts; owner revocation disables the Kingdom
identity immediately. Do not paste tokens into a map, task, message or screenshot.

## Commands and permissions

| Command | Purpose | Required Kingdom grants |
| --- | --- | --- |
| `/kingdom`, `/help` | Generate an owner-confirmed challenge; read help | None; signed request and configured server still required |
| `/status` | Actual running/stopped status | `view_status` |
| `/knights` | Installed workers and curated health summaries | `view_knights` |
| `/profiles` | Installed profile catalog and this identity's preference | `view_status` |
| `/profiles profile_id:… map_id:…` | Save preference for an already imported map | `view_status`, `import_skillmaps` |
| `/skills` | Saved skill count | `view_skills` |
| `/skillmap import file:…` | Validate attachment, preview, then confirm | `import_skillmaps` |
| `/skillmap export map_id:…` | Send canonical JSON attachment and SHA-256 | `export_skillmaps` |
| `/skillmap test map_id:…` | Queue governed read-only provider tasks | `test_skillmaps`, `run_task`, `providers.test` |
| `/apis` | List reviewed adapters | `view_providers` |
| `/apis provider_id:… enabled:…` | Change the Kingdom's shared provider setting | `view_providers`, `manage_providers` |
| `/tasks` | This identity's actual provider task statuses | `run_task` |

Responses are ephemeral and disable mentions. Signed requests use a five-minute
timestamp window, atomic replay rejection and bounded body parsing. Non-PING
requests receive an immediate deferred acknowledgement; command work and attachments
run afterward. Interaction tokens remain in memory for delivery, not in SQLite.
Attachment downloads are limited to public-DNS Discord attachment hosts over verified
TLS. Export does not require a testing grant; collecting local test evidence does.

## Portable map format

See `docs/examples/product-research.skillmap.json`, its safe YAML equivalent,
and `docs/portable-skillmap.schema.json`. Both formats represent the same strict
versioned model. Filename must be a plain `.json`, `.yaml` or `.yml` name; upload
limit is 256 KiB. Unknown fields, malformed UTF-8, duplicate keys, YAML tags,
anchors and aliases, secret-looking strings, executable-looking payloads,
paths, uploaded URLs and invalid identifiers are rejected. Maps cannot contain
permissions, tools or trust grants. A credential reference is an identifier,
never an actual credential; authenticated provider execution is unsupported.

Schema `1.0` includes `map_id`, requested `capabilities`, `skills`, `providers`,
`preferred_resources`, read-only `constraints`, descriptive `metadata` and bounded
`test_results`. Read-only must be literal true. Timeouts are 1–15 seconds and
at most ten providers may be requested per test batch. Defaults remain bounded.
Preview identifies known metadata checks, unsupported skills/capabilities,
credential requirements and currently eligible local workers. Confirmation is
identity-bound, checksum-bound, single-use and expires after five minutes.

Canonical export sorts semantic records and capability sets, excludes the
non-semantic creation timestamp, uses stable UTF-8 JSON and appends one newline.
The SHA-256 covers those exact bytes. Reimport produces the same canonical
content and hash. An imported `verified` result remains an untrusted portable
claim. Kingdom's results view uses only completed local tasks, their identity/map
binding and independently rechecked evidence. Merely importing a map never installs
a skill, activates a profile, provisions a model or grants a permission.

## Public API directory and test workflow

[Public APIs](https://github.com/public-apis/public-apis) is discovery information.
Refresh fetches its fixed README URL and saves bounded table metadata in the
existing ProviderRegistry repository. Its authentication/HTTPS claims are not a
security review. Catalog entries cannot supply executable endpoints or tools.
An unavailable or malformed refresh preserves the existing local catalog.

Only two reviewed adapters are currently implemented:

| Provider | Real fixed read-only check | What it proves |
| --- | --- | --- |
| Open Food Facts | Product barcode `3017620422003`, fields `code,product_name` | Public product metadata, not prices or a complete research workflow |
| Open-Meteo | Current temperature at latitude/longitude zero | Public weather metadata, not alerts or forecasting automation |

Both start disabled. The owner separately enables a provider and grants
`providers.test` to an installed local worker. Both worker security layers must
permit the action. A revoked, unhealthy or busy worker is ineligible. The requesting
identity also needs all three task/test grants. Runtime start, autonomy restrictions,
approval requirements and existing task policy still apply.

Transport permits HTTPS GET only, rejects local/private/link-local/multicast DNS,
pins the connection to a validated public address, verifies TLS hostname and
certificate, follows no redirects and bounds response bytes and read time.
The independently implemented verifier checks content type, provider-specific
schema, fixed request identity and exact response hash. Failed or malformed
responses never become verified skills. DNS resolution uses the operating system's
resolver; its latency is not an independently interruptible deadline.

The sample requests `product_research`, `price_comparison` and `web_search`.
Only the limited product-metadata check is supported. Map resource preferences rank currently eligible local workers first, followed by workers in the saved profile preference for that map. Unknown or unavailable resources are ignored; ranking never grants a permission or installs a worker.

The actual `product-research`
skill, price comparison, unrestricted web search, buying, remote/federated provider
workers, authenticated adapters and arbitrary uploaded endpoints are unsupported.
Choose **Test reviewed providers**, inspect **Tasks**, then **Collect results**
and **Export JSON**. An empty eligible-worker list is actionable information, not
a simulated successful test.

## Storage, presentation and troubleshooting

Idempotent initialization adds `integration_records(kind,id,value_json,updated_at)`
to Kingdom's existing SQLite database. It stores maps, previews, explicit settings,
profile preferences, task bindings, challenge hashes, links and replay IDs. Existing
tasks/memory/schema are preserved. No interaction body, bot token, webhook token
or provider credential is persisted. Do not share your whole database as evidence.

Worker details show the intersection of current grants in both active security layers. Model permission still requires a configured model provider; provider permission still requires an explicitly enabled service. Revoked workers show offline.

Normal worker cards, memory/task indexes, events and routing views show curated
summaries. Source input and generated text are deliberate task details; developer
diagnostics require explicit opt-in and redact common credential fields. A task
ID is not a source-code field. Earlier unsafe rendering included raw task prompts
as index headings and unrestricted event/result/provider records; this release
removes those normal-view paths and tests malicious caption values.

If Discord is disabled, check environment and restart. If Developer Portal PING
fails, check public HTTPS routing, public key and clock. If commands are absent,
register them for the correct application/guild. If access is denied, link the
actual invoking identity and review the specific grants. If import fails, use the
sample schema, plain filename and UTF-8. If no worker is available, check installed
profile, both permission layers, health and active tasks. If a public test fails,
check network/service availability; no success is fabricated. Only deployment-side
live testing can certify Discord connectivity.

## Repeatable verification

Run `python -m pytest`, `node --test frontend/tests/presentation.test.js apps/mobile/mobile-client.test.js`,
and the frontend production build. Native release CI additionally exercises the
frozen backend, bundled profile catalog, map roundtrip, desktop start, verified task,
runtime stop and a rendered dashboard screenshot on each supported x86_64 platform.
Mocks prove behavior and failure handling; they do not prove live Discord delivery.
Live public-service checks are recorded separately from mocked integration tests.
