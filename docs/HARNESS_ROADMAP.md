# Kingdom harness: implementation and evidence map

Kingdom is an extensible harness for models and agents. Model weights, an agent harness, tool permissions, retrieval and training are distinct layers. A larger context or a model modification does not grant tools or establish better reasoning.

## Available foundation

- **Model computers:** Ollama and OpenAI-compatible servers, explicit selection or opt-in pools, TLS, bounded per-computer capacity. Each computer runs a complete model. This does not shard one model across CPU/RAM.
- **Native agent workbench:** saved bounded model/tool conversations; workspace read/list/write and optional process tools dispatch through existing governed tasks. Continue a turn, review pending operations, and resume from verified tool evidence. File and process execution stays on the Kingdom host. Models must actually support tool calls.
- **External harness adapters:** owner-configured installed CLI argument templates, durable connection revisions and exact task snapshots. Hermes, Claude-style CLIs or custom agents can be connected without hardcoded personal paths. No shell string interpolation. External agents retain their own credential stores and tool controls; a working directory is not a sandbox.
- **Portable skills:** SKILL.md preview/confirmation/export, provenance and digests. Documents are untrusted instructions, not executable installers or permission grants. The original preferences-only skill map remains compatible. know-it-all AI supports reviewed imports/exports.
- **Service computers:** explicit SSH service inventory and allowlisted systemd actions, queued through exact process approvals. Existing services remain in their original supervised deployment; registration does not claim migration.

## Next phases and acceptance gates

1. **Agent reliability:** benchmark actual tool calls, edits, tests and recovery on several model sizes. Add budget-aware automatic continuation and per-project workspace selection. Acceptance: a real multi-file coding task with reviewed changes, passing tests, restart recovery and no duplicate actions.
2. **Knowledge:** approved ingestion from chosen Discord channels and files; source identity, access scope, deletion and citations. Existing lexical memory retrieval must not be called vector RAG. Add a real embedding-provider interface and persisted similarity search. Acceptance: measured retrieval quality and isolation across users/projects.
3. **Tool discovery and building:** discover metadata, resolve pinned packages, show licenses/source hashes, build in isolation and run functional tests. Only activate after owner-approved capability grants. Discord text cannot silently install arbitrary code. Acceptance: install/revoke a real reviewed tool and reject a malicious package/reference.
4. **Model lifecycle:** isolated dataset/export, optional fine-tuning jobs, evaluation, versioned model artifacts and rollback. Add optional Heretic jobs only for supported weight formats and available hardware. Heretic is model modification, not retrieval or an intelligence upgrade. Upstream: https://github.com/p-e-w/heretic . It requires Python/PyTorch; no local training or Heretic conversion has been demonstrated by this release.
5. **Distributed execution:** signed remote tool jobs with scoped credentials, resource reservations, cancellation and independent results. Current model offload is real; current host tools are not automatically remote. Acceptance: a remotely executed build with verified artifacts and disconnect recovery.

## Repository boundaries

Kingdom owns runtime, adapters and portable contracts. know-it-all AI owns Discord delivery/review. ThreadMap defaults to the deployed Discord application in owner instructions; repository edits require an explicit repo target. Keep deployment secrets, private addresses, live knowledge and personal profiles outside public repositories. Preserve existing branches/PRs until their changes are reviewed; do not mass-delete history as cleanup.

The product should offer optional integrations rather than assume every installation uses Hermes or a particular model. A successful process exit is evidence of a command completing, not proof that generated code is correct or that a model learned.
