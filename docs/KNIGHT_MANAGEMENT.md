# Manage paired Knights through Kingdom

Pairing joins computers into one logical Kingdom. It does not give another
computer permission to restart services or install code. Each computer retains
its unique key and grants. The owner chooses these additional capabilities:

* `knight.manage.execute`: inspect observed local services and request actions
  on explicitly registered **local user services**.
* `knight.update.execute`: transfer an immutable source release and request an
  update through an already installed local adapter.

The owner control plane is `POST /knight-management/{node_id}`. Requests and
receipts use the existing pinned identities, signed RPC and durable replay
ledger. Example request bodies:

```json
{"operation":"inspect","arguments":{}}
```

```json
{"operation":"service_action","arguments":{"service_node":"worker","unit":"worker.service","action":"restart"}}
```

If direct peer networking is unavailable, the same owner can request
`POST /knight-management/{node_id}/proof` with that body, transport its returned
`message` through an existing authorized connection to the peer's `/nodes/rpc`,
then submit the entire signed reply to
`POST /knight-management/{node_id}/receipt`. This changes no firewall or SSH
permissions. Kingdom retains the pending peer, operation and request ID for five
minutes; only a matching signed, single-use receipt is accepted. A relay cannot
invent success or substitute a different operation.

Service actions are exact governed process tasks with the requesting peer saved
as provenance. They never relay to a third computer through SSH. Existing
capability checks and the owner's selected approval policy remain in force.

## Optional source updater

This adapter currently supports Linux **systemd user services** with exactly one
explicit `Environment=PYTHONPATH=...` entry. It does not update Docker images,
system services, native installers, operating systems, dependencies or firmware.
Those deployments require separate installed adapters. No adapter is installed
by pairing or by receiving a message.

The operator installs a JSON profile on the receiving computer and sets
`KINGDOM_KNIGHT_UPDATE_PROFILE` in its service environment. The profile contains
absolute `unit_file`, `releases_root`, `state_root`, and `python` paths, plus a
loopback `base_url` such as `http://127.0.0.1:8000`. `unit_file` must be a service
inside the current user's `~/.config/systemd/user` directory. Paths must not
contain whitespace or systemd expansion syntax. Keep this configuration outside
agent workspaces. The service must already support the source verification route.

1. Produce and independently test a full source tar archive. Exclude private
   state, `.git`, `.env` and bytecode. Encode it as base64.
2. Send `stage_update` with `archive_b64` and its exact `sha256`. The receiver
   checks bounded archive/content sizes, paths, file types, duplicate entries,
   syntax of backend Python sources and all extracted hashes. Existing releases
   cannot be overwritten. Staging is **not** deployment.
3. Send `activate_update` with `release` equal to that digest. This submits a
   governed process task; at levels 0–4 normal human approval rules still apply.
   No grants or execution policy are expanded by the adapter.
4. A separate transient user service waits for queued/running tasks to drain and
   refuses outstanding agent sessions or requests. It keeps an exact unit backup,
   switches only its source location, and restarts the configured service.
5. Verification checks the same Kingdom identity, readiness, and the actual
   running backend source root/hash. Failure restores the old unit and restarts
   it; the receipt distinguishes successful rollback from failed recovery.
6. Poll `update_status` with that `release`. Only a `verified` receipt with
   `runtime_source_verified` proves promotion. A process exit, staging receipt or
   scheduling task completion does not.

Receipts are stored in SQLite and also as portable JSON evidence in local data.
An exclusive update lock prevents concurrent promotions. If the update process
is forcibly killed, the retained lock requires operator review; it is never
silently removed to retry an uncertain deployment. Existing source directories
and unit backups are retained for recovery.

Source hash/health checks prove that a particular tested release is running;
they do not prove general autonomous coding competence. Review and test a
generated change before promoting its release.
