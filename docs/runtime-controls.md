# Runtime controls

Governance → Autonomy policy saves an execution limit in the local SQLite database. It survives a restart and applies to queued and future tasks, including remote dispatch. A task already executing is not interrupted.

| Level | Enforced behavior |
|---|---|
| L0 Observer | Holds queued tasks. No new local execution or remote dispatch. |
| L1 Safe analysis | Built-in text and Python syntax analysis may run within existing grants. Other tasks require an individual approval. |
| L2 Approve every task | Each task needs an exact, actor- and operation-bound single-use human approval. |
| L3 Bounded execution | Existing capability and risk policy applies; high-risk operations always require approval. |

Autonomy never grants capabilities, authenticates another identity, approves high-risk actions, or certifies a draft skill. Upgrades retain the previous bounded behavior (L3) unless a policy is saved. Invalid persisted levels fall back to Observer. The unsupported L4/L5 description cards have been removed.

Denying an approval cancels its waiting task. Cancelling a waiting task cancels its pending approval. Start the local runtime to process approved queued work.

Runtime modes change actual polling cadence: Persistent 100 ms; Burst 20 ms; Adaptive 100 ms with queued work and 500 ms when idle. Mode selection lasts for the process session. Calendar scheduling, privacy mode, sandbox isolation, and higher autonomy levels are unavailable. Stop Runtime stops the local scheduler; Observer also prevents new remote dispatch. Existing remote leases and already running work are not cancelled by Observer.

Intelligence records and worker activity display backend data without sample topology. Routing reports actual provider configuration and session usage; latency and cost measurements are unavailable. Built-in text and syntax analysis need no AI provider. Teaching creates a draft, not an executable or certified skill.

Design references: [Carbon dashboards](https://carbondesignsystem.com/data-visualization/dashboards/), [Carbon empty states](https://www.carbondesignsystem.com/building-blocks/core/patterns/empty-states), and [Nielsen Norman Group system status](https://www.nngroup.com/articles/visibility-system-status/).
