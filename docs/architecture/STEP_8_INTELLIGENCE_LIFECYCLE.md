# Step 8 — Intelligence Lifecycle Architecture

## Overview

Kingdom's intelligence engine operates on a continuous feedback, evaluation, and evolution loop without compromising zero-trust governance or system integrity.

```text
INPUT
 ↓
INGESTION (Prompt Firewall & Multi-modal Parser)
 ↓
VALIDATION (Capability & Schema Check)
 ↓
PROVENANCE (Source Authority Weighting)
 ↓
KNOWLEDGE (Domain Knowledge Base & Vector Index)
 ↓
MEMORY (Decay & Utility Weighted Context)
 ↓
AI MAP (Operational Graph Relationships)
 ↓
RETRIEVAL (Vector / Keyword Hybrid Search)
 ↓
PLANNING (Swarm & Hybrid Routing)
 ↓
EXECUTION (Knight Tool Invocation)
 ↓
EXPERIENCE (Execution Trace Recording)
 ↓
OUTCOME (SkillOutcome & Feedback Capture)
 ↓
FEEDBACK (User Approval / Rejection / Correction)
 ↓
LEARNING CANDIDATE (ImprovementProposal Generation)
 ↓
TEST (Sandbox Benchmark Evaluation)
 ↓
SIMULATION (HypothesisEngine Multi-Metric Gating)
 ↓
APPROVAL (Governance Escalation Boundary Check)
 ↓
PROMOTION (Version Bump & Active State Update)
 ↓
DISTRIBUTION (Swarm Sync & Topology Broadcast)
 ↓
MONITORING (Performance Telemetry Tracking)
 ↓
ROLLBACK (Instant Version Restoration)
```

---

## Separation of Subsystem Layers

Kingdom enforces explicit boundaries between models, knowledge, skills, and memory:

1. **Model:** Underlying inference engine; cannot execute tools directly or bypass governance.
2. **Memory:** Contextual execution experience (`backend/memory/`) weighted by decay and utility.
3. **Knowledge:** Validated domain information (`backend/memory/knowledge_domains.py`) with source authority metadata.
4. **AI Map:** Operational understanding and relationship graph (`backend/skills/map.py`).
5. **Skill:** Reusable procedure (`backend/skills/models.py`) with explicit lifecycle state.
6. **Outcome:** Measured execution metric (`SkillOutcome`) capturing latency, cost, and user feedback.
7. **Policy:** Governed execution constraints enforced strictly in backend Python code.

---

## Authority Weighting Hierarchy

Source authority is weighted explicitly outside model inferences:

| Source Authority | Weight | Description |
|---|---|---|
| `explicit_user_instruction` | `1.00` | Direct human command or explicit correction |
| `human_supervisor` | `1.00` | Supervised human approval decision |
| `verified_system_state` | `0.95` | Validated kernel or hardware telemetry |
| `trusted_integration` | `0.90` | Authenticated internal adapter data |
| `approved_document` | `0.85` | Ingested and verified business document |
| `execution_engine` | `0.80` | Internal runtime execution result |
| `previous_experience` | `0.70` | Historical execution memory |
| `model_inference` | `0.50` | Unvalidated model output |
| `untrusted_external_content` | `0.10` | External web / API payload |

---

## Sandbox Hypothesis Gating & Promotion

All learning candidate proposals must pass multi-metric benchmark evaluations in `HypothesisEngine` (`backend/learning/hypothesis.py`):
- **Speedup:** `latency_delta_pct <= -5.0%`
- **Accuracy:** `accuracy_delta_pct >= 0.0%`
- **Security:** `security_violations == 0`

Proposals requesting permission escalation, trust level alteration, or financial policy changes require **Governance Level 4+ Commander** approval (`backend/learning/experiment.py`).
