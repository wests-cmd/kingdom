# Vault layouts and reconnecting Knights

A Kingdom can run on one computer or coordinate several Knights. Joining paired
Kingdoms presents one logical cluster; each computer retains its own identity,
credentials and authority. Reconnection never transfers authority to an unknown
replacement machine.

## Choose a layout

| Layout | Intended use | Current implementation |
| --- | --- | --- |
| Standalone | One Knight keeps project memory locally | Local durable vault |
| Central archive | One archive plus bounded caches on each Knight | Identity-pinned local external archive and cache; authenticated remote synchronization remains pending |
| Balanced peers | Available Knights distribute archive copies by capacity | Deterministic placement planner only; transfer and replication remain pending |

Storage capacity is configurable. No particular drive size, host name or machine
count is required. A central archive is not a backup; retain a verified independent
copy. Never share the live SQLite database over a network filesystem.

## Access and payment information

Notes may carry explicit Apprentice role allowlists. Unlabelled notes are shared
within their project; restricted notes are excluded from ordinary model retrieval
and from offline cached search for other roles. Owner administration can inspect
all notes. Role labels are retrieval controls, not operating-system sandboxes.

Keep payment instruments with a payment provider. General AI notes reject common
card-number and security-code patterns, including import paths. This detector is
not a comprehensive secret scanner. Payment agents should use scoped provider
references; coding agents must not receive payment credentials or secret-store
access. Merely selecting a role does not grant a tool or provider permission.

## External archive configuration

Without external configuration, notes remain local. Administrators can set
`KINGDOM_VAULT_ROOT` to an existing absolute archive directory and
`KINGDOM_VAULT_ID` to its `.kingdom-vault-id` marker. The database is
`vault.sqlite3`. Formatting, mounting and migration are separate authorized setup
steps that verify the physical device, preserve existing files and check backups.

`KINGDOM_HOT_CACHE_BYTES` defaults to 8 MB and permits up to 64 MB. Cached reads
include age and non-authoritative status. Missing or changed archive media causes
writes to fail visibly; Kingdom must not silently create a replacement on the OS
disk. Cross-Knight synchronization must preserve project and role isolation.

## Discovery and visibility

The local service inventory observes running services without starting or stopping
them. Authenticated fresh peer reports can expose their observations in Swarm's
network view. A missing report means unknown, not zero services or Apprentices.
Discovery does not grant control over a discovered application. Service management
and remote updates require explicit adapters, tool grants and verification.

Swarm groups Apprentices beneath their Knight. Its links show logical pairing,
not a claim about physical Ethernet or Wi-Fi connections. Easy and Advanced views
are selected in Settings; Advanced retains diagrams while adding identifiers.
