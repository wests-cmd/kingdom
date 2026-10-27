# Kingdom development

## Source of truth

Run commands from the repository root. CI selects Python 3.12 and Node.js 24;
[`requirements-dev.txt`](../requirements-dev.txt) includes runtime requirements.
Frontend, desktop and companion package files have separate responsibilities.
[`AGENTS.md`](../AGENTS.md) describes project rules.

## Install and run

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

PowerShell activation is `venv\Scripts\Activate.ps1`; use your selected `python`
executable. Start from the same working directory on later runs to retain the
same `data/` state. No models are downloaded by these commands.

For frontend hot reload, keep the backend running and run
`npm --prefix frontend run dev` in a second terminal. It uses port 5173. When
needed set `VITE_API_URL=http://127.0.0.1:8000` in the frontend environment before
starting Vite. Allow only that frontend origin in backend `ALLOWED_ORIGINS`.
Do not use frontend environment variables for private owner/provider credentials.

## Verify

```bash
python -m pytest
node --test frontend/tests/*.test.js apps/mobile/mobile-client.test.js
python scripts/validate_version.py
```

Build assets before tests that exercise static routes. A fresh source run can
create local `data/`; use a disposable checkout for destructive test fixtures and
never point tests at a user's live state. Scripts and fixtures can have additional
platform/dependency requirements; a skipped test is not a verified capability.

## Package and change safely

The [release process](RELEASE_PROCESS.md) and
[verified-native workflow](../.github/workflows/release.yml)
own exact-version packaging and installer evidence. Electron's `desktop`
package needs its staged frozen backend; `npm --prefix desktop run build` alone
is not the full release pipeline. Do not rename source folders just to resemble
another project: keep imports, service commands and packaging paths stable.

Update the [architecture map](ARCHITECTURE.md), [operations guide](OPERATIONS.md)
and [status](PROJECT_STATUS.md) when interfaces, configuration or verification
change. Link detailed existing guides from the [index](README.md). Keep dated
reports as history and put current instructions in the appropriate guide.
