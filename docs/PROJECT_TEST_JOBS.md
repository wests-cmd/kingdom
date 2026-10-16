# Governed local project test jobs

Submit to the existing `POST /tasks` endpoint with the existing `process.run@1.0.0`
tool, `process.execute` capability, exact reviewed argv/timeout, and `max_attempts: 1`.
Add metadata `project_test` with `project` (`threadmap`, `centipede`, or `kingdom`),
40-character `source_revision`, `runner` (`unittest` or `pytest`), and
`minimum_tests` (positive integer). Existing owner authentication, worker grants
and exact high-risk approval remain required. This descriptor grants no authority.

`GET /tasks/{id}/test-report` derives a repeatable report from the durable task and
rechecks the existing local execution receipt. Process completion is distinct
from a nonempty successful test summary; missing, changed or truncated evidence
does not pass. Revision is owner supplied, not source-tree attestation. A command
can print a false summary: reports establish what the approved command reported,
not application correctness. Tests with side effects are not sandboxed.

Poll the existing task endpoint, and cancel with existing `POST /tasks/{id}/cancel`.
Existing cancellation semantics apply; running commands are not guaranteed to be
terminated. A restart reconciles running process jobs to `RECOVERY_REQUIRED` and
does not blindly rerun them. Inspect effects and submit a new task with a fresh
exact approval to rerun. Re-reading a report never executes or retries a command.
Submission idempotency, automatic repair, source-attested suites and terminating
running host processes are future work, not implemented by this reporting layer.
