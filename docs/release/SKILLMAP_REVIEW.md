# v1.1.0 integration review

## 1. Architecture and source-display review

Reviewed the task engine, Swarm/Knights, ZeroTrust and capability registry,
HTTP owner authentication, skills lifecycle/map, ProviderRegistry, SQLite,
native packaging, SDK/mobile scaffold and normal frontend record views.
The new adapters share these services and store integration records in the existing
database. There is no separate Discord execution engine or permission authority.

The historical online-Knight source-code incident was not independently reproduced.
`BaseKnight.current_task` normally contains a task ID. The confirmed defect was
unrestricted presentation: worker activity/capability fields were printed directly,
intelligence indexes used raw task prompts or memory content as headings, and
event, routing and task views printed whole internal records. Worker permissions are derived from both current active security layers rather than role declarations; revoked workers show offline, and a model permission is distinguished from configured-provider availability. Curated worker DTOs,
allowlisted device captions, generic record headings, task result summaries and
explicit redacted developer details remove these paths. Audit prompt snippets are
replaced by lengths. Do not describe a task ID as executable source.

## 2. Authorization and transport review

Confirmed owner-protected integration APIs with explicit typed public response schemas, safe grant/revocation events, explicit Discord link grants,
hashed five-minute single-use challenges, identity/checksum-bound import
confirmation, signature freshness, application/server binding, atomic replay
rejection and deferred command acknowledgement. Empty Discord grants remain empty;
guild administration is irrelevant to Kingdom authorization. Revocation and
restart hydration use the existing node security manager.

Reviewed HTTPS-only fixed provider/CDN endpoints, public-DNS pinning, TLS
verification, no redirects, response bounds, timeouts, disabled-by-default
providers and independent provider schema/hash checks. Imported evidence is a
claim; collection uses actual local governed task records and re-verifies them.
Rejected request validation omits raw inputs. Webhook continuation tokens are
redacted from HTTP logs and never persisted. Remote provider workers and
authenticated provider execution remain unsupported. DNS uses the OS resolver.

## 3. Schema and failure-path review

Checked strict versioned JSON/safe YAML, byte limits, duplicate keys, aliases/tags,
literal read-only enforcement, secret/executable/endpoint rejection, unique IDs,
declared provider references, bounded metadata/evidence and deterministic export.
Controlled tests cover tampering, expired/reused previews and challenges, denied
grants, malformed/timeout/MIME/schema responses, replayed signatures, arbitrary
attachment URLs, private/mixed/multicast DNS, and unavailable/revoked/busy workers.
Discord import-preview-button-confirm-export uses mocked transport and real shared
services; this proves code behavior, not a deployed Discord connection.

## 4. User workflow review

The isolated owner browser flow imports the sample, accurately shows unsupported
price comparison/web search/skill installation, refuses a test without an eligible
worker, executes a real enabled provider through a local Knight, collects evidence,
downloads canonical JSON, saves a real profile preference, survives restart and
reimports identical bytes. A download check found browser duplicate suffixes were
rejected; bounded plain names with spaces/parentheses now work without allowing
paths. Normal views keep developer diagnostics off by default. Phone-width checks
use the actual browser viewport; they do not certify a physical phone application.

## 5. Build, dependency and release review

Version authority and package roots use 1.1.0; the existing Centipede v1TAS/1.4.0
contract and `kingdom.cluster.v1` protocol remain intact. A CI clean install caught
a dependency lockfile version accidentally changed during the release bump.
Dependency records were restored from main; only package-root versions changed.
Clean frontend/desktop installs and production build passed afterward.

Local final validation: `python -m pytest -q` **287 passed**;
`node --test frontend/tests/presentation.test.js apps/mobile/mobile-client.test.js`
**3 passed**; frontend production build, version validator and syntax/diff checks
passed. The one backend warning is Starlette's httpx TestClient deprecation.
Live Open Food Facts and Open-Meteo metadata checks returned HTTP 200 with
public-DNS/TLS/schema/hash verification and canonical roundtrip. Public APIs
refresh recorded 1,762 discovery entries. DummyJSON was removed because its
placeholder products cannot prove real product metadata.

Native CI must pass on Linux, Windows and Intel macOS before merging/publishing.
Its smoke now verifies bundled profile data and portable-map roundtrip, a real
desktop task, start/stop and dashboard rendering before evidence capture. Release
publication verifies staged and downloaded bytes, manifest/hash agreement, tag
source and main source, and refuses replacement of published assets. Native
Apple Silicon/ARM64/mobile builds, signing, notarization and automatic desktop
upgrades are not claimed.

**CODE VERIFIED / LIVE DISCORD CONNECTION NOT VERIFIED.** No credentials,
public callback deployment or live test Discord server were supplied. Public
provider verification does not establish live Discord delivery. Deployment setup
and a real slash-command/link/import/test/export pass remain external work.
