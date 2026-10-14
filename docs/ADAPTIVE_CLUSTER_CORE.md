# Kingdom's adaptive cluster core

Kingdom is an AI harness that grows useful capabilities and coordinates computers to complete tasks. Chats are one interface to this runtime. A cluster can combine small local models, larger model servers, installed harnesses and scoped tool workers; each member need not run the same software or model.

## The operating loop

1. Record the owner's goal, acceptance conditions, budgets and allowed scope.
2. Plan bounded tasks and dependencies; assign model, harness and computer separately.
3. Select approved resources with fresh capacity and relevant verified outcomes.
4. Reserve resources and execute through governed adapters with cancellation and checkpoints.
5. Check outputs independently, including relevant tests, before accepting completion.
6. Retain reviewed evidence, reusable skills and failure lessons; use them for future placement and planning.

Useful adaptation must be inspectable and reversible. Routing learns from controller-verified results rather than worker assertions. Retrieval supplies relevant evidence without granting authority. Tool acquisition requires provenance, inspection and approved activation. Optional fine-tuning or model modification requires suitable hardware, evaluations and rollback; it is not an automatic reward for accumulating chat history.

## What exists and what must be proven

Existing foundations include paired computers, capability grants, fenced task leases, signed RPC, fresh CPU/memory reports, remote text/syntax analysis with controller-side verification, model-server offload, native tool conversations, external CLI adapters, reviewed portable skills and embedding retrieval. The automatic remote analysis path now ranks eligible computers using current load plus a bounded failure penalty from persisted outcomes for the same tool. Revoked, busy, unhealthy or stale nodes remain ineligible regardless of past success.

This is task distribution, not shared RAM or arbitrary model-weight sharding. General remote builds, cross-computer native agent tools and reliable multi-stage coding clusters are still unfinished. A historical success does not authorize another action. Current automatic remote dispatch remains restricted to its existing analysis tools and autonomy policy.

Remote disconnect recovery consults persisted lease fencing, including changes made by another controller. Interrupted text/Python analysis can be requeued; unknown operations and commands remain in `RECOVERY_REQUIRED` with their evidence retained instead of automatically repeating possible side effects. A healthy active lease is left alone. This is recovery of controller state, not proof that a disconnected worker process has stopped.

## Next delivery gates

- Resource reservations: two competing tasks must not overcommit one computer; report why a task waits or falls back.
- Generic remote execution adapters: execute an approved build on another computer, bind artifacts to the task/lease/source revision, and independently verify them.
- Dependency-aware missions: planner, implementation and review tasks can run on different nodes; failed prerequisites block dependants.
- Disconnect recovery: fence stale workers, preserve checkpoints and prevent duplicate side effects.
- Durable adaptation: evaluate routing against measured latency, verified success, costs and resource use; expose/reset the evidence. Avoid rewarding unverified results or permanently starving new workers.
- Skill and retrieval growth: evaluate whether reviewed knowledge actually improves task completion; synchronize revocations and isolation across adapters.
- Model lifecycle: benchmark several real models/harnesses; promote tuning candidates only after checks and retain rollback.
- Cluster user experience: show the goal, computer assignments, dependencies, budgets, evidence, pending approvals and recovery actions in one understandable workspace.

Acceptance for the core: an owner submits a goal once; multiple approved computers complete dependent work with real evidence, independent review, capacity control and safe recovery. Until that end-to-end scenario passes, describe the individual foundations and their limits rather than claim the whole cluster autonomously works.

Pinned mission steps now wait when their approved, fresh and healthy computer is busy or overloaded. The mission retains its reviewed computer assignment and resumes when capacity returns; the workspace displays the waiting reason. Revoked, stale or unhealthy computers still require review.
