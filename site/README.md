# Kingdom public information site

Static HTML/CSS, independent of the authenticated Kingdom dashboard. No runtime
account, API, package install or build is needed. Open `index.html` locally to
preview it. Links point to the actual repository, current development docs and
release index; the site does not claim that development installers are published.

Cloudflare Pages setup after the owner creates and authorizes an account:

- Select this repository and the intended reviewed branch.
- Root directory: `site`.
- Framework preset: None.
- Build command: leave blank.
- Build output directory: `.`.
- Environment variables: none.

Alternatively, use Pages Direct Upload for this directory through the dashboard.
Do not upload the repository root or any credentials. `wrangler.jsonc` supports
an owner-authorized CLI deployment from this directory if preferred later.

Publishing requires a Cloudflare account; viewing the resulting static site
does not. Until that account exists this is prepared source, not a live URL.
No billing upgrade, backend proxy, sign-in, analytics, external assets, model
inference or data storage is configured. See `../docs/OPTIONAL_CLOUD.md` for the
separate authenticated frontend and optional service roadmap.
