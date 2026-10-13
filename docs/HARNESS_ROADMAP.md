# Kingdom harness: implementation and evidence map

Kingdom is an extensible harness for models and agents. Model weights, an agent harness, tool permissions, retrieval and training are distinct layers. A larger context or a model modification does not grant tools or establish better reasoning.

## Available foundation

- **Model computers:** Ollama and OpenAI-compatible servers, explicit selection or opt-in pools, TLS, bounded per-computer capacity. Each computer runs a complete model. This does not shard one model across CPU/RAM.
- **Native agent workbench:** saved bounded model/tool conversations; workspace read/list/write and optional process tools dispatch through existing governed tasks. Continue a turn, review pending operations, and resume from verified tool evidence. File and process execution stays on the Kingdom host. Models must actually support tool calls.
- **External harness adapters:** owner-configured installed CLI argument templates, durable connection revisions and exact task snapshots. Hermes, Claude-style CLIs or custom agents can be connected without hardcoded personal paths. No shell string interpolation. External agents retain their own credential stores and tool controls; a working directory is not a sandbox.
- **Portable skills:** SKILL.md preview/confirmation/export, provenance and digests. Documents are untrusted instructions, not executable installers or permission grants. The original preferences-only skill map remains compatible. know-it-all AI supports reviewed imports/exports.
- **Service computers:** explicit SSH service inventory and allowlisted systemd actions, queued through exact process approvals. Existing services remain in their original supervised deployment; registration does not claim migration.

## October 13 checkpoint

Implemented in source: per-project agent workspaces, bounded automatic continuation, opt-in owner memory, actual embedding-backed retrieval with citations and deletion, reviewed Discord JSON ingestion with provenance and duplicate suppression, governed tool build/test recipes, and optional model preparation/evaluation/artifact registries. Tool recipes do not provide operating-system isolation. Model promotion records a candidate; it does not switch inference profiles automatically.

Laptop 2 runs the source harness behind private Tailscale HTTPS. Its deployed revision predates the final Discord import/provenance and default-model-selection changes. Real local embeddings and an approved tool build/test passed there. Windows retains its previous running desktop version because Application Control rejected the new backend executable. No policy bypass was attempted.

The latest live native-agent smoke check stopped in needs_review before a tool call; the proposed multi-file coding check therefore did not run. Earlier successful tool calls do not establish coding reliability. No fine-tuning or Heretic conversion has run.

## Remaining acceptance gates

1. **Agent reliability:** diagnose the failed live tool-call check and benchmark edits, tests and recovery on several model sizes. Acceptance: a real multi-file coding task with reviewed changes, passing tests, restart recovery and no duplicate actions.
2. **Knowledge:** connect approved live Discord channel fetching; evaluate retrieval quality, permission isolation and embedding-model version changes. Current Discord ingestion uses explicitly supplied exports, not automatic channel synchronization.
3. **Tool discovery and building:** discover metadata, resolve pinned packages, show licenses/source hashes, build in isolation and run functional tests. Only activate after owner-approved capability grants. Discord text cannot silently install arbitrary code. Acceptance: install/revoke a real reviewed tool and reject a malicious package/reference.
4. **Model lifecycle:** isolated dataset/export, optional fine-tuning jobs, evaluation, versioned model artifacts and rollback. Add optional Heretic jobs only for supported weight formats and available hardware. Heretic is model modification, not retrieval or an intelligence upgrade. Upstream: https://github.com/p-e-w/heretic . It requires Python/PyTorch; no local training or Heretic conversion has been demonstrated by this release.
5. **Distributed execution:** signed remote tool jobs with scoped credentials, resource reservations, cancellation and independent results. Current model offload is real; current host tools are not automatically remote. Acceptance: a remotely executed build with verified artifacts and disconnect recovery.

## Repository boundaries

Kingdom owns runtime, adapters and portable contracts. know-it-all AI owns Discord delivery/review. ThreadMap defaults to the deployed Discord application in owner instructions; repository edits require an explicit repo target. Keep deployment secrets, private addresses, live knowledge and personal profiles outside public repositories. Preserve existing branches/PRs until their changes are reviewed; do not mass-delete history as cleanup.

The product should offer optional integrations rather than assume every installation uses Hermes or a particular model. A successful process exit is evidence of a command completing, not proof that generated code is correct or that a model learned.
