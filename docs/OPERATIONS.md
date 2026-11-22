# Kingdom operations

## Start and inspect

For source startup use the commands in [development](DEVELOPMENT.md). The source
backend binds loopback 8000 in those instructions. [`scripts/start.sh`](../scripts/start.sh)
instead binds all interfaces; do not treat it as equivalent network exposure.
Native desktop installations manage their bundled backend separately.

Check `/health/live` for liveness and `/health/ready` for readiness. Neither
proves a worker completed an assignment. The Runtime start/stop controls and
autonomy level are distinct; inspect Tasks, programmes, dependencies and retained
receipts rather than infer work from a connected badge.

## User visibility and mesh revocation after the next reviewed release

The merged user-facing Home, task timeline, verified-change receipts, in-app notifications and optional host/model-health view are described in [user visibility](USER_VISIBILITY.md). They appear in a native install only when that **installed version** contains the change; v1.2.7 does not. Do not infer a computer was updated from a main-branch commit or a control-panel badge.

New task events are indexed by task identity for the owner-only timeline; preexisting events without the index may not appear. Notification records are filtered by type and omit payload contents; viewed state is local to the open page, not a persistent cross-device acknowledgement. Health data is sourced from host and signed inventory reports, not independently measured Kingdom-process resource consumption.

Mesh members can be revoked by the owner. [PR #183](https://github.com/wests-cmd/kingdom/pull/183) and the v1.2.8 candidate also protect the **signed-RPC heartbeat** and degraded-health paths, making these SQLite writes conditional on the **current persisted approval state**: a late heartbeat must not restore a revoked or quarantined member. Three-computer CI tested join, restart and revocation; [run 44979802578](https://github.com/wests-cmd/kingdom/actions/runs/44979802578) passed 2,004 backend tests and 5 skipped, while [native run 44979802576](https://github.com/wests-cmd/kingdom/actions/runs/44979802576) passed on Windows, Linux and Intel macOS.

When investigating unexpected mesh convergence or security state, inspect the exact node statuses, roster generation, transport and identity-bound RPC evidence. The test emits a **redacted** per-node state/roster summary on failure; do not expose certificates, owner tokens or full event payloads. Never work around failure by clearing device trust or silently reapproving nodes. The physical commissioning checklist remains [not accepted](https://github.com/wests-cmd/kingdom/issues/172).

## Configuration and state

| Setting/path | Purpose |
| --- | --- |
| `data/kingdom.db` in source working directory | Task, policy, mission and evidence state |
| `data/owner-token` or `KINGDOM_OWNER_TOKEN` | Owner API authentication; never share in chat, code or tasks |
| `ALLOWED_ORIGINS` | Explicit browser origins, separate from reachability and credentials |
| Frontend `VITE_API_URL` | Optional development/backend selection; public configuration only |
| [`configs/install_profiles.json`](../configs/install_profiles.json) | Available install-profile definitions |
| [`frontend/ui-compatibility.json`](../frontend/ui-compatibility.json) | Version compatibility metadata, not proof of a successful rollout |

The backend reads process environment; `.env.example` is only a template unless
the selected launcher explicitly loads it. Native per-user state, removable
vaults and container bind mounts can live elsewhere; follow
[vault/device layout](VAULT_AND_DEVICE_LAYOUT.md) and inspect the actual launcher.
Do not change an identity or copy credentials to make a second installation
appear connected. Keep runtime state outside source and build output.

## Devices and optional services

Use [device pairing](device-connections.md) and
[container/worker enrollment](docker-cluster.md). A phone's `localhost` is not
the PC. HTTPS reachability and a configured CORS origin do not grant execution;
pairing, capabilities, autonomy and task-specific approval still apply.
Discord callbacks need a reachable public HTTPS endpoint and their separate
verification; a private tailnet address alone cannot receive those callbacks.

## Backup, recovery and updates

Back up the actual database, required keys/configuration and external vault
using an application-consistent procedure before upgrades. A copied SQLite file
while writes/WAL are active is not a tested restore. Retain the previous artifact
and verify a restore in an isolated environment before claiming disaster recovery.

Windows v1.2.1+ uses Settings → Desktop updates; macOS/Linux use their matching
package. Validate published hashes/manifest, check the exact installed version,
and verify identities, policy, grants and data after restart. Roll back through
the documented release/deployment procedure when acceptance fails. Publishing
or selecting a desired version does not install it across every Knight.

Unknown remote side effects require reconciliation before retry. Do not delete
state, renew expired permissions, widen grants or bypass OS controls to turn a
held task green. See [runtime controls](runtime-controls.md),
[automation handover](automation-handover.md), [release gates](CLUSTER_SHIPPING_CHECKLIST.md)
and [project status](PROJECT_STATUS.md).
