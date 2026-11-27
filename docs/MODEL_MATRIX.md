# Permanent model-size acceptance — v1.3.0 onward

Every candidate runs the normal full CI suite, including offline matrix contract tests. Those tests are NOT real inference. Before approving a model-certified v1.3.0 or later release, run the same six synthetic tasks through Kingdom's actual ModelService on three distinct, preinstalled local models and retain exact-source evidence.

| Tier | Actual parameter count | Example size (not preinstalled or verified) |
| --- | --- | --- |
| Small | 1–3 billion or fewer | 1.5B |
| Medium | >3–13 billion | 7B |
| Large | >13 billion | 32B |

Use a dedicated idle owner-controlled machine with adequate memory and cooling. The small tier is the first candidate for a roughly 4 GB host; do not try 7B/32B on such a host without measured headroom. No downloads, cloud service, paid API, model-generated process, or unreviewed tool calls. Each invocation uses an isolated temporary Kingdom database and the loopback Ollama server. Size must be observed via /api/show and /api/tags, not inferred from a tag. Quantization, host RAM, timing, output token count and model digest are retained. Host identity and model metadata are local observations, not cryptographic independent proof.

Install the existing pinned Kingdom dependencies in a clean checkout. Use these commands on separately capable lab hosts, replacing the example tags with **exact installed tags**. Keep the JSON reports outside the checkout and transfer them to one operator host using the same exact source revision.

    python scripts/model_matrix.py run --tier small --model qwen2.5:1.5b --confirm-idle-local-lab --output ../small.json
    python scripts/model_matrix.py run --tier medium --model qwen2.5:7b --confirm-idle-local-lab --output ../medium.json
    python scripts/model_matrix.py run --tier large --model qwen2.5:32b --confirm-idle-local-lab --output ../large.json
    python scripts/model_matrix.py verify ../small.json ../medium.json ../large.json

The exit code is nonzero when inference fails, a tier is unavailable, the model changes, or evidence is incomplete. The six checks cover literal instructions, arithmetic, conversation context, JSON, reading code without execution, and one untrusted-data instruction boundary. This is not a proof of general prompt-injection resistance, model intelligence, safe agent operation, native tool use or vision; those need additional capability-specific suites. The script refuses hosts with less available system RAM than the installed model file plus 512 MiB (minimum 1 GiB). This is a conservative preflight, not a proof of runtime RAM or VRAM sufficiency; the operator must choose a suitable dedicated host. No real tier is claimed until the owner lab has run it. Do not count simulated HTTP adapters or fabricated records.

The release reviewer must hold the model-certified release until all three live records pass for the exact candidate, and repeat the matrix after source or model changes. For final release, repeat against the exact release checkout if the merge changes the source commit. No publication workflow or signing policy is silently bypassed.

## Required publication gate (v1.3.0 and later)
The normal PR CI runs offline grading and evidence-validation contract tests. For a release, an authorized repository operator runs the three local tests on the exact reviewed revision, then dispatches **Review live model matrix evidence** on the exact main revision, supplying the three JSON reports. The GitHub-hosted workflow verifies them and stores only synthetic case metadata. The native publication job requires a successful dispatch for the exact main commit and independently revalidates the downloaded records; missing, stale, simulated or failed evidence blocks publication. After submitting evidence, rerun the failed publication job. Do not enroll public-repository self-hosted runners or expose Ollama to GitHub. The records are operator-supplied, not independently attested; deliberate fabrication is outside this validation's guarantees. Keep the original lab logs and review them before dispatch. A candidate must also pass normal native and security gates.

Lab reports must use a new path outside the checkout. The runner checks the installed tag before resolving metadata and rechecks the tracked source revision after inference. Duplicate JSON keys, zero-duration cases and completion token counts outside the configured 128-token budget are rejected. These are contract safeguards, not real model evidence.
