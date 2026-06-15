"""Bidirectional lock between the backoffice view code and the governance
registry policy (``governance/policies/backoffice-views.v1.json``).

The same discipline the naming-dictionary + check_term_coverage already have,
applied to backoffice views: a view registered in the code but missing from the
policy is RED, and a policy entry with no matching view in the code is RED. This
stops the backoffice from drifting away from an honest, machine-verified map of
which views exist, where they live, and what they read.

The test imports ``backoffice.view_registry`` (side-effect free, no
``st.set_page_config``) rather than ``backoffice.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "governance" / "policies" / "backoffice-views.v1.json"

# Prefixes a readsFrom path is allowed to start with. Catches typos that would
# silently point a freshness badge at a non-existent surface. ``docs`` was added
# with ADR 0044 (the Identitet/SOUL view reads docs/openclaw-workspace/).
KNOWN_READS_FROM_PREFIXES = ("governance", "data", "packages", "scripts", "docs")


@pytest.fixture(scope="module")
def policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def policy_by_view(policy: dict) -> dict[str, dict]:
    return {entry["view"]: entry for entry in policy["views"]}


@pytest.mark.governance
def test_every_code_view_has_a_policy_entry(policy_by_view: dict[str, dict]):
    """Code -> policy: every (section, view) the sidebar exposes is registered."""
    from backoffice.view_registry import iter_views

    missing: list[str] = []
    wrong_section: list[str] = []
    for section, view in iter_views():
        entry = policy_by_view.get(view)
        if entry is None:
            missing.append(f"{section} / {view}")
            continue
        if entry["section"] != section:
            wrong_section.append(
                f"{view}: code section '{section}' != policy section '{entry['section']}'"
            )
    assert not missing, (
        "Backoffice views with no entry in backoffice-views.v1.json "
        "(register them there): " + "; ".join(missing)
    )
    assert not wrong_section, "Section mismatch: " + "; ".join(wrong_section)


@pytest.mark.governance
def test_every_policy_entry_maps_to_real_code(policy: dict):
    """Policy -> code: every entry points at a view that actually exists in the
    owning module, in the section the registry maps that module to."""
    from backoffice.view_registry import SECTION_MODULES

    module_by_name = {mod.__name__: mod for mod in SECTION_MODULES.values()}
    section_by_module_name = {
        mod.__name__: section for section, mod in SECTION_MODULES.items()
    }

    errors: list[str] = []
    for entry in policy["views"]:
        view = entry["view"]
        owner = entry["ownerSource"]
        section = entry["section"]
        module = module_by_name.get(owner)
        if module is None:
            errors.append(f"{view}: ownerSource '{owner}' is not a registered view module")
            continue
        if view not in module.VIEWS:
            errors.append(f"{view}: not present in {owner}.VIEWS")
        if section_by_module_name.get(owner) != section:
            errors.append(
                f"{view}: section '{section}' does not match the section "
                f"'{section_by_module_name.get(owner)}' that owns {owner}"
            )
    assert not errors, "Stale/incorrect policy entries: " + "; ".join(errors)


@pytest.mark.governance
def test_policy_sections_match_registry_sections(policy: dict):
    """The policy's declared section list must equal the code's section labels."""
    from backoffice.view_registry import SECTIONS

    assert list(policy["sections"]) == list(SECTIONS.keys()), (
        "backoffice-views.v1.json:sections must match backoffice.view_registry.SECTIONS "
        f"order/labels. Policy: {policy['sections']}, code: {list(SECTIONS.keys())}"
    )
    for entry in policy["views"]:
        assert entry["section"] in policy["sections"], (
            f"{entry['view']}: section '{entry['section']}' is not in the declared sections list"
        )


@pytest.mark.governance
def test_no_duplicate_view_entries(policy: dict):
    views = [entry["view"] for entry in policy["views"]]
    duplicates = sorted({v for v in views if views.count(v) > 1})
    assert not duplicates, f"Duplicate view entries in policy: {duplicates}"


@pytest.mark.governance
def test_reads_from_paths_use_known_prefixes(policy: dict):
    """A readsFrom path must point inside a known repo surface (typo guard)."""
    bad: list[str] = []
    for entry in policy["views"]:
        for source in entry["readsFrom"]:
            top = source.split("/", 1)[0]
            if top not in KNOWN_READS_FROM_PREFIXES:
                bad.append(f"{entry['view']}: '{source}'")
    assert not bad, (
        "readsFrom paths must start with one of "
        f"{KNOWN_READS_FROM_PREFIXES}: " + "; ".join(bad)
    )
