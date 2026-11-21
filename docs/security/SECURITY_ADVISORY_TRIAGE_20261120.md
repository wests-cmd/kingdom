# Kingdom: November 2026 autonomous-agent security triage

**Scope**: source review of current `main`, plus a focused review-branch patch. This is NOT an inspection of the installed services on Laptop 2, DT1, Windows Laptop 1, mobile clients or remote nodes. Nothing in this document certifies deployment.

## Original research: confirmed affected packages and conditions

| Report | Confirmed advisory | Affected / fix |
| --- | --- | --- |
| Malicious Python startup hook | [GHSA-764m-3ppc-5m73](https://github.com/advisories/GHSA-764m-3ppc-5m73) | `agent-framework` PyPI 1.26.1, 1.26.2 contained credential theft |
| Git tool command execution | [GHSA-8wv7-r664-7594](https://github.com/modelcontextprotocol/servers/security/advisories/GHSA-8wv7-r664-7594) | `mcp-server-git` prior to 2026.11.18; repo-controlled Git submodule configuration |
| Malicious memory MCP plugin | [GHSA-9hvg-j8mj-55xr](https://github.com/advisories/GHSA-9hvg-j8mj-55xr) | npm `mem0-mcp-server`: all published releases |
| MCP registry admin escalation | [CVE-2026-100307](https://aws.amazon.com/security/security-bulletins/2026-179-aws/) | `mcp-gateway-registry` 1.0.9–1.24.7, fix 1.25.0; review persisted grants |
| MCP gateway internal-network SSRF | [CVE-2026-125926](https://aws.amazon.com/security/security-bulletins/2026-180-aws/) | `mcp-gateway-registry` 1.0.3–1.34.0, fix 1.35.0; review existing server URLs |

These reports concern **other software**. Their presence in a news brief is not evidence that Kingdom or a joined computer installed them.

## Source evidence

The three `requirements*.txt` files, three direct npm `package.json` files, and three npm lockfiles on main were inspected for these specific dependency names. None was present in these declared sources at review time. This does **not** establish a full transitive, system, model-extension or worker installation inventory.

Existing reusable code:
- `backend/security/zero_trust.py`, `approval_engine.py`, `http_auth.py` enforce a range of identity, approval and owner controls.
- `backend/security/node_security.py` rotates tokens and revokes in-process node credentials. This does not alone prove persistent cross-machine fencing after failover.
- `backend/runtime/knight_updates.py` stages hashed releases and attempts rollback.
- `scripts/audit_release_dependencies.py` already queries OSV for installed Python packages in the native release workflow.
- `backend/skills/installer.py` gates skill state, but does not prove isolated package execution or a safe `pip install` environment.
- `backend/integrations/github.py` supplies an integration provider, not a formal Git command sandbox.

## Code changes for review (not deployment)

- `scripts/audit_known_compromises.py`: network-free, standard-library static check for the named affected packages in recursively included Python requirements and npm direct/lock manifests. Any unpinned watched package or affected pinned version fails; missing/invalid manifest blocks the scan. `--installed` additionally scans installed Python metadata, but that check necessarily happens after Python startup.
- `tests/test_known_compromise_gate.py`: adversarial fixtures for malicious `.pth` package versions, old MCP Git releases, npm transitive malware, registry SSRF version, missing inventory, and nested Python requirements.
- `.github/workflows/ci.yml`, `.github/workflows/release.yml`: fail the jobs **before** `pip`/`npm` installation if a known compromised dependency appears in checked manifests; keep the existing OSV release audit.
- `backend/security/scoped_authorization.py`: repair an independent *secondary* authorization helper that previously trusted `request.context["approved_by_commander"]` or a caller-selected governance level for HIGH risk. New HIGH-risk decisions require a trusted runtime-supplied validator of the exact request. The request alone never constitutes verified approval. A host must actually inject a verifier bound to its existing approval records; this change does not silently add a second approval store.
- `tests/test_scoped_authorization_proof.py`: prove forged commander assertions fail, exceptions deny, scope mutation is rejected, revocation denies, and low-risk reads remain possible.

## Strict installed-runtime security acceptance checklist

**0 verified YES / 0 confirmed NO / 8 NOT TESTED**. A source test is not an installed physical-device acceptance test.

| Requirement | Result | Missing independent proof |
| --- | --- | --- |
| Malicious dependency cannot reach protected credentials | NOT TESTED | OS-level isolated install using a malicious fixture while production secrets remain inaccessible |
| Git repository controlled command cannot escape sandbox | NOT TESTED | Actual repo with hostile hooks, submodules, filters and helper commands in isolated worker |
| Self-approval is blocked | NOT TESTED | End-to-end agent-to-effect attempt against every approval path, including governance changes |
| RPC replay cannot duplicate effects | NOT TESTED | Durable request-id and epoch replay tests across node reboot, network split and controller failover |
| Revocation survives reconnection | NOT TESTED | Real worker re-enrollment attempt using revoked identity after supervisor restart |
| Network destinations are restricted | NOT TESTED | DNS rebinding, redirect, IPv6, localhost and cloud metadata attempts from registered MCP tools |
| Required monitoring cannot be disabled | NOT TESTED | Tamper, crash, storage exhaustion and OS principal separation proving fail-closed attestation |
| Recovery and rollback preserve authority | NOT TESTED | Interrupted upgrade and rollback tests across multiple physical workers with stale lease rejection |

## Decision boundary

This PR is a **reviewed candidate**, not an automatic security-policy deployment. Do not self-merge this authorization change. Release remains blocked under the eight-item policy until mandatory physical tests provide evidence. Do not claim the workstation, mobile APK, or remote workers were audited from a GitHub source tree.

**Next commissioning work:** inspect every installed dependency and service account on Laptop 2 and DT1, ensure untrusted Git and package execution take place under OS-enforced isolation with no production secrets, and execute the eight adversarial scenarios above with trusted external evidence and a fail-closed release gate.
