# Kingdom branch consolidation and retirement

**Repository:** `wests-cmd/kingdom` · **Reviewed:** 2026-11-19

## One runtime, two keeper branches

- `main` stays the protected public release baseline.
- `integration/kingdom-cohesion-20261119` is the only proposed integration
  branch. The integration PR must pass reviewed CI before merging to `main`.
- The 35 historical branch tips are pinned in
  `docs/branch_retirement_manifest.json`. Their source can be recovered through
  permanent Git tags under `kingdom-history/2026-11-19/<original-name>`.

## Results of branch review

Every historical branch diverged from the integration branch. Many were hundreds
of commits behind it. Importing their entire trees would restore outdated
authorization, packaging, UI and runtime behavior.

**Ported and repaired in the integration branch:**

- `bolt-stream-consultation-queries-...` — bounded SQLite query streaming
- `fix/node-token-timing-validation-...` — token checking plus stronger token
  rotation, collision, and non-ASCII rejection
- `codex-adapter-observation-repair-...` — read-only, truthful agent/model
  discovery; does not mistake a PATH binary for an authenticated tool
- `bolt/audit-log-history-speedup-...` — bounded newest-first history scan,
  repaired thread-safe append/evict semantics

**Prefer current main implementations:** memory token caching and learning
outcome scanning already use optimized patterns with edge-case safeguards.
Existing node enrollment, mission workspace, native desktop updates, autonomous
build proposal guards and worker lifecycle are newer than the old branches.

**Retained in history, not declared merged or production-ready:** independent
security-monitor experiments, self-repair executor experiments, older desktop
and mobile interface branches, archived Jules and profile/catalog experiments,
and other divergent work. Their backup tags preserve source code for later
inspection; preserving a branch is not proof that all its features were adopted.

## Safe retirement workflow

1. Review draft PR #165 and its CI. Merge only when required tests pass.
2. After the workflow exists on `main`, open **Actions → Review and retire
   historical Kingdom branches → Run workflow**.
3. Choose `audit` first. The audit performs no branch deletions.
4. Choose `archive-and-delete` and enter `ARCHIVE_AND_RETIRE_35` to retire
   eligible historical branches. The workflow refuses changed branch heads and
   active-PR heads; it creates and verifies backup tags before a leased deletion.
5. Confirm that only `main` and the integration branch remain in Branches.
   A skipped branch needs separate review, never forced deletion.

This is a manual, explicit action. Merging the integration PR never triggers
deletion. The retirement script is not allowed to delete either keeper branch.

## Non-negotiable acceptance gates

- Backend and distributed-process E2E green at the exact integration head
- Desktop builds verified for supported OS targets
- Operator approval/security regression tests green
- Physical two-node and five-node recovery rehearsals
- Installer/update/rollback verification on clean machines
- Branch retirement dry-run inspected before deletion

Do not present historical source tags as a substitute for tested feature parity.
