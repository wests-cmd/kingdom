# Local decision selectors

Two small linear pairwise ranking models were trained inside DT1's existing
network-isolated, 256 MiB model-lab container. No upstream Nimble code, weights,
CUDA dependencies or paid service was installed. The design uses contrastive
candidate comparisons inspired by Nimble, independently implemented here.

The model selector ranks a fresh set of installed, requirement-compatible model
profiles. Structured task labels are owner preferences; model names are not
evidence of capabilities. New profile identities require no retraining.
The Knight selector ranks an already eligible set of workers and bounds its
suggested count by ready independent tasks, owner concurrency and available nodes.
It consumes a plan's ready work; it does not write plans.

## Current release behavior

Both selectors run in **shadow mode**. Automatic model responses include the
shadow ranking. Eligible remote analysis assignments retain a shadow Knight
recommendation in persisted task metadata. Existing scheduling, capacity locks,
tool grants, battery checks, health and freshness checks remain authoritative.
Missing or invalid artifacts leave the existing scheduler available.
Authenticated owners can inspect `/model-lab/decision-selectors/status`.
Native starter builds include both artifacts and the training receipt.

Training uses synthetic resource-policy labels, not private owner conversations.
The receipt reports held-out pair accuracy and independent multi-fact policy
agreement. Those scores measure policy imitation, not semantic correctness,
observed speedup, hardware throughput or autonomous software engineering.
The source trainer and seed make both small artifacts reproducible.

## Remaining acceptance gates

1. Collect independent real-job outcomes for both selections, including elapsed
   time, success and actual memory measurements; compare against current routing.
2. Validate task-type coverage from structured plans. Unknown capabilities require
   abstention or clarification rather than a guessed model capability.
3. Connect multi-Knight count recommendations to the reviewed mission DAG and
   host-level reservations. Current integration observes single analysis offloads.
4. Implement temporary-container admission and verified cleanup through existing
   authorized tools. A recommendation does not create a container or more RAM.
5. Promote a version only after real outcome tests, with rollback to the existing
   scheduler. Automatic self-training and promotion are not enabled.
6. Upload the tested distribution to the owner's configured Discord destination.
   A portable skill map is preferences only; it cannot install executable code.

See [research and source identities](research/DECISION_MODELS_20261025.md).
