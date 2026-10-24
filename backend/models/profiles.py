"""Owner-configured model endpoints with encrypted, write-only credentials."""
import json
import os
from pathlib import Path
import re
import time
import ssl
from urllib.parse import urlsplit
from cryptography.fernet import Fernet


def model_tls_context(config):
    certificate = config.get('ca_certificate', '')
    return ssl.create_default_context(cadata=certificate) if certificate else True


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
        if config.get('hosting', 'auto') not in {'auto', 'local', 'cloud'}:
            raise ValueError('Choose local or cloud model hosting')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', ident): raise ValueError('Invalid model profile name')
        parts = urlsplit(config['endpoint'])
        if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('Use a model server URL without embedded credentials')
        if parts.scheme == 'http' and parts.hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ValueError('Remote model servers require HTTPS')
        certificate = config.get('ca_certificate', '')
        if not isinstance(certificate, str) or len(certificate) > 32000:
            raise ValueError('Invalid model server CA certificate')
        if certificate:
            if parts.scheme != 'https': raise ValueError('A CA certificate requires an HTTPS endpoint')
            try: model_tls_context(config)
            except (ssl.SSLError, ValueError) as error:
                raise ValueError('Invalid model server CA certificate') from error
        if len(config['model']) > 200 or not config['model'].strip(): raise ValueError('Supply the installed model identifier')
        if config['provider'] not in {'ollama', 'openai_compatible'}: raise ValueError('Unsupported model protocol')
        if config.get('ollama_think') is not None and type(config['ollama_think']) is not bool:
            raise ValueError('ollama_think must be an explicit boolean or unset')
        if config.get('ollama_think') is not None and config['provider'] != 'ollama':
            raise ValueError('ollama_think is only supported by native Ollama profiles')
        if config.get('variant') not in {'standard', 'fine_tuned', 'abliterated', 'custom'}: raise ValueError('Unsupported model label')
        pool = config.get('pool_group', '')
        if pool and not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', pool):
            raise ValueError('Use a short pool name such as chat')
        computer = config.get('computer_id', '')
        if computer and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', computer):
            raise ValueError('Use a short computer name such as laptop3')
        for field, default, minimum, maximum in [('max_parallel', 1, 1, 4), ('timeout_seconds', 120, 30, 600),
                                                 ('max_output_tokens', 512, 16, 8192), ('num_ctx', 8192, 512, 131072)]:
            value = config.get(field, default)
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise ValueError('Invalid ' + field)
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
