# Four historical Kingdom branches — final adoption decision

**Decision date:** 2026-11-20 · **Reviewed against:** `main` at `e5781a873b3cddd6fa4226f20e902ab4ac60cfd8` · **Owner-directed choice:** retain useful, safe improvements; reject unsafe or already-obsolete branch implementations. This is a code/source comparison, not a claim of installed-device acceptance.

All four original SHAs were verified under `kingdom-history/2026-11-19/<branch-name>` before branch cleanup, and all four old branch references were subsequently retired. The full historical tag set (35) was preserved. Archiving is not implementing.

| Historical source and immutable head | Decision | Code-level evidence | What is retained on current main |
| --- | --- | --- | --- |
| `codex/monitor-execution-guard-20261023` — `aee1296f97878c8ec5ccc7879a674cd2e0cd02ba` | **Archive, do not integrate.** | Adds `backend/security/required_monitor.py` and `monitor_supervisor.py`: Ed25519 receipts and Unix `SO_PEERCRED`-bounded signer. Its own design notes explicitly say actual separate-UID deployment and effect-broker mediation are *not verified*. Integrating this into `ZeroTrust` without a production isolation test could make authorization unexpectedly unavailable; it is Linux-specific. | Existing owner approval, token trust, audit and service supervision remain authoritative; independent monitor is not a shipped feature. |
| `feat/autonomous-harness-foundation-17802645864919866654` — `980772d689651accd8b1b4d68c20591d8031274a` | **Keep useful negative tests only; reject executor.** | `IsolatedBuildRunner.execute_build(job,file_changes,test_fn)` validates paths and runs `test_fn()` but never writes `file_changes`. Thus its claimed auto-repair results cannot prove patch correctness. The reviewer merely scans text for skip markers; it does not independently execute candidates. | Current `backend/runtime/self_build_guard.py` proposal/authorization gating stays intact. New `tests/test_gap_api_owner_boundary.py` ports actual anonymous-denial checks. No false claim of self-building execution. |
| `jules-12217898583924398317-1da231a0` — `f60585244e67250cfb63fa6f0adcb6a15b93af67` | **Archive, do not integrate.** | `PublicApisSourceAdapter` fetches configurable URLs with `follow_redirects=True`; `VerificationService.verify_provider` blindly GETs provider-controlled documentation/homepage URL with redirects. This introduces SSRF/redirect/network egress risks and untrusted catalog data could imply providers are free, reachable, or authorized without proper verification. Duplicate schema/profiles also conflict with current model profiles. | Keep current configured model profiles, truthful read-only adapter discovery, and human-governed execution. A general external API catalog is still *not implemented*. |
| `jules-external-oracle-harness-4034832206850530088` — `df15fe1fba098faeb0eb18d5dfa6e0c1bfc6f87e` | **Superseded by newer code; remove legacy branch.** | Current `main` already contains `scripts/jules-external-oracle.py`, `tests/test_jules_external_oracle.py`, documentation, and stronger reviewed image/instance/source isolation checks. The old oracle lacks these newer checks. Both use command arguments for probe headers; the current oracle is repaired in this review to use stdin instead. | Current host-owned oracle and its regression tests, with protected stdin-only fixture-token transport. |

## Merge / security acceptance

- [x] Compare all four source branches against current `main`; no whole-branch merge (historical branches trail current main by 66–355 commits).
- [x] Keep four exact historical commit backups (tags; no released feature implied).
- [x] Copy/adapt only the owner-authentication regression from the self-build prototype and harden the actual current oracle's Docker probe argv.
- [x] Latest combined backend/frontend/desktop CI on PR #168 passed before merge: 1,977 backend tests, 5 skipped; frontend and desktop packaging succeeded. Windows native hit a networked E2E timeout; it is separately tracked and not certified by this acceptance.
- [ ] Independently installed multi-node signer, auto-build executor and general provider catalog **are not included and are not represented as passed**.
- [x] Close draft PR #131 as reviewed/rejected for this release; original source remains recoverable via immutable archive tag.
- [x] Delete all four historical branch refs after exact original SHA and tag checks. [Action run 44785597436](https://github.com/wests-cmd/kingdom/actions/runs/44785597436) succeeded with four retired, zero skipped. Preserve only `main` and `integration/kingdom-cohesion-20261119`.

## Guardrails

A proof of offline code behavior is not an installed-systems guarantee. Other later projects can revisit the archived designs, but must start from current Kingdom contracts, require owner consent for security/trust changes, independently verify worker identity and build candidate integrity, and deny invalid or unverified provider/monitor claims. The archive tags preserve design history, **not functional parity or authorized rollout**.
