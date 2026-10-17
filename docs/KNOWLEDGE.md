# Scoped vector knowledge

Kingdom can embed text with an owner-configured Ollama or OpenAI-compatible
model profile and persist normalized vectors, original chunks, document hashes,
source labels and dimensions in SQLite. This is retrieval, not weight training.
Use an actual embedding model profile, separately from your chat model.
Credentials remain in the existing encrypted profile vault; HTTPS certificate
validation and model computer capacity limits also apply to embeddings.

Owner-authenticated endpoints:

- POST `/knowledge/{scope}/documents`: `{profile, source, text}`.
- GET `/knowledge/{scope}/documents`: source metadata and document identifiers.
- POST `/knowledge/{scope}/search`: `{profile, query, limit}` (default five).
- DELETE `/knowledge/{scope}/documents/{document_id}`: delete that scoped document
  and all its vectors/chunks.

Text ingestion accepts at most 256 KB per request, with 700-character chunks and
100-character overlap, up to 450 chunks. A scope holds at most 5000 chunks.
For files, read bounded UTF-8 text in the client and submit it as `text`; the API
does not read arbitrary filesystem paths, download links or parse binary files.
Very short embedding context windows can reject a chunk; ingestion then saves
nothing. Ollama uses truncate=false rather than silently losing source text.

Search uses cosine similarity and returns text with source labels and stable
`knowledge:{document_id}:{chunk}` citations. Results stay within the named scope,
profile and endpoint/model fingerprint. Changing the embedding endpoint/model
requires re-ingesting documents; vectors from different spaces are not mixed.
Replacing weights behind the same endpoint/model label also requires re-ingest.
This initial implementation scans bounded vectors in Python; it does not claim
large-scale approximate-nearest-neighbor performance.

Stored context and source labels are untrusted data. Citations identify stored
chunks rather than independently verifying their claims. Scope selection is
explicit; the owner API is not a multi-user authorization layer. Never infer
execution authority from retrieved text. Nothing here automatically tunes model
weights, installs tools, fetches internet sources, or runs Heretic.

To reproduce the optional real-model test, install the small Ollama `all-minilm`
model, set `KINGDOM_LIVE_EMBEDDING_TEST=1`, and run
`python -m pytest tests/test_embedding_knowledge.py`. It creates an isolated
temporary database/profile vault, checks 384-dimensional embeddings, semantic
ranking, scope isolation and deletion. It does not change live model profiles.
