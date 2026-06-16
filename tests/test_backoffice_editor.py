"""Unit tests for the shared safe-save helper (backoffice/views/_editor.py).

The flow preview-diff -> validate -> atomic write -> verify -> rollback used to
live inline across model_roles / governance / identity. These tests pin the one
shared implementation: validation blocks the write, a failing post-write verify
rolls the file back to its previous bytes, and the happy path leaves exactly
what ``write`` wrote on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backoffice.io import atomic_write_text
from backoffice.views import _editor

pytestmark = pytest.mark.tooling


@pytest.mark.tooling
def test_validate_block_prevents_any_write(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    target.write_text("original", encoding="utf-8")
    wrote: list[str] = []

    result = _editor.commit_edit(
        target=target,
        validate=lambda: ["Fält A tomt.", "Fält B tomt."],
        write=lambda: wrote.append("x"),
        success_message="sparat",
    )

    assert not result.ok
    assert not result.wrote
    assert result.message == "Fält A tomt. Fält B tomt."
    assert wrote == [], "write must never run when validate red-flags"
    assert target.read_text(encoding="utf-8") == "original"


@pytest.mark.tooling
def test_happy_path_without_verify_persists(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    target.write_text("old", encoding="utf-8")

    result = _editor.commit_edit(
        target=target,
        write=lambda: atomic_write_text(target, "new"),
        success_message="sparat ok",
    )

    assert result.ok and result.wrote
    assert result.message == "sparat ok"
    assert target.read_text(encoding="utf-8") == "new"


@pytest.mark.tooling
def test_happy_path_with_passing_verify_persists(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    target.write_text("old", encoding="utf-8")

    result = _editor.commit_edit(
        target=target,
        write=lambda: atomic_write_text(target, "new"),
        verify=_editor.make_readback_verify(target, lambda _content: []),
        success_message="sparat ok",
    )

    assert result.ok and result.wrote
    assert target.read_text(encoding="utf-8") == "new"


@pytest.mark.tooling
def test_failing_verify_rolls_back_to_previous_bytes(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    target.write_text("ORIGINAL", encoding="utf-8")

    result = _editor.commit_edit(
        target=target,
        write=lambda: atomic_write_text(target, "BROKEN"),
        verify=_editor.make_readback_verify(target, lambda _content: ["trasig"]),
        success_message="sparat ok",
        rollback_message=lambda output: f"rollback genomfört. {output}",
    )

    assert not result.ok
    assert result.rolled_back
    assert "rollback" in result.message and "trasig" in result.message
    assert target.read_text(encoding="utf-8") == "ORIGINAL"


@pytest.mark.tooling
def test_write_oserror_reports_and_leaves_disk_untouched(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    target.write_text("original", encoding="utf-8")

    def _boom() -> None:
        raise OSError("disk full")

    result = _editor.commit_edit(
        target=target,
        write=_boom,
        success_message="sparat ok",
        write_error_message=lambda exc: f"misslyckades: {exc}. Inget har ändrats.",
    )

    assert not result.ok and not result.wrote
    assert "Inget har ändrats" in result.message
    assert target.read_text(encoding="utf-8") == "original"


@pytest.mark.tooling
def test_readback_verify_flags_unreadable_target(tmp_path: Path) -> None:
    missing = tmp_path / "gone.txt"
    verdict = _editor.make_readback_verify(missing, lambda _content: [])()
    assert not verdict.ok
    assert "läsa tillbaka" in verdict.output


@pytest.mark.tooling
def test_diff_lines_shows_change() -> None:
    lines = _editor.diff_lines("a\nb\n", "a\nc\n")
    body = "\n".join(lines)
    assert "-b" in body
    assert "+c" in body
