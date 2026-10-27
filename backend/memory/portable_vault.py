"""Project-scoped Markdown interchange; SQLite is canonical, indexes disposable.

Imports grant no permissions and never fetch provenance/receipt references.
Exports omit credential-shaped values; arbitrary secrets cannot be inferred.
"""
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

_ID = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
_SECRET = re.compile(r'(?i)(password|api[_ -]?key|secret|token|authorization|private[_ -]?key|credential|cookie|access[_ -]?code)')


def project_identity(scope):
    """Keep arbitrary front-door scope labels isolated without filesystem paths."""
    if not isinstance(scope, str) or not scope.strip() or len(scope) > 200:
        raise ValueError('Invalid project scope')
    return 'project_' + hashlib.sha256(scope.encode('utf-8')).hexdigest()[:32]


def identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('Invalid project or document identity')
    return value


def _redact_private_keys(text):
    """Scan bounded PEM headers once, including unfinished private-key blocks."""
    marker = re.compile(r'-----((?:BEGIN|END)) ([^-\r\n]{0,80}PRIVATE KEY)-----')
    parts, cursor, opened = [], 0, None
    for match in marker.finditer(text):
        if match[1] == 'BEGIN' and opened is None:
            opened = match.start()
        elif match[1] == 'END' and opened is not None:
            parts.extend((text[cursor:opened], '[redacted]'))
            cursor, opened = match.end(), None
    if opened is not None:
        parts.extend((text[cursor:opened], '[redacted]'))
    else:
        parts.append(text[cursor:])
    return ''.join(parts)


def clean_text(value):
    text = _redact_private_keys(str(value))
    text = re.sub(r'(?i)(?:ghp_|github_pat_|sk-|(?:sk|rk)_(?:test|live)_)[A-Za-z0-9_-]{10,}|bearer\s+\S+', '[redacted]', text)
    # Consume each authority token once; do not retry a username/password split
    # at every colon when untrusted text has no terminating @.
    text = re.sub(r'(?i)(https?://)([^\s/@]*)',
                  lambda m: m[1]+'[redacted]' if ':' in m[2] and m.string[m.end():m.end()+1]=='@' else m[0], text)
    return re.sub(r'(?im)((?:password|api[_ -]?key|secret|token|authorization)\s*[:=]\s*)[^\n,;]+', r'\1[redacted]', text)


def clean_metadata(value, depth=0):
    if depth > 6:
        raise ValueError('Metadata nesting exceeds limit')
    if isinstance(value, dict):
        return {clean_text(key): clean_metadata(item, depth+1) for key, item in value.items() if not _SECRET.search(str(key))}
    if isinstance(value, list):
        return [clean_metadata(item, depth+1) for item in value]
    if isinstance(value, str):
        return clean_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise ValueError('Unsupported metadata')


class PortableVault:
    def __init__(self, database, publish=None):
        self.db, self.publish = database, publish or (lambda *args: None)
        with self.db.get_connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS portable_vault (
                project TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL,body TEXT NOT NULL,
                metadata TEXT NOT NULL,updated REAL NOT NULL,PRIMARY KEY(project,id))''')
            conn.execute('''CREATE TABLE IF NOT EXISTS portable_vault_index (
                project TEXT NOT NULL,id TEXT NOT NULL,terms TEXT NOT NULL,PRIMARY KEY(project,id))''')
            conn.execute('''CREATE TABLE IF NOT EXISTS portable_vault_trash (
                project TEXT NOT NULL,id TEXT NOT NULL,document TEXT NOT NULL,PRIMARY KEY(project,id))''')
            conn.commit()

    def put(self, project, body, provenance=None, receipts=None, ident=None, expected_revision=0, allowed_roles=None):
        project, ident = identifier(project), identifier(ident or uuid.uuid4().hex)
        if not isinstance(body, str) or len(body.encode()) > 262144:
            raise ValueError('Document exceeds 256 KB')
        from backend.memory.vault_policy import readers,reject_payment_details
        reject_payment_details(json.dumps({'body':body,'provenance':provenance or {},'receipts':receipts or []}))
        metadata = clean_metadata({'provenance': provenance or {}, 'receipts': receipts or [], 'trust': 'untrusted','allowed_roles':readers(allowed_roles)})
        encoded = json.dumps(metadata, allow_nan=False, sort_keys=True)
        if len(encoded) > 32768:
            raise ValueError('Metadata exceeds limit')
        body = clean_text(body)
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            old = conn.execute('SELECT revision,metadata FROM portable_vault WHERE project=? AND id=?', (project, ident)).fetchone()
            if not old and conn.execute('SELECT 1 FROM portable_vault_trash WHERE project=? AND id=?', (project, ident)).fetchone():
                raise ValueError('Document is in trash; restore explicitly before editing')
            actual = old[0] if old else 0
            if expected_revision != actual:
                raise ValueError('Document changed; reload before updating')
            if allowed_roles is None and old:
                metadata['allowed_roles']=readers(json.loads(old[1]).get('allowed_roles',[]))
                encoded=json.dumps(metadata,allow_nan=False,sort_keys=True)
                if len(encoded)>32768:raise ValueError('Metadata exceeds limit')
            revision = actual+1
            conn.execute('INSERT OR REPLACE INTO portable_vault VALUES(?,?,?,?,?,?)', (project, ident, revision, body, encoded, time.time()))
            self._index(conn, project, ident, body)
            conn.commit()
        self.publish('vault.document_saved', {'project': project, 'id': ident, 'revision': revision})
        return self.get(project, ident)

    @staticmethod
    def _index(conn, project, ident, body):
        terms = ' '.join(sorted(set(re.findall(r'\w+', body.lower()))))
        conn.execute('INSERT OR REPLACE INTO portable_vault_index VALUES(?,?,?)', (project, ident, terms))

    def get(self, project, ident):
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT * FROM portable_vault WHERE project=? AND id=?', (identifier(project), identifier(ident))).fetchone()
        if not row:
            raise KeyError(ident)
        return {'project': row['project'], 'id': row['id'], 'revision': row['revision'], 'body': row['body'], **json.loads(row['metadata'])}

    def export(self, project):
        identifier(project)
        with self.db.get_connection() as conn:
            # One SQLite read snapshot avoids mixed revisions under concurrent edits.
            rows = conn.execute('SELECT * FROM portable_vault WHERE project=? ORDER BY id', (project,)).fetchall()
        files = {}
        for row in rows:
            ident, body = row['id'], row['body']
            doc = {'project': row['project'], 'id': ident, 'revision': row['revision'], **json.loads(row['metadata'])}
            doc['sha256'] = hashlib.sha256(body.encode()).hexdigest()
            header = json.dumps(doc, sort_keys=True).replace('<', '\\u003c').replace('>', '\\u003e')
            files[ident+'.md'] = '<!-- kingdom-vault '+header+' -->\n'+body
        return files

    def trash(self, project, ident, expected_revision):
        identifier(project); identifier(ident)
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM portable_vault WHERE project=? AND id=?', (project, ident)).fetchone()
            if not row or row['revision'] != expected_revision:
                raise ValueError('Document changed or is already removed')
            conn.execute('INSERT OR REPLACE INTO portable_vault_trash VALUES(?,?,?)', (project, ident, json.dumps(dict(row))))
            conn.execute('DELETE FROM portable_vault WHERE project=? AND id=?', (project, ident))
            conn.execute('DELETE FROM portable_vault_index WHERE project=? AND id=?', (project, ident))
            conn.commit()
        self.publish('vault.document_trashed', {'project': project, 'id': ident})
        return {'id': ident, 'status': 'trashed', 'recoverable': True}

    def restore(self, project, ident):
        identifier(project); identifier(ident)
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT document FROM portable_vault_trash WHERE project=? AND id=?', (project, ident)).fetchone()
            if not row or conn.execute('SELECT 1 FROM portable_vault WHERE project=? AND id=?', (project, ident)).fetchone():
                raise ValueError('No restorable document')
            saved = json.loads(row[0])
            conn.execute('INSERT INTO portable_vault VALUES(?,?,?,?,?,?)', (project, ident, saved['revision']+1, saved['body'], saved['metadata'], time.time()))
            conn.execute('DELETE FROM portable_vault_trash WHERE project=? AND id=?', (project, ident))
            self._index(conn, project, ident, saved['body'])
            conn.commit()
        return self.get(project, ident)

    def import_files(self, project, files):
        identifier(project)
        if not isinstance(files, dict) or len(files) > 100 or sum(len(str(v).encode()) for v in files.values()) > 2*1024*1024:
            raise ValueError('Import exceeds 100 documents or 2 MB')
        prepared = []
        for name, markdown in files.items():
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}\.md', name) or not isinstance(markdown, str):
                raise ValueError('Invalid Markdown filename')
            header, separator, body = markdown.partition('\n')
            if not separator or not header.startswith('<!-- kingdom-vault ') or not header.endswith(' -->'):
                raise ValueError('Missing portable metadata')
            meta = json.loads(header[len('<!-- kingdom-vault '):-4])
            if not isinstance(meta, dict) or meta.get('project') != project or not isinstance(meta.get('id'), str) or meta['id']+'.md' != name:
                raise ValueError('Document is outside the selected project')
            if hashlib.sha256(body.encode()).hexdigest() != meta.get('sha256'):
                raise ValueError('Document checksum mismatch')
            # Validate everything before the atomic import transaction.
            identifier(meta['id'])
            if len(body.encode()) > 262144:
                raise ValueError('Document exceeds 256 KB')
            from backend.memory.vault_policy import readers,reject_payment_details
            reject_payment_details(json.dumps({'body':body,'provenance':meta.get('provenance',{})}))
            metadata = clean_metadata({'provenance': meta.get('provenance', {}), 'receipts': meta.get('receipts', []), 'trust': 'untrusted','allowed_roles':readers(meta.get('allowed_roles',[]))})
            encoded = json.dumps(metadata, allow_nan=False, sort_keys=True)
            if len(encoded) > 32768:
                raise ValueError('Metadata exceeds limit')
            prepared.append((meta['id'], clean_text(body), encoded))
        imported = []
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            for ident, body, metadata in prepared:
                if conn.execute('SELECT 1 FROM portable_vault_trash WHERE project=? AND id=?', (project, ident)).fetchone():
                    raise ValueError('Import cannot silently restore a trashed document')
                old = conn.execute('SELECT body,metadata FROM portable_vault WHERE project=? AND id=?', (project, ident)).fetchone()
                if old:
                    previous = json.loads(old[1])
                    previous.setdefault('allowed_roles', [])
                    if old[0] != body or previous != json.loads(metadata):
                        raise ValueError('Existing identity has different content; update with expected revision')
                    continue
                conn.execute('INSERT INTO portable_vault VALUES(?,?,?,?,?,?)', (project, ident, 1, body, metadata, time.time()))
                self._index(conn, project, ident, body)
                imported.append(ident)
            conn.commit()
        self.publish('vault.imported', {'project': project, 'ids': imported})
        return {'imported': imported, 'unchanged': len(files)-len(imported), 'trust': 'untrusted'}

    def rebuild_index(self, project):
        identifier(project)
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('DELETE FROM portable_vault_index WHERE project=?', (project,))
            rows = conn.execute('SELECT id,body FROM portable_vault WHERE project=?', (project,)).fetchall()
            for row in rows:
                self._index(conn, project, row[0], row[1])
            conn.commit()
        self.publish('vault.index_rebuilt', {'project': project, 'count': len(rows)})
        return len(rows)

    def search(self, project, query, reader_role=None):
        terms = set(re.findall(r'\w+', query.lower()))
        with self.db.get_connection() as conn:
            rows = conn.execute('SELECT id,terms FROM portable_vault_index WHERE project=?', (identifier(project),)).fetchall()
        from backend.memory.vault_policy import can_read
        found=[self.get(project,row[0]) for row in rows if terms.intersection(row[1].split())]
        return [document for document in found if can_read(document,reader_role)][:20]

    def export_directory(self, project, root):
        """Internal-only caller supplies a configured root, never an HTTP path."""
        root = Path(root).resolve()
        target = root / identifier(project)
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            raise ValueError('Unsafe project directory')
        target.mkdir(parents=True, exist_ok=True)
        for name, markdown in self.export(project).items():
            path = target/name
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError('Unsafe document path')
            # Exclusive create never follows or overwrites a concurrently supplied path.
            with path.open('x', encoding='utf-8') as output:
                output.write(markdown)
        return str(target)
