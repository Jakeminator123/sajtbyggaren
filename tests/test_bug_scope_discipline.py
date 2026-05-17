"""Tests for scripts/list_open_bugs.py and the bug-scope summary line.

Locks the contract that lets agents trust list_open_bugs.py as the
canonical source for "what is currently in scope":

- Script parses the real `docs/known-issues.md` without raising and
  returns a sane shape (active + misplaced + unknown + closed lists).
- Every entry in `active` lives in the Öppna section and has Fix: open;
  every entry in `misplaced` has a Fix: <sha> but still lives in Öppna
  (Steward cleanup signal).
- No B-ID is double-listed across Öppna and Stängda sections (would
  hide misplaced entries silently if both branches matched).
- The summary line at the top of `docs/known-issues.md` matches the
  numbers the script reports (freshness check, same pattern as
  test_docs_freshness.py).
- The matching cursor rule mirror file exists under `.cursor/rules/`
  so agents that read `.cursor/rules/` directly also pick up the
  bug-scope-discipline rule (rules_sync.py contract).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "list_open_bugs.py"
KNOWN_ISSUES = REPO_ROOT / "docs" / "known-issues.md"
RULE_SOURCE = REPO_ROOT / "governance" / "rules" / "bug-scope-discipline.md"
RULE_MIRROR = REPO_ROOT / ".cursor" / "rules" / "bug-scope-discipline.mdc"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from list_open_bugs import (  # noqa: E402
    CLOSED_HEADING,
    OPEN_HEADING,
    BugEntry,
    collect_bug_state,
)


@pytest.fixture(scope="module")
def state() -> dict[str, list[BugEntry]]:
    """Real-file state used by most tests; cached per module run."""
    return collect_bug_state()


@pytest.mark.tooling
def test_script_exists_and_is_executable_module() -> None:
    """The script must exist with a `main()` entry point so the rule
    can rely on `python scripts/list_open_bugs.py` working.
    """
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "def main(" in text
    assert "if __name__ == \"__main__\":" in text


@pytest.mark.tooling
def test_collect_bug_state_returns_four_buckets(
    state: dict[str, list[BugEntry]],
) -> None:
    """The library API must always return the four documented buckets,
    even when one of them is empty. Agents and tests rely on the keys.
    """
    assert set(state.keys()) == {"active", "misplaced", "unknown", "closed"}
    for entries in state.values():
        assert isinstance(entries, list)


@pytest.mark.tooling
def test_active_entries_all_carry_fix_open(
    state: dict[str, list[BugEntry]],
) -> None:
    """`active` is the agent's scope. If a bug lands here with a Fix:
    SHA marker the classification is broken and the agent could plan
    work that's already done.
    """
    for entry in state["active"]:
        assert entry.fix_open is True, (
            f"{entry.id} classified as active but lacks Fix: open marker"
        )
        assert entry.fix_sha is None, (
            f"{entry.id} classified as active but also has Fix: {entry.fix_sha}"
        )


@pytest.mark.tooling
def test_misplaced_entries_have_fix_sha_in_oppna_section(
    state: dict[str, list[BugEntry]],
) -> None:
    """`misplaced` exists specifically to flag posts that landed in a
    commit but were never moved to "Stängda". They must carry a Fix
    SHA; otherwise they would belong in `active` or `unknown`.
    """
    for entry in state["misplaced"]:
        assert entry.fix_sha is not None
        assert entry.fix_open is False


@pytest.mark.tooling
def test_no_bug_id_appears_in_both_oppna_and_stangda(
    state: dict[str, list[BugEntry]],
) -> None:
    """A duplicate B-ID would mean the same bug is tracked twice and
    the misplaced-vs-closed distinction breaks down. Hard fail.
    """
    open_ids = {
        entry.id for entry in (*state["active"], *state["misplaced"], *state["unknown"])
    }
    closed_ids = {entry.id for entry in state["closed"]}
    overlap = open_ids & closed_ids
    assert not overlap, (
        f"B-IDs {sorted(overlap)} appear in both Öppna and Stängda; "
        "move the open entry to Stängda or delete the duplicate."
    )


def _split_open_closed_sections(text: str) -> tuple[str, str]:
    open_pos = text.find(OPEN_HEADING)
    closed_pos = text.find(CLOSED_HEADING)
    assert open_pos != -1, "Öppna-heading saknas i known-issues.md"
    assert closed_pos != -1, "Stängda-heading saknas i known-issues.md"
    assert closed_pos > open_pos, (
        "Stängda-heading måste komma efter Öppna-heading i known-issues.md"
    )
    return text[open_pos:closed_pos], text[closed_pos:]


@pytest.mark.tooling
def test_parser_does_not_silently_drop_open_entries(
    state: dict[str, list[BugEntry]],
) -> None:
    """Fail-open guard: every `- **` bullet in the Öppna section must
    be represented by exactly one parsed entry in active/misplaced/unknown.
    """
    text = KNOWN_ISSUES.read_text(encoding="utf-8")
    open_section, _ = _split_open_closed_sections(text)
    open_bullet_count = len(re.findall(r"^- \*\*", open_section, flags=re.MULTILINE))
    parsed_open_count = len(state["active"]) + len(state["misplaced"]) + len(
        state["unknown"]
    )
    assert parsed_open_count == open_bullet_count, (
        f"Öppna-section has {open_bullet_count} bug bullets but parser returned "
        f"{parsed_open_count} entries (active+misplaced+unknown). "
        "A bug post was silently dropped."
    )


@pytest.mark.tooling
def test_parser_does_not_silently_drop_closed_entries(
    state: dict[str, list[BugEntry]],
) -> None:
    """Fail-open guard for Stängda: bullet count must equal parser count."""
    text = KNOWN_ISSUES.read_text(encoding="utf-8")
    _, closed_section = _split_open_closed_sections(text)
    closed_bullet_count = len(
        re.findall(r"^- \*\*", closed_section, flags=re.MULTILINE)
    )
    parsed_closed_count = len(state["closed"])
    assert parsed_closed_count == closed_bullet_count, (
        f"Stängda-section has {closed_bullet_count} bug bullets but parser "
        f"returned {parsed_closed_count} entries. A closed bug was silently "
        "dropped."
    )


@pytest.mark.tooling
def test_parser_fails_loud_on_synthetic_format_break() -> None:
    """A malformed bug bullet must raise SystemExit with a line number.

    This locks the runtime behavior review #29 requested: if someone
    introduces a typo in the bug entry header (e.g. missing backticks),
    the parser may not ignore it and continue. It must fail loudly with
    enough context to fix the broken line quickly.
    """
    broken_text = f"""{OPEN_HEADING}

- **B999 Hög** - malformed entry (missing backticks around ID).
  Fix: open. Test: open.

{CLOSED_HEADING}

- **`B61` Låg** (stängd 2026-05-18, synthetic) - valid closed entry.
  Fix: `abc1234`. Test: `tests/test_dummy.py::test_dummy`.
"""
    with pytest.raises(SystemExit, match=r"Öppna-sektionen.*rad \d+"):
        collect_bug_state(text=broken_text)


_SUMMARY_RE = re.compile(
    r"^> \*\*Aktivt bug-scope:\*\*\s*"
    r"(?P<active>\d+)\s+aktiva,\s*"
    r"(?P<misplaced>\d+)\s+misplaced.*?,\s*"
    r"(?P<unknown>\d+)\s+unknown,\s*"
    r"(?P<closed>\d+)\s+stängda",
    re.MULTILINE,
)


@pytest.mark.tooling
def test_known_issues_summary_line_matches_script(
    state: dict[str, list[BugEntry]],
) -> None:
    """Freshness check: when someone edits known-issues.md they must
    also bump the summary line so the file is self-consistent. Same
    pattern as test_docs_freshness.py:test_agents_md_ruff_baseline_*.
    """
    text = KNOWN_ISSUES.read_text(encoding="utf-8")
    match = _SUMMARY_RE.search(text)
    assert match is not None, (
        "docs/known-issues.md saknar (eller har felaktigt formatterad) "
        "sammanfattningsrad. Förväntad form (en rad nära toppen):\n"
        "  > **Aktivt bug-scope:** N aktiva, M misplaced "
        "(...), K unknown, L stängda. Kör `python scripts/list_open_bugs.py` "
        "för full lista. Format-disciplin: se "
        "governance/rules/bug-scope-discipline.md."
    )
    assert int(match.group("active")) == len(state["active"]), (
        f"Summary line says {match.group('active')} aktiva but the script "
        f"counts {len(state['active'])}. Update the summary line."
    )
    assert int(match.group("misplaced")) == len(state["misplaced"]), (
        f"Summary line says {match.group('misplaced')} misplaced but the "
        f"script counts {len(state['misplaced'])}."
    )
    assert int(match.group("unknown")) == len(state["unknown"]), (
        f"Summary line says {match.group('unknown')} unknown but the "
        f"script counts {len(state['unknown'])}."
    )
    assert int(match.group("closed")) == len(state["closed"]), (
        f"Summary line says {match.group('closed')} stängda but the script "
        f"counts {len(state['closed'])}."
    )


@pytest.mark.tooling
def test_rule_source_exists_and_is_alwaysapply() -> None:
    """The rule must exist in the governance source dir AND be marked
    `alwaysApply: true` so agents pick it up without explicit globbing.
    """
    assert RULE_SOURCE.exists(), (
        "governance/rules/bug-scope-discipline.md saknas. Skapa rule-källan; "
        "rules_sync.py speglar den till .cursor/rules/."
    )
    text = RULE_SOURCE.read_text(encoding="utf-8")
    assert text.startswith("---"), (
        "Rule-filen måste börja med en frontmatter-block med `description:` "
        "och `alwaysApply:`-fält."
    )
    assert "alwaysApply: true" in text
    assert "scripts/list_open_bugs.py" in text, (
        "Rule-filen måste namnge scripts/list_open_bugs.py så agenter "
        "vet exakt vilket kommando som ska köras."
    )


@pytest.mark.tooling
def test_rule_mirror_exists_and_matches_source() -> None:
    """`.cursor/rules/bug-scope-discipline.mdc` must exist and carry the
    auto-generated header that `rules_sync.py` writes. Mirrors the
    contract enforced by `python scripts/rules_sync.py --check`.
    """
    assert RULE_MIRROR.exists(), (
        ".cursor/rules/bug-scope-discipline.mdc saknas. "
        "Kör `python scripts/rules_sync.py` för att skapa spegeln."
    )
    mirror_text = RULE_MIRROR.read_text(encoding="utf-8")
    source_text = RULE_SOURCE.read_text(encoding="utf-8")
    assert "AUTO-GENERATED FROM governance/rules/bug-scope-discipline.md" in mirror_text
    assert source_text in mirror_text, (
        "Spegeln är out-of-sync mot källan. Kör `python scripts/rules_sync.py`."
    )
