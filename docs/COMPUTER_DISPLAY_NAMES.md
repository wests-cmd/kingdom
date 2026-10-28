# Computer usernames in Swarm

Swarm labels use username and computer name instead of view-relative Knight numbers. The same labels appear in the overview, computer cards, coordination diagram and team selectors. Unknown generic hostnames fall back to a distinguishing identity suffix. Long diagram text is shortened with the complete label retained in its title and card.

Owner-managed labels live in SQLite `computer_display_names(node_id, username, computer)`. `local` identifies the local display; remote rows use the complete pinned Kingdom node ID. The local default is the account running Kingdom. Verified host account names may be recorded by an authorized operator when a container's account differs from the owner's host account. New peers are not assigned guessed usernames.

Labels are presentation data only. They do not replace cryptographic identity, change routing or authorization, alter connection state, grant permissions or impersonate an authenticated user. A disconnected card keeps its real connection state when renamed.

October 25 owner labels: bot1 · Laptop 2; bot2 · Laptop 3; centipede-admin · DT1. Laptop 2 and Laptop 3 received compatibility builds against their existing frontend versions, preserving their backend behavior. Their original sources and service definitions remain available for rollback. This is not a full stable release upgrade.
