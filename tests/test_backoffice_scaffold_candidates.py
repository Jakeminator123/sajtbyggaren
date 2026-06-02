"""Boundary guard: Backoffice scaffold creation writes candidates to data/.

``repo-boundaries.v1.json`` says both ``backoffice.py`` and ``backoffice/``
``mustNotDo`` "skriva till packages/ eller apps/". The Scaffolds view used to
create the first file set directly under
``packages/generation/orchestration/scaffolds/<id>/`` (canonical), which
violated that boundary. The fix mirrors the existing Variant Candidates and
Dossier Candidates pattern: Backoffice writes a candidate skeleton under
``data/scaffold-candidates/<id>/`` and promotion to ``packages/`` happens via a
Builder-agent/PR.

The test reads the view source as text so it does not need to import Streamlit.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDING_BLOCKS = REPO_ROOT / "backoffice" / "views" / "building_blocks.py"
REPO_BOUNDARIES = REPO_ROOT / "governance" / "policies" / "repo-boundaries.v1.json"


def test_scaffold_candidates_dir_is_under_data() -> None:
    source = BUILDING_BLOCKS.read_text(encoding="utf-8")
    assert (
        'SCAFFOLD_CANDIDATES_DIR = REPO_ROOT / "data" / "scaffold-candidates"' in source
    ), (
        "Backoffice must declare a scaffold-candidates dir under data/, mirroring "
        "VARIANT_CANDIDATES_DIR and DOSSIER_CANDIDATES_DIR."
    )


def test_scaffold_create_writes_candidate_not_canonical_package() -> None:
    """The scaffold-create button must target ``SCAFFOLD_CANDIDATES_DIR`` (data/),
    never ``SCAFFOLDS_DIR`` (packages/). If this reverts, Backoffice would write
    canonical scaffold folders again and break repo-boundaries.v1.json.
    """
    source = BUILDING_BLOCKS.read_text(encoding="utf-8")
    assert "SCAFFOLD_CANDIDATES_DIR / pick" in source, (
        "view_scaffolds must create the skeleton under SCAFFOLD_CANDIDATES_DIR."
    )
    assert "SCAFFOLDS_DIR / pick" not in source, (
        "view_scaffolds must NOT mkdir/write into the canonical scaffolds package "
        "(packages/generation/orchestration/scaffolds/). Write a candidate to "
        "data/scaffold-candidates/ and let a Builder-agent/PR promote it."
    )


def test_repo_boundaries_still_forbids_backoffice_package_writes() -> None:
    """Pin the rule the code change honours so a future boundary relaxation is a
    deliberate, reviewed edit rather than silent drift.
    """
    boundaries = json.loads(REPO_BOUNDARIES.read_text(encoding="utf-8"))
    by_path = {o["path"]: o for o in boundaries["ownership"]}
    for path in ("backoffice.py", "backoffice/"):
        must_not_do = by_path[path]["mustNotDo"]
        assert any("packages/" in rule for rule in must_not_do), (
            f"repo-boundaries must keep forbidding {path} from writing to packages/."
        )
