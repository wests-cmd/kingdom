# Preparing a native stable release

The canonical version is the literal `STATE['version']` in backend/state.py.
Native CI resolves it once, validates the four package versions and three lockfile
root versions, and requires reviewed version-specific release notes. All platform
builds and aggregate publication use that version and the exact candidate SHA.
This removes workflow version edits; it does not remove test or publication gates.

Run `python scripts/prepare_version.py X.Y.Z` first. This is a dry-run: it reports
the proposed files and performs no writes. Choose an explicit newer stable
version. Review that plan, then use the same command with `--apply` when ready.
If old package metadata diverges, the command stops; inspect it before explicitly
adding `--repair-existing-metadata`. This migration option repairs metadata only,
not runtime or acceptance failures.

Preparation synchronizes backend/state.py, frontend/desktop/mobile/native-mobile
package versions, their existing lockfile root entries, Android versionName and
iOS MARKETING_VERSION. Dependency versions and Android/iOS store build numbers
are preserved; store publication and signing remain separate work. Historical
release notes and README download links are not blindly rewritten.

All changes are validated and staged before replacement. Failed replacements
roll back prior replacements. Each file replacement is atomic; the collection is
not a filesystem transaction and is not power-loss atomic. An interrupted process
can retain `.version-preparation.lock`; inspect the files and restore consistency
before removing that lock and retrying. Do not run preparation concurrently with
other metadata edits or an in-progress candidate verification.

The generated docs/releases/vX.Y.Z.md is a scaffold with
`<!-- RELEASE_REVIEW_REQUIRED -->`. Replace it with factual reviewed changes,
exact-source validation and remaining limits, then remove that marker. Native CI
rejects missing or unreviewed notes. A scaffold is never evidence of passing tests,
trusted signing, general autonomous coding or hardware acceptance.

Run `python scripts/validate_version.py --tag vX.Y.Z` and relevant tests locally.
Commit the reviewed metadata, notes and actual implementation together through
the normal PR process. Native CI still builds/tests three platforms, exercises
installers, audits dependencies and checks artifact hashes. Main publication still
requires the exact current main SHA and matching tag, refuses to replace an
already published release, creates a draft, downloads/verifies its bytes, and
only then makes it stable. Preparation never pushes, tags, builds or publishes.

Version-script and versioned release-note changes trigger native checks. PR
checks and branch protections remain applicable; docs-only changes are not a
reason to assume required checks are waived.
