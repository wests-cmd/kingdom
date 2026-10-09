# Mission workspace

Kingdom has five active autonomy levels plus Pause:

| Level | Behavior |
|---|---|
| Pause | No new task executes. Already running operations are not killed. |
| 1 | Built-in text and syntax analysis; other work needs approval. |
| 2 | Exact, single-use approval for every task. |
| 3 | Tasks execute inside existing grants. High-risk operations require approval. |
| 4 | Approved missions advance automatically with 20 steps and two safe retries/explicit source repairs. |
| 5 | Up to 50 steps and three retries/repairs; supported analysis can use healthy approved remote computers. |

Level 5 queues up to three independent ready steps. Local execution remains sequential; paired computers may execute their leased analysis independently. Granting a level never grants tool capabilities or bypasses high-risk approval.

Use Routing to save and test a model connection. Use Governance to grant specific computer tools to an installed Apprentice. Use Tasks to enter the objective, attach references, generate and edit a plan, and approve its exact revision. The runtime must be started to process tasks. Commands and Windows desktop input appear in the approval queue with their exact parameters.

Attachments allow 20 files per task, 20 MB each, with a 512 MB compressed original-file storage budget. ZIP files are inspected without extraction/execution; traversal, symlinks and excessive expansion are rejected. PDF parsing has bounded streams, page trees and extraction; OCR is absent. Images need a configured vision model for visual interpretation. Context selection is extractive and can omit details; originals remain available for later retrieval. Task history is retained and is not automatically purged.

Mission completion requires verified task results and zero exit codes for command tests. `repair_source` explicitly names a directly dependent write-file step that may be corrected after a failed test. Only that file is writable by the repair; the original command stays fixed, external edits block overwrites, and exhausted budgets stop for review. Model-generated text and desktop-input receipts do not prove external application success. Test quality still determines what application behavior has been demonstrated.

Partial updates currently mean a compatible UI component, not a delta patch to backend binaries or hot-swapping native code. The release pipeline supplies the UI ZIP, hashes and compatibility manifest. The running backend retains its process and task state; refresh switches the page, and rollback changes the selected UI. Native updates require restart. Old component directories are retained for open pages and rollback.

Knights are real paired computers. Local agents are Knight Apprentices; legacy internal API names remain for compatibility. Captain group membership is owner-created, pairing grants remain mandatory, and signed assignment requests enforce group boundaries. Automatic offload currently supports bounded text/Python syntax analysis. Stale or unknown capacity does not qualify, and unavailable computers fall back locally before a lease is issued.
