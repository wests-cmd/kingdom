"""Optional, hardware-gated model preparation with governed execution and promotion evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Literal
from uuid import uuid4, uuid5, NAMESPACE_URL

from pydantic import BaseModel, ConfigDict, Field
from backend.runtime.computer_tools import workspace_path


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class HardwareRequirements(Strict):
    ram_gb: float = Field(default=16, ge=1, le=4096)
    vram_gb: float = Field(default=8, ge=0, le=1024)
    disk_gb: float = Field(default=20, ge=1, le=10000)


class DatasetProvenance(Strict):
    source: str = Field(min_length=1, max_length=1000)
    revision: str = Field(min_length=1, max_length=200)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    path: str | None = Field(default=None, max_length=300)


class PreparationRequest(Strict):
    operation: Literal['heretic', 'fine_tune', 'custom']
    base_model: str = Field(min_length=1, max_length=300)
    output_path: str = Field(min_length=1, max_length=300)
    executable: str = Field(min_length=1, max_length=1000)
    argv: list[str] = Field(default_factory=list, max_length=35)
    hardware: HardwareRequirements = Field(default_factory=HardwareRequirements)
    datasets: list[DatasetProvenance] = Field(default_factory=list, max_length=20)
    rollback_model_profile: str = Field(min_length=1, max_length=100)
    timeout_seconds: int = Field(default=1800, ge=30, le=1800)
    downloads_authorized: bool = False


def hardware_snapshot():
    import psutil
    root = workspace_path()
    result = {'ram_gb': round(psutil.virtual_memory().available / 2**30, 2),
              'disk_gb': round(shutil.disk_usage(root).free / 2**30, 2), 'vram_gb': 0.0,
              'gpu_probe': 'No supported NVIDIA probe; GPU readiness is unverified'}
    executable = shutil.which('nvidia-smi')
    if executable:
        try:
            probe = subprocess.run([executable, '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5, **({'creationflags': subprocess.CREATE_NO_WINDOW} if __import__('os').name == 'nt' else {}))
            values = [float(line.strip()) / 1024 for line in probe.stdout.splitlines()]
            if probe.returncode == 0 and values:
                result.update(vram_gb=max(values), gpu_probe='nvidia-smi free memory; largest single GPU')
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    return result


def _argv_valid(argv):
    if not argv or len(argv) > 40 or any(not isinstance(arg, str) or not arg or len(arg) > 4000 or '\x00' in arg for arg in argv):
        raise ValueError('Use a bounded exact argument list')
    if not Path(argv[0]).is_absolute() or not Path(argv[0]).is_file():
        raise ValueError('Choose an installed executable by absolute path')
    return argv


class ModelLabService:
    def __init__(self, engine, database):
        self.engine, self.db = engine, database
        from threading import RLock
        self.lock = RLock()
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS model_lab_jobs(id TEXT PRIMARY KEY,state_json TEXT NOT NULL)'); conn.commit()

    def list(self):
        with self.db.get_connection() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT state_json FROM model_lab_jobs ORDER BY rowid DESC LIMIT 100')]

    def get(self, ident):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT state_json FROM model_lab_jobs WHERE id=?', (ident,)).fetchone()
        if not row: raise KeyError('Model preparation job not found')
        return json.loads(row[0])

    def _save(self, state):
        state['updated_at'] = time.time()
        with self.db.get_connection() as conn:
            conn.execute('INSERT INTO model_lab_jobs VALUES(?,?) ON CONFLICT(id) DO UPDATE SET state_json=excluded.state_json', (state['id'], json.dumps(state))); conn.commit()
        self.engine.events.publish('model_lab.updated', {'id': state['id'], 'status': state['status']})
        return state

    def create(self, request):
        output = workspace_path(request.output_path)
        if output.exists(): raise ValueError('Use a new output path; base models and prior artifacts are never overwritten')
        if request.base_model.startswith('-') or '\x00' in request.base_model: raise ValueError('Invalid base model')
        executable = str(Path(request.executable).resolve())
        _argv_valid([executable])
        for dataset in request.datasets:
            if dataset.path:
                path = workspace_path(dataset.path)
                if not path.is_file() or self._hash(path) != dataset.sha256: raise ValueError('Dataset provenance does not match the local file')
        if request.operation == 'fine_tune' and not request.datasets:
            raise ValueError('Fine-tuning requires dataset provenance')
        if request.operation == 'heretic':
            argv = [executable, '--model', request.base_model, '--trial-index', '0', '--model-action', 'save',
                    '--save-directory', str(output), '--export-strategy', 'merge', '--checkpoint-action', 'continue']
        else:
            if '{output}' not in request.argv or '{base_model}' not in request.argv:
                raise ValueError('Custom trainer arguments need standalone {base_model} and {output} placeholders')
            replacements = {'{output}': str(output), '{base_model}': request.base_model}
            argv = [executable] + [replacements.get(arg, arg) for arg in request.argv]
            _argv_valid(argv)
        ident = uuid4().hex
        return self._save({'id': ident, 'request': request.model_dump(), 'argv': argv, 'status': 'draft',
            'created_at': time.time(), 'notice': 'Preparation is optional. Downloads, execution and promotion are distinct owner decisions. No model has been trained or replaced.'})

    @staticmethod
    def _hash(path):
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''): digest.update(chunk)
        return digest.hexdigest()

    def start(self, ident):
        with self.lock:
            state = self.get(ident)
            if state['status'] not in {'draft', 'hardware_blocked'}: return state
            request = PreparationRequest.model_validate(state['request'])
            snapshot = hardware_snapshot()
            missing = [key for key, value in request.hardware.model_dump().items() if snapshot[key] < value]
            state['hardware_snapshot'] = snapshot
            if missing:
                state.update(status='hardware_blocked', missing_hardware=missing)
                return self._save(state)
            if not request.downloads_authorized:
                raise ValueError('Explicitly authorize possible model/dataset downloads before dispatch')
            if workspace_path(request.output_path).exists(): raise ValueError('Output already exists; choose a new path')
            # The exact arguments are bound into the existing single-use process approval.
            self._dispatch(state, 'preparation', state['argv'], request.timeout_seconds)
            state['status'] = 'preparing'
            return self._save(state)

    def _dispatch(self, state, stage, argv, timeout):
        _argv_valid(argv)
        key = 'model-lab:' + state['id'] + ':' + stage
        task_id = str(uuid5(NAMESPACE_URL, 'kingdom-mission:' + key))
        state[stage + '_task_id'] = task_id
        self._save(state)
        if not self.engine.tasks.get(task_id):
            self.engine.submit_task('Model lab ' + stage, {'actor': 'owner', '_mission_step_key': key,
                'model_lab_job_id': state['id'], 'tool': 'harness.run@1.0.0', 'max_attempts': 1,
                'tool_parameters': {'argv': argv, 'cwd': '.', 'timeout_seconds': timeout, 'environment': {}}})

    def _task_verified(self, task_id):
        task = self.engine.tasks.get(task_id)
        if not task: raise ValueError('Retained model job task is missing; review before retrying')
        if task['status'].lower() not in {'completed', 'succeeded'}:
            if task['status'].lower() in {'failed', 'cancelled', 'denied', 'blocked', 'recovery_required'}:
                raise ValueError('Governed model job failed or requires review')
            return False
        results = (task.get('result') or {}).get('results', [])
        if len(results) != 1 or results[0].get('verification', {}).get('state') != 'VERIFIED' or results[0].get('outcome', {}).get('tool') != 'harness.run@1.0.0' or results[0]['outcome'].get('output', {}).get('exit_code') != 0:
            raise ValueError('Successful independently verified process evidence is required')
        return True

    def inspect_artifact(self, state):
        root = workspace_path(state['request']['output_path'])
        if not root.is_dir() or not (root / 'config.json').is_file(): raise ValueError('Prepared model needs config.json and model weights')
        manifest = []
        for path in root.rglob('*'):
            if path.is_symlink(): raise ValueError('Model artifacts cannot contain symbolic links')
            if path.is_file():
                workspace_path(str(path.relative_to(workspace_path())))
                if len(manifest) >= 500: raise ValueError('Model artifact exceeds 500 files')
                manifest.append({'path': str(path.relative_to(root)), 'bytes': path.stat().st_size, 'sha256': self._hash(path)})
        if not any(item['path'].endswith(('.safetensors', '.bin', '.gguf')) and item['bytes'] > 0 for item in manifest):
            raise ValueError('Prepared model contains no nonempty model weights')
        return {'manifest': sorted(manifest, key=lambda item: item['path']),
                'sha256': hashlib.sha256(json.dumps(sorted(manifest, key=lambda item: item['path']), sort_keys=True).encode()).hexdigest()}

    def refresh(self, ident):
        with self.lock:
            state = self.get(ident)
            if state['status'] == 'preparing' and self._task_verified(state['preparation_task_id']):
                state['artifact'] = self.inspect_artifact(state)
                state['status'] = 'awaiting_evaluation'
            elif state['status'] == 'evaluating' and self._task_verified(state['evaluation_task_id']):
                current = self.inspect_artifact(state)
                if current['sha256'] != state['artifact']['sha256']: raise ValueError('Artifact changed during evaluation')
                report_path = workspace_path(state['evaluation_report_path'])
                if report_path.stat().st_size > 128000: raise ValueError('Evaluation report exceeds 128 KB')
                report = json.loads(report_path.read_text(encoding='utf-8'))
                if not isinstance(report, dict) or report.get('passed') is not True or report.get('base_model') != state['request']['base_model'] or report.get('artifact_sha256') != current['sha256'] or not isinstance(report.get('metrics'), dict) or not report['metrics']:
                    raise ValueError('Evaluation must pass, report metrics and bind the base model and artifact hash')
                state.update(status='evaluated', evaluation={'report': report, 'sha256': self._hash(report_path)})
            return self._save(state)

    def evaluate(self, ident, argv, report_path):
        with self.lock:
            state = self.get(ident)
            if state['status'] != 'awaiting_evaluation': raise ValueError('Verify prepared artifacts before evaluating')
            target = workspace_path(report_path)
            if target.exists(): raise ValueError('Use a new evaluation report path')
            _argv_valid(argv)
            state['evaluation_report_path'] = report_path
            self._dispatch(state, 'evaluation', argv, state['request']['timeout_seconds'])
            state['status'] = 'evaluating'
            return self._save(state)

    def promote(self, ident):
        with self.lock:
            state = self.get(ident)
            if state['status'] != 'evaluated': raise ValueError('A passing evaluated candidate is required')
            if self.inspect_artifact(state)['sha256'] != state['artifact']['sha256']: raise ValueError('Artifact changed after evaluation')
            state.update(status='promoted', promoted_at=time.time(), promotion_scope='Approved candidate registry only; configure and test a serving model profile separately. Existing inference profiles are unchanged.')
            return self._save(state)

    def rollback(self, ident):
        with self.lock:
            state = self.get(ident)
            if state['status'] != 'promoted': raise ValueError('Only a promoted candidate can be withdrawn')
            state.update(status='withdrawn', rollback_at=time.time(), rollback_scope='Candidate withdrawn; serving profiles were never changed by promotion.',
                         rollback_model_profile=state['request']['rollback_model_profile'])
            return self._save(state)
