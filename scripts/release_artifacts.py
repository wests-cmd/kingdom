"""Stage and verify a closed inventory of native installers and build evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

INVENTORY = {
    "linux": ["Kingdom-{version}.AppImage", "kingdom-desktop_{version}_amd64.deb", "kingdom-backend-linux-x86_64"],
    "windows": ["Kingdom-Setup-{version}.exe", "kingdom-backend-windows-x86_64.exe"],
    "macos": ["Kingdom-{version}.dmg", "kingdom-backend-macos-x86_64"],
}


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def stage(platform, version, commit):
    destination = Path("release_staging")
    destination.mkdir(exist_ok=True)
    filenames = [item.format(version=version) for item in INVENTORY[platform]]
    for name in filenames:
        source = (Path("desktop/bin") / ("kingdom-backend.exe" if platform == "windows" else "kingdom-backend")) if name.startswith("kingdom-backend-") else Path("desktop/dist") / name
        if not source.is_file() or source.stat().st_size == 0:
            raise RuntimeError(f"Required artifact missing: {source}")
        shutil.copy2(source, destination / name)
    for kind in ("backend", "desktop"):
        source = Path("evidence") / f"{kind}.json"
        evidence = json.loads(source.read_text())
        if evidence.get("version") != version:
            raise RuntimeError("Smoke evidence version mismatch")
        if kind == "desktop" and not all(evidence.get(key) for key in ("dashboardLoaded", "profilePersisted", "catalogLoaded")):
            raise RuntimeError("Desktop smoke evidence incomplete")
        if kind == "backend" and not evidence.get("frontend_served"):
            raise RuntimeError("Backend smoke evidence incomplete")
        shutil.copy2(source, destination / f"{platform}-{kind}-evidence.json")
    shutil.copy2(Path("evidence/desktop.png"), destination / f"{platform}-desktop.png")
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
        for artifact in manifest["artifacts"]:
            name = artifact["filename"]
            assert Path(name).name == name and name not in {".", ".."}
            path = directory / name
            assert path.is_file() and path.stat().st_size == artifact["size"] > 0
            assert digest(path) == artifact["sha256"], name
            artifacts.append(artifact)
    expected = {a["filename"] for a in artifacts} | {f"{p}-manifest.json" for p in INVENTORY}
    assert {p.name for p in directory.iterdir()} == expected, "Unexpected or duplicate staging files"
    release = {"product": "Kingdom", "release_name": "Kingdom v1TAS", "version": version,
               "tag": f"v{version}", "commit": commit, "release_channel": "stable",
               "artifacts": artifacts, "limitations": ["Windows installers are unsigned.",
               "macOS Intel build is unsigned and not notarized; Apple Silicon native build is not supplied."]}
    (directory / "release-manifest.json").write_text(json.dumps(release, indent=2) + "\n")
    checksums = "".join(f"{digest(p)}  {p.name}\n" for p in sorted(directory.iterdir()) if p.is_file())
    (directory / "SHA256SUMS").write_text(checksums)
    notes = f"""Kingdom v1TAS (v{version})

Source commit: `{commit}`

Verified native x86_64 installers: Linux AppImage and DEB, Windows NSIS, macOS Intel DMG. Each platform builds its own bundled backend; Python and Node.js are not required on the user's machine.

Every build passes the backend test suite, a frozen backend startup/readiness and frontend check, and a packaged desktop first-run setup/profile persistence/dashboard check. Platform evidence and screenshots are attached. These checks establish the documented release gate; they are not exhaustive hardware compatibility testing.

Windows installers are unsigned. The macOS Intel installer is unsigned and not notarized; a native Apple Silicon installer is not supplied. OS trust prompts may apply. No signing or notarization claim is made.

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
