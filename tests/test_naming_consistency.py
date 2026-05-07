"""Regression tests for naming and docs consistency (round 2).

Each test corresponds to a specific bug ID from the audits captured in
``docs/known-issues.md``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NAMING_PATH = REPO_ROOT / "governance" / "policies" / "naming-dictionary.v1.json"


def _naming() -> dict:
    return json.loads(NAMING_PATH.read_text(encoding="utf-8"))


def _term_ids() -> set[str]:
    return {t["id"] for t in _naming()["terms"]}


# ---------------------------------------------------------------------------
# N1 - glossary.md must list the four dossier-type terms
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_glossary_lists_four_dossier_types() -> None:
    """N1: docs/glossary.md must define Site/Feature/Integration/Data Dossier."""
    glossary = (REPO_ROOT / "docs" / "glossary.md").read_text(encoding="utf-8")
    for canonical in ["Site Dossier", "Feature Dossier", "Integration Dossier", "Data Dossier"]:
        assert canonical in glossary, f"docs/glossary.md missing {canonical}"


# ---------------------------------------------------------------------------
# N2 - pipeline-mapping.md must not lie about what is in globallyForbidden
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_pipeline_mapping_does_not_misclaim_globally_forbidden() -> None:
    """N2: any term the doc claims is in globallyForbidden must actually be there."""
    doc = (REPO_ROOT / "docs" / "architecture" / "pipeline-mapping.md").read_text(encoding="utf-8")
    forbidden = set(_naming().get("globallyForbidden", []))

    # The doc may reference forbidden words explicitly. The bug we fix here is
    # the doc making a positive claim "X står i globallyForbidden" when X is
    # not in the list. We pattern-match that specific claim shape.
    pattern = re.compile(r"`([^`]+)`\s+(?:och|och även|samt|,)?[^`]{0,40}?st(?:år|\u00e5r)\s+i\s+`?globallyForbidden")
    for match in pattern.finditer(doc):
        term = match.group(1)
        assert term in forbidden, (
            f"pipeline-mapping.md falsely claims `{term}` is in globallyForbidden"
        )


# ---------------------------------------------------------------------------
# N3 - dossier owner-path must exist on disk
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_dossier_owner_path_exists_on_disk() -> None:
    """N3: ownerPackage for dossier-terms must point to a real directory."""
    dossier_dir = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
    assert dossier_dir.is_dir(), "Dossier owner-path missing; create the directory or update repo-boundaries"
    assert (dossier_dir / "README.md").exists(), "Dossier folder must explain its layout"


# ---------------------------------------------------------------------------
# N4 - preview-runtime-policy must not say "no F2/F3 tier" then mention F3
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_preview_runtime_policy_self_consistent() -> None:
    """N4: policy must not contradict itself by mixing 'no tier' with 'F3-likt'."""
    policy = json.loads(
        (REPO_ROOT / "governance" / "policies" / "preview-runtime-policy.v1.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(policy, ensure_ascii=False)
    forbidden_phrases = ["F3-likt", "tier-3 SDK", "tier 3 SDK"]
    for phrase in forbidden_phrases:
        assert phrase not in serialized, (
            f"preview-runtime-policy contains '{phrase}' which contradicts the no-tier principle"
        )


# ---------------------------------------------------------------------------
# Naming v7 sanity: four dossier-type terms registered with consistent owner
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_four_dossier_type_terms_registered() -> None:
    ids = _term_ids()
    for required in ["siteDossier", "featureDossier", "integrationDossier", "dataDossier"]:
        assert required in ids, f"Missing naming-dictionary term: {required}"

    expected_owner = "packages/generation/orchestration/dossiers"
    for term in _naming()["terms"]:
        if term["id"] in {"siteDossier", "featureDossier", "integrationDossier", "dataDossier"}:
            assert term["ownerPackage"] == expected_owner, (
                f"{term['id']} ownerPackage drift: {term['ownerPackage']}"
            )


# ---------------------------------------------------------------------------
# BO5 - placeholder detector
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_placeholder_detector_recognises_status_field(tmp_path: Path) -> None:
    """BO5: backoffice helper must flag placeholder JSON files."""
    from backoffice.views.building_blocks import is_placeholder_file, scaffold_is_real

    placeholder = tmp_path / "scaffold.json"
    placeholder.write_text('{"_status": "placeholder, fill per scaffold-contract"}\n', encoding="utf-8")
    assert is_placeholder_file(placeholder)

    real = tmp_path / "scaffold-real.json"
    real.write_text('{"id": "x", "version": "1.0.0"}\n', encoding="utf-8")
    assert not is_placeholder_file(real)

    # Whole-scaffold check: dir with placeholders is not real
    scaffold_dir = tmp_path / "fake-scaffold"
    scaffold_dir.mkdir()
    (scaffold_dir / "scaffold.json").write_text(
        '{"_status": "placeholder, fill per scaffold-contract"}\n', encoding="utf-8"
    )
    (scaffold_dir / "routes.json").write_text(
        '{"_status": "placeholder, fill per scaffold-contract"}\n', encoding="utf-8"
    )
    (scaffold_dir / "sections.json").write_text(
        '{"_status": "placeholder, fill per scaffold-contract"}\n', encoding="utf-8"
    )
    assert not scaffold_is_real(scaffold_dir)
