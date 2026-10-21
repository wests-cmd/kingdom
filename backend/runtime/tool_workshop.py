"""Prepare reviewed local tool recipes; execution stays in governed tasks."""
import hashlib
import json
from pathlib import Path
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.runtime.computer_tools import workspace_path
from backend.runtime.harnesses import HarnessConfig, HarnessService, validate_config

_lock = RLock()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


class DependencyPin(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._+!\-]{0,99}$')
    source: str = Field(min_length=1, max_length=1000)
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class RecipeCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    argv: list[str] = Field(min_length=1, max_length=40)
    timeout_seconds: int = Field(default=60, ge=1, le=120)

    @field_validator('argv')
    @classmethod
    def valid_argv(cls, value):
        if any(not arg or len(arg) > 4000 or '\x00' in arg for arg in value):
            raise ValueError('Use bounded exact arguments, not a shell command string')
        if not Path(value[0]).is_absolute() or not Path(value[0]).is_file():
            raise ValueError('Recipe executable must be an installed absolute file')
        return value


class ToolProposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=1, max_length=4000)
    source: str = Field(min_length=1, max_length=1000)
    files: dict[str, str] = Field(min_length=1, max_length=32)
    dependencies: list[DependencyPin] = Field(default_factory=list, max_length=32)
    build: RecipeCommand
    test: RecipeCommand
    connection: HarnessConfig

    @field_validator('files')
    @classmethod
    def valid_files(cls, value):
        total = 0
        for name, content in value.items():
            path = Path(name)
            if not name or len(name) > 200 or path.is_absolute() or ':' in name or '..' in path.parts or '\\' in name:
                raise ValueError('Use relative source filenames without traversal')
            total += len(content.encode('utf-8'))
        if total > 512 * 1024:
            raise ValueError('Proposal source exceeds 512 KiB')
        return value


class ToolWorkshop:
    def __init__(self, engine, database):
        self.engine, self.db = engine, database
        with database.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS tool_workshop(id TEXT PRIMARY KEY,state_json TEXT NOT NULL)')
            conn.commit()

    def _save(self, state):
        with self.db.get_connection() as conn:
            conn.execute('INSERT INTO tool_workshop VALUES(?,?) ON CONFLICT(id) DO UPDATE SET state_json=excluded.state_json',
                         (state['id'], json.dumps(state)))
            conn.commit()
        self.engine.events.publish('tool_workshop.changed', {'id': state['id'], 'status': state['status']})
        return state

    def get(self, ident):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT state_json FROM tool_workshop WHERE id=?', (ident,)).fetchone()
        if not row:
            raise KeyError(ident)
        return json.loads(row[0])

    def list(self):
        with self.db.get_connection() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT state_json FROM tool_workshop ORDER BY id')]

    def discover(self, query):
        query = query.casefold()
        return {'connections': [p for p in HarnessService(self.engine, self.db).list()
                                if query in (p['name'] + ' ' + p['kind']).casefold()],
                'proposals': [p for p in self.list() if query in (p['name'] + ' ' + p['objective']).casefold()],
                'notice': 'Discovery searches configured local connections and retained proposals. Discord documents never install tools.'}

    def propose(self, proposal):
        with _lock:
            data = proposal.model_dump()
            ident = uuid4().hex
            cwd = 'tool-workshop/' + ident
            root = workspace_path(cwd)
            root.mkdir(parents=True, exist_ok=False)
            manifest = {}
            for name, content in data.pop('files').items():
                target = workspace_path(cwd + '/' + name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding='utf-8', newline='\n')
                manifest[name] = file_digest(target)
            data.update(id=ident, cwd=cwd, source_files=manifest, status='proposed', evidence=[], task_id=None,
                        executables={cmd.argv[0]: file_digest(cmd.argv[0]) for cmd in (proposal.build, proposal.test)},
                        notice='Staged source is untrusted. Review exact recipe and dependencies before submitting governed host-process tasks.')
            data['checksum'] = digest(json.dumps(data, sort_keys=True).encode())
            return self._save(data)

    def _check_sources(self, state):
        for name, expected in state['source_files'].items():
            target = workspace_path(state['cwd'] + '/' + name)
            if not target.is_file() or file_digest(target) != expected:
                raise ValueError('Staged source changed; create and review a new proposal')
        for path, expected in state['executables'].items():
            if not Path(path).is_file() or file_digest(path) != expected:
                raise ValueError('Recipe executable changed; create a new proposal')

    def _artifacts(self, state):
        root = workspace_path(state['cwd'])
        artifacts, size = {}, 0
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError('Tool artifacts cannot contain symlinks')
            if not path.is_file():
                continue
            size += path.stat().st_size
            if len(artifacts) >= 1000 or size > 20 * 1024 * 1024:
                raise ValueError('Tool artifacts exceed 1000 files or 20 MiB')
            artifacts[str(path.relative_to(root))] = file_digest(path)
        return artifacts

    def review(self, ident, checksum):
        with _lock:
            state = self.get(ident)
            if state['status'] != 'proposed' or checksum != state['checksum']:
                raise ValueError('Review the current proposed checksum')
            self._check_sources(state)
            state['status'] = 'reviewed'
            return self._save(state)

    def advance(self, ident):
        with _lock:
            state = self.get(ident)
            if state['status'] in {'disabled', 'failed', 'registered', 'ready', 'proposed'}:
                return state
            self._check_sources(state)
            if state['task_id']:
                task = self.engine.get_task(state['task_id'])
                if not task:
                    state.update(status='failed', error='Retained recipe task is missing; no automatic retry')
                    return self._save(state)
                status = task['status'].lower()
                if status not in {'completed', 'succeeded'}:
                    if status in {'failed', 'cancelled', 'blocked', 'denied', 'recovery_required', 'unknown'}:
                        state.update(status='failed', error='Recipe task failed or needs review', task_status=status)
                    else:
                        state['task_status'] = status
                    return self._save(state)
                results = (task.get('result') or {}).get('results', [])
                expected = {**state[state['stage']], 'cwd': state['cwd']}
                if task.get('metadata', {}).get('tool_parameters') != expected:
                    state.update(status='failed', error='Recipe task command no longer matches reviewed snapshot')
                    return self._save(state)
                valid = len(results) == 1 and results[0].get('verification', {}).get('state') == 'VERIFIED'
                outcome = results[0].get('outcome', {}) if valid else {}
                output = outcome.get('output', {})
                if outcome.get('tool') != 'process.run@1.0.0' or output.get('exit_code') != 0:
                    state.update(status='failed', error='Recipe has no verified zero-exit process evidence')
                    return self._save(state)
                state['evidence'].append({'stage': state['stage'], 'task_id': state['task_id'],
                                          'command': state[state['stage']], 'output': output,
                                          'verification': results[0]['verification']})
                state['task_id'] = None
                if state['stage'] == 'test':
                    connection = self._connection(state)
                    state.update(status='ready', connection_executable_sha256=file_digest(connection.argv[0]),
                                 artifacts=self._artifacts(state))
                    return self._save(state)
                state['status'] = 'built'
                return self._save(state)
            stage = 'test' if state['status'] == 'built' else 'build'
            command = state[stage]
            task = self.engine.submit_task('Tool workshop ' + stage + ': ' + state['name'],
                {'actor': 'owner', 'actor_id': 'owner', 'tool': 'process.run@1.0.0',
                 'tool_parameters': {**command, 'cwd': state['cwd']}, 'max_attempts': 1,
                 '_mission_step_key': 'tool-workshop:' + ident + ':' + stage,
                 'source': 'owner_reviewed_tool_recipe', 'workshop_id': ident, 'proposal_checksum': state['checksum']})
            state.update(status='waiting_' + stage, stage=stage, task_id=task['id'])
            return self._save(state)

    def _connection(self, state):
        config = HarnessConfig.model_validate(state['connection'])
        # Staging references resolve only inside this proposal's workspace.
        config.argv = [str(workspace_path(state['cwd'] + arg[len('{staging}'):]))
                       if arg == '{staging}' or arg.startswith('{staging}/') else arg for arg in config.argv]
        return validate_config(config)

    def register(self, ident, checksum, connection_id):
        with _lock:
            state = self.get(ident)
            if state['status'] != 'ready' or checksum != state['checksum']:
                raise ValueError('Only a reviewed, successfully built and tested proposal can be registered')
            self._check_sources(state)
            if self._artifacts(state) != state['artifacts']:
                raise ValueError('Tool artifacts changed after testing')
            config = self._connection(state)
            if file_digest(config.argv[0]) != state['connection_executable_sha256']:
                raise ValueError('Connection executable changed after testing')
            if HarnessService(self.engine, self.db).get(connection_id):
                raise ValueError('Choose a new connection identifier; existing connections are never overwritten')
            profile = HarnessService(self.engine, self.db).save(connection_id, config)
            state.update(status='registered', connection_id=profile['id'])
            return self._save(state)

    def disable(self, ident):
        with _lock:
            state = self.get(ident)
            if state['status'] == 'registered':
                raise ValueError('Registered connections are managed separately; disabling a recipe does not revoke running jobs')
            if state.get('task_id'):
                task = self.engine.get_task(state['task_id'])
                if task and task['status'].lower() in {'queued', 'waiting_approval'}:
                    self.engine.cancel_task(task['id'])
            state.update(status='disabled', notice='No further recipe tasks will be submitted. An already running task may finish.')
            return self._save(state)
