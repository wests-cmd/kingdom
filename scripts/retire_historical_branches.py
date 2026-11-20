"""Archive exact historical branch tips as tags before optionally retiring branches.

This command is deliberately conservative:
- dry-run by default
- only listed pinned branches can be touched
- never main or the keeper
- no open pull request head can be deleted
- refuse any branch whose head changed
- verify that the remote archive tag points to the original commit
- force-with-lease protects against a concurrent branch update

Invoke via the manually dispatched GitHub Actions workflow on main AFTER
the integration PR is merged. No deletion is automatic on code merge.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def load_manifest(path=None):
    location = Path(path) if path else Path(__file__).resolve().parents[1] / "docs" / "branch_retirement_manifest.json"
    manifest = json.loads(location.read_text(encoding="utf-8"))
    candidates = manifest["branches"]
    names = [record["name"] for record in candidates]
    keepers = set(manifest["keepers"])
    if len(names) != len(set(names)) or len(candidates) != 35:
        raise ValueError("Unexpected branch manifest size or duplicate")
    if keepers != {"main", "integration/kingdom-cohesion-20261119"} or keepers.intersection(names):
        raise ValueError("Protected keeper set is invalid")
    if not all(len(row["sha"]) == 40 and all(c in "0123456789abcdef" for c in row["sha"]) for row in candidates):
        raise ValueError("Invalid commit pin")
    if manifest["history_tag_prefix"] != "kingdom-history/2026-11-19/":
        raise ValueError("Archive namespace changed")
    accepted = {"integrated", "superseded", "review_required"}
    if any(row.get("disposition") not in accepted or
           not isinstance(row.get("review"), str) or len(row["review"]) < 20
           for row in candidates):
        raise ValueError("Every historical branch needs a reviewed disposition and rationale")
    return manifest


def active_pull_request_heads(repository):
    raw = run("gh", "api", "--paginate", f"repos/{repository}/pulls?state=open&per_page=100",
              "--jq", ".[].head.ref")
    return set(raw.splitlines())


def remote_heads():
    result = {}
    for line in run("git", "ls-remote", "--heads", "origin").splitlines():
        sha, ref = line.split(None, 1)
        if ref.startswith("refs/heads/"):
            result[ref.removeprefix("refs/heads/")] = sha
    return result


def remote_tag_sha(tag):
    lines = run("git", "ls-remote", "--tags", "origin", "refs/tags/" + tag).splitlines()
    if not lines:
        return None
    exact = [line for line in lines if line.endswith("refs/tags/" + tag)]
    return exact[0].split()[0] if len(exact) == 1 else None


def record_summary(results):
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as output:
        output.write("## Historical branch retirement\n\n")
        output.write("| Branch | Result |\n|---|---|\n")
        for branch, state in results:
            output.write(f"| `{branch}` | {state} |\n")


def main():
    manifest = load_manifest()
    mode = os.environ.get("RETIRE_MODE", "audit")
    if mode not in ("audit", "archive-only", "archive-and-delete"):
        raise ValueError("Invalid mode")
    can_archive = mode in {"archive-only", "archive-and-delete"}
    can_delete = mode == "archive-and-delete"
    if can_delete and os.environ.get("RETIRE_CONFIRMATION") != "ARCHIVE_AND_RETIRE_35":
        raise ValueError("Deletion needs exact explicit confirmation")
    if can_archive and os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Archive and deletion can only run on main")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if repository != manifest["repository"]:
        raise ValueError("Wrong GitHub repository")
    heads = remote_heads()
    if not all(keeper in heads for keeper in manifest["keepers"]):
        raise ValueError("Both keeper branches must exist")
    open_heads = active_pull_request_heads(repository)
    results = []
    for row in manifest["branches"]:
        name, expected = row["name"], row["sha"]
        if name not in heads:
            results.append((name, "already absent; verify old archive independently"))
            continue
        if heads[name] != expected:
            results.append((name, "SKIPPED: branch advanced since review"))
            continue
        tag = manifest["history_tag_prefix"] + name
        existing = remote_tag_sha(tag)
        if existing is not None and existing != expected:
            results.append((name, "SKIPPED: archive tag conflict"))
            continue
        if mode == "audit":
            status = "BLOCKED: unresolved code review" if row["disposition"] == "review_required" else "reviewed"
            if name in open_heads:
                status += "; open pull request"
            results.append((name, status + "; archive required"))
            continue
        # Archive in a separately reviewable mode WITHOUT removing refs.
        # Also archive unresolved branches and branches with active PRs.
        if existing is None:
            run("git", "tag", tag, expected)
            run("git", "push", "origin", "refs/tags/" + tag)
        if remote_tag_sha(tag) != expected:
            raise RuntimeError("Archive tag verification failed; branch retained")
        if not can_delete:
            results.append((name, "ARCHIVED: branch retained"))
            continue
        if row["disposition"] == "review_required":
            results.append((name, "HELD: unported experiment or unresolved feature"))
            continue
        if name in open_heads:
            results.append((name, "HELD: open pull request"))
            continue
        try:
            # Protect against branch movement after the initial head snapshot.
            run("git", "push", "--force-with-lease=refs/heads/" + name + ":" + expected,
                "origin", ":refs/heads/" + name)
        except subprocess.CalledProcessError:
            results.append((name, "SKIPPED: branch moved or protected"))
            continue
        results.append((name, "ARCHIVED AND RETIRED"))
    record_summary(results)
    for name, state in results:
        print(f"{name}: {state}")
    print("Only reviewed safe branches may be retired. Archive tags preserve source, not feature parity.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Retirement aborted safely: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
