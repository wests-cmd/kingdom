#!/usr/bin/env python3
"""
Kingdom Version Validation & Consistency Utility
Verifies version synchronization across backend, frontend, desktop, mobile,
release tags, build artifacts, and release-manifest.json.
"""

import sys
import os
import json
import re
import hashlib
import argparse

SEMVER_REGEX = re.compile(r"^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?$")

def get_authoritative_version(root_dir: str) -> str:
    state_file = os.path.join(root_dir, "backend", "state.py")
    if not os.path.exists(state_file):
        raise FileNotFoundError(f"Authoritative version file missing: {state_file}")

    with open(state_file, "r") as f:
        content = f.read()

    match = re.search(r'"version"\s*:\s*"([^"]+)"', content)
    if not match:
        raise ValueError(f"Could not parse 'version' from {state_file}")

    version = match.group(1)
    if not SEMVER_REGEX.match(version):
        raise ValueError(f"Authoritative version '{version}' does not match semver format X.Y.Z")

    return version

def check_package_json(filepath: str, expected_version: str) -> bool:
    if not os.path.exists(filepath):
        print(f"[ERROR] Required package file missing: {filepath}")
        return False

    with open(filepath, "r") as f:
        data = json.load(f)

    ver = data.get("version")
    if ver != expected_version:
        print(f"[ERROR] Version mismatch in {filepath}: found '{ver}', expected '{expected_version}'")
        return False
    print(f"[OK] {filepath}: {ver}")
    return True

def validate_tag(tag: str, expected_version: str) -> bool:
    normalized_tag = tag.lstrip("v")
    if normalized_tag != expected_version:
        print(f"[ERROR] Git tag mismatch: tag '{tag}' vs canonical version '{expected_version}'")
        return False
    print(f"[OK] Git tag '{tag}' matches version '{expected_version}'")
    return True

def validate_manifest(manifest_path: str, expected_version: str) -> bool:
    if not os.path.exists(manifest_path):
        print(f"[ERROR] Release manifest missing: {manifest_path}")
        return False

    with open(manifest_path, "r") as f:
        data = json.load(f)

    ver = data.get("version")
    if ver != expected_version:
        print(f"[ERROR] Manifest version mismatch: found '{ver}', expected '{expected_version}'")
        return False

    artifacts = data.get("artifacts", [])
    if not isinstance(artifacts, list):
        print(f"[ERROR] Manifest artifacts field is not a list")
        return False

    print(f"[OK] Manifest {manifest_path} version '{ver}' matches canonical version '{expected_version}' ({len(artifacts)} artifacts declared)")
    return True

def validate_artifacts_dir(staging_dir: str, expected_version: str) -> bool:
    if not os.path.exists(staging_dir):
        print(f"[ERROR] Artifacts staging directory missing: {staging_dir}")
        return False

    manifest_path = os.path.join(staging_dir, "release-manifest.json")
    if not validate_manifest(manifest_path, expected_version):
        return False

    sums_path = os.path.join(staging_dir, "SHA256SUMS")
    if not os.path.exists(sums_path):
        print(f"[ERROR] SHA256SUMS file missing in {staging_dir}")
        return False

    with open(sums_path, "r") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or "SHA256SUMS" in line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        expected_hash = parts[0]
        fname = parts[1].lstrip("*")
        fpath = os.path.join(staging_dir, fname)

        if not os.path.exists(fpath):
            print(f"[ERROR] Listed artifact missing: {fpath}")
            return False

        if os.path.getsize(fpath) == 0:
            print(f"[ERROR] Artifact is empty (0 bytes): {fpath}")
            return False

        sha = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
        if sha.lower() != expected_hash.lower():
            print(f"[ERROR] Hash mismatch for {fname}: computed {sha}, expected {expected_hash}")
            return False

        print(f"[OK] Verified artifact {fname} (SHA256: {sha[:12]}...)")

    return True

def main():
    parser = argparse.ArgumentParser(description="Validate Kingdom Version Consistency & Artifacts")
    parser.add_argument("--root", default=".", help="Root directory of Kingdom repository")
    parser.add_argument("--tag", help="Git tag to validate against canonical version")
    parser.add_argument("--manifest", help="Path to release-manifest.json to validate")
    parser.add_argument("--artifacts-dir", help="Path to release_staging directory to validate")
    parser.add_argument("--print-version", action="store_true", help="Print canonical version and exit")

    args = parser.parse_args()
    root_dir = os.path.abspath(args.root)

    try:
        canonical_version = get_authoritative_version(root_dir)
    except Exception as e:
        print(f"[FATAL] Failed to read authoritative version: {e}", file=sys.stderr)
        sys.exit(1)

    if args.print_version:
        print(canonical_version)
        sys.exit(0)

    print(f"=== Kingdom Version & Artifact Validation (Canonical: {canonical_version}) ===")

    success = True

    package_files = [
        os.path.join(root_dir, "frontend", "package.json"),
        os.path.join(root_dir, "desktop", "package.json"),
        os.path.join(root_dir, "apps", "mobile", "package.json")
    ]

    for pkg in package_files:
        if not check_package_json(pkg, canonical_version):
            success = False

    if args.tag:
        if not validate_tag(args.tag, canonical_version):
            success = False

    if args.manifest:
        if not validate_manifest(args.manifest, canonical_version):
            success = False

    if args.artifacts_dir:
        if not validate_artifacts_dir(args.artifacts_dir, canonical_version):
            success = False

    if success:
        print("=== Validation PASSED ===")
        sys.exit(0)
    else:
        print("=== Validation FAILED ===", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
