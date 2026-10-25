# Problem guide and observability

The service-owned problem guide scans up to 100 local saved programmes every
30 seconds. It records blocked planning and failed/review-held mission work as
durable incidents, links the original programme/item correlation identifier,
and routes a disabled repair note to the planner, connection researcher or coder
role. Routing is a recommendation, not proof that a worker acknowledged it.
It creates no incidents or repair notes while the runtime is stopped or policy
level is zero. Shutdown waits for the current scan instead of detaching a writer.

The existing work-list loop still owns planning, approval, execution, bounded
repairs, immutable checks and separate section integration. A repair note cannot
execute, reset a retry budget, grant tools, change policy, suppress security
monitoring or publish code. No extra model is kept loaded for classification.
An unknown diagnosis needs the configured planner or owner; no fabricated fix
is substituted. Local-only routing does not send logs or vaults to cloud models.

`GET /problems` requires the owner session. The Tasks page shows open incidents,
the suggested role, original reference and whether a repair note was saved.
Stable incident and work keys prevent duplicate notes after restart, including
a crash between registering a note and saving its ID. Reports resolve only when
the original work checkpoint reports accepted completion, not when a retry starts.
Resolution does not delete evidence or mark the separate repair note completed.

The queue retains at most 200 incidents; reaching capacity is explicitly visible.
Operators must review retained evidence rather than silently lose it through
automatic deletion. Metrics use four fixed category labels; correlation IDs stay
in incident/event records rather than create a time series per task. Raw prompts,
provider errors, credentials and endpoints are never copied into these reports.

## Reel mapping and remaining coverage

Reference: https://www.instagram.com/reel/De4iU2vMW7X/ . Its readable caption
describes seven levels of observability; video/audio were not independently
transcribed. This adaptation uses Kingdom's existing events and checkpoints:

* Logs: structured opened/routed/resolved events.
* Metrics: bounded open counts by fixed category.
* Traces/correlation: links to original saved programme/item and work note.
  This is not a complete distributed latency trace or OpenTelemetry rollout.
* Alerts: open problem reports with duplicate suppression and visible capacity.
  Pager delivery and sustained error-rate alerts remain separate work.
* Reliability target: a proposed 60-second routing target, explicitly unmeasured.
  It is not a measured SLO or customer SLA.
* Cardinality: fixed category labels and finite retention.

The present endpoint covers this Knight's local programme observations. Signed
cross-Knight problem aggregation, Centipede's native client panel, HTTP/database
span timings, measured service targets and independently verified general repair
execution remain unfinished. Existing independent security monitoring remains
separate and authoritative. Installing Prometheus/Grafana or claiming all services
are instrumented is not implied by this lightweight addition.

## Real planning failure corrected

The local model returned a valid `function_copy.v1` proposal within exactly one
Markdown JSON fence. Parsing now accepts that presentation wrapper, then runs the
unchanged schema, scope, source-hash and immutable-test checks. Extra prose,
additional JSON objects and other fence languages remain invalid. Original model
text remains in stage evidence. No retry budget is increased by this correction.
