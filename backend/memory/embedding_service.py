"""Persisted, scope-isolated vector retrieval using real model profile embeddings."""
import hashlib
import json
import math
import re
import time
import uuid

import httpx

from backend.events.event_bus import event_bus
from backend.models.profiles import ModelProfiles, model_tls_context


def validate_vector(value, dimension=None):
    if not isinstance(value, list) or not 1 <= len(value) <= 8192:
        raise ValueError("Embedding must contain 1 to 8192 numbers")
    if dimension is not None and len(value) != dimension:
        raise ValueError("Embedding dimension changed")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in value):
        raise ValueError("Embedding contains non-finite or invalid numbers")
    norm = math.hypot(*(float(item) for item in value))
    if not math.isfinite(norm) or norm == 0:
        raise ValueError("Embedding must have a finite nonzero norm")
    return [float(item) / norm for item in value]


class ProfileEmbeddingProvider:
    def __init__(self, profiles):
        self.profiles = profiles

    def fingerprint(self, profile_id):
        config = self.profiles.get(profile_id)
        # Endpoint/model changes cannot silently compare incompatible vector spaces.
        return hashlib.sha256(json.dumps([config['provider'], config['endpoint'], config['model']]).encode()).hexdigest()

    async def embed(self, profile_id, texts):
        from backend.models.capacity import capacity
        configured = self.profiles.list()
        candidate = self.profiles.get(profile_id)
        async with capacity.acquire([candidate], server_profiles=configured):
            profile = self.profiles.get(profile_id, credential=True)
            headers = {'Authorization': 'Bearer ' + profile['api_key']} if profile['api_key'] else {}
            if profile['provider'] == 'ollama':
                path = '/api/embed'
                body = {'model': profile['model'], 'input': texts, 'truncate': False}
            else:
                path = '/embeddings'
                body = {'model': profile['model'], 'input': texts}
            async with httpx.AsyncClient(timeout=profile.get('timeout_seconds', 120),
                    follow_redirects=False, verify=model_tls_context(profile)) as client:
                response = await client.post(profile['endpoint'] + path, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
            if profile['provider'] == 'ollama':
                return payload.get('embeddings')
            data = payload.get('data')
            if not isinstance(data, list) or sorted(row.get('index', -1) for row in data) != list(range(len(texts))):
                raise ValueError('Invalid embedding response indexes')
            return [row['embedding'] for row in sorted(data, key=lambda row: row['index'])]


class EmbeddingKnowledge:
    def __init__(self, database, provider=None, events=None):
        self.db = database
        self.provider = provider or ProfileEmbeddingProvider(ModelProfiles(database))
        self.events = events or event_bus
        with database.get_connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS knowledge_documents (
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, source TEXT NOT NULL, profile TEXT NOT NULL,
                fingerprint TEXT NOT NULL, dimension INTEGER NOT NULL, sha256 TEXT NOT NULL, created REAL NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS knowledge_chunks (
                document_id TEXT NOT NULL, position INTEGER NOT NULL, text TEXT NOT NULL, vector TEXT NOT NULL,
                PRIMARY KEY(document_id,position))''')
            conn.execute('CREATE INDEX IF NOT EXISTS knowledge_scope ON knowledge_documents(scope,profile)')
            conn.execute('CREATE TABLE IF NOT EXISTS knowledge_provenance(document_id TEXT PRIMARY KEY,metadata_json TEXT NOT NULL)')

    @staticmethod
    def scope(value):
        if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_.-]{0,63}', value):
            raise ValueError('Use a named knowledge scope')
        return value

    def list_documents(self, scope):
        self.scope(scope)
        with self.db.get_connection() as conn:
            rows = conn.execute('SELECT id,source,profile,dimension,sha256,created FROM knowledge_documents WHERE scope=? ORDER BY created DESC', (scope,)).fetchall()
        return [dict(row) for row in rows]

    async def ingest(self, scope, profile, source, text, provenance=None):
        self.scope(scope)
        if not isinstance(text, str) or not text.strip() or len(text.encode()) > 262144 or '\x00' in text:
            raise ValueError('Supply 1 to 262144 bytes of text')
        if not isinstance(source, str) or not source.strip() or len(source) > 500 or '\x00' in source:
            raise ValueError('Supply a source label up to 500 characters')
        # Character chunks bound model inputs independently of tokenizers; overlap retains context.
        chunks = [text[start:start + 700] for start in range(0, len(text), 600)]
        if len(chunks) > 450:
            raise ValueError('Document exceeds chunk limit')
        fingerprint = self.provider.fingerprint(profile)
        metadata=json.dumps(provenance or {},ensure_ascii=False)
        if not isinstance(provenance or {},dict) or len(metadata)>4000:raise ValueError('Source provenance must be a bounded object')
        source_hash=hashlib.sha256(text.encode()).hexdigest()
        with self.db.get_connection() as conn:
            existing=conn.execute('SELECT id,dimension FROM knowledge_documents WHERE scope=? AND source=? AND profile=? AND fingerprint=? AND sha256=?',(scope,source,profile,fingerprint,source_hash)).fetchone()
            if existing:
                count=conn.execute('SELECT COUNT(*) FROM knowledge_chunks WHERE document_id=?',(existing['id'],)).fetchone()[0]
                return {'document_id':existing['id'],'scope':scope,'chunks':count,'dimension':existing['dimension'],'state':'already_embedded'}
        vectors = []
        for start in range(0, len(chunks), 16):
            batch = chunks[start:start + 16]
            result = await self.provider.embed(profile, batch)
            if not isinstance(result, list) or len(result) != len(batch):
                raise ValueError('Embedding count differs from chunk count')
            for vector in result:
                vectors.append(validate_vector(vector, len(vectors[0]) if vectors else None))
        if fingerprint != self.provider.fingerprint(profile):
            raise ValueError('Embedding profile changed during ingestion')
        ident = uuid.uuid4().hex
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            count = conn.execute('SELECT COUNT(*) FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id WHERE d.scope=?', (scope,)).fetchone()[0]
            if count + len(chunks) > 5000:
                raise ValueError('Scope exceeds 5000 chunk limit; delete documents first')
            conn.execute('INSERT INTO knowledge_documents VALUES(?,?,?,?,?,?,?,?)',
                (ident, scope, source, profile, fingerprint, len(vectors[0]), hashlib.sha256(text.encode()).hexdigest(), time.time()))
            conn.executemany('INSERT INTO knowledge_chunks VALUES(?,?,?,?)',
                [(ident, index, chunk, json.dumps(vectors[index])) for index, chunk in enumerate(chunks)])
            conn.execute('INSERT INTO knowledge_provenance VALUES(?,?)',(ident,metadata))
        self.events.publish('knowledge.ingested', {'scope': scope, 'document_id': ident, 'chunks': len(chunks)})
        return {'document_id': ident, 'scope': scope, 'chunks': len(chunks), 'dimension': len(vectors[0]), 'state': 'embedded'}

    async def search(self, scope, profile, query, limit=5):
        self.scope(scope)
        if not isinstance(query, str) or not query.strip() or len(query) > 8000 or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
            raise ValueError('Invalid search query or limit')
        fingerprint = self.provider.fingerprint(profile)
        with self.db.get_connection() as conn:
            rows = conn.execute('''SELECT d.id,d.source,d.dimension,c.position,c.text,c.vector,p.metadata_json FROM knowledge_documents d
                JOIN knowledge_chunks c ON c.document_id=d.id LEFT JOIN knowledge_provenance p ON p.document_id=d.id WHERE d.scope=? AND d.profile=? AND d.fingerprint=?''',
                (scope, profile, fingerprint)).fetchall()
        if not rows:
            return []
        result = await self.provider.embed(profile, [query])
        if not isinstance(result, list) or len(result) != 1:
            raise ValueError('Invalid query embedding count')
        vector = validate_vector(result[0], rows[0]['dimension'])
        if fingerprint != self.provider.fingerprint(profile):
            raise ValueError('Embedding profile changed during search')
        ranked = []
        for row in rows:
            stored = validate_vector(json.loads(row['vector']), len(vector))
            score = max(-1.0, min(1.0, sum(a * b for a, b in zip(vector, stored))))
            ranked.append({'document_id': row['id'], 'source': row['source'], 'chunk': row['position'], 'provenance':json.loads(row['metadata_json']) if row['metadata_json'] else {},
                'citation': f"knowledge:{row['id']}:{row['position']}", 'text': row['text'], 'score': score})
        return sorted(ranked, key=lambda row: (-row['score'], row['citation']))[:limit]

    def delete(self, scope, document_id):
        self.scope(scope)
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT id FROM knowledge_documents WHERE scope=? AND id=?', (scope, document_id)).fetchone()
            if not row:
                raise KeyError('Document not found in this scope')
            conn.execute('DELETE FROM knowledge_chunks WHERE document_id=?', (document_id,))
            conn.execute('DELETE FROM knowledge_provenance WHERE document_id=?',(document_id,))
            conn.execute('DELETE FROM knowledge_documents WHERE id=?', (document_id,))
        self.events.publish('knowledge.deleted', {'scope': scope, 'document_id': document_id})
        return {'deleted': document_id}
