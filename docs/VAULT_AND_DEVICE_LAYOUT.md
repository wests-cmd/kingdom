# Vault and reconnecting devices

Keep one archive on an always-connected machine, and a bounded hot cache on each
Kingdom. Computers retain distinct Kingdom identities. A disconnected computer is
not spare capacity; reconnecting a different identity requires pairing rather than
silently inheriting its predecessor's authority.

## Storage roles

| Storage | Recommended role |
| --- | --- |
| Dedicated 1 TB external drive | Main vault on the permanent server; readable project notes, reports and receipts |
| Server internal disk | OS, Kingdom services, containers and temporary computation |
| Each computer's internal disk | Its own state, credentials and small local hot cache |
| Large installer/live USB | Recovery/live boot, separate from the canonical vault |
| Small installer USB | OS installation/recovery; verify target identity before writes |
| 128 GB removable model storage | Optional model files and reusable downloads; not the only vault backup |
| 64 GB SD | Device-specific workspace/cache or backup, after identifying existing contents |

These are roles, not automatic formatting instructions. Capacity alone does not
identify a device. Preserve files and inspect model/serial/filesystem before any
migration. A central disk is not a backup: keep an additional verified copy on
separate storage.

## Implemented storage contract

Without external configuration, existing notes remain in the local database.
Administrators can configure `KINGDOM_VAULT_ROOT` to an existing absolute path and
`KINGDOM_VAULT_ID` to the identity stored in `.kingdom-vault-id` on that archive.
The archive database is `vault.sqlite3`. Creation of the marker and migration of
existing notes are explicit installation steps after media identification, not
actions performed by an HTTP caller or by a model.

`KINGDOM_HOT_CACHE_BYTES` defaults to 8 MB per Kingdom, with a 64 MB maximum.
Read/save/search operations populate a bounded, scoped local cache. Disconnecting
the archive permits cached reads marked with age and non-authoritative status.
Archive writes fail visibly while absent or when its identity differs. A missing
mount must never cause a new vault to appear silently on the OS disk.

The vault API and shared request retrieval use this configured storage. Notes do
not include owner credentials or grant agent authority. A remotely connected
Kingdom still needs authenticated, scoped synchronization; mounting one SQLite
database concurrently across network filesystems is not the synchronization
protocol. The local cache implementation does not claim that remote sync is done.

## Example device placement

The owner's DT1 is an installed headless Centipede server, with laptop 2 currently
hosting additional services and models. Laptop 1 and laptop 3 may leave and
return; reserve their work only while reachable and retain their own identities.
Phones can use an authenticated front door without being counted as compute
workers. Installing an APK is separate from replacing Android with another OS.

The identified MXQ runs Android 4.4.2 with kernel 3.10.33. That version/build does
not identify its SoC or establish Wi-Fi-to-Ethernet sharing support. Before using
it as a network bridge/router, identify actual Ethernet/Wi-Fi interfaces,
firmware, routing support and supported administrative access. Do not flash an
image selected only by the generic MXQ label. Preserve DT1's working Ethernet
path while testing a replacement. Physical attachment of a drive or Ethernet
cable remains a physical step.
