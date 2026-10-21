from types import SimpleNamespace
import math
import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.memory.embedding_service import EmbeddingKnowledge, validate_vector
from backend.memory import knowledge_api
from backend.storage.db import Database


class Embeddings:
    version = 'v1'
    def fingerprint(self, profile):
        return self.version
    async def embed(self, profile, texts):
        return [[1, 0] if 'cat' in text.lower() else [0, 1] for text in texts]

@pytest.mark.asyncio
async def test_unchanged_ingest_reuses_vectors(tmp_path):
    provider=Embeddings();calls=[]
    original=provider.embed
    async def counted(profile,texts):calls.append(texts);return await original(profile,texts)
    provider.embed=counted
    knowledge=service(tmp_path,provider)
    first=await knowledge.ingest('project','embed','cats.md','Cats purr',provenance={'publisher_verified':False})
    second=await knowledge.ingest('project','embed','cats.md','Cats purr')
    assert first['document_id']==second['document_id'] and second['state']=='already_embedded' and len(calls)==1
    hits=await knowledge.search('project','embed','cat')
    assert hits[0]['provenance']=={'publisher_verified':False}

def test_discord_preview_binds_import_scope_and_channels(tmp_path):
    import json
    from backend.security.http_auth import require_owner
    knowledge_api.initialize(Database(tmp_path/'discord-api.db'),Embeddings())
    app=FastAPI();app.include_router(knowledge_api.router);app.dependency_overrides[require_owner]=lambda:'owner'
    payload={'profile':'embed','allowed_channel_ids':['2'],'export_json':json.dumps({'messages':[{'id':'1','channel_id':'2','author_id':'3','timestamp':'now','content':'Cats purr'}]})}
    with TestClient(app) as client:
        preview=client.post('/knowledge/project/discord/preview',json=payload).json()
        approved={**payload,'checksum':preview['checksum']}
        assert client.post('/knowledge/other/discord/import',json=approved).status_code==409
        assert client.post('/knowledge/project/discord/import',json=approved).status_code==200
        hits=client.post('/knowledge/project/search',json={'profile':'embed','query':'cat'}).json()
        assert hits[0]['provenance']['channel_id']=='2' and hits[0]['provenance']['publisher_verified'] is False


def service(tmp_path, provider=None):
    return EmbeddingKnowledge(Database(tmp_path / 'knowledge.db'), provider or Embeddings(),
        SimpleNamespace(publish=lambda *args: None))


@pytest.mark.asyncio
async def test_vectors_persist_rank_and_never_cross_scope(tmp_path):
    knowledge = service(tmp_path)
    cats = await knowledge.ingest('project-a', 'embed', 'cats.md', 'Cats like warm places.')
    await knowledge.ingest('project-a', 'embed', 'ocean.md', 'Waves are water.')
    await knowledge.ingest('private', 'embed', 'secret.md', 'Cats are secret.')
    restored = service(tmp_path)
    hits = await restored.search('project-a', 'embed', 'cat', 2)
    assert hits[0]['source'] == 'cats.md'
    assert hits[0]['score'] == 1.0
    assert hits[0]['citation'] == f"knowledge:{cats['document_id']}:0"
    assert len(hits) == 2
    assert not await restored.search('empty', 'embed', 'cat')
    with pytest.raises(KeyError):
        restored.delete('private', cats['document_id'])
    restored.delete('project-a', cats['document_id'])
    assert len(restored.list_documents('project-a')) == 1
    with restored.db.get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM knowledge_chunks WHERE document_id=?', (cats['document_id'],)).fetchone()[0] == 0


@pytest.mark.parametrize('vector', [[], [0, 0], [float('nan')], [float('inf')], [True], ['1']])
def test_invalid_vectors(vector):
    with pytest.raises(ValueError):
        validate_vector(vector)


@pytest.mark.asyncio
async def test_failed_or_changed_embedding_never_partially_persists(tmp_path):
    provider = Embeddings()
    knowledge = service(tmp_path, provider)
    async def bad(profile, texts):
        return [[1, 0], [1, 0, 0]][:len(texts)]
    provider.embed = bad
    with pytest.raises(ValueError):
        await knowledge.ingest('project', 'embed', 'bad', 'x' * 1500)
    assert knowledge.list_documents('project') == []
    provider = Embeddings()
    knowledge = service(tmp_path, provider)
    await knowledge.ingest('project', 'embed', 'good', 'cats')
    provider.version = 'v2'
    assert await knowledge.search('project', 'embed', 'cats') == []


@pytest.mark.asyncio
async def test_bounds_and_search_dimension_validation(tmp_path):
    provider = Embeddings()
    knowledge = service(tmp_path, provider)
    with pytest.raises(ValueError):
        await knowledge.ingest('../scope', 'embed', 'source', 'text')
    with pytest.raises(ValueError):
        await knowledge.ingest('scope', 'embed', 'source', 'x' * 262145)
    await knowledge.ingest('scope', 'embed', 'source', 'cat')
    async def changed(profile, texts):
        return [[1, 0, 0]]
    provider.embed = changed
    with pytest.raises(ValueError):
        await knowledge.search('scope', 'embed', 'cat')


def test_knowledge_api_requires_owner(tmp_path):
    knowledge_api.initialize(Database(tmp_path / 'api.db'), Embeddings())
    app = FastAPI()
    app.include_router(knowledge_api.router)
    with TestClient(app) as client:
        assert client.get('/knowledge/project/documents').status_code in (401, 403)
    from backend.security.http_auth import require_owner
    app.dependency_overrides[require_owner] = lambda: 'owner'
    with TestClient(app) as client:
        response = client.post('/knowledge/project/documents', json={'profile':'embed', 'source':'cats.md', 'text':'Cats are nice'})
        assert response.status_code == 200
        result = client.post('/knowledge/project/search', json={'profile':'embed', 'query':'cat'})
        assert result.status_code == 200 and result.json()[0]['source'] == 'cats.md'


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv('KINGDOM_LIVE_EMBEDDING_TEST') != '1', reason='Opt-in installed local all-minilm integration')
async def test_real_local_embedding_ranking_and_scoped_delete(tmp_path):
    from backend.models.profiles import ModelProfiles
    from backend.memory.embedding_service import ProfileEmbeddingProvider
    db = Database(tmp_path / 'live.db')
    profiles = ModelProfiles(db, tmp_path / 'vault')
    profiles.save('embedding-test', {'endpoint':'http://127.0.0.1:11434', 'model':'all-minilm',
        'provider':'ollama', 'variant':'standard', 'computer_id':'this-pc', 'max_parallel':1})
    knowledge = EmbeddingKnowledge(db, ProfileEmbeddingProvider(profiles))
    cats = await knowledge.ingest('garden', 'embedding-test', 'cats.md', 'Cats are domestic animals that purr and chase mice.')
    await knowledge.ingest('garden', 'embedding-test', 'ocean.md', 'Ocean waves move across salty seawater.')
    await knowledge.ingest('other', 'embedding-test', 'private.md', 'Cats are private in this other scope.')
    hits = await knowledge.search('garden', 'embedding-test', 'What animals purr?', 2)
    assert cats['dimension'] == 384
    assert hits[0]['source'] == 'cats.md'
    assert len(hits) == 2 and all(hit['source'] != 'private.md' for hit in hits)
    knowledge.delete('garden', cats['document_id'])
    assert len(knowledge.list_documents('garden')) == 1
