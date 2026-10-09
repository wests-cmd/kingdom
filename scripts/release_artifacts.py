"""Stage and verify a closed inventory of native installers and build evidence."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.security.capabilities import ALL_CAPABILITIES
from backend.system.compatibility import (
    CENTIPEDE_API_CONTRACT_VERSION,
    CENTIPEDE_PROTOCOL,
    KINGDOM_PRODUCT_VERSION,
)

INVENTORY = {
    "linux": ["Kingdom-{version}.AppImage", "kingdom-desktop_{version}_amd64.deb", "kingdom-backend-linux-x86_64"],
    "windows": ["Kingdom-Setup-{version}.exe", "kingdom-backend-windows-x86_64.exe"],
    "macos": ["Kingdom-{version}.dmg", "kingdom-backend-macos-x86_64"],
}


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify_accessibility_evidence(evidence, version):
    matched = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-[a-zA-Z0-9.]+)?', version)
    if not matched:
        raise ValueError('Invalid release evidence version')
    if tuple(map(int, matched.groups())) < (1, 1, 2):
        return  # Older published releases predate this acceptance gate.
    required = {
        'appearance': ('logoLoaded','lightModeApplied','persistedAfterReload','resetVerified'),
        'accessibility': ('highContrastApplied','scale200Applied','noHorizontalOverflow','ownerPreferencesSaved','persistedAfterReload'),
    }
    for group, checks in required.items():
        data = evidence.get(group)
        if not isinstance(data, dict) or any(data.get(check) is not True for check in checks):
            raise RuntimeError(f'Native {group} evidence incomplete')


def stage(platform, version, commit):
    destination = Path("release_staging")
    destination.mkdir(exist_ok=True)
    if platform == 'linux' and tuple(map(int,version.split('.')[:3])) >= (1,2,0):
        from scripts.build_ui_component import build
        compatibility=json.loads(Path('frontend/ui-compatibility.json').read_text())['compatible_backends']
        build('frontend/dist',destination/f'Kingdom-UI-{version}.zip',version,compatibility)
    filenames = [item.format(version=version) for item in INVENTORY[platform]]
    for name in filenames:
        source = (Path("desktop/bin") / ("kingdom-backend.exe" if platform == "windows" else "kingdom-backend")) if name.startswith("kingdom-backend-") else Path("desktop/dist") / name
        if not source.is_file() or source.stat().st_size == 0:
            raise RuntimeError(f"Required artifact missing: {source}")
        shutil.copy2(source, destination / name)
    for kind in ("backend", "desktop", "dependencies"):
        source = Path("evidence") / f"{kind}.json"
        evidence = json.loads(source.read_text())
        expected_platform = {"linux": "linux", "windows": "win32", "macos": "darwin"}[platform]
        if evidence.get("platform") != expected_platform:
            raise RuntimeError("Smoke evidence platform mismatch")
        if evidence.get("version") != version:
            raise RuntimeError("Smoke evidence version mismatch")
        if kind == "desktop" and not all(evidence.get(key) for key in ("dashboardLoaded", "profilePersisted", "catalogLoaded", "realtimeConnected", "runtimeStarted", "runtimeStopped", "taskExecuted")):
            raise RuntimeError("Desktop smoke evidence incomplete")
        if kind == "desktop" and (evidence["taskExecuted"].get("words") != 3 or evidence["taskExecuted"].get("verification") != "VERIFIED"):
            raise RuntimeError("Native task outcome evidence incomplete")
        if kind == "desktop" and evidence.get("arch") != "x64":
            raise RuntimeError("Smoke evidence architecture mismatch")
        if kind == "desktop":
            verify_accessibility_evidence(evidence, version)
        if kind == "backend" and not evidence.get("frontend_served"):
            raise RuntimeError("Backend smoke evidence incomplete")
        if kind == "dependencies" and (not evidence.get("audited") or evidence.get("findings")
                                      or evidence.get("cryptography") != "50.0.2"):
            raise RuntimeError("Dependency audit evidence incomplete")
        shutil.copy2(source, destination / f"{platform}-{kind}-evidence.json")
    shutil.copy2(Path("evidence/desktop.png"), destination / f"{platform}-desktop.png")
    if tuple(map(int,version.split('.')[:3])) >= (1,2,0):
        for name in ('mission-workspace','governance'):
            shutil.copy2(Path('evidence')/f'{name}.png',destination/f'{platform}-{name}.png')
        if not all(json.loads((destination/f'{platform}-desktop-evidence.json').read_text()).get('missionWorkspace',{}).get(key) is True
                   for key in ('fiveLevels','largeEditor','attachmentRoundtrip','missionVerified')):
            raise RuntimeError('Native mission workspace evidence is incomplete')
    artifacts = [{"filename": name, "size": (destination / name).stat().st_size,
                  "sha256": digest(destination / name), "platform": platform, "arch": "x86_64"}
                 for name in sorted(p.name for p in destination.iterdir())]
    manifest = {"version": version, "tag": f"v{version}", "commit": commit,
                "platform": platform, "artifacts": artifacts}
    (destination / f"{platform}-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def verify(directory, version, commit):
    artifacts = []
    for platform, templates in INVENTORY.items():
        manifest_path = directory / f"{platform}-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["version"] == version and manifest["commit"] == commit
        assert manifest["platform"] == platform and manifest["tag"] == f"v{version}"
        names = {item["filename"] for item in manifest["artifacts"]}
        assert {name.format(version=version) for name in templates} <= names
        desktop_evidence = json.loads((directory / f'{platform}-desktop-evidence.json').read_text())
        assert desktop_evidence.get('version') == version
        assert desktop_evidence.get('platform') == {'linux':'linux','windows':'win32','macos':'darwin'}[platform]
        verify_accessibility_evidence(desktop_evidence, version)
        for artifact in manifest["artifacts"]:
            name = artifact["filename"]
            assert Path(name).name == name and name not in {".", ".."}
            path = directory / name
            assert path.is_file() and path.stat().st_size == artifact["size"] > 0
            assert digest(path) == artifact["sha256"], name
            artifacts.append(artifact)
    expected = {a["filename"] for a in artifacts} | {f"{p}-manifest.json" for p in INVENTORY}
    if tuple(map(int,version.split('.')[:3])) >= (1,2,0):
        assert f'Kingdom-UI-{version}.zip' in expected, 'UI component package missing'
    assert {p.name for p in directory.iterdir()} == expected, "Unexpected or duplicate staging files"
    release = {"product": "Kingdom", "release_name": "Kingdom v1TAS",
               "version": KINGDOM_PRODUCT_VERSION, "release_version": version,
               "kingdom_version": version,
               "contract_version": CENTIPEDE_API_CONTRACT_VERSION,
               "protocol": dict(CENTIPEDE_PROTOCOL),
               "protocol_version": "kingdom.cluster.v1",
               "capabilities": sorted(ALL_CAPABILITIES),
               "tag": f"v{version}", "commit": commit, "release_channel": "stable",
               "artifacts": artifacts, "limitations": ["Windows installers are unsigned.",
               "macOS Intel build is unsigned and not notarized; Apple Silicon native build is not supplied."]}
    (directory / "release-manifest.json").write_text(json.dumps(release, indent=2) + "\n")
    checksums = "".join(f"{digest(p)}  {p.name}\n" for p in sorted(directory.iterdir()) if p.is_file())
    (directory / "SHA256SUMS").write_text(checksums)
    notes = f"""Kingdom v1TAS (v{version})

Source commit: `{commit}`

Verified native x86_64 installers: Linux AppImage and DEB, Windows NSIS, macOS Intel DMG. Each platform builds its own bundled backend; Python and Node.js are not required on the user's machine.

Every build passes the backend test suite, a frozen backend startup/readiness and frontend check, and a packaged desktop first-run setup/profile persistence/dashboard check that submits a real text-analysis task through the UI and verifies its result. Platform evidence and screenshots are attached. These checks establish the documented release gate; they are not exhaustive hardware compatibility testing.

Administrative APIs and live connections require owner authentication. Worker results are signed and bound to exact active leases. Approvals persist, expire, and can be consumed only once for the exact authorized operation. Supported tasks execute bounded text/Python analysis; AI text generation requires a configured model provider and never proves external actions occurred. Broker connection, live market data, and trade execution are unavailable. Desktop upgrades use these verified installers; automatic in-place desktop upgrades are not provided.

Windows installers are unsigned. The macOS Intel installer is unsigned and not notarized; a native Apple Silicon installer is not supplied. OS trust prompts may apply. No signing or notarization claim is made.

This patch adds the user-selected crowned K desktop icon and purple citadel artwork, with working device-local appearance settings: five palettes, custom accent, light/dark/device color mode, spacing, display size, reduced motion, background intensity and reset. Accent text and buttons adjust contrast automatically. Preferences persist on this browser or desktop installation.

This release adds a restrained interface, live recorded activity, persisted and enforced L0-L3 task autonomy, actual runtime polling modes, and cancellation of pending task approvals. Static sample topology and unsupported autonomy/mode cards are removed.

This release fixes knowledge text ingestion, draft skill teaching, worker identity displays, memory listing, task failure explanations, and log filters/timestamps. Device connections support single-use codes and locally generated QR links to a reachable HTTPS server. Browser companions require owner approval and do not gain owner/task authority; native mobile packages remain unavailable.

Portable JSON/YAML skill maps support strict import, preview, owner confirmation and canonical export with SHA-256. Public APIs is untrusted discovery metadata. Explicitly enabled Open Food Facts and Open-Meteo adapters run bounded read-only checks through permissioned local Knights and independent schema/hash verification. Pricing, unrestricted web search, authenticated provider adapters and arbitrary uploaded endpoints are unsupported. Discord is opt-in and disabled by default; its signed adapter and linking workflow are code-tested, but a live Discord connection has not been verified. Follow docs/DISCORD_SKILLMAPS.md for setup and deployment requirements.

Verify downloaded files with `sha256sum -c SHA256SUMS` (or compare SHA-256 using your platform's tools). Exact filenames, sizes, hashes, platforms, and source commit are recorded in `release-manifest.json`.
"""
    Path("release-notes.md").write_text(notes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["stage", "verify"])
    parser.add_argument("--platform", choices=list(INVENTORY))
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--directory", type=Path, default=Path("release_staging"))
    args = parser.parse_args()
    if args.command == "stage":
        stage(args.platform, args.version, args.commit)
    else:
        verify(args.directory, args.version, args.commit)
