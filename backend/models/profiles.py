"""Owner-configured model endpoints with encrypted, write-only credentials."""
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from cryptography.fernet import Fernet


class ModelProfiles:
    def __init__(self, database, root='data/secrets'):
        self.db, self.root = database, Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        key = self.root / 'vault.key'
        if not key.exists():
            try:
                fd = os.open(key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, 'wb') as handle: handle.write(Fernet.generate_key())
            except FileExistsError: pass
        self.cipher = Fernet(key.read_bytes())
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS model_profiles(id TEXT PRIMARY KEY, config_json TEXT NOT NULL, secret BLOB)')
            conn.commit()

    def save(self, ident, config, api_key=None):
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', ident): raise ValueError('Invalid model profile name')
        parts = urlsplit(config['endpoint'])
        if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('Use a model server URL without embedded credentials')
        if parts.scheme == 'http' and parts.hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ValueError('Remote model servers require HTTPS')
        if len(config['model']) > 200 or not config['model'].strip(): raise ValueError('Supply the installed model identifier')
        if config['provider'] not in {'ollama', 'openai_compatible'}: raise ValueError('Unsupported model protocol')
        if config.get('variant') not in {'standard', 'fine_tuned', 'abliterated', 'custom'}: raise ValueError('Unsupported model label')
        config = {**config, 'id': ident, 'endpoint': config['endpoint'].rstrip('/'), 'updated_at': time.time()}
        secret = self.cipher.encrypt(api_key.encode()) if api_key else None
        with self.db.get_connection() as conn:
            previous = conn.execute('SELECT secret FROM model_profiles WHERE id=?', (ident,)).fetchone()
            if api_key is None and previous: secret = previous[0]
            conn.execute('INSERT INTO model_profiles VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET config_json=excluded.config_json,secret=excluded.secret', (ident, json.dumps(config), secret))
            conn.commit()
        return self.get(ident)

    def get(self, ident, credential=False):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT config_json,secret FROM model_profiles WHERE id=?', (ident,)).fetchone()
        if not row: raise KeyError('Model profile not found')
        item = json.loads(row[0]); item['has_credentials'] = bool(row[1])
        if credential: item['api_key'] = self.cipher.decrypt(row[1]).decode() if row[1] else ''
        return item

    def list(self):
        with self.db.get_connection() as conn:
            identifiers = [row[0] for row in conn.execute('SELECT id FROM model_profiles ORDER BY id')]
        return [self.get(ident) for ident in identifiers]
