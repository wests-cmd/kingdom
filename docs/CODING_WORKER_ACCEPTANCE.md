# Coding worker acceptance

Kingdom supplies the governed tool loop. A configured model must still demonstrate
that it can use those tools and solve the intended class of task. Model metadata,
a healthy connection, an installed integration or a completed response alone is
not a coding acceptance result.

## Setup and recovery

In **Talk & work**, use **Check coding setup without inference**. This checks
reachable installed models with declared tool support, minimum context fit,
runtime state and an Apprentice with workspace read/write grants. It does not
benchmark model quality or grant permissions. Configure the intended model's tool
support only after checking its provider or testing it, and retain normal policy.

Create a saved job in a dedicated project folder. Automatic placement selects an
eligible installed model; tool execution stays on the Kingdom host. Limit model
turns and runtime. Inspect the saved conversation, task identities and tool
results. Closing the browser does not turn a foreground request into a persistent
worker; use the documented background request controls where supported.

For code changes, select **Require verified source read and edit**. API callers
can supply `required_tools` from `workspace_read`, `workspace_list`,
`workspace_write` and the separately enabled `process_run`. These requirements
grant nothing: they prevent a response from completing without actual verified
tool results. Owner review clears that stage's evidence requirement, so a previous
write cannot satisfy a subsequent requested correction. This gate verifies the
operation, not the correctness of its contents; independent tests still apply.

A nonexistent path from a read/list operation becomes a failed observation for
the model to correct. It is never counted as verified success. Permission errors,
failed writes, failed processes and ambiguous outcomes still stop for review.

An owner can submit **Reviewed correction or independent test failure** to a
completed or review-needed job. The exact checkpoint must match. This preserves
the conversation and original turn budget, and cannot replay pending writes,
processes or approval decisions. Exhausted jobs require a separately reviewed
assignment. Do not use review feedback to bypass a denied operation.

## Acceptance protocol

1. Snapshot actual source and fixed independent tests in an isolated project.
   Record test hashes and demonstrate the bug with a failing baseline.
2. Ask the model to read source and tests, then edit only the permitted source.
   Do not give it the corrected implementation or let it alter acceptance tests.
3. Retain actual governed task results. A textual patch or a model's claim is
   insufficient; verify the resulting file and exact write scope.
4. Run the original tests independently, with no network or credentials and a
   read-only job mount. Preserve command, exit status, output and source/test
   hashes. Review the diff for regressions beyond test coverage.
5. If tests fail, return the real failure through reviewed feedback, within the
   same budget. Never promote an untested or failed edit.
6. Apply an accepted diff to the owning project, run its relevant regression
   checks and retain the provenance. Publishing is a separate authorized step.

Start with small repairs, then evaluate multi-file changes, test-driven repair,
dependency/API changes, interrupted execution, stale review and unavailable
workers. Track first-attempt success, success after review, failure and latency
separately. A single reviewed repair proves that scoped path, not reliable general
autonomous coding or equivalence to another harness. External harness adapters
remain optional, and their account access and model quality are not inherited.
