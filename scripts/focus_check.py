"""Drift detector: does the repo match docs/current-focus.md?

Run as the first step in any agent session. Catches the most common
operator mistakes: forgotten merge, forgotten push, stale focus file,
unexpected open PRs, or extra local branches lying around. Output is
human-readable; non-zero exit only when something is actively wrong
(local diverges from origin, focus file has no Last verified SHA, etc).

Usage:

    python scripts/focus_check.py            # full check
    python scripts/focus_check.py --json     # machine-readable summary

The "Last verified" SHA in docs/current-focus.md is the anchor. Every
time the focus file is updated to match a new repo state, the SHA on
that line should be bumped to the commit that does the update.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FOCUS_FILE = REPO_ROOT / "docs" / "current-focus.md"

LAST_VERIFIED_RE = re.compile(
    r"^Last verified state:\s*`?([0-9a-f]{7,40})`?",
    re.IGNORECASE | re.MULTILINE,
)


def run(args: list[str]) -> tuple[int, str]:
    """Run a command, return (returncode, stdout-stripped)."""
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, (result.stdout or "").strip()


def read_focus_sha() -> str | None:
    if not FOCUS_FILE.exists():
        return None
    text = FOCUS_FILE.read_text(encoding="utf-8")
    match = LAST_VERIFIED_RE.search(text)
    return match.group(1) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="emit a JSON summary instead of the human-readable report",
    )
    args = parser.parse_args()

    report: dict[str, str] = {}
    warnings: list[str] = []
    errors: list[str] = []

    _, branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    report["branch"] = branch

    _, head_sha = run(["git", "rev-parse", "HEAD"])
    report["head"] = head_sha[:7] if head_sha else "?"

    _, dirty = run(["git", "status", "--porcelain"])
    if dirty:
        warnings.append(f"working tree has uncommitted changes:\n{dirty}")
        report["working_tree"] = "dirty"
    else:
        report["working_tree"] = "clean"

    fetch_code, _ = run(["git", "fetch", "--quiet", "origin"])
    if fetch_code != 0:
        warnings.append("could not fetch from origin (offline?)")

    _, origin_sha = run(["git", "rev-parse", f"origin/{branch}"]) if branch else (1, "")
    report["origin"] = origin_sha[:7] if origin_sha else "?"

    if branch and origin_sha and head_sha:
        if head_sha != origin_sha:
            ahead_code, ahead = run(
                ["git", "rev-list", "--count", f"origin/{branch}..HEAD"]
            )
            behind_code, behind = run(
                ["git", "rev-list", "--count", f"HEAD..origin/{branch}"]
            )
            ahead_n = int(ahead) if ahead_code == 0 and ahead.isdigit() else 0
            behind_n = int(behind) if behind_code == 0 and behind.isdigit() else 0
            if ahead_n and behind_n:
                errors.append(
                    f"local {branch} has diverged from origin "
                    f"(ahead {ahead_n}, behind {behind_n}). Reconcile before continuing."
                )
            elif ahead_n:
                warnings.append(
                    f"local {branch} is ahead of origin by {ahead_n} commit(s). "
                    "Forgotten push?"
                )
            elif behind_n:
                warnings.append(
                    f"local {branch} is behind origin by {behind_n} commit(s). "
                    "Forgotten pull?"
                )
        else:
            report["sync"] = "in sync"

    focus_sha = read_focus_sha()
    if focus_sha is None:
        errors.append(
            "docs/current-focus.md is missing or has no 'Last verified state: <sha>' line"
        )
    else:
        report["focus_sha"] = focus_sha[:7]
        if head_sha and not head_sha.startswith(focus_sha):
            # Count how many commits separate them.
            count_code, count_text = run(
                ["git", "rev-list", "--count", f"{focus_sha}..HEAD"]
            )
            n = int(count_text) if count_code == 0 and count_text.isdigit() else None
            if n:
                warnings.append(
                    f"docs/current-focus.md is stale: HEAD is {n} commit(s) ahead "
                    f"of the focus SHA {focus_sha[:7]}. Update the focus file "
                    "(or read the recent commits to understand the new state)."
                )
            else:
                warnings.append(
                    "docs/current-focus.md SHA does not match HEAD and could not be "
                    "compared (focus SHA may be on a different branch or rebased away)."
                )

    pr_code, pr_json = run(
        ["gh", "pr", "list", "--state", "open", "--json", "number,title,isDraft,headRefName"]
    )
    if pr_code == 0 and pr_json:
        try:
            prs = json.loads(pr_json)
        except json.JSONDecodeError:
            prs = []
        report["open_prs"] = ", ".join(f"#{p['number']}" for p in prs) or "(none)"

    branch_code, branches = run(["git", "branch", "--format=%(refname:short)"])
    if branch_code == 0:
        extras = [
            b.strip()
            for b in branches.splitlines()
            if b.strip() and b.strip() != "main"
        ]
        report["extra_local_branches"] = ", ".join(extras) if extras else "(none)"
        if extras and not warnings:
            report["extra_local_branches"] += "  (not necessarily wrong, just FYI)"

    if args.emit_json:
        print(
            json.dumps(
                {"report": report, "warnings": warnings, "errors": errors},
                indent=2,
            )
        )
    else:
        print("focus_check")
        print("=" * 60)
        for key, value in report.items():
            print(f"  {key:<22} {value}")
        if warnings:
            print("\nWarnings:")
            for w in warnings:
                print(f"  - {w}")
        if errors:
            print("\nErrors:")
            for e in errors:
                print(f"  - {e}")
        if not warnings and not errors:
            print("\nResult: OK - repo matches docs/current-focus.md.")
        elif errors:
            print("\nResult: BLOCK - resolve errors before continuing.")
        else:
            print("\nResult: WARN - review warnings above before continuing.")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
