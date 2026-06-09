"""Guardrail that keeps the test suite from re-accumulating oversized files.

Oversized, mixed-responsibility test files are the suite's biggest
maintenance risk (a single 5k-line file is hard to read, review and split).
This guard enforces a soft cap on test-file size:

* New test files must stay under ``MAX_LINES``.
* A small ``KNOWN_OVERSIZED`` allowlist tracks the remaining legacy files
  that are still scheduled to be split/consolidated. The allowlist is kept
  honest by ``test_oversized_allowlist_is_current`` so that once a file is
  split below the cap it MUST be removed from the allowlist (it cannot be
  forgotten and silently keep its exemption).

To split a file: do the split, then delete its entry here.
"""

from __future__ import annotations

from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

MAX_LINES = 1200

# Legacy files still above the cap, tracked for split/consolidation.
# Direction (from the test-hygiene review): split test_prompt_to_project_input
# and test_builder_route_emission by target, parametrize the follow-up
# copy-directive matrix, and break up the discovery resolver suite.
KNOWN_OVERSIZED = {
    "test_prompt_to_project_input.py",
    "test_discovery_resolver.py",
    "test_followup_copy_directives.py",
    "test_builder_route_emission.py",
}


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _test_files() -> list[Path]:
    return sorted(TESTS_DIR.glob("test_*.py"))


def test_no_new_oversized_test_files() -> None:
    """No test file may exceed MAX_LINES unless it is on the allowlist."""
    offenders = {
        path.name: _line_count(path)
        for path in _test_files()
        if _line_count(path) > MAX_LINES and path.name not in KNOWN_OVERSIZED
    }
    assert not offenders, (
        "These test files exceed the "
        f"{MAX_LINES}-line cap and are not on the KNOWN_OVERSIZED allowlist: "
        f"{offenders}. Split them into topic-focused files (see "
        "tests/test_viewser_*.py for the pattern), or — only if unavoidable — "
        "add them to KNOWN_OVERSIZED with a tracking note."
    )


def test_oversized_allowlist_is_current() -> None:
    """Every allowlisted file must still exist and still exceed the cap.

    This forces the allowlist to shrink: once a legacy file is split below
    MAX_LINES, leaving it here makes this test fail until it is removed.
    """
    by_name = {path.name: path for path in _test_files()}

    missing = sorted(name for name in KNOWN_OVERSIZED if name not in by_name)
    assert not missing, (
        f"KNOWN_OVERSIZED lists files that no longer exist: {missing}. "
        "Remove them from the allowlist."
    )

    no_longer_oversized = sorted(
        name
        for name in KNOWN_OVERSIZED
        if _line_count(by_name[name]) <= MAX_LINES
    )
    assert not no_longer_oversized, (
        "These files are now within the "
        f"{MAX_LINES}-line cap and must be removed from KNOWN_OVERSIZED: "
        f"{no_longer_oversized}."
    )
