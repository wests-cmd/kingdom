"""Offline, fail-closed pre-install audit for explicitly named 2026 compromised packages.

Runs before pip/npm: installing a .pth-based Python stealer merely to audit it
can already expose secrets. Not a general malware scanner or sandbox proof.
"""
import argparse
from importlib import metadata
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ("requirements.txt", "requirements-dev.txt", "requirements-release.txt")
NPM = ("desktop/package.json", "frontend/package.json", "apps/mobile/native/package.json")
LOCKS = ("desktop/package-lock.json", "frontend/package-lock.json", "apps/mobile/native/package-lock.json")
WATCHED = ("agent-framework", "mcp-server-git", "mcp-gateway-registry", "mem0-mcp-server")


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+){1,3}", value):
        return None
    return tuple(int(p) for p in value.split("."))


def risk(name, version, ecosystem):
    name = normalize(name)
    if ecosystem == "npm" and name == "mem0-mcp-server":
        return "All published npm mem0-mcp-server versions are malicious"
    if ecosystem == "PyPI" and name == "agent-framework":
        if version in {"1.26.1", "1.26.2"}:
            return "PyPI agent-framework credential stealer"
        if version is None:
            return "Unpinned agent-framework can resolve to a compromised version"
    if ecosystem == "PyPI" and name == "mcp-server-git":
        v = version_tuple(version)
        if v is None or v < (2026, 11, 18):
            return "Git repository command execution: require exact >=2026.11.18"
    if name == "mcp-gateway-registry":
        v = version_tuple(version)
        if v is None or v < (1, 35, 0):
            return "MCP registry privilege/SSRF fixes require exact >=1.35.0"
    return None


def requirement_entries(path, seen, root):
    path = path.resolve()
    if path in seen:
        return
    seen.add(path)
    if not path.is_file() or not path.is_relative_to(root):
        raise ValueError("Missing or out-of-root requirements file: " + str(path))
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        original = line.strip()
        if not original or original.startswith("#"):
            continue
        # A VCS/editable requirement can hide its normalized name behind #egg.
        # Do not execute or attempt to resolve such a dependency during audit.
        if original.startswith(("-e ", "--editable ", "git+", "https://", "http://")):
            if any(name in normalize(original) for name in WATCHED):
                raise ValueError(f"Unreviewed watched VCS requirement at {path}:{number}")
            continue
        line = original.split("#", 1)[0].strip()
        if line.startswith(("-r ", "--requirement ")):
            yield from requirement_entries(path.parent / line.split(None, 1)[1], seen, root)
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*(.*)$", line)
        if match:
            name, rest = match.groups()
            exact = re.fullmatch(r"(?:==|===)\s*([0-9][A-Za-z0-9_.-]*)(?:\s*;.*)?", rest)
            yield name, exact.group(1) if exact else None, f"{path}:{number}"
        elif any(name in line.lower() for name in WATCHED):
            raise ValueError(f"Unrecognized watched Python dependency at {path}:{number}")


def npm_manifest_entries(data, path):
    for group in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        for name, value in data.get(group, {}).items():
            # npm aliases can hide a dangerous package under an unrelated key.
            if isinstance(value, str) and value.startswith("npm:"):
                real_name = value[4:].rsplit("@", 1)[0]
                yield real_name, None, f"{path}:{group}:alias:{name}"
            yield name, value if version_tuple(value) is not None else None, f"{path}:{group}"


def npm_lock_entries(data, path):
    for location, info in data.get("packages", {}).items():
        if not location or not isinstance(info, dict):
            continue
        yield info.get("name") or location.rsplit("node_modules/", 1)[-1], info.get("version"), f"{path}:{location}"
    def walk(deps, prefix):
        for name, value in deps.items():
            if isinstance(value, dict):
                yield name, value.get("version"), f"{path}:{prefix}{name}"
                yield from walk(value.get("dependencies", {}), prefix + name + "/")
    yield from walk(data.get("dependencies", {}), "")


def scan(root=ROOT, installed=False):
    root = Path(root).resolve()
    findings, examined = [], 0
    def check(name, version, source, ecosystem):
        nonlocal examined
        examined += 1
        reason = risk(name, version, ecosystem)
        if reason:
            findings.append({"name": normalize(name), "version": str(version or "UNPINNED"),
                             "source": str(source), "reason": reason})
    seen = set()
    for p in PYTHON:
        for name, version, source in requirement_entries(root / p, seen, root):
            check(name, version, source, "PyPI")
    for p in NPM + LOCKS:
        path = root / p
        if not path.is_file():
            raise ValueError("Missing npm manifest/lockfile: " + p)
        data = json.loads(path.read_text(encoding="utf-8"))
        iterator = npm_lock_entries(data, p) if p in LOCKS else npm_manifest_entries(data, p)
        for name, version, source in iterator:
            check(name, version, source, "npm")
    if installed:
        # Enumerate metadata; never import the package's Python modules here.
        for item in metadata.distributions():
            check(item.metadata.get("Name", ""), item.version, "installed:Python", "PyPI")
    return {"status": "blocked" if findings else "no_known_matches",
            "entries_checked": examined, "installed_python_checked": installed,
            "findings": findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    try:
        report = scan(args.root, installed=args.installed)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "audit_failed", "reason": str(error)}))
        return 2
    print(json.dumps(report, indent=2))
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
