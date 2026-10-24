# Host container observation

Containerized Kingdom normally cannot observe host programs or sibling
containers. An optional **operator-owned observer** can export bounded status
for containers whose names start with `kingdom`. This is observation only.

Install `scripts/observe-host-containers.py` on the Linux Docker host under its
normal administrator account. It calls only Docker list and selected-field
inspection, then atomically writes `/run/kingdom-host-observation/containers.json`.
Run it with a supervised service and a private writable runtime directory. The
observer needs existing host Docker permissions; an Apprentice must never
receive those permissions, the Docker socket, or a general command adapter.

Mount only that report directory read-only into Kingdom and configure:

```text
KINGDOM_HOST_CONTAINER_REPORT=/run/kingdom-host-observation/containers.json
```

The reader requires a root-owned regular file without group/world write access,
rejects symlinks and files larger than 64 KiB, and requires a report at most
60 seconds old. Missing, stale, future, invalid or unavailable observations
become **unavailable**, never an empty current-success report. Only container
names, running state and restart policy survive validation. Credentials, mounts,
logs and arbitrary extra fields are excluded. The host observer is trusted to
report accurately; a signed peer inventory attests the Knight, not independent
container execution or application correctness.

The normalized report uses the existing `container` scope and additive optional
fields for compatibility with older inventory readers. Updated UI labels the
host report separately. Restart policy is shown as configuration, not proof of
successful startup. Other host programs, assignments, CPU/RAM metrics and
source/test receipts are not provided by this adapter.

The operator must configure the mount and observer explicitly. The application
does not discover the Docker socket, install a service, grant access, start or
stop containers, or enable a host observer from model output.
