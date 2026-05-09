"""Cleanliness guards for compatible-dossiers.json across all scaffolds.

Each scaffold under ``packages/generation/orchestration/scaffolds/<id>/``
ships a ``compatible-dossiers.json`` that lists Dossier IDs the scaffold
allows or blocks. The file accepts four shapes per
``scaffold-contract.v1.json:compatibleDossiersFields``:

- ``required`` (always activate)
- ``recommended`` (likely activate)
- ``conditional`` (activate when a stated condition holds)
- ``disallowedByDefault`` (defensive block list, even for Dossiers not
  yet imported)

B18 (closed 2026-05-08) found a vocabulary leak where section names
(``service-list``, ``reviews``, ``trust-proof``...) had been listed as
Dossier IDs. The file-level ``_comment`` field added then explains the
distinction, but no test guarded against re-introduction of the leak.

These tests close that gap. The required/recommended/conditional fields
must resolve to a real Dossier - either an on-disk
``<class>/<dossierId>/manifest.json`` or a Dossier ID listed in
``capability-map.v1.json:capabilities[].dossiers``. The
``disallowedByDefault`` field may carry aspirational IDs (block a future
Dossier before it is imported) but it must never carry a section name,
a scaffold ID, or a capability slug - those are different categories
and would silently mis-classify the leakage as policy.

Closes the test gap captured in the Starter/Dossier Hygiene 1A audit
(scope 2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
CAPABILITY_MAP_PATH = (
    REPO_ROOT / "governance" / "policies" / "capability-map.v1.json"
)
SCAFFOLD_CONTRACT_PATH = (
    REPO_ROOT / "governance" / "policies" / "scaffold-contract.v1.json"
)


def _scaffold_dirs() -> list[Path]:
    if not SCAFFOLDS_DIR.exists():
        return []
    return sorted(p for p in SCAFFOLDS_DIR.iterdir() if p.is_dir())


def _load_compatible_dossiers(scaffold_dir: Path) -> dict:
    return json.loads(
        (scaffold_dir / "compatible-dossiers.json").read_text(encoding="utf-8")
    )


def _ids_in_compatible(compat: dict) -> dict[str, list[str]]:
    """Group every ID-string the file mentions by which field it came from.

    Keys map to the field name so failure messages can point at the
    exact list that needs cleaning.
    """
    grouped: dict[str, list[str]] = {
        "required": [],
        "recommended": [],
        "conditional": [],
        "disallowedByDefault": [],
    }
    for key in ("required", "recommended", "disallowedByDefault"):
        for value in compat.get(key, []) or []:
            if isinstance(value, str) and value.strip():
                grouped[key].append(value)
    for entry in compat.get("conditional", []) or []:
        if isinstance(entry, dict):
            value = entry.get("id")
            if isinstance(value, str) and value.strip():
                grouped["conditional"].append(value)
    return grouped


def _section_ids_for_scaffold(scaffold_dir: Path) -> set[str]:
    sections_path = scaffold_dir / "sections.json"
    if not sections_path.exists():
        return set()
    sections = json.loads(sections_path.read_text(encoding="utf-8"))
    found: set[str] = set()
    if isinstance(sections, dict):
        for page, page_spec in sections.items():
            if not isinstance(page_spec, dict):
                continue
            for key in ("requiredSections", "optionalSections"):
                for value in page_spec.get(key, []) or []:
                    if isinstance(value, str) and value.strip():
                        found.add(value)
            # The page key itself is a section-of-the-route, not a Dossier.
            # B18 specifically called out that sections.json's home/services/
            # about/contact pages were once mistaken for Dossiers.
            if isinstance(page, str):
                found.add(page)
    return found


def _scaffold_registry_ids() -> set[str]:
    contract = json.loads(SCAFFOLD_CONTRACT_PATH.read_text(encoding="utf-8"))
    return {
        entry["id"]
        for entry in contract.get("primaryScaffoldRegistry", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def _capability_slugs() -> set[str]:
    cap_map = json.loads(CAPABILITY_MAP_PATH.read_text(encoding="utf-8"))
    capabilities = cap_map.get("capabilities", {})
    return set(capabilities.keys()) if isinstance(capabilities, dict) else set()


def _on_disk_dossier_ids() -> set[str]:
    found: set[str] = set()
    if not DOSSIERS_DIR.exists():
        return found
    for klass in ("soft", "hard"):
        klass_dir = DOSSIERS_DIR / klass
        if not klass_dir.exists():
            continue
        for child in klass_dir.iterdir():
            if child.is_dir() and (child / "manifest.json").exists():
                found.add(child.name)
    return found


def _capability_map_dossier_ids() -> set[str]:
    cap_map = json.loads(CAPABILITY_MAP_PATH.read_text(encoding="utf-8"))
    found: set[str] = set()
    for entry in cap_map.get("capabilities", {}).values():
        if not isinstance(entry, dict):
            continue
        for value in entry.get("dossiers", []) or []:
            if isinstance(value, str) and value.strip():
                found.add(value)
    return found


@pytest.mark.governance
@pytest.mark.parametrize(
    "scaffold_dir", _scaffold_dirs(), ids=lambda p: p.name
)
def test_compatible_dossiers_have_no_section_ids(scaffold_dir: Path) -> None:
    """B18 regression: scaffold sections must not appear as Dossier IDs.

    Sections like ``hero``, ``service-list``, ``reviews``, ``trust-proof``
    or page keys like ``home``/``contact`` belong in ``sections.json``,
    not in ``compatible-dossiers.json``. Mixing them is the exact
    vocabulary leak ADR 0012 forbids.
    """
    compat = _load_compatible_dossiers(scaffold_dir)
    section_ids = _section_ids_for_scaffold(scaffold_dir)
    if not section_ids:
        pytest.skip("scaffold has no sections.json")
    grouped = _ids_in_compatible(compat)
    leaks: list[str] = []
    for field, ids in grouped.items():
        for value in ids:
            if value in section_ids:
                leaks.append(f"{field}: '{value}'")
    assert not leaks, (
        f"compatible-dossiers.json for scaffold '{scaffold_dir.name}' "
        f"lists section names as Dossier IDs (B18 leak): {leaks}. "
        f"Sections live in sections.json. Move the entry there or "
        f"remove it - sections are not Dossiers."
    )


@pytest.mark.governance
@pytest.mark.parametrize(
    "scaffold_dir", _scaffold_dirs(), ids=lambda p: p.name
)
def test_compatible_dossiers_have_no_scaffold_ids(scaffold_dir: Path) -> None:
    """A scaffold ID is not a Dossier ID. Dossiers attach to scaffolds;
    scaffolds do not list other scaffolds as compatible Dossiers.
    """
    compat = _load_compatible_dossiers(scaffold_dir)
    scaffold_ids = _scaffold_registry_ids()
    if not scaffold_ids:
        pytest.skip("scaffold registry empty")
    grouped = _ids_in_compatible(compat)
    leaks: list[str] = []
    for field, ids in grouped.items():
        for value in ids:
            if value in scaffold_ids:
                leaks.append(f"{field}: '{value}'")
    assert not leaks, (
        f"compatible-dossiers.json for scaffold '{scaffold_dir.name}' "
        f"lists scaffold IDs (from primaryScaffoldRegistry): {leaks}. "
        f"Use the Dossier ID instead, or remove the entry."
    )


@pytest.mark.governance
@pytest.mark.parametrize(
    "scaffold_dir", _scaffold_dirs(), ids=lambda p: p.name
)
def test_compatible_dossiers_have_no_capability_slugs(scaffold_dir: Path) -> None:
    """A capability slug names what a Dossier offers (``payments``,
    ``interactive-game``); a Dossier ID names a specific implementation
    (``stripe-checkout``, ``interactive-game-loop``). compatible-dossiers
    must reference IDs, not slugs - planning needs the implementation,
    not the abstract capability.
    """
    compat = _load_compatible_dossiers(scaffold_dir)
    slugs = _capability_slugs()
    if not slugs:
        pytest.skip("capability-map.v1 has no capabilities")
    grouped = _ids_in_compatible(compat)
    leaks: list[str] = []
    for field, ids in grouped.items():
        for value in ids:
            if value in slugs:
                leaks.append(f"{field}: '{value}'")
    assert not leaks, (
        f"compatible-dossiers.json for scaffold '{scaffold_dir.name}' "
        f"lists capability slugs (from capability-map.v1.capabilities): "
        f"{leaks}. Use the Dossier ID that implements the capability, "
        f"not the slug itself."
    )


@pytest.mark.governance
@pytest.mark.parametrize(
    "scaffold_dir", _scaffold_dirs(), ids=lambda p: p.name
)
def test_compatible_dossiers_active_lists_resolve_to_real_dossiers(
    scaffold_dir: Path,
) -> None:
    """required/recommended/conditional must resolve to Dossier IDs
    that either exist on disk or are listed in capability-map.v1 as
    candidates. disallowedByDefault is excluded - it may name future
    Dossier IDs that are not imported yet (defensive block).
    """
    compat = _load_compatible_dossiers(scaffold_dir)
    real_ids = _on_disk_dossier_ids() | _capability_map_dossier_ids()
    grouped = _ids_in_compatible(compat)
    unknown: list[str] = []
    for field in ("required", "recommended", "conditional"):
        for value in grouped[field]:
            if value not in real_ids:
                unknown.append(f"{field}: '{value}'")
    assert not unknown, (
        f"compatible-dossiers.json for scaffold '{scaffold_dir.name}' "
        f"references Dossier IDs that do not exist on disk and are "
        f"not registered in capability-map.v1: {unknown}. Either add "
        f"the Dossier under packages/generation/orchestration/dossiers/"
        f"{{soft,hard}}/, register it as a candidate in capability-map, "
        f"or remove the entry."
    )


@pytest.mark.governance
def test_compatible_dossiers_helper_collects_all_four_fields() -> None:
    """Meta test: the helper must enumerate every shape the schema
    allows. If a future scaffold-contract.v1.json bump adds a new
    list shape (e.g. ``conditionalRequired``) the helper must learn
    it before the per-scaffold tests can be trusted.
    """
    sample = {
        "required": ["a"],
        "recommended": ["b", "c"],
        "conditional": [{"id": "d", "when": "x"}],
        "disallowedByDefault": ["e"],
    }
    grouped = _ids_in_compatible(sample)
    assert grouped["required"] == ["a"]
    assert grouped["recommended"] == ["b", "c"]
    assert grouped["conditional"] == ["d"]
    assert grouped["disallowedByDefault"] == ["e"]


@pytest.mark.governance
def test_compatible_dossiers_helper_skips_malformed_entries() -> None:
    """Empty strings, non-string values and conditional entries without
    a usable id are dropped; they should never count as leaks.
    """
    sample = {
        "required": ["", None, 7, "valid"],
        "recommended": [],
        "conditional": [
            {"id": "", "when": "x"},
            {"id": None, "when": "y"},
            {"id": "real", "when": "z"},
            "string-not-dict",
        ],
        "disallowedByDefault": ["block"],
    }
    grouped = _ids_in_compatible(sample)
    assert grouped["required"] == ["valid"]
    assert grouped["conditional"] == ["real"]
    assert grouped["disallowedByDefault"] == ["block"]
