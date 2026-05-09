"""Consistency guard between SCAFFOLD_TO_STARTER and data/starters/README.md.

``packages.generation.planning.SCAFFOLD_TO_STARTER`` is the runtime
mapping the planner uses to decide which Starter a chosen Scaffold runs
on. It is a hand-maintained Python dict today (see ADR 0014 and the
known commerce-base hold described in docs/known-issues.md). The
canonical operator-facing source is the table + machine-readable block
in ``data/starters/README.md``.

Without a guard, the two can drift in either direction:

- A future commit adds ``saas-product -> saas-base`` to the dict but
  forgets to update the README, so operators read stale routing.
- A future commit updates the README block but forgets the dict, so
  the planner silently picks the wrong Starter.

These tests close both gaps:

1. Every entry in ``SCAFFOLD_TO_STARTER`` must match the canonical
   mapping line by line. Mismatched starter IDs fail loudly.
2. Every Scaffold ID in ``primaryScaffoldRegistry`` must appear in the
   canonical mapping. Silently dropping a Scaffold is a known-issues-
   class regression (the same shape as the bug tracked under the
   commerce-base hold).
3. Every Starter ID referenced in the canonical mapping must exist on
   disk under ``data/starters/<id>/`` with a ``README.md``.
4. The known commerce-base hold (ecommerce-lite -> marketing-base
   instead of commerce-base) must be marked with the literal token
   B20 on its mapping line so reviewers can distinguish the
   intentional temporary routing from a regression. The marker token
   itself is documented in docs/known-issues.md as the bug ID.

Closes the test gap captured in the Starter/Dossier Hygiene 1A audit
(scope 3).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STARTERS_README_PATH = REPO_ROOT / "data" / "starters" / "README.md"
STARTERS_DIR = REPO_ROOT / "data" / "starters"
SCAFFOLD_CONTRACT_PATH = (
    REPO_ROOT / "governance" / "policies" / "scaffold-contract.v1.json"
)

_BLOCK_RE = re.compile(
    r"<!--\s*scaffold-starter-mapping:start\s*-->\s*\n"
    r"(?P<body>.*?)"
    r"\n\s*<!--\s*scaffold-starter-mapping:end\s*-->",
    re.DOTALL,
)
_LINE_RE = re.compile(
    r"^\s*-\s*(?P<scaffold>[A-Za-z0-9][\w-]*)\s*:\s*"
    r"(?P<starter>[A-Za-z0-9][\w-]*)\s*(?P<note>\(.*?\))?\s*$"
)


def _starters_readme() -> str:
    return STARTERS_README_PATH.read_text(encoding="utf-8")


def _extract_block(readme: str) -> str:
    match = _BLOCK_RE.search(readme)
    if match is None:
        raise AssertionError(
            "Canonical scaffold-starter-mapping block not found in "
            "data/starters/README.md. The block must be wrapped in "
            "<!-- scaffold-starter-mapping:start --> and "
            "<!-- scaffold-starter-mapping:end --> HTML comments so "
            "this guard can parse it."
        )
    return match.group("body")


def parse_canonical_mapping(readme: str) -> dict[str, tuple[str, str | None]]:
    """Return a {scaffoldId: (starterId, optional-note)} mapping.

    The note carries any parenthetical annotation on the line (e.g.
    ``"(B20: temporary; ...)"``). It is None when the line had no
    annotation. The note is preserved so callers can pin specific
    annotations - notably B20 - without a separate parse.
    """
    body = _extract_block(readme)
    mapping: dict[str, tuple[str, str | None]] = {}
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("<!--"):
            continue
        match = _LINE_RE.match(line)
        if match is None:
            raise AssertionError(
                f"Cannot parse line in scaffold-starter-mapping block: "
                f"{raw_line!r}. Expected '- <scaffoldId>: <starterId>' "
                f"with an optional '(note)' suffix."
            )
        scaffold = match.group("scaffold")
        if scaffold in mapping:
            raise AssertionError(
                f"scaffold-starter-mapping lists scaffold {scaffold!r} "
                f"more than once. Each scaffold may map to exactly one "
                f"starter. Pick one and remove the duplicate."
            )
        mapping[scaffold] = (match.group("starter"), match.group("note"))
    if not mapping:
        raise AssertionError(
            "scaffold-starter-mapping block parsed but contains no "
            "mapping lines."
        )
    return mapping


def _scaffold_registry_ids() -> set[str]:
    contract = json.loads(SCAFFOLD_CONTRACT_PATH.read_text(encoding="utf-8"))
    return {
        entry["id"]
        for entry in contract.get("primaryScaffoldRegistry", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


@pytest.mark.governance
def test_runtime_dict_matches_canonical_mapping() -> None:
    """SCAFFOLD_TO_STARTER must be a subset of and consistent with the
    canonical mapping in data/starters/README.md.
    """
    from packages.generation.planning import SCAFFOLD_TO_STARTER

    canonical = parse_canonical_mapping(_starters_readme())
    drift: list[str] = []
    for scaffold_id, starter_id in SCAFFOLD_TO_STARTER.items():
        if scaffold_id not in canonical:
            drift.append(
                f"runtime maps {scaffold_id!r} -> {starter_id!r} but "
                f"the canonical mapping does not list this scaffold"
            )
            continue
        canonical_starter = canonical[scaffold_id][0]
        if canonical_starter != starter_id:
            drift.append(
                f"{scaffold_id!r}: runtime {starter_id!r} vs canonical "
                f"{canonical_starter!r}"
            )
    assert not drift, (
        "SCAFFOLD_TO_STARTER (in packages/generation/planning/plan.py) "
        "drifted from the canonical scaffold-starter-mapping block in "
        "data/starters/README.md:\n  " + "\n  ".join(drift)
    )


@pytest.mark.governance
def test_canonical_mapping_covers_every_registered_scaffold() -> None:
    """Every Scaffold ID in primaryScaffoldRegistry must appear in the
    canonical mapping. Silently dropping a Scaffold is a B20-class
    regression.
    """
    canonical = parse_canonical_mapping(_starters_readme())
    registry = _scaffold_registry_ids()
    missing = sorted(registry - set(canonical))
    assert not missing, (
        f"primaryScaffoldRegistry lists scaffolds with no entry in "
        f"data/starters/README.md scaffold-starter-mapping block: "
        f"{missing}. Either add a mapping line or drop the scaffold "
        f"from the registry."
    )


@pytest.mark.governance
def test_canonical_mapping_starters_exist_on_disk() -> None:
    """Every Starter ID referenced in the canonical mapping must exist
    on disk under data/starters/<id>/ with a README.md.
    """
    canonical = parse_canonical_mapping(_starters_readme())
    drift: list[str] = []
    for scaffold_id, (starter_id, _note) in canonical.items():
        starter_dir = STARTERS_DIR / starter_id
        if not starter_dir.is_dir():
            drift.append(
                f"{scaffold_id} -> {starter_id}: data/starters/"
                f"{starter_id}/ does not exist"
            )
            continue
        if not (starter_dir / "README.md").exists():
            drift.append(
                f"{scaffold_id} -> {starter_id}: data/starters/"
                f"{starter_id}/README.md does not exist"
            )
    assert not drift, "\n  ".join(drift)


@pytest.mark.governance
def test_b20_temporary_mapping_is_explicit() -> None:
    """The known B20 drift (ecommerce-lite -> marketing-base, instead
    of the canonical commerce-base) must be flagged on its mapping
    line. Without the marker reviewers cannot tell intentional
    temporary routing from a real regression.

    The marker is the literal token B20 anywhere in the line's
    parenthetical note. Unmarked, the line would still parse and the
    other tests would still pass - that is exactly the silent drift
    this guard prevents.
    """
    canonical = parse_canonical_mapping(_starters_readme())
    if "ecommerce-lite" not in canonical:
        pytest.skip("ecommerce-lite missing from canonical mapping")
    starter, note = canonical["ecommerce-lite"]
    if starter == "commerce-base":
        return
    assert note and "B20" in note, (
        f"ecommerce-lite is mapped to {starter!r} (not the canonical "
        f"commerce-base) but the mapping line carries no B20 marker. "
        f"Add '(B20: ...)' to the line so the temporary routing is "
        f"explicit, or close B20 by switching to commerce-base."
    )


@pytest.mark.governance
def test_canonical_mapping_starter_set_is_a_subset_of_known_starters() -> None:
    """Every Starter the canonical mapping mentions must be one of the
    five Starters declared in the Starter Registry table at the top of
    data/starters/README.md (marketing-base, saas-base, commerce-base,
    portfolio-base, docs-base). A new Starter ID has to be added to
    the table first, then to the mapping.
    """
    canonical = parse_canonical_mapping(_starters_readme())
    registered_starters = {
        "marketing-base",
        "saas-base",
        "commerce-base",
        "portfolio-base",
        "docs-base",
    }
    used_starters = {starter for starter, _ in canonical.values()}
    unknown = used_starters - registered_starters
    assert not unknown, (
        f"scaffold-starter-mapping references Starter IDs that are "
        f"not in the Starter Registry table: {sorted(unknown)}. Add "
        f"the Starter to the table and create data/starters/<id>/ "
        f"first, then update the mapping."
    )


@pytest.mark.governance
def test_parser_rejects_unknown_line_shape() -> None:
    """Meta test: the parser must fail loudly on lines it cannot
    interpret, so a typo in the mapping block surfaces as a test
    failure instead of silently dropping a scaffold.
    """
    bad_readme = (
        "<!-- scaffold-starter-mapping:start -->\n"
        "- local-service-business: marketing-base\n"
        "* not-a-dash: line\n"
        "<!-- scaffold-starter-mapping:end -->\n"
    )
    with pytest.raises(AssertionError, match="Cannot parse line"):
        parse_canonical_mapping(bad_readme)


@pytest.mark.governance
def test_parser_rejects_duplicate_scaffold() -> None:
    """A scaffold may map to exactly one starter. The parser must
    refuse a block that lists the same scaffold twice rather than
    silently picking one.
    """
    bad_readme = (
        "<!-- scaffold-starter-mapping:start -->\n"
        "- duplicate: marketing-base\n"
        "- duplicate: saas-base\n"
        "<!-- scaffold-starter-mapping:end -->\n"
    )
    with pytest.raises(AssertionError, match="more than once"):
        parse_canonical_mapping(bad_readme)


@pytest.mark.governance
def test_parser_requires_block() -> None:
    """The README MUST contain the delimited block. A README without
    the block is a documentation regression - someone removed the
    machine-readable mapping.
    """
    with pytest.raises(AssertionError, match="not found"):
        parse_canonical_mapping("just some markdown without the block")
