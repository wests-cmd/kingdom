# Existing private links

`supervise-private-links.py --config <owner-private-config.json>` keeps explicit
SSH forwards alive with bounded retries. It uses existing SSH identities,
configuration files and host-key approvals. It does not discover computers,
approve fingerprints, create grants, install startup services or start models.

The private JSON has `lock_file`, `state_file` and a `links` array. Each link has
a public `name` and an `argv` array containing the exact approved SSH command.
Use an SSH executable, optional `-F` configuration and `-i` key file, `-N`, a
single host destination, and explicit `-L`/`-R` loopback forwards. Required `-o`
settings are `StrictHostKeyChecking=yes`, `BatchMode=yes`,
`ExitOnForwardFailure=yes`, and bounded positive `ServerAliveInterval`,
`ServerAliveCountMax` and `ConnectTimeout` values (maximum 60).

Multiple forwards in one configuration entry are supervised independently.
An occupied remote model port therefore cannot prevent the dashboard's local
forward from reconnecting. Separate entries with friendly names are preferable
when their status should be recognizable to an operator. Remote SSH sessions
can retain forwarding ports after an unclean network loss; verify the exact
session owner and absence of child work before closing an orphan. Do not kill
the SSH server or unrelated sessions to release a port.
On an owner-managed SSH server, bounded `ClientAliveInterval` and
`ClientAliveCountMax` settings also let the server retire unreachable clients
instead of retaining their remote listeners indefinitely. Validate the exact
server configuration before reloading it; client-side keepalives alone do not
ensure a server detects an unclean network loss.

Stop with Ctrl+C. Only children started by this supervisor are terminated.
Do not start it alongside another launcher that owns the same forwarding ports.
It uses a process lock to prevent duplicate supervisors for that configuration.
Unverifiable locks require owner inspection; do not delete a live lock.

Receipts contain public link names, process IDs, retry counts and state. They
omit command arguments, SSH paths, addresses and error output. `process_running`
means only that SSH has not exited. Use Kingdom's signed inventory, heartbeat,
load report and actual task receipts to verify application connectivity and work.
Keep the config private and its local SSH configuration trusted. It must not be
constructed from model output or untrusted downloaded instructions.
