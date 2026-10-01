# Kingdom

<img src="frontend/public/branding/kingdom-icon.png" alt="Kingdom crowned K" width="72">

A desktop command center for local workers, governed tasks and persistent knowledge. Start with the installer for your computer; **Python and Node.js are included, so you do not need to install them separately.**

**Current stable release: [Kingdom v1TAS · v1.1.1](https://github.com/wests-cmd/kingdom/releases/tag/v1.1.1)**

[Join the Kingdom Discord](https://discord.gg/4b8f9YS2Wp) · [All releases](https://github.com/wests-cmd/kingdom/releases) · [Report a problem](https://github.com/wests-cmd/kingdom/issues)

## Download Kingdom

Choose **one** installer that matches your computer. These are the published v1.1.1 files.

| Your computer | Download | What to do next |
| --- | --- | --- |
| **Windows — Intel/AMD 64-bit** | **[Download Windows installer](https://github.com/wests-cmd/kingdom/releases/download/v1.1.1/Kingdom-Setup-1.1.1.exe)** | Run `Kingdom-Setup-1.1.1.exe`, then open the Kingdom desktop shortcut. |
| **macOS — Intel** | **[Download Mac DMG](https://github.com/wests-cmd/kingdom/releases/download/v1.1.1/Kingdom-1.1.1.dmg)** | Open the DMG, drag Kingdom into Applications, then launch it. |
| **Linux — Intel/AMD 64-bit** | **[Download AppImage](https://github.com/wests-cmd/kingdom/releases/download/v1.1.1/Kingdom-1.1.1.AppImage)** | Allow the downloaded file to run as a program in its file properties, then open it. |
| **Ubuntu / Debian — amd64** | **[Download DEB package](https://github.com/wests-cmd/kingdom/releases/download/v1.1.1/kingdom-desktop_1.1.1_amd64.deb)** | Open it with your distribution's package installer, then launch Kingdom. |

**Before installing:** Windows and macOS builds are unsigned; the Mac build is not notarized. Your operating system may show a trust prompt. Native Apple Silicon, Windows ARM64, Linux ARM64, Android and iOS installers are **not supplied**. Mac DMG testing covers Intel Macs; Apple Silicon compatibility is not certified.

**Check your download:** [SHA256SUMS](https://github.com/wests-cmd/kingdom/releases/download/v1.1.1/SHA256SUMS) and [release manifest](https://github.com/wests-cmd/kingdom/releases/download/v1.1.1/release-manifest.json) list the exact files and hashes. The [release page](https://github.com/wests-cmd/kingdom/releases/tag/v1.1.1) also contains native startup evidence and screenshots. Choose an installer above rather than GitHub's “Source code” archive or a standalone backend file.

## Your first five minutes

1. Open Kingdom and follow the setup wizard. It inspects your computer and offers Developer, Research, Full Swarm, Server and Custom profiles.
2. Choose the workers you need. Desktop mode opens the command center and signs in to its own bundled backend automatically. Server mode runs without the desktop window.
3. Open **Runtime** and start the runtime when you are ready to process work.
4. In **Tasks**, choose **Analyze text**, enter a short piece of text and submit it. Check the completed result. Python syntax checks are also available without a cloud account.
5. Open **Settings** to choose a palette or custom color, light/dark/device mode, spacing, display size, motion and castle background strength. These choices save on this device.

AI text generation needs a configured model provider. Joining Discord, selecting a profile or importing a skill map does not configure a model or grant new permissions. A generated answer is not proof that an external action occurred. Broker connections, live market data and trade execution are unavailable.

### Already have Kingdom?

Close Kingdom, check the new installer's hash, and run the matching installer. Keep your existing per-user data and `local_profile.json`; do not delete them to update. Native desktop updates use these installers—automatic in-place desktop updates are not provided. Back up your data before an upgrade. If you need to re-run setup, close the app and keep a backup of your profile before changing it.

## Connect a phone or another device

Open **Devices & Knowledge** or **Nodes & Cluster → Connect a phone / device**. Enter a trusted HTTPS Kingdom address that both devices can reach, create a single-use code, and scan the QR or open `/#/connect` and enter the code. Approve the request in **Pending Approvals**. Codes expire after five minutes.

`localhost` on a phone refers to the phone, not your PC. Desktop loopback alone cannot connect another device. The browser companion is a limited pairing/status connection; it does not receive owner or task-execution authority. [Read the device connection guide](docs/device-connections.md).

## Kingdom Discord

**[Join Kingdom's server](https://discord.gg/4b8f9YS2Wp)** for the community. For installation problems, include your Kingdom version, operating system and exact error, with credentials and private data removed. Track reproducible bugs in [GitHub Issues](https://github.com/wests-cmd/kingdom/issues).

The server's **Kingdom Centipede Skill Bot** provides documentation lookup with `/commands`, `/ask`, `/search`, `/sources`, `/projectinfo`, `/compare` and `/exportknowledge`. `/aiask` produces a local AI draft for review. Administrators can teach private notes using `/teach` in **bot-knowledge**; ordinary chat is not automatically learned. Private notes do not feed public answers, and teaching does not retrain a model or execute desktop tasks.

The desktop's **optional runtime slash-command adapter** is a separate integration and starts disabled. When an operator configures it, `/help` lists its commands and `/kingdom` requests an owner-confirmed linking code. Joining the community server never grants desktop permissions. Server administrator status does not grant Kingdom authority. Never post an owner access code, bot token, private linking code or API key in a public channel.

[Bot setup and permissions](docs/DISCORD_SKILLMAPS.md) · [Community FAQ and live bot test checklist](docs/COMMUNITY_GUIDE.md)

## What Kingdom can do

- Manage installed local workers and persist tasks, memory and activity in SQLite.
- Apply human approvals and deny-by-default capability permissions; enforce task autonomy through **Governance**.
- Import JSON/YAML skill maps with preview, owner confirmation, canonical export and SHA-256. Maps are preferences, not executable code or permission grants.
- Run explicitly enabled, bounded, read-only Open Food Facts and Open-Meteo checks through authorized workers. Public API directory entries are discovery metadata, not verified adapters.

[Runtime controls and limitations](docs/runtime-controls.md) · [Portable maps and providers](docs/DISCORD_SKILLMAPS.md) · [Appearance and artwork](docs/BRANDING.md)

## Developers and server operators

Desktop users can skip this section. Source development uses Python 3.12 and Node.js 24 in CI.

```bash
git clone https://github.com/wests-cmd/kingdom.git
cd kingdom
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

For Windows PowerShell, activate the environment with `venv\Scripts\Activate.ps1`. For a production frontend build, use `npm --prefix frontend run build`. The repository also supplies `scripts/install.sh` and Docker configuration for operators.

Server administrative APIs require the private `data/owner-token` or `KINGDOM_OWNER_TOKEN`. Keep credentials in the credential broker/process environment; do not put them in tasks or maps. Configure only the network access you need. `.env.example` is a template, and `configs/install_profiles.json` supplies the install profile catalog. Optional Discord deployment requires the signed public callback described in [its setup guide](docs/DISCORD_SKILLMAPS.md); a private Tailscale address cannot receive Discord callbacks.

## License

Kingdom uses the custom [CYA License v2.0](LICENSE). Read the [license](LICENSE) and [commercial-use policy](COMMERCIAL_USE.md) before commercial use.
