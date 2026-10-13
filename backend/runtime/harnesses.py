"""Owner-configured CLI adapters, executed as exact approved host-process tasks."""
import hashlib
import json
import os
from pathlib import Path
import re
from pydantic import BaseModel, ConfigDict, Field

ENVIRONMENT_KEYS = {'HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'HERMES_HOME',
                    'HERMES_PROFILE', 'OLLAMA_HOST', 'ANTHROPIC_BASE_URL'}

class HarnessConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(default='custom-cli', pattern=r'^[a-z][a-z0-9_-]{0,40}$')
    argv: list[str] = Field(min_length=2, max_length=40)
    environment: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=600, ge=1, le=1800)

def validate_config(config):
    if not Path(config.argv[0]).is_absolute() or not Path(config.argv[0]).is_file():
        raise ValueError('Choose an installed executable by absolute path')
    if sum(arg == '{prompt}' for arg in config.argv) != 1:
        raise ValueError('Include exactly one standalone {prompt} argument')
    for arg in config.argv:
        if not arg or len(arg) > 4000 or '\x00' in arg: raise ValueError('Invalid command argument')
        if any(token in arg and arg != token for token in ('{prompt}', '{workspace}')):
            raise ValueError('Placeholders must occupy a complete argument')
    validate_environment(config.environment)
    return config

def validate_environment(environment):
    if not isinstance(environment, dict) or not set(environment) <= ENVIRONMENT_KEYS:
        raise ValueError('Use supported configuration paths; keep API keys in the harness credential store')
    if any(not isinstance(value, str) or len(value) > 2000 or '\x00' in value for value in environment.values()):
        raise ValueError('Invalid harness environment')

class HarnessService:
    def __init__(self, engine, database):
        self.engine, self.db = engine, database
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS harness_profiles(id TEXT PRIMARY KEY,config_json TEXT NOT NULL)')
            conn.commit()

    def list(self):
        with self.db.get_connection() as conn:
            rows = conn.execute('SELECT id,config_json FROM harness_profiles ORDER BY id').fetchall()
        return [{'id': row[0], **json.loads(row[1])} for row in rows]

    def get(self, ident):
        return next((item for item in self.list() if item['id'] == ident), None)

    def save(self, ident, config):
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', ident): raise ValueError('Use a short connection name')
        validate_config(config)
        data = config.model_dump()
        data['revision'] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        with self.db.get_connection() as conn:
            conn.execute('INSERT INTO harness_profiles VALUES(?,?) ON CONFLICT(id) DO UPDATE SET config_json=excluded.config_json', (ident, json.dumps(data)))
            conn.commit()
        self.engine.events.publish('harness.saved', {'id': ident, 'revision': data['revision']})
        return {'id': ident, **data}

    def submit(self, ident, prompt, cwd='.'):
        from backend.runtime.computer_tools import workspace_path
        profile = self.get(ident)
        if not profile: raise ValueError('Harness connection not found')
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000 or '\x00' in prompt:
            raise ValueError('Describe the job in 1–4000 characters')
        config = validate_config(HarnessConfig.model_validate({key: value for key, value in profile.items() if key not in {'id', 'revision'}}))
        work = workspace_path(cwd)
        work.mkdir(parents=True, exist_ok=True)
        argv = [prompt if arg == '{prompt}' else str(work) if arg == '{workspace}' else arg for arg in config.argv]
        return self.engine.submit_task(prompt, metadata={'actor': 'owner', 'tool': 'harness.run@1.0.0',
            'harness_id': ident, 'harness_revision': profile['revision'],
            'tool_parameters': {'argv': argv, 'cwd': cwd, 'timeout_seconds': config.timeout_seconds, 'environment': config.environment},
            'required_capabilities': ['process.execute'], 'source': 'owner_harness_connection'})

def run_harness(params):
    from backend.runtime.computer_tools import run_process
    environment = params.get('environment', {})
    validate_environment(environment)
    inherited = {key: os.environ[key] for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA') if key in os.environ}
    result = run_process(params, max_timeout=1800, environment={**inherited, **environment})
    return {**result, 'scope': 'External harness host process. Its own tools and credentials remain governed by that harness; working directory is not an OS sandbox.',
            'verification_scope': 'Process exit and captured output only; repository changes require separate tests and review.'}
