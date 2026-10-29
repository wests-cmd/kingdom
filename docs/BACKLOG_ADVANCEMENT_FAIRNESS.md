# Bounded backlog advancement

The backlog advances at most one already reviewed mission per tick. When both
new ready work and running work are eligible, a persisted cursor alternates their
turns. Ready work retains the configured task-type and item priorities. Running
work rotates through the priority-ordered eligible list after the previous
running item, so a slow high-priority task cannot monopolize every observation.

The cursor is saved in the same SQLite transaction as the durable advancement
lease. Rebuilding the service preserves the next turn; it does not replay a task
or expire an uncertain lease. Any outstanding durable lease still holds all
advancement until existing reconciliation proves it safe.

New mission admission is additionally capped by the owner's current
`mission_budget.max_parallel`. Running backlog items count toward that cap even
when individually paused. If the cap is one, a second mission waits until the
first leaves running state. This is a conservative additional limit; each
mission's own execution budget and all execution-policy checks still apply.
Malformed or missing admission budgets fall back to one.

This scheduler does not create a plan, approve a mission, enable a paused item,
ignore dependencies, or weaken receipt verification. Disabled unbound planning
notes remain non-executable. A running daemon and an enabled backlog do not prove
that any eligible reviewed work exists.

Verification uses the real MissionService, SQLite TaskManager and governed
subprocess receipts. It covers queued work alongside unrelated ready work,
finished prerequisites followed by dependent work, actual failed test suites,
restart without duplicate tasks, a stream of higher-priority ready items, and
owner admission cap one. It does not prove deployment or live fleet progress.
