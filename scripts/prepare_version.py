#!/usr/bin/env python3
"""Prepare reviewed release metadata; dry-run by default. Never publish or run builds."""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import tempfile

try:
    from scripts.validate_version import (PACKAGES, LOCKS, UI_CATALOG, REVIEW_MARKER, get_authoritative_version,
                                         metadata_errors, stable_version)
except ModuleNotFoundError:
    from validate_version import (PACKAGES, LOCKS, UI_CATALOG, REVIEW_MARKER, get_authoritative_version,
                                  metadata_errors, stable_version)


def prepare(root, version, repair_existing=False):
    root = Path(root).resolve()
    version = stable_version(version)
    old = stable_version(get_authoritative_version(str(root)))
    if tuple(map(int, version.split('.'))) <= tuple(map(int, old.split('.'))):
        raise ValueError('Choose a version newer than the authoritative version')
    errors = metadata_errors(root, old)
    if errors and not repair_existing:
        raise ValueError('Existing metadata diverges; inspect it and explicitly use --repair-existing-metadata: ' + '; '.join(errors))
    originals, updates = {}, {}

    def change(relative, transform):
        path = root / relative
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root.parent):
            raise ValueError('Release metadata cannot use symlinks')
        raw = path.read_bytes()
        originals[relative] = raw
        text = raw.decode('utf-8')
        newline = '\r\n' if '\r\n' in text else '\n'
        updates[relative] = transform(text).replace('\r\n', '\n').replace('\n', newline).encode()

    def state(text):
        tree = ast.parse(text)
        assignment, = [node for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'STATE' for target in node.targets)]
        if not isinstance(assignment.value, ast.Dict):
            raise ValueError('Expected a literal STATE dictionary')
        entries = [(key, value) for key, value in zip(assignment.value.keys, assignment.value.values)
                   if isinstance(key, ast.Constant) and key.value == 'version']
        if len(entries) != 1:
            raise ValueError('Expected one authoritative version entry')
        node = entries[0][1]
        lines = text.splitlines(keepends=True)
        # AST columns are UTF-8 byte offsets; operate on the original bytes.
        raw = text.encode()
        begin = sum(len(line.encode()) for line in lines[:node.lineno - 1]) + node.col_offset
        end = sum(len(line.encode()) for line in lines[:node.end_lineno - 1]) + node.end_col_offset
        return (raw[:begin] + json.dumps(version).encode() + raw[end:]).decode()

    change('backend/state.py', state)
    for relative in PACKAGES + LOCKS:
        def package(text, lock=relative in LOCKS):
            data = json.loads(text)
            data['version'] = version
            if lock:
                data['packages']['']['version'] = version
            return json.dumps(data, indent=2, ensure_ascii=False) + '\n'
        change(relative, package)

    def ui_catalog(text):
        data = json.loads(text)
        # A new frontend must not inherit untested older-backend compatibility.
        data['compatible_backends'] = [version]
        return json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    change(UI_CATALOG, ui_catalog)

    def android(text):
        text, count = re.subn(r'(?m)^(\s*versionName\s+)"[^"]+"', lambda match: match[1] + json.dumps(version), text)
        if count != 1:
            raise ValueError('Expected exactly one Android versionName; build number is not changed')
        return text
    change('apps/mobile/native/android/app/build.gradle', android)

    def ios(text):
        text, count = re.subn(r'(?m)^(\s*MARKETING_VERSION\s*=\s*)[^;]+;', lambda match: match[1] + version + ';', text)
        if count < 1:
            raise ValueError('Expected iOS marketing version settings; build numbers are not changed')
        return text
    change('apps/mobile/native/ios/App/App.xcodeproj/project.pbxproj', ios)
    notes = f'docs/releases/v{version}.md'
    path = root / notes
    if path.exists() or path.is_symlink():
        raise ValueError('Release notes already exist; preparation never overwrites them')
    originals[notes] = None
    updates[notes] = (f'# Kingdom v{version}\n\n{REVIEW_MARKER}\n\n'
                      'Draft release notes. Review against the exact candidate source and actual results; '
                      'remove the review marker only after replacing this scaffold.\n\n'
                      '## Changes\n\n- Describe reviewed changes and their user-visible behavior.\n\n'
                      '## Validation\n\n- Record exact-source tests, native build/installer evidence and remaining gaps.\n\n'
                      '## Limits\n\n- Record signing, platform, permission and acceptance limits. '
                      'Do not infer general autonomous coding or device support from bounded tests.\n').encode()
    return {'from': old, 'version': version, 'existing_metadata_errors': errors,
            'originals': originals, 'updates': updates}


def apply(root, plan):
    """Stage first, compare original bytes, replace, rollback on exceptions.

    Individual replacements are atomic; a multi-file transaction is not power-loss atomic.
    An interrupted process retains the lock for manual inspection, never blind retry.
    """
    root = Path(root).resolve()
    lock = root / '.version-preparation.lock'
    handle = lock.open('x', encoding='utf-8')
    staged, written, safe_cleanup = {}, [], False
    try:
        with handle:
            json.dump({'from': plan['from'], 'version': plan['version'], 'files': list(plan['updates'])}, handle)
            handle.flush(); os.fsync(handle.fileno())
        for relative, content in plan['updates'].items():
            target = root / relative
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.version-', delete=False) as temporary:
                temporary.write(content); temporary.flush(); os.fsync(temporary.fileno())
                staged[relative] = Path(temporary.name)
        for relative, original in plan['originals'].items():
            target = root / relative
            if target.is_symlink() or (target.read_bytes() if target.exists() else None) != original:
                raise ValueError('Metadata changed after preparation: ' + relative)
        for relative, temporary in staged.items():
            os.replace(temporary, root / relative)
            written.append(relative)
        safe_cleanup = True
    except BaseException:
        for relative in reversed(written):
            target = root / relative
            original = plan['originals'][relative]
            if original is None:
                target.unlink()
            else:
                with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.version-rollback-', delete=False) as temporary:
                    temporary.write(original); temporary.flush(); os.fsync(temporary.fileno())
                os.replace(temporary.name, target)
        safe_cleanup = True
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        if safe_cleanup:
            lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version')
    parser.add_argument('--root', default='.')
    parser.add_argument('--apply', action='store_true', help='Explicitly write prepared metadata; default is dry-run')
    parser.add_argument('--repair-existing-metadata', action='store_true', help='Explicitly align divergent package metadata with the new canonical version')
    args = parser.parse_args()
    try:
        plan = prepare(args.root, args.version, args.repair_existing_metadata)
        print(json.dumps({key: value for key, value in plan.items() if key not in {'originals', 'updates'}} | {'files': list(plan['updates']), 'apply': args.apply}, indent=2))
        if args.apply:
            apply(args.root, plan)
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        parser.exit(1, f'Version preparation stopped: {error}\n')


if __name__ == '__main__':
    main()
