"""Freshness guards for narrative documentation.

These tests catch the class of drift where prose claims something about
the codebase that is no longer true. The post-Sprint-2B audit round 2
(2026-05-08) found two such drifts:

- ``AGENTS.md`` said "4 ruff findings remain" while ``ruff check``
  actually reported 0.
- ``packages/generation/orchestration/dossiers/README.md`` said "Inga
  Dossiers är implementerade än" while ``soft/interactive-game-loop/``
  existed on disk.

Each test parses a specific claim from a specific document and asserts
it against reality. When the prose is reformatted, the test author updates
the parsing pattern - that is the explicit cost of the guard. The benefit
is that drift between docs and code is now a CI failure instead of an
audit finding three sprints later.

Closes B25 (AGENTS.md ruff drift), B26 (dossier README implementation
count drift), and B27 (substring false-positive in dossier id presence
check) per docs/known-issues.md.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"


def _list_dossiers_on_disk() -> list[str]:
    """Return all dossierIds that have a manifest.json on disk.

    Walks ``packages/generation/orchestration/dossiers/<class>/<dossierId>/``
    and yields the directory names where ``manifest.json`` exists.
    """
    found: list[str] = []
    for klass in ("soft", "hard"):
        klass_dir = DOSSIERS_DIR / klass
        if not klass_dir.exists():
            continue
        for child in sorted(klass_dir.iterdir()):
            if child.is_dir() and (child / "manifest.json").exists():
                found.append(child.name)
    return found


def _id_appears_as_token(dossier_id: str, text: str) -> bool:
    """Return True if ``dossier_id`` appears as a whole id-token in ``text``.

    Plain substring matching (``id in text``) gave a false positive when
    one dossier id was a substring of another - e.g. a hypothetical
    ``game`` Dossier would incorrectly count as "mentioned in README"
    just because the README mentioned ``interactive-game-loop``. This
    helper requires the id to be bordered on BOTH sides by characters
    that are NOT in ``[\\w-]`` (alphanumerics, underscore, or hyphen).

    That boundary lets the id match inside backticks, square brackets,
    parentheses, slashes (e.g. ``soft/interactive-game-loop/``), spaces,
    commas, or end-of-string - but it correctly REJECTS the id when it
    sits inside another hyphenated token. Closes B27.
    """
    pattern = r"(?<![\w-])" + re.escape(dossier_id) + r"(?![\w-])"
    return re.search(pattern, text) is not None


@pytest.mark.tooling
def test_agents_md_ruff_baseline_claim_matches_reality():
    """The Gotchas section in AGENTS.md states the current ruff baseline
    finding count. That number must match what ``python -m ruff check .``
    actually returns. If a cleanup commit changes the count, AGENTS.md
    must be updated in the same commit.
    """
    agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    match = re.search(
        r"baseline\s+is\s+\*\*(\d+)\s+findings\*\*",
        agents_md,
        re.IGNORECASE,
    )
    assert match is not None, (
        "AGENTS.md must contain a 'baseline is bold-N-findings' statement "
        "in the Gotchas section that this test can parse (where bold-N "
        "is the markdown bold form around an integer). If you reformatted "
        "the ruff section, update the regex above to match the new shape."
    )
    claimed = int(match.group(1))

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        actual = 0
    else:
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        m = re.search(r"Found\s+(\d+)\s+error", combined)
        actual = int(m.group(1)) if m else -1

    assert actual >= 0, (
        f"Could not parse ruff output to determine finding count. "
        f"Stdout:\n{result.stdout}\nStderr:\n{result.stderr}"
    )
    assert claimed == actual, (
        f"AGENTS.md claims ruff baseline is {claimed} findings but "
        f"`python -m ruff check .` reports {actual}. Update AGENTS.md "
        f"to match reality (or fix the new findings before they ship)."
    )


@pytest.mark.tooling
def test_dossier_readme_implementation_status_matches_disk():
    """The Status section in dossiers/README.md tells operators which
    Dossiers are actually implemented today. That claim must match the
    set of ``<class>/<dossierId>/manifest.json`` files on disk.

    If a new Dossier is added without updating README, this test fails.
    If the only Dossier is removed without updating README, this test
    also fails.
    """
    readme = (DOSSIERS_DIR / "README.md").read_text(encoding="utf-8")
    readme_lower = readme.lower()
    actual_dossiers = _list_dossiers_on_disk()
    actual_count = len(actual_dossiers)

    falsy_phrases_when_some_exist = [
        "inga dossiers är implementerade",
        "inga dossiers implementerade",
        "no dossiers are implemented",
        "no dossiers implemented",
    ]

    if actual_count == 0:
        truthy_present = any(
            phrase in readme_lower for phrase in falsy_phrases_when_some_exist
        )
        assert truthy_present, (
            "Disk has 0 implemented Dossiers but dossiers/README.md does "
            "not contain a sentence acknowledging that. Add the canonical "
            "phrase 'Inga Dossiers är implementerade än' (or English "
            "equivalent) so operators are not misled."
        )
        return

    for phrase in falsy_phrases_when_some_exist:
        assert phrase not in readme_lower, (
            f"Disk has {actual_count} implemented Dossier(s) "
            f"({actual_dossiers}) but dossiers/README.md still claims "
            f"'{phrase}'. Update the Status section to reflect the actual "
            f"implementation count."
        )

    for dossier_id in actual_dossiers:
        assert _id_appears_as_token(dossier_id, readme), (
            f"Dossier '{dossier_id}' exists on disk under "
            f"packages/generation/orchestration/dossiers/ but is not "
            f"mentioned by id in dossiers/README.md. Add it to the Status "
            f"section so operators can find it. (Substring matches inside "
            f"another hyphenated token do NOT count - see B27.)"
        )


@pytest.mark.tooling
def test_id_appears_as_token_distinguishes_overlapping_dossier_ids():
    """B27 regression: ``dossier_id in text`` substring matching gave a
    false positive for overlapping ids. A hypothetical ``game`` Dossier
    on disk would have been considered "mentioned in README" just because
    the README mentioned ``interactive-game-loop``. The id-token helper
    must treat hyphens as part of the id, not as token-separators.

    If a future refactor reverts to plain substring matching, this test
    fails because ``game`` would suddenly be reported as "present" inside
    ``interactive-game-loop``.
    """
    readme_like = (
        "See [interactive-game-loop](soft/interactive-game-loop/) for the "
        "playable mini-game contract. Backtick form: `interactive-game-loop`. "
        "Comma at end: interactive-game-loop, ok."
    )

    assert _id_appears_as_token("interactive-game-loop", readme_like) is True, (
        "The full id must match - link text, path, backtick and comma "
        "boundaries are all valid token boundaries."
    )

    assert _id_appears_as_token("game", readme_like) is False, (
        "Substring 'game' must NOT match inside 'interactive-game-loop'. "
        "If this assertion fails, the dossier_id presence check has been "
        "reverted to plain substring matching and B27 has reopened."
    )
    assert _id_appears_as_token("game-loop", readme_like) is False, (
        "Substring 'game-loop' must NOT match inside 'interactive-game-loop'."
    )
    assert _id_appears_as_token("interactive", readme_like) is False, (
        "Substring 'interactive' must NOT match inside 'interactive-game-loop'."
    )
    assert _id_appears_as_token("loop", readme_like) is False, (
        "Substring 'loop' must NOT match inside 'interactive-game-loop'."
    )
    assert _id_appears_as_token("interactive-game", readme_like) is False, (
        "Substring 'interactive-game' must NOT match inside "
        "'interactive-game-loop'."
    )

    bare_id = "Status: pacman-game is the only implementation."
    assert _id_appears_as_token("pacman-game", bare_id) is True
    assert _id_appears_as_token("pacman", bare_id) is False
    assert _id_appears_as_token("game", bare_id) is False
