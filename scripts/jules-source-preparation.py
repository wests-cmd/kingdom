"""Reconstruct candidate source from a pinned local Git object and retained patch.

No candidate commands, hooks, network, tests or signing run here. The operator
must protect the repository, input files and review directory independently.
"""
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def tree_digest(source):
    files = {}
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('Candidate links are forbidden')
        if path.is_file():
            files[path.relative_to(source).as_posix()] = digest(path.read_bytes())
        elif not path.is_dir():
            raise ValueError('Candidate special files are forbidden')
    if not files:
        raise ValueError('Empty candidate source')
    return digest(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())


def safe_path(value):
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or '..' in path.parts or
            '\\' in value or ':' in value or any(p.lower() == '.git' for p in path.parts)):
        raise ValueError('Unsafe candidate path')
    return path


def prepare(repository, revision, patch, expected_patch_sha256, output, allowed_paths):
    """Return independently reconstructed provenance; output must be new.

    allowed_paths is an operator-owned exact file list, never patch-supplied.
    The caller retains the raw archive and patch with this preparation proof.
    """
    if not re.fullmatch('[a-f0-9]{40}', revision):
        raise ValueError('Exact Git commit required')
    if not isinstance(patch, bytes) or not 0 < len(patch) <= 2_000_000:
        raise ValueError('Bounded retained patch bytes required')
    if digest(patch) != expected_patch_sha256:
        raise ValueError('Retained provider patch digest changed')
    allowed = {str(safe_path(value)) for value in allowed_paths}
    if not allowed or len(allowed) > 100:
        raise ValueError('Bounded exact operator file scope required')
    if re.search(rb'\b(?:120000|160000)\b|GIT binary patch|^rename |^copy ', patch, re.M):
        raise ValueError('Links, submodules, copies, renames and binary patches are forbidden')
    repo = Path(repository).resolve()
    gitdir=repo if (repo/'HEAD').is_file() and (repo/'objects').is_dir() else repo/'.git'
    if not gitdir.is_dir() or gitdir.is_symlink():
        raise ValueError('A contained local Git object store is required')
    config=(gitdir/'config').read_bytes()
    if (len(config)>65536 or re.search(rb'(?im)^[^#;\n]*(?:promisor|partialclone|\[include)',config)
            or (gitdir/'objects/info/alternates').exists() or list((gitdir/'objects').rglob('*.promisor'))):
        raise ValueError('Git external object stores, includes and lazy fetching are forbidden')
    destination = Path(output)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Use a fresh review directory; never overwrite earlier evidence')
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1')

    def git(args, cwd=repo, data=None):
        result = subprocess.run(['git', '-c', 'protocol.allow=never', '-c', 'core.hooksPath=' + os.devnull, *args],
                                cwd=cwd, input=data, capture_output=True, env=env, timeout=30)
        if result.returncode:
            raise ValueError('Protected Git reconstruction failed')
        return result.stdout

    if git(['rev-parse', '--verify', revision + '^{commit}']).strip().decode() != revision:
        raise ValueError('Git source object differs from exact base')
    helper_path=Path(__file__).with_name('archive-verified-source.py')
    helper_spec=importlib.util.spec_from_file_location('raw_archive',helper_path)
    helper=importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helper)
    archive_bytes, archive_receipt = helper.archive_source(repo,revision,max_bytes=200_000_000)
    if len(archive_bytes) > 200_000_000:
        raise ValueError('Protected source archive too large')
    destination.mkdir(mode=0o700)
    source = destination / 'source'
    source.mkdir(mode=0o755)
    count = total = 0
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
        for member in archive:
            name = safe_path(member.name)
            count += 1
            total += member.size
            if count > 50_000 or total > 200_000_000 or not (member.isfile() or member.isdir()):
                raise ValueError('Unsupported protected source archive')
            path = source.joinpath(*name.parts)
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as handle:
                    handle.write(archive.extractfile(member).read())
                path.chmod(0o644)
    stats = git(['apply', '--numstat', '-z', '-'], cwd=source, data=patch)
    changed = []
    for record in stats.split(b'\0'):
        if not record:
            continue
        fields = record.split(b'\t')
        if len(fields) != 3 or not all(part.isdigit() for part in fields[:2]):
            raise ValueError('Only ordinary textual file patches are supported')
        changed.append(str(safe_path(fields[2].decode('utf-8'))))
    if not changed or any(name not in allowed for name in changed):
        raise ValueError('Provider patch exceeds the independently reviewed file scope')
    git(['apply', '--check', '-'], cwd=source, data=patch)
    git(['apply', '--whitespace=nowarn', '-'], cwd=source, data=patch)
    for path in source.rglob('*'):
        path.chmod(0o555 if path.is_dir() else 0o444)
    source.chmod(0o555)
    proof = dict(format='kingdom.source-preparation.v1', base_revision=revision,
                 patch_sha256=digest(patch), source_archive_sha256=digest(archive_bytes),
                 candidate_tree_sha256=tree_digest(source), changed_paths=sorted(set(changed)))
    (destination / 'base.tar.gz').write_bytes(archive_bytes)
    (destination / 'candidate.patch').write_bytes(patch)
    (destination / 'preparation.json').write_text(json.dumps(proof, sort_keys=True, indent=2), encoding='utf-8')
    return proof
