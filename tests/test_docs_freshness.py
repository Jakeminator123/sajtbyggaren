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

Closes B25 (AGENTS.md ruff drift) and B26 (dossier README implementation
count drift) per docs/known-issues.md.
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
        assert dossier_id in readme, (
            f"Dossier '{dossier_id}' exists on disk under "
            f"packages/generation/orchestration/dossiers/ but is not "
            f"mentioned by id in dossiers/README.md. Add it to the Status "
            f"section so operators can find it."
        )
