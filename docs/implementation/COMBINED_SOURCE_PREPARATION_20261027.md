# Ordered combined returned-source preparation

`scripts/jules-combined-source-preparation.py` is a preparation foundation only.
It reconstructs one fresh tree from a pinned local Git base and an operator-owned
ordered set of retained returned patches. It runs no candidate program, test,
model or provider request and authorizes no task, publication or deployment.
Successful patch application is **not** combined functional/integration acceptance.
Existing programme and backend acceptance gates are unchanged.

## Inputs and trust

The Python `prepare` interface takes the repository, project/source, exact base,
ordered `expected_inputs`, retained `candidates`, fresh output, exact allowed file
paths and current reviewer registry. Every call cryptographically verifies each
existing V2 Ed25519 component receipt. There is no `verified: true`, accepted-time
override, caller-selected verifier, or expired-receipt shortcut.

Each operator-pinned expected record contains exactly:

```text
receipt_id
receipt_sha256 = SHA256(canonical JSON of the complete signed envelope)
binding = exact job/project/backlog/mission/version/step/source/base/patch/contract
```

Each retained candidate contains only patch bytes and the complete signed
attestation. List lengths and positional identity must match the complete pinned
order. A missing, additional, duplicated or silently reordered input is rejected.
If the operator explicitly reviews a different order, it is a new input plan;
even disjoint patches yielding the same final bytes produce a different ordered
input hash. Duplicate receipt, job, component backlog and patch identities are
rejected.

Receipts must still be unexpired within their original maximum one-hour window,
with a currently enabled reviewer scoped to the exact project/source/contract.
They must attest nonempty passing isolated read-only execution. A signature does
not expand the reviewer's scope or make a narrow component test adequate for a
larger combined outcome.

## Exact reconstruction

1. Validate all signed envelopes, their separately pinned hashes/bindings, patch
   bytes, common project/source/base, bounds and operator file scope.
2. Use the existing raw-Git exporter/source preparer on the exact base. Git hooks,
   global configuration, lazy fetching, alternates and external protocols remain
   forbidden by that preparation path. Export attributes do not select a working
   checkout or rewrite the raw committed source.
3. Reconstruct **each** individual base-plus-patch tree and compare its actual
   candidate-tree and base-archive hashes with that component's signed receipt.
   A later component's receipt is not compared to the aggregate after earlier
   patches. Its individual provenance is retained separately.
4. Apply ordinary textual patches sequentially to the fresh combined tree with
   check-before-apply. Conflicts fail; there is no three-way merge or silent
   fallback to the original checkout. Links, submodules, copies, renames, binary
   patches and changes outside the exact file allowlist remain forbidden.
5. Freeze the resulting tree read-only and emit
   `combined-preparation.json` only after all inputs have applied. The record binds
   complete ordered receipt identities/bindings, canonical envelope hashes,
   per-step aggregate tree hashes, raw base archive hash, final tree hash and a
   provenance hash. It explicitly claims preparation, not passing combined tests.

The first component's preparation record is retained as
`component-1-preparation.json`; later individual reconstruction directories,
patches and signed envelopes are retained as evidence. A conflict or mismatch can
leave a partial fresh directory, but emits no combined preparation record. Never
reuse or overwrite that directory as a successful result.

Bounds: two to eight components, at most 2 MB per patch/8 MB total, 64 KiB per
envelope and ordered manifest, up to 100 exact allowed paths, the existing raw
source export bounds, and a conservative 512 MiB retained-source/archive estimate
across individual verification copies. Large compositions fail rather than
silently dropping verification.

## Protected operator CLI

The CLI requires `python -I` on POSIX, root-owned non-writable script/dependency
paths, a protected immutable **bare** Git mirror, a private operator configuration
and output parent, and protected ordinary retained input files. Output must stay
outside the source mirror. The fixed trust path is
`/etc/kingdom/independent-reviewers.json`; configuration cannot nominate another
trust registry. Duplicate JSON fields are rejected. No signing key or secret is
read by this public-key-only preparation stage.

Configuration has exactly these keys:

```text
repository, project, source, base_revision,
expected_inputs: ordered full identity/hash/binding records,
candidates: ordered {patch_file, receipt_file} records,
output: new private review directory,
allowed_paths: operator-approved exact relative files
```

`cryptography` is an existing Kingdom dependency and is explicitly required in
the operator-controlled isolated Python environment. The CLI checks its package
paths are independently protected, outside candidate source; candidate backend
verifier code is never imported. The normal DT1 host Python was previously found
without this package, so this source does **not** establish that the host CLI is
ready to run. A correctly protected existing environment/image is required; the
script installs no dependencies or trust. Runtime/interpreter and all dependency
integrity remain operator prerequisites.

## Evidence and remaining seam

Tests use actual Git repositories/bare mirrors, raw source reconstruction and
real Ed25519 signatures generated only for fixtures. They cover two independent
patches, conflicts, missing/additional/duplicate/reordered input, source/base/hash
substitution, invalid signatures, expiry/revocation, first and later component
tree/archive mismatches, file scope and fresh output. No fixture candidate code
is imported or executed.

Still required: a protected combined-source test contract and trusted producer
that executes suitable integration checks against this exact combined tree,
attests its complete ordered provenance, and connects that verdict to programme
section gates. This unsigned preparation record is not accepted by any existing
gate, and neither component passes nor clean patch application substitutes for
that independent combined-source verdict. No production installation or live
autonomy demonstration occurred in this change.
