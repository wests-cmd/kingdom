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
