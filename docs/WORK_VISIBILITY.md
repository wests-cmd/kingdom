# Work visibility and the two-view acceptance test

A UI-driven test on 2026-10-18 started the installed Kingdom team backlog. The
local model listed an empty project and wrote cu01-diagnostic-receipt.md without
reading the actual failing source/session. Its timeout diagnosis was unsupported.
The user-side review rejected it and stopped the job; retain that file as an
unaccepted model output, not an actual failure receipt.

The owner-authenticated activity panel shows current phase, model wait, requested
connection, actual responding model, tool host, workspace, pending task IDs,
approval state, safe rejection reasons and next actions. Tool receipts, source
reads and file writes are separate from independent test verification. Empty
listings without a source read produce an explicit warning. A response labelled
completed never becomes proof of a tested repair. Older missing events cannot be
reconstructed. Unavailable refreshes are labelled as stale snapshots.

| Check | Human view | Technical view |
| --- | --- | --- |
| Task | Is this useful and the requested result? | Does the real diff meet acceptance? |
| Progress | Is it waiting, stopped or blocked? What next? | Are real tasks and matching receipts present? |
| Claims | Is there visible support for the answer? | Were source/error inspected and independent tests run? |
| Interface | Can I use it comfortably at half screen? | Do layout bounds and responsive checks pass? |

People can inspect technical evidence too; the summary removes the need to read
raw logs for basic facts. This update grants no capabilities and does not resume
jobs. Independent tests remain unverified until a separate trusted verification
contract exists. This panel is not a general language-model truth detector.

Autonomous ChatGPT operation and reliable general coding remain unproven. An
expired observation now has a distinct safe error code; delayed-action screen
revalidation remains a separate task. The unsupported diagnosis is not accepted.
