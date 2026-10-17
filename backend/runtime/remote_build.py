"""Reviewed, bounded remote builds with independently checked golden artifacts.

A temporary working directory is not an OS sandbox. Commands need the worker's
process.execute grant and the controller's exact high-risk task approval.
"""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import signal
import subprocess
import sys
import tempfile
import time

from pydantic import BaseModel, ConfigDict, Field, model_validator

TOOL = 'build.run@1.0.0'


def relative_name(name):
    if not isinstance(name, str) or not name or len(name) > 240 or '\\' in name or ':' in name or any(ord(c)<32 or ord(c)==127 for c in name):
        raise ValueError('Build files need portable relative paths')
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {'', '.', '..'} for part in name.split('/')):
        raise ValueError('Build path escapes its source bundle')
    return name


def source_digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


class BuildSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    source_revision: str = Field(pattern=r'^(?:[a-f0-9]{40}|[a-f0-9]{64})$')
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    files: dict[str, str] = Field(min_length=1, max_length=100)
    argv: list[str] = Field(min_length=1, max_length=40)
    expected_artifacts: dict[str, str] = Field(min_length=1, max_length=20)
    timeout_seconds: int = Field(default=15, ge=1, le=20)

    @model_validator(mode='after')
    def bounded(self):
        for name in [*self.files, *self.expected_artifacts]:
            relative_name(name)
        if sum(len(value.encode()) for value in self.files.values()) > 500_000:
            raise ValueError('Source bundle exceeds 500 KB')
        if any(not arg or len(arg) > 4000 or '\x00' in arg for arg in self.argv):
            raise ValueError('Use bounded exact command arguments')
        if any(len(value) != 64 or any(c not in '0123456789abcdef' for c in value) for value in self.expected_artifacts.values()):
            raise ValueError('Reviewed artifact SHA256 values are required')
        if source_digest(self.files) != self.source_sha256:
            raise ValueError('Source bundle digest mismatch')
        return self


def build(params):
    params = dict(params)
    context = params.pop('_task_context')
    if not context.get('task_id') or not context.get('lease_id') or type(context.get('fencing_token')) is not int or context['fencing_token'] < 1:
        raise ValueError('Remote builds require an active fenced task lease')
    spec = BuildSpec.model_validate(params)
    # The first adapter uses POSIX process groups to stop child processes at
    # timeout and after completion. Windows remote builds await a Job Object adapter.
    if os.name != 'posix':
        raise ValueError('This remote build adapter requires a POSIX worker')
    with tempfile.TemporaryDirectory(prefix='kingdom-build-') as temporary:
        root = Path(temporary)
        for name, content in spec.files.items():
            target = root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.encode())
        argv = [sys.executable if spec.argv[0] == '@python' else spec.argv[0], *spec.argv[1:]]
        env = {key: os.environ[key] for key in ('PATH', 'LANG') if key in os.environ}
        env.update(HOME=str(root), TMPDIR=str(root), PYTHONIOENCODING='utf-8', PYTHONNOUSERSITE='1')
        started = time.monotonic()
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen(argv, cwd=root, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, shell=False, start_new_session=True)
            try:
                while process.poll() is None:
                    if time.monotonic()-started > spec.timeout_seconds or os.fstat(log.fileno()).st_size > 1_000_000:
                        raise TimeoutError('Build exceeded time or output budget')
                    time.sleep(.02)
                code = process.returncode
            finally:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait(timeout=5)
            log.seek(0)
            output = log.read(16384).decode(errors='replace')
        if code != 0:
            raise ValueError('Build command failed with exit code '+str(code))
        artifacts, total = {}, 0
        for name, expected in spec.expected_artifacts.items():
            target = root/name
            if any(parent.is_symlink() for parent in [target, *target.parents]) or not target.is_file():
                raise ValueError('Build artifact missing or symlinked')
            if target.stat().st_size > 500_000:
                raise ValueError('Build artifact exceeds budget')
            content = target.read_bytes(); total += len(content)
            if not content or total > 500_000 or hashlib.sha256(content).hexdigest() != expected:
                raise ValueError('Build artifact differs from reviewed digest or exceeds budget')
            artifacts[name] = {'sha256': expected, 'base64': base64.b64encode(content).decode()}
        return {**context, 'source_revision': spec.source_revision, 'source_sha256': spec.source_sha256,
                'argv': spec.argv, 'exit_code': code, 'artifacts': artifacts, 'log': output,
                'scope': 'Reviewed host command; temporary working directory is not an OS sandbox. Artifact integrity is verified, not application correctness.'}


def verify(task, output):
    spec = BuildSpec.model_validate(task['metadata']['tool_parameters'])
    if not isinstance(output, dict) or output.get('exit_code') != 0:
        raise ValueError('Missing successful build receipt')
    for key, expected in {'task_id': task['id'], 'lease_id': task.get('lease_id'),
                          'fencing_token': task.get('fencing_token'), 'source_revision': spec.source_revision,
                          'source_sha256': spec.source_sha256, 'argv': spec.argv}.items():
        if output.get(key) != expected:
            raise ValueError('Build receipt does not match reviewed source, command or lease')
    artifacts = output.get('artifacts')
    if not isinstance(artifacts, dict) or set(artifacts) != set(spec.expected_artifacts):
        raise ValueError('Build artifact set differs from review')
    total = 0
    for name, artifact in artifacts.items():
        encoded = artifact.get('base64') if isinstance(artifact, dict) else None
        if not isinstance(encoded, str) or len(encoded) > 700_000:
            raise ValueError('Invalid artifact encoding or size')
        content = base64.b64decode(encoded, validate=True); total += len(content)
        expected = spec.expected_artifacts[name]
        if not content or total > 500_000 or artifact.get('sha256') != expected or hashlib.sha256(content).hexdigest() != expected:
            raise ValueError('Independent artifact verification failed')
    return {'state': 'VERIFIED', 'method': 'reviewed_source_and_lease_bound_artifact_sha256',
            'scope': 'Returned bytes match reviewed artifact digests. Command execution is attested by the approved signed worker; application correctness requires separate tests.'}
