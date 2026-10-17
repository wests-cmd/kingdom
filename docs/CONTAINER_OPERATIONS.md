# Container deployment and recovery

Build the repository Dockerfile for ordinary online deployment. For an offline host, prepare a pinned Python base image, an exact source release with built frontend assets, and a hash-verified wheelhouse on an online machine. Build with `--network=none --pull=false`; never infer package compatibility from the downloading machine's Python version.

## Preserve an existing installation

Before switching runtimes, stop accepting work and verify no running or leased jobs. Back up the complete existing data directory with restricted permissions. Preserve the Kingdom identity, signing keys, owner token, policy and paired peers. Do not copy another installation's identity to make a new node.

Test a candidate on a separate loopback port and separate data directory. Verify readiness, the frontend and rejection of unauthenticated private endpoints. Stop the old runtime before mounting its canonical data in the replacement. Disable the old startup unit only after the replacement passes checks. Keep its source and unit for rollback; never run both against the same data.

The installed Centipede deployment has been exercised with Python 3.11, a non-root UID, read-only container root, all capabilities dropped, no-new-privileges, a bounded temporary directory and explicit CPU, memory and process limits. The application binds loopback. Host networking preserves existing loopback model relays on Linux; this topology is not portable to every Docker host. With bridge networking, explicitly configure model reachability and publish the UI on `127.0.0.1`, rather than exposing the owner API to the LAN by default.

## Separate workshop

A spare container is capacity, not an autonomous worker. Keep it stopped until a bounded job is assigned. Use a separate writable volume owned by its non-root UID, no network unless required, and no host credential directories or Docker socket. A 512 MB workshop limit leaves more memory for the main harness on small computers. Define the allowed source, expected output, independent tests and timeout before starting a job. A sleeping container or zero process exit does not prove useful work.

## Verification and rollback

Record image ID, exact source revision, data location, startup mechanism and checks. Verify the running container and readiness after cutover, plus authenticated functionality through the normal owner interface. Restart policy does not prove a physical reboot succeeded; keep that check separate.

For rollback, stop the container, confirm it released the data and listening port, then start the preserved service. Restore a backup only if needed and only with both runtimes stopped. Never regenerate identities as a troubleshooting shortcut.

AirLLM is optional. Successful imports and a tiny CPU matrix multiplication establish dependency compatibility only. Model weights, peak memory, inference latency and answer correctness require separate measured evidence before enabling it as a thinking provider.
