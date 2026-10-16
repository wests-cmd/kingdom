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


def identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('Invalid project or document identity')
    return value


def clean_text(value):
    text = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', '[redacted]', str(value), flags=re.S)
    text = re.sub(r'(?i)(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{10,}|bearer\s+\S+', '[redacted]', text)
    text = re.sub(r'(?i)(https?://)[^\s/@]+:[^\s/@]+@', r'\1[redacted]@', text)
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
            conn.commit()

    def put(self, project, body, provenance=None, receipts=None, ident=None, expected_revision=0):
        project, ident = identifier(project), identifier(ident or uuid.uuid4().hex)
        if not isinstance(body, str) or len(body.encode()) > 262144:
            raise ValueError('Document exceeds 256 KB')
        metadata = clean_metadata({'provenance': provenance or {}, 'receipts': receipts or [], 'trust': 'untrusted'})
        encoded = json.dumps(metadata, allow_nan=False, sort_keys=True)
        if len(encoded) > 32768:
            raise ValueError('Metadata exceeds limit')
        body = clean_text(body)
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            old = conn.execute('SELECT revision FROM portable_vault WHERE project=? AND id=?', (project, ident)).fetchone()
            actual = old[0] if old else 0
            if expected_revision != actual:
                raise ValueError('Document changed; reload before updating')
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
            metadata = clean_metadata({'provenance': meta.get('provenance', {}), 'receipts': meta.get('receipts', []), 'trust': 'untrusted'})
            encoded = json.dumps(metadata, allow_nan=False, sort_keys=True)
            if len(encoded) > 32768:
                raise ValueError('Metadata exceeds limit')
            prepared.append((meta['id'], clean_text(body), encoded))
        imported = []
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            for ident, body, metadata in prepared:
                old = conn.execute('SELECT body,metadata FROM portable_vault WHERE project=? AND id=?', (project, ident)).fetchone()
                if old:
                    if tuple(old) != (body, metadata):
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

    def search(self, project, query):
        terms = set(re.findall(r'\w+', query.lower()))
        with self.db.get_connection() as conn:
            rows = conn.execute('SELECT id,terms FROM portable_vault_index WHERE project=?', (identifier(project),)).fetchall()
        return [self.get(project, row[0]) for row in rows if terms.intersection(row[1].split())][:20]

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
