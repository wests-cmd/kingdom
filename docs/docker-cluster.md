# Docker commander and workers

Docker Compose starts a commander and two independent worker daemons. Starting containers does **not** enroll or approve workers. Each worker has its own identity and data volume. Neither worker runs an HTTP server, so their inherited commander HTTP healthcheck is disabled. A running container alone does not mean it is connected or authorized: inspect approval state and heartbeat in **Nodes & Cluster**.

## Start

From the repository root, run `docker compose up -d --build`. Open the commander dashboard at `http://localhost:8000`. If port 8000 is occupied by your desktop app, stop that app first or use a Compose override with a different host port.

Sign in using the commander's owner access code. For a new installation it is stored inside the commander at `/app/data/owner-token`; retrieve it privately with `docker compose exec kingdom-commander cat /app/data/owner-token`. Do not post or screenshot that code. Complete the profile setup if prompted.

## Enroll each worker

1. In the commander dashboard, open **Nodes & Cluster → Invite a compute worker** and generate a new single-use worker invitation. Browser phone pairing uses a different flow.
2. In a private terminal run:

   ```sh
   docker compose exec kingdom-knight-a python scripts/pair_docker_worker.py --capabilities compute gpu
   ```

   Enter the invitation at the hidden prompt. The helper reuses worker A's persistent identity and submits its signed request. It does not grant permissions or start a second daemon.
3. Review the name and fingerprint in **Pending Approvals**. Explicitly approve only the capabilities you intend to grant. Advertising `gpu` does not prove GPU hardware exists; Compose does not provision GPU access.
4. Generate a **separate** invitation for worker B and run:

   ```sh
   docker compose exec kingdom-knight-b python scripts/pair_docker_worker.py --capabilities memory storage
   ```

   Review and approve its scope separately. The existing daemon polls approval and reconnects without container recreation. Capabilities are grants, not proof that arbitrary tools or workloads are supported.

Invitations are single-use and expire at the time shown in the dashboard (the current worker invitation UI requests ten minutes). If enrollment fails, create a fresh invitation. Do not put pairing codes in Compose files, environment variables, shell command arguments, logs or source control.

## Verify and restart

Use `docker compose ps` and `docker compose logs --tail=30 kingdom-knight-a` for process status. The commander healthcheck should be healthy; workers should be running without an HTTP healthcheck. Confirm each worker's approval state, granted capabilities and fresh heartbeat in the dashboard. Test only an implemented controlled tool with matching task grants; a running worker does not grant task authority.

`docker compose restart` retains named volumes and identities. Re-enrollment is unnecessary for an already approved identity. Revocation blocks reconnect and task execution. `docker compose down` retains named volumes; **do not use `down -v`** unless you intentionally want to erase the cluster's persisted state and identities.
