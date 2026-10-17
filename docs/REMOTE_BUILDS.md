# Reviewed remote builds

Kingdom supports `build.run@1.0.0` on approved POSIX workers. The controller
submits a bounded source bundle and exact argument list, then independently
checks returned artifact bytes against digests reviewed before execution.
This first adapter is for small reproducible builds with known expected
artifacts. It is not a general autonomous coding or large-build service.

## Authority and execution

- Pair a Linux worker and explicitly grant `process.execute`. A `compute` grant
  alone cannot run a build. Workers must run the updated daemon source.
- Each exact build task requires the existing high-risk process approval.
  Mission approval does not replace individual command approval.
- Submit an owner-authenticated task with `execution_target: remote`, an exact
  `assigned_knight`, `tool: build.run@1.0.0`, and the specification below as
  `tool_parameters`. The controller forces the process capability and one
  attempt even if a caller supplies weaker metadata.
- Missions use `kind: build`, a required `computer_id`, and a `build` object.
  Coordinated missions require level 5 and fresh healthy worker capacity.
  Generated `input_from` bindings cannot change a reviewed build command.
- The guided editor displays the reviewed specification and offers workers
  with actual process grants. The advanced plan editor accepts build steps.

The specification is:

```json
{
  "source_revision": "40-character revision or 64-character content revision",
  "source_sha256": "64-character canonical source bundle SHA256",
  "files": {"build.py": "reviewed UTF-8 source"},
  "argv": ["@python", "build.py"],
  "expected_artifacts": {"package.zip": "64-character reviewed SHA256"},
  "timeout_seconds": 15
}
```

Use `backend.runtime.remote_build.source_digest(files)` to calculate the source
digest. A revision label does not prove Git provenance: the reviewed bundle's
digest binds the actual bytes. `@python` selects the worker interpreter without
assuming a controller-specific executable path. Commands execute with
`shell=False`; no packages are automatically downloaded or installed.

## Evidence and limits

The worker executes in a fresh temporary directory with a reduced environment.
Time is limited to 20 seconds, source and returned artifacts to 500 KB each,
source files to 100, artifacts to 20, and logs to a bounded capture. Nonzero
exit, missing files, symlinked artifacts, changed artifact digests and excess
budgets fail. POSIX process groups are stopped after execution or timeout.

Returned artifacts are base64 bytes in the persisted task result. The Tasks
workspace offers a download button for each verified build artifact. The
owner-authenticated `GET /tasks/{task_id}/build-artifacts/{name}` endpoint
rechecks the actual bytes and task/source/lease binding each time, rejects
unverified or changed evidence, and returns a noncached attachment. Downloading
does not execute or install the file.

The controller
checks the exact task identity, active lease and fencing token, command, source
digest, artifact names and independently computed byte hashes. Signed RPC
authenticates the worker. Expired/revoked leases cannot submit accepted results.
Interrupted builds remain `RECOVERY_REQUIRED`; they are never blindly retried.

`VERIFIED` here means returned bytes match the reviewed artifact digests.
Execution is attested by the approved worker, not cryptographically proven by
remote hardware. Separate application tests are still required. A temporary
working directory is not an OS sandbox: approved commands execute as the worker
account and can access that account's resources. Windows workers, long builds,
unknown artifact hashes, container isolation, live process cancellation and
general coding harness offload require additional adapters and tests.

Validation includes real process and timeout tests on Linux and an opt-in
physical remote-computer test in `tests/e2e/test_process_distributed_execution.py`.
Set `KINGDOM_E2E_REMOTE_CONFIG` to a private JSON file with `target`,
`identity_file`, `python` and `source` to run that test. It uses an isolated
controller, real signed RPC, explicit node approval and exact process approval;
it does not modify the live controller service.
