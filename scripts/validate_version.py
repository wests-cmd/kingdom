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
import argparse
import ast
from pathlib import Path

SEMVER_REGEX = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?")
PACKAGES = ('frontend/package.json', 'desktop/package.json', 'apps/mobile/package.json', 'apps/mobile/native/package.json')
LOCKS = ('frontend/package-lock.json', 'desktop/package-lock.json', 'apps/mobile/native/package-lock.json')
REVIEW_MARKER = '<!-- RELEASE_REVIEW_REQUIRED -->'


def stable_version(version):
    if not isinstance(version, str) or not SEMVER_REGEX.fullmatch(version) or '-' in version:
        raise ValueError('Stable releases require an exact X.Y.Z version')
    return version


def metadata_errors(root, version):
    errors = []
    for relative in PACKAGES + LOCKS:
        try:
            data = json.loads((Path(root) / relative).read_text(encoding='utf-8'))
            if data.get('version') != version:
                errors.append(f'{relative}: version differs from {version}')
            if relative in LOCKS and data.get('packages', {}).get('', {}).get('version') != version:
                errors.append(f'{relative}: root package version differs from {version}')
        except (OSError, ValueError, TypeError, AttributeError) as error:
            errors.append(f'{relative}: invalid or missing metadata ({type(error).__name__})')
    return errors


def release_identity(root):
    version = stable_version(get_authoritative_version(str(root)))
    errors = metadata_errors(root, version)
    if errors:
        raise ValueError('; '.join(errors))
    notes = f'docs/releases/v{version}.md'
    text = (Path(root) / notes).read_text(encoding='utf-8')
    if not text.strip() or REVIEW_MARKER in text:
        raise ValueError('Release notes need review before native release automation')
    return {'version': version, 'tag': f'v{version}', 'notes': notes}

def get_authoritative_version(root_dir: str) -> str:
    state_file = os.path.join(root_dir, "backend", "state.py")
    if not os.path.exists(state_file):
        raise FileNotFoundError(f"Authoritative version file missing: {state_file}")

    with open(state_file, "r") as f:
        content = f.read()

    tree = ast.parse(content)
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'STATE' for target in node.targets)]
    if len(assignments) != 1:
        raise ValueError('Exactly one literal STATE assignment is required')
    version = ast.literal_eval(assignments[0].value)['version']
    if not isinstance(version, str) or not SEMVER_REGEX.fullmatch(version):
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
    if tag not in (expected_version, 'v' + expected_version):
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

    print(f"[OK] Manifest {manifest_path} version '{ver}' matches canonical version '{expected_version}'")
    return True

def main():
    parser = argparse.ArgumentParser(description="Validate Kingdom Version Consistency")
    parser.add_argument("--root", default=".", help="Root directory of Kingdom repository")
    parser.add_argument("--tag", help="Git tag to validate against canonical version")
    parser.add_argument("--manifest", help="Path to release-manifest.json to validate")
    parser.add_argument("--print-version", action="store_true", help="Print canonical version and exit")
    parser.add_argument('--release-identity', action='store_true', help='Emit reviewed stable version/tag/notes as GitHub outputs')

    args = parser.parse_args()
    root_dir = os.path.abspath(args.root)

    if args.release_identity:
        try:
            identity = release_identity(root_dir)
            if os.environ.get('GITHUB_REF', '').startswith('refs/tags/') and os.environ['GITHUB_REF'] != 'refs/tags/' + identity['tag']:
                raise ValueError('Triggered tag does not match authoritative version')
            print('\n'.join(f'{key}={value}' for key, value in identity.items()))
            return
        except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
            parser.exit(1, f'Release identity blocked: {error}\n')

    try:
        canonical_version = get_authoritative_version(root_dir)
    except Exception as e:
        print(f"[FATAL] Failed to read authoritative version: {e}", file=sys.stderr)
        sys.exit(1)

    if args.print_version:
        print(canonical_version)
        sys.exit(0)

    print(f"=== Kingdom Version Validation (Canonical: {canonical_version}) ===")

    success = True

    package_files = [os.path.join(root_dir, relative) for relative in PACKAGES]

    for pkg in package_files:
        if not check_package_json(pkg, canonical_version):
            success = False
    for error in metadata_errors(root_dir, canonical_version):
        print('[ERROR] ' + error)
        success = False

    if args.tag:
        if not validate_tag(args.tag, canonical_version):
            success = False

    if args.manifest:
        if not validate_manifest(args.manifest, canonical_version):
            success = False

    if success:
        print("=== Version Validation PASSED ===")
        sys.exit(0)
    else:
        print("=== Version Validation FAILED ===", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
