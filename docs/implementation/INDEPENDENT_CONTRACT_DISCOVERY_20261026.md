# Protected independent test-contract discovery

Programme planning now reads a fixed operator catalog at
`/etc/kingdom/independent-test-contracts.json`. This source change installs no
manifest, reviewer, signing key, grant or service. Discovery is unavailable on
Windows or when protected configuration is missing or invalid. Ordinary local
planning remains available and receives an explicit unavailable reason.

The manifest and every ancestor must be root-owned, without symlinks or
group/world write access. The manifest must be an ordinary file of at most
65,536 bytes, with a strict version-one schema and no duplicate JSON fields.
There may be at most 32 entries. Each entry binds a bounded description and
coverage limits to an exact contract ID/hash, project, source and explicit base
revision allowlist, minimum test count and expiration. Unknown fields, malformed
entries or duplicate contract IDs make the manifest unavailable.

Example shape only; zero expiry is deliberately expired, and the hash/revision
must be replaced with real independently reviewed values by an operator:

```json
{
  "version": 1,
  "contracts": [{
    "contract_id": "api-negative-fences",
    "contract_sha256": "<64 lowercase hexadecimal characters>",
    "project": "kingdom",
    "source": "sources/github/wests-cmd/kingdom",
    "base_revisions": ["<40 lowercase hexadecimal characters>"],
    "minimum_tests": 7,
    "description": "Seven fixed API negative fences",
    "coverage_limits": ["No generic functional correctness or returned-patch composition proof"],
    "expires_at": 0
  }]
}
```

Discovery also reads the existing protected
`/etc/kingdom/independent-reviewers.json` registry. A listed contract is exposed
only when at least one currently enabled reviewer has a valid 32-byte public
key and explicitly includes that project, source and exact contract hash in its
scope. Descriptions are operator-declared metadata, not verified semantic
coverage. Expired entries, unlisted bases, unrelated sources and unregistered
hashes produce no available matching contract. The prompt includes at most eight
entries within a 24,000-character contract metadata budget, and reports omitted
matching entries explicitly.

## Planner behavior and authority

The execution context includes exact `independent_review` descriptors and their
coverage limits. Every external-review step in a native generated proposal must
match a currently discovered descriptor, including minimum tests; this includes
earlier non-acceptance steps even when final acceptance is an ordinary project
test or another registered external review. An invented or stale hash is rejected
before becoming a plan for review. The prompt explicitly says
that negative fences cannot establish generic functional correctness and that
task-specific adequate coverage still needs owner review. The saved proposal
remains `needs_review`: catalog entries cannot approve a mission, enable Jules,
acquire missing tools, change model/worker grants or execute anything.

Existing manual owner-reviewed external proposals remain supported. This new
catalog does not replace protected attestation verification or the owner's exact
mission/placement review. A root-installed discovery entry alone grants no
execution authority. Actual provider dispatch still needs the existing current
policy, credentials, allowlists, dependencies and reviewed binding. Receipt
verification still checks current reviewer trust and exact source/patch binding.

Returned patch composition remains blocked. A contract for one returned patch
cannot establish section integration by testing the original checkout. A
separately implemented combined-returned-source contract is still required; the
existing integration guard is unchanged.

## Validation limits

Unit tests cover strict metadata, stale/revoked/unregistered scope, changed hashes,
explicit unavailability, ordinary planning with no catalog, exact prompt
descriptors, native rejection of invented hashes and no mission/task creation.
Transport/model output is not an independent verdict.

An additional test is enabled only by
`KINGDOM_CATALOG_ISOLATED_FIXTURE=1` in an explicit isolated root POSIX container
with an empty `/etc/kingdom` tmpfs. It refuses existing registry/manifest files,
uses only a fixture public key (no signing key), verifies the actual fixed paths
and OS permissions, and removes only its own files. It must not be enabled on a
production host. This is protected-read/prompt integration evidence, not an
installed production catalog or a general autonomous coding demonstration.
