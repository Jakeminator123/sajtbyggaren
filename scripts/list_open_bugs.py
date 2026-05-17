"""List the active bug scope from docs/known-issues.md.

Run as part of an agent session's start sequence so the agent's
"active scope" is the buggar in the "Öppna - inte fixade än" section
of known-issues.md, never one of the (much larger) closed list.

The script also flags **misplaced** entries: posts that still live in
the "Öppna" section but already have `Fix: <sha>` set. Those are
buggar that landed in a PR/commit but were never moved to the
"Stängda" section, which is the most common reason agents and the
operator confuse the actual scope.

Usage:

    python scripts/list_open_bugs.py            # human-readable
    python scripts/list_open_bugs.py --json     # machine-readable
    python scripts/list_open_bugs.py --quiet    # exit-code only

Exit codes:

    0 - parsed successfully (irrespective of bug counts)
    1 - could not find the expected section headings or parse failed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWN_ISSUES = REPO_ROOT / "docs" / "known-issues.md"

OPEN_HEADING = "## Öppna - inte fixade än"
CLOSED_HEADING = "## Stängda - regression-test säkrar fixet"

# Matches the opening line of a bug entry. Severity is intentionally
# permissive because the file uses "Hög", "Medel", "Låg", "Medel-Hög",
# "Hög-säkerhet", "Låg-Medel", etc. ID accepts letters, digits, dash,
# and the slash that B6/B10-style merged posts use.
#
# Entries in "Öppna" look like:
#     - **`B61` Hög** - <text>
# Entries in "Stängda" look like:
#     - **`B61` Hög** (stängd 2026-05-15, demo-baseline-fix 1A-hotfix) - <text>
# The optional `(... )` group between severity and the leading dash
# covers the Stängda variant so both sections parse with one regex.
_ENTRY_RE = re.compile(
    r"^- \*\*`(?P<id>[A-Z][A-Z0-9/-]*)` (?P<severity>[A-Za-zÅÄÖåäö-]+)\*\*"
    r"(?:\s*\([^)]*\))?"
    r"\s*-\s*(?P<rest>.+?)$",
    re.MULTILINE,
)

# Match `Fix: \`<sha>\`` (closed via commit) inside an entry body.
_FIX_SHA_RE = re.compile(r"Fix:\s*`?([0-9a-f]{7,40})`?")
# Match `Fix: open` (not yet closed) inside an entry body.
_FIX_OPEN_RE = re.compile(r"Fix:\s*open\b", re.IGNORECASE)


@dataclass(frozen=True)
class BugEntry:
    """A single bug post extracted from known-issues.md."""

    id: str
    severity: str
    summary: str
    fix_sha: str | None
    fix_open: bool

    @property
    def status(self) -> str:
        """One of `active`, `misplaced`, or `unknown`.

        - `active`: lives in Öppna, Fix marker says open. True scope.
        - `misplaced`: lives in Öppna but has a Fix: <sha> marker
          (should be moved to Stängda).
        - `unknown`: no recognisable Fix marker; needs operator review.
        """
        if self.fix_open:
            return "active"
        if self.fix_sha:
            return "misplaced"
        return "unknown"


def _split_known_issues(text: str) -> tuple[str, str]:
    """Return (open_section, closed_section) substrings.

    Raises SystemExit if either heading is missing - that would mean
    the file format has drifted and the script needs an update before
    the agent trusts the output.
    """
    open_pos = text.find(OPEN_HEADING)
    closed_pos = text.find(CLOSED_HEADING)
    if open_pos == -1 or closed_pos == -1:
        raise SystemExit(
            "list_open_bugs: cannot find Öppna and/or Stängda heading "
            f"in {KNOWN_ISSUES.relative_to(REPO_ROOT)}. The script and "
            "the file format are out of sync; update one of them."
        )
    if closed_pos < open_pos:
        raise SystemExit(
            "list_open_bugs: Stängda heading appears before Öppna in "
            f"{KNOWN_ISSUES.relative_to(REPO_ROOT)}; expected the "
            "opposite order."
        )
    return text[open_pos:closed_pos], text[closed_pos:]


def _collect_entries(section: str) -> list[BugEntry]:
    """Extract bug entries from a section substring.

    Each entry covers from one `_ENTRY_RE` match through to the
    character just before the next match (or to end-of-section). The
    full entry body is then scanned for Fix-status markers.
    """
    matches = list(_ENTRY_RE.finditer(section))
    entries: list[BugEntry] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        body = section[start:end]
        summary = match.group("rest").strip().rstrip(".").strip()
        # Trim to a readable terminal-width slice; the full body is
        # always accessible in known-issues.md if more context is needed.
        if len(summary) > 140:
            summary = summary[:137] + "..."
        fix_sha_match = _FIX_SHA_RE.search(body)
        fix_open_match = _FIX_OPEN_RE.search(body)
        entries.append(
            BugEntry(
                id=match.group("id"),
                severity=match.group("severity"),
                summary=summary,
                fix_sha=fix_sha_match.group(1) if fix_sha_match else None,
                fix_open=bool(fix_open_match),
            )
        )
    return entries


def collect_bug_state(text: str | None = None) -> dict[str, list[BugEntry]]:
    """Parse known-issues.md and return categorised entries.

    Returns a dict with keys `active`, `misplaced`, `unknown`, and
    `closed`. Useful as a library entry point for the regression test
    that locks the summary line at the top of the file.
    """
    if text is None:
        text = KNOWN_ISSUES.read_text(encoding="utf-8")
    open_section, closed_section = _split_known_issues(text)
    open_entries = _collect_entries(open_section)
    closed_entries = _collect_entries(closed_section)
    grouped: dict[str, list[BugEntry]] = {
        "active": [],
        "misplaced": [],
        "unknown": [],
        "closed": closed_entries,
    }
    for entry in open_entries:
        grouped[entry.status].append(entry)
    return grouped


def _print_human(state: dict[str, list[BugEntry]]) -> None:
    active = state["active"]
    misplaced = state["misplaced"]
    unknown = state["unknown"]
    closed = state["closed"]

    print("Aktivt bug-scope (from docs/known-issues.md)")
    print("=" * 60)
    print(
        f"  Active: {len(active)}    "
        f"Misplaced: {len(misplaced)}    "
        f"Unknown: {len(unknown)}    "
        f"Closed: {len(closed)}"
    )
    print()

    if active:
        print("Active (Fix: open) - this is the scope for new work:")
        for entry in active:
            print(f"  {entry.id:<10} {entry.severity:<14} {entry.summary}")
    else:
        print("Active: (none - no buggar with Fix: open)")
    print()

    if misplaced:
        print(
            "Misplaced (has Fix: <sha> but still in Öppna section) - "
            "should be moved to Stängda by a Steward pass:"
        )
        for entry in misplaced:
            print(
                f"  {entry.id:<10} {entry.severity:<14} "
                f"fix={entry.fix_sha[:7]}  {entry.summary}"
            )
        print()

    if unknown:
        print(
            "Unknown (Öppna entry without a recognisable Fix marker) - "
            "needs operator triage:"
        )
        for entry in unknown:
            print(f"  {entry.id:<10} {entry.severity:<14} {entry.summary}")
        print()

    print(
        "Reminder: scope for new agent work is the Active list only. "
        "Misplaced and Closed entries are protected by regression-tests; "
        "ändra dem inte utan att Steward först har flyttat dem."
    )


def _print_json(state: dict[str, list[BugEntry]]) -> None:
    payload = {key: [asdict(entry) for entry in entries] for key, entries in state.items()}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List active bug scope from docs/known-issues.md."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of a human-readable report",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress output; useful when only the exit code matters",
    )
    args = parser.parse_args(argv)

    state = collect_bug_state()

    if args.quiet:
        return 0
    if args.json:
        _print_json(state)
    else:
        _print_human(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
