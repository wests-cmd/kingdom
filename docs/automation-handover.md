# Verified automation handover

The Automations screen shows connected adapters, real retained progress, the
current owner, a handover plan, test evidence and failures. Discovery is explicit;
Kingdom does not search for credentials or take over unrelated services.

The first adapter supervises the existing Laptop 2 skill workshop. It reuses its
reviewed runner, durable progress database, publication reconciliation and process
lock. It adds supervision rather than generating a second publisher. Release
notices and the Discord gateway remain separate services.

## Authority and execution

An owner must approve the exact installed adapter revision. Adoption also requires
autonomy level 3. Levels 0–2 never automatically adopt an external worker. Once
adopted, any lower level pauses its scheduled work. Existing external workers
remain independent until adoption. Approval grants only this reviewed adapter;
it does not grant arbitrary process execution, generated-code execution, new
capabilities or permission changes.

Before adoption, checks verify source hashes, deployment regression evidence and
read-only inspection of the current progress. Failed checks keep original
ownership. On runtime failure, ownership rolls back and the original runner is
used on the next timer invocation. There is deliberately no immediate rerun after
an uncertain publication. The shared work database prevents lost progress.

Transient failures retry after 30 minutes, at most three adoption attempts per
exact approval. Every retry rechecks the candidate. A code mismatch, exhausted
retry limit or broken tests needs a reviewed fix and fresh approval; the bot does
not silently rewrite production code. Operational failures store exception
classes rather than exception messages which could contain credentials.

SQLite leases prevent concurrent execution across processes. A crash leaves a
durable lease; time alone never expires it because the worker may still be alive.
The local timer may recover it only while holding its exclusive supervisor lock,
or an operator may recover the exact lease after verifying the process stopped.

## Connection

`KINGDOM_AUTOMATION_STATE` chooses the SQLite supervision database (default
`data/automation/state.sqlite3`). `KINGDOM_WORKSHOP_ROOT` explicitly connects the
local workshop, whose `app/automation-manifest.json` lists tested source hashes.
The API and local timer share that state file. No Discord token is collected by
the supervisor. The existing sandboxed timer remains the execution boundary.

While a parallel preview runs beside the stable server, set
`KINGDOM_POLICY_AUTHORITY_TOKEN_FILE` to the stable server's local owner-token file.
Policy reads and writes then go only to the fixed loopback stable endpoint on
port 8012. Both interfaces control the same autonomy level; an unavailable
authority blocks supervised execution. Normal single-server installs omit it.

`GET /automations` and `POST /automations/{id}/approve` require the ordinary owner
session. Inventory contains no arbitrary executable command field. Adapter code
is reviewed and registered locally, never submitted through the API.
