# Kingdom

## Overview

Kingdom is a standalone web and desktop command center for models, Apprentices,
governed tasks, shared knowledge and approved Knight computers. Its direction is
plan → place → execute → verify → remember → adapt. A connected computer or an
AI answer is not proof that a task completed.

**Published native release: [v1.2.4](https://github.com/wests-cmd/kingdom/releases/tag/v1.2.4)**
(release listing checked October 27, 2026). Source branches and locally patched
installations can differ; see [project status](docs/PROJECT_STATUS.md).

<img src="frontend/public/branding/kingdom-icon.png" alt="Kingdom crowned K" width="72">

### Install the desktop app

Choose one matching installer; native packages include their runtime.

| Computer | Published v1.2.4 download |
| --- | --- |
| Windows Intel/AMD 64-bit | [Kingdom-Setup-1.2.4.exe](https://github.com/wests-cmd/kingdom/releases/download/v1.2.4/Kingdom-Setup-1.2.4.exe) |
| macOS Intel | [Kingdom-1.2.4.dmg](https://github.com/wests-cmd/kingdom/releases/download/v1.2.4/Kingdom-1.2.4.dmg) |
| Linux Intel/AMD 64-bit | [Kingdom-1.2.4.AppImage](https://github.com/wests-cmd/kingdom/releases/download/v1.2.4/Kingdom-1.2.4.AppImage) |
| Debian/Ubuntu amd64 | [kingdom-desktop_1.2.4_amd64.deb](https://github.com/wests-cmd/kingdom/releases/download/v1.2.4/kingdom-desktop_1.2.4_amd64.deb) |

Check [SHA256SUMS](https://github.com/wests-cmd/kingdom/releases/download/v1.2.4/SHA256SUMS)
and the [release manifest](https://github.com/wests-cmd/kingdom/releases/download/v1.2.4/release-manifest.json).
Windows/macOS packages are unsigned; macOS is not notarized. Native ARM64,
Android and iOS release installers are not supplied by this release. Operating
system protections remain in force. The [browser app](docs/FREE_WEB_APP.md) is a
separate option that needs a running reachable server.

Open the app, complete setup, choose a profile, start Runtime, then submit
**Tasks → Analyze text** and inspect its actual result. AI generation needs a
configured provider. An optional opening passcode starts disabled; remote access
still needs its own authentication. [Mission guide](docs/MISSION_WORKSPACE.md).

## Project map

| Piece | Authoritative files | Role |
| --- | --- | --- |
| Web interface | [frontend](frontend), [Vite configuration](frontend/vite.config.js) | React UI; development port 5173; built assets served by the backend |
| API and runtime | [backend/main.py](backend/main.py), [backend/api.py](backend/api.py), [runtime](backend/runtime) | FastAPI, scheduling, policy, tasks and SQLite evidence |
| Connected computers | [backend/cluster](backend/cluster) | Signed peer communication, approvals, capabilities and leases |
| Desktop shell | [desktop](desktop) | Electron wrapper around the bundled loopback backend |
| Companion clients | [apps/mobile](apps/mobile) | Separate web/native companion source and pairing flows |
| Packaging and checks | [scripts](scripts), [.github/workflows](.github/workflows), [tests](tests) | Builds, validation, release and regression evidence |

See [architecture](docs/ARCHITECTURE.md) for request flow and boundaries. Runtime
layout and existing imports stay intact; documentation navigation is the common
entry point rather than a second application tree.

## Run locally

Source development uses Python 3.12 and Node.js 24, matching CI. From the repo root:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. In PowerShell, use `python` and activate with
`venv\Scripts\Activate.ps1` instead. Build the frontend **before** starting the
backend so its static routes find `frontend/dist`. The working directory owns
the source-run `data/` directory. [Development guide](docs/DEVELOPMENT.md) covers
the optional separate Vite server and desktop packaging prerequisites.

## Configuration

The backend reads process environment; copying [.env.example](.env.example)
does not establish that a launcher loads it. Source administrative requests use
`data/owner-token` or `KINGDOM_OWNER_TOKEN`. Keep these private and outside tasks,
maps, source control and public chats. `ALLOWED_ORIGINS` controls browser origins;
frontend development can use `VITE_API_URL` for an explicitly selected backend.
Provider selection, existing grants and autonomy are separate controls.
[Operations and configuration](docs/OPERATIONS.md).

## Verification

Documentation navigation: `python scripts/check_docs.py` (Python 3 standard library). CI checks the same local targets and required README sections; it does not check external URLs or prove runtime completion.

With development dependencies installed and web assets built:

```bash
python -m pytest
node --test frontend/tests/*.test.js apps/mobile/mobile-client.test.js
python scripts/validate_version.py
```

These commands do not prove physical-device connectivity or installed updates.
Use the [cluster shipping checklist](docs/CLUSTER_SHIPPING_CHECKLIST.md) and
[release process](docs/RELEASE_PROCESS.md) for those separate gates.

## Operations and updates

Windows v1.2.1+ exposes **Settings → Desktop updates**. macOS/Linux use their
matching package. Back up data before updates; verify the exact installed source
and rollback path. Publishing a release does not update every Knight.
[Operations](docs/OPERATIONS.md), [containers](docs/docker-cluster.md),
[vault/device layout](docs/VAULT_AND_DEVICE_LAYOUT.md).

## Integrations

[Centipede OS](https://github.com/wests-cmd/Centipede-os) is a separate application
and OS-image project. Configure its connection explicitly; installing either
product does not install, trust or authorize the other. Models, CLI harnesses,
Discord adapters, public APIs and portable skill maps are optional integrations.
Maps and community membership grant no execution authority.
[Integration boundaries](docs/ARCHITECTURE.md#integrations).

For another device, use a reachable trusted HTTPS server, create a single-use
pairing code and approve it. `localhost` on a phone refers to the phone.
[Device connections](docs/device-connections.md).

## Status and roadmap

The published release supports bounded governed work, programmes, scoped peer
reports and analysis tools. General autonomous repository coding, automatic
installation on every Knight, universal self-repair and broad hardware support
remain separate acceptance work. [Current status](docs/PROJECT_STATUS.md),
[architecture direction](docs/ADAPTIVE_CLUSTER_CORE.md), [roadmap](docs/HARNESS_ROADMAP.md).

## Documentation

Start at the [documentation index](docs/README.md): setup, development,
operations, integration, verification and historical reports have separate homes.
Use [GitHub Issues](https://github.com/wests-cmd/kingdom/issues) for reproducible
bugs and [Kingdom Discord](https://discord.gg/4b8f9YS2Wp) for community help.
Never post credentials or private linking codes. [Community guide](docs/COMMUNITY_GUIDE.md).

## License

Read the [CYA License v2.0](LICENSE) and [commercial-use policy](COMMERCIAL_USE.md).
