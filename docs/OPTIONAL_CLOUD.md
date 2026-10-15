# Optional cloud services

Kingdom remains a local adaptive harness: models, tools, cluster execution and
the authoritative SQLite database run on the owner's server. Cloud accounts are
optional. No service in this document has been provisioned by this change.

## Cloudflare Pages: prepared static frontend

The Vite UI can be built for Pages; it does **not** include the Python backend,
models, persistent jobs, credentials or SQLite. An existing backend must remain
reachable from each user's browser. A private Tailscale backend still requires
that user's tailnet access; hosting the UI does not make that backend public.

Pages Git build settings:

- Root directory: `frontend`
- Build command: `npm ci && npm run build`
- Output directory: `dist`
- Optional public build variable: `VITE_API_URL=https://api.kingdom.example`

`frontend/wrangler.jsonc` also declares the Pages output directory for an
owner-authorized CLI deployment after building. Wrangler is not a runtime
dependency, and deployment requires the owner's Cloudflare account access.
No automatic publishing workflow or paid plan is configured.

Set the backend's `ALLOWED_ORIGINS` to the exact trusted frontend HTTPS origin
(plus any existing required local origins), without wildcard or spaces. Restart
the backend through its normal deployment process. Never embed the owner token,
database URL, R2 keys, Resend key or Clerk secret in `VITE_*`: Vite publishes those
values to every browser. The URL is public configuration, not authentication.

### Authentication boundary and release check

Existing owner HTTP requests use the in-memory access code or HTTP-only cookie;
the WebSocket requires the existing HTTP-only `SameSite=strict` session cookie.
An unrelated `pages.dev` site and `*.ts.net` backend are cross-site. CORS alone
does not make that cookie available, so this combination is **not a verified
full hosted dashboard**. Do not weaken the cookie or put tokens in WebSocket URLs.

For a full static deployment, use HTTPS frontend/backend subdomains of the same
owner-controlled site, explicitly allow the frontend origin, and verify login,
authenticated WebSocket updates, task creation, artifact downloads and device
pairing in a real browser. Owning/configuring a custom domain may cost money.
Until that test passes, the free supported full UI remains the frontend served
directly by the existing Kingdom backend. Pages can still host public docs.
The API, WebSocket and companion pairing now share one endpoint configuration.

## Optional integrations backlog (not implemented)

| Provider | Proposed responsibility | Boundary before enabling |
| --- | --- | --- |
| Neon | Exported task metadata / optional shared search | Add explicit export adapter and deletion policy. SQLite stays authoritative; no silent database migration or cloud upload. |
| Clerk | Optional multi-user hosted identity | Map verified server-side identity to Kingdom roles. A Clerk login must never automatically grant owner or tool execution authority. |
| Resend | Opt-in job completion / recovery emails | Add server-side secrets, recipient consent, deduplication and daily/monthly send caps. No email credentials in frontend. |
| R2 | Opt-in reports and release artifacts | Add bounded upload adapter, private access, retention, checksums and storage/request caps. Large models must not upload automatically. |

Planning baseline checked October 15, 2026 (recheck at account setup):

| Service | Advertised free allowance used for planning |
| --- | --- |
| Pages | 500 builds/month; 25 MiB per asset |
| Neon | 1 GB database storage and 100 compute-unit hours/month per project |
| Clerk | 50,000 monthly retained users |
| Resend | 3,000 emails/month and 100/day |
| R2 Standard | 10 GB-month storage; 1 million Class A and 10 million Class B operations/month; direct egress free |

Use free plans only after checking current account-specific quotas at setup.
Free allowances and billing rules can change; these figures are not an account
entitlement. Configure an application-side stop before any limit,
disable fallback to paid services, and require owner action for upgrades. Those
application caps are still backlog work, not an implemented guarantee against
provider charges; not every provider offers a hard spending limit.
Accounts and credentials are necessary for these integrations; local use needs none.

Official limits and setup references:
[Pages](https://developers.cloudflare.com/pages/platform/limits/),
[Neon](https://neon.com/pricing), [Clerk](https://clerk.com/pricing),
[Resend](https://resend.com/pricing),
[R2](https://developers.cloudflare.com/r2/pricing/).

## Acceptance checklist before publishing

1. Build with no `VITE_API_URL` and verify the existing local backend UI.
2. Build with the intended public HTTPS backend origin; confirm no secrets exist
   in the bundle and no localhost endpoint is used in the production build.
3. Verify CORS rejects an unrelated origin and unauthenticated control requests
   remain rejected. Confirm same-site authenticated WebSocket events in-browser.
4. Confirm the backend's existing SQLite task history and approval gates remain
   unchanged. Keep the previous local UI available for rollback.
5. Publish only after the owner has configured the account/domain and those
   deployment checks pass. A successful static build alone does not pass them.
