from __future__ import annotations

from pathlib import Path

import pytest

from scripts.steward_auto_bump import (
    PullRequestSummary,
    bump_documents,
    is_trivial_docs_only_diff,
    validate_sha,
)

CURRENT_FOCUS = """# Aktuellt fokus

Introtext.

Last verified state: `abc1234` (2026-05-24 UTC, gammal checkpoint).
Gammal current-focus-rad som ska arkiveras.

Sedan abc1234 har andra detaljer redan funnits kvar.
"""


HANDOFF = """# Handoff - Sajtbyggaren

**Datum:** 2026-05-24 UTC. Verifierad `main` är `abc1234`.

Gammal handoff-rad som ska arkiveras.

**MCP-server-status:** Oförändrad.

## Standard loop

Detaljer.
"""


def write_docs(tmp_path: Path) -> tuple[Path, Path]:
    current_focus = tmp_path / "current-focus.md"
    handoff = tmp_path / "handoff.md"
    current_focus.write_text(CURRENT_FOCUS, encoding="utf-8")
    handoff.write_text(HANDOFF, encoding="utf-8")
    return current_focus, handoff


def bump_once(current_focus: Path, handoff: Path, sha: str = "def5678"):
    return bump_documents(
        current_focus_path=current_focus,
        handoff_path=handoff,
        merge_sha=sha,
        pr_number=42,
        pr_title="Close steward drift",
        pr_summaries=[
            PullRequestSummary(number=41, title="Prepare steward docs"),
            PullRequestSummary(number=42, title="Close steward drift"),
        ],
        date_text="2026-05-25",
    )


def test_bump_is_idempotent_for_same_sha(tmp_path: Path):
    current_focus, handoff = write_docs(tmp_path)

    first = bump_once(current_focus, handoff)
    second = bump_once(current_focus, handoff)

    assert first.changed is True
    assert second.changed is False
    assert second.reason == "already verified"
    assert current_focus.read_text(encoding="utf-8").count("## Föregående checkpoint") == 1


def test_trivial_detector_skips_small_docs_only_diff():
    assert is_trivial_docs_only_diff(
        ["docs/reports/small-note.md", "docs/architecture/context.md"],
        additions=21,
        deletions=12,
    )


def test_trivial_detector_bumps_for_code_or_large_or_protected_docs_diff():
    assert not is_trivial_docs_only_diff(["scripts/build_site.py"], additions=3, deletions=2)
    assert not is_trivial_docs_only_diff(["docs/reports/large.md"], additions=49, deletions=1)
    assert not is_trivial_docs_only_diff(["docs/current-focus.md"], additions=1, deletions=1)
    assert not is_trivial_docs_only_diff(["docs/handoff.md"], additions=1, deletions=1)
    assert not is_trivial_docs_only_diff(["docs/workboard.json"], additions=1, deletions=1)
    assert not is_trivial_docs_only_diff(["docs/known-issues.md"], additions=1, deletions=1)


def test_bump_archives_previous_checkpoint_blocks(tmp_path: Path):
    current_focus, handoff = write_docs(tmp_path)

    result = bump_once(current_focus, handoff)

    current_text = current_focus.read_text(encoding="utf-8")
    handoff_text = handoff.read_text(encoding="utf-8")
    assert result.changed is True
    assert "Last verified state: `def5678`" in current_text
    assert "PR #41 — Prepare steward docs" in current_text
    assert "PR #42 — Close steward drift" in current_text
    assert "## Föregående checkpoint" in current_text
    assert "Gammal current-focus-rad som ska arkiveras." in current_text
    assert "**Datum:** 2026-05-25 UTC, steward-auto efter PR #42" in handoff_text
    assert "Verifierad `main` är `def5678`" in handoff_text
    assert "## Föregående checkpoint" in handoff_text
    assert "Gammal handoff-rad som ska arkiveras." in handoff_text


def test_sha_validation_rejects_invalid_input():
    with pytest.raises(ValueError, match="hexadecimal SHA"):
        validate_sha("not-a-sha")
