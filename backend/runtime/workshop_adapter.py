"""Local skill workshop inventory; no remote commands or credential collection."""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from backend.runtime.automation import ReviewRequired


class WorkshopAdapter:
    id = 'laptop2-skill-workshop'
    name = 'Laptop 2 skill workshop'

    def __init__(self, root, runner=None):
        self.root = Path(root)
        self.runner = runner
        self.manifest = json.loads((self.root / 'app/automation-manifest.json').read_text())
        self.revision = hashlib.sha256(json.dumps(self.manifest, sort_keys=True).encode()).hexdigest()

    def inspect(self):
        path = self.root / 'skill-workshop/workshop.sqlite3'
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            skills = db.execute('SELECT COUNT(*) FROM skills').fetchone()[0]
            active = db.execute("SELECT slug,mode,elapsed,status FROM sessions WHERE status IN ('working','publishing')").fetchall()
        return {'completed_skills': skills, 'active_work': [dict(zip(('skill','mode','seconds','status'), row)) for row in active],
                'schedule': '9 AM Pacific; 3h new + 3h new + 3h refine + 3h Kingdom review',
                'outputs': ['Discord #ai-skill-map', 'Discord #road-map'],
                'original_retained': True}

    def verify(self):
        if not self.manifest.get('tests_passed') or not self.manifest.get('files'):
            raise ReviewRequired('Deployment test evidence is missing')
        for name, digest in self.manifest['files'].items():
            if Path(name).name != name or not name.endswith('.py'):
                raise ReviewRequired('Invalid reviewed source name')
            if hashlib.sha256((self.root / 'app' / name).read_bytes()).hexdigest() != digest:
                raise ReviewRequired('Reviewed source changed; test and approve its new revision')
        core = self.manifest.get('supervisor_files', {})
        expected = {'backend/runtime/automation.py', 'backend/runtime/workshop_adapter.py',
                    'scripts/workshop_supervisor.py'}
        if set(core) != expected:
            raise ReviewRequired('Supervisor source evidence is missing')
        for name, digest in core.items():
            if hashlib.sha256((self.root / 'kingdom-automation-source' / name).read_bytes()).hexdigest() != digest:
                raise ReviewRequired('Supervisor changed; retest and approve its new revision')
        if hashlib.sha256((self.root / 'app/workshop_supervisor.py').read_bytes()).hexdigest() != core['scripts/workshop_supervisor.py']:
            raise ReviewRequired('Installed supervisor entry point changed')
        observed = self.inspect()
        return {'passed': True, 'checks': ['reviewed source hashes', 'read-only progress inspection',
                                         'deployment regression suite'],
                'completed_skills': observed['completed_skills'],
                'revision': self.revision}

    def run_original(self):
        if self.runner is None:
            raise RuntimeError('Execution belongs to the local sandboxed timer')
        self.runner()

    def run_candidate(self):
        self.verify()
        self.run_original()
