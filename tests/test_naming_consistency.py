"""Regression tests for naming and docs consistency.

Each test corresponds to a specific bug ID from the audits captured in
``docs/known-issues.md``. ADR 0012 removed the four Dossier-typ-axel terms
(Site/Feature/Integration/Data Dossier) and the `hybrid` Dossier class so the
operator-vokabulär stays at one canonical chain.
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
# ADR 0012 - Dossier type-axis is removed; only Project Input + soft/hard remain
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_dossier_type_axis_terms_are_removed() -> None:
    ids = _term_ids()
    for removed in ["siteDossier", "featureDossier", "integrationDossier", "dataDossier", "hybridDossier"]:
        assert removed not in ids, (
            f"naming-dictionary still has '{removed}' as canonical term; "
            "ADR 0012 removed the Dossier type axis."
        )


@pytest.mark.governance
def test_project_input_term_is_registered() -> None:
    ids = _term_ids()
    assert "projectInput" in ids, "projectInput must be canonical (ADR 0012)"
    project_input = next(t for t in _naming()["terms"] if t["id"] == "projectInput")
    assert "Deep Brief" in project_input["aliasesAllowed"], (
        "projectInput should allow 'Deep Brief' as alias"
    )


@pytest.mark.governance
def test_dossier_type_terms_are_globally_forbidden() -> None:
    forbidden = set(_naming().get("globallyForbidden", []))
    for forbidden_term in [
        "Site Dossier",
        "Feature Dossier",
        "Integration Dossier",
        "Data Dossier",
        "Hybrid Dossier",
    ]:
        assert forbidden_term in forbidden, (
            f"'{forbidden_term}' must be in globallyForbidden after ADR 0012"
        )


@pytest.mark.governance
def test_dossier_classes_are_only_soft_and_hard() -> None:
    ids = _term_ids()
    assert "softDossier" in ids
    assert "hardDossier" in ids
    assert "hybridDossier" not in ids


# ---------------------------------------------------------------------------
# ADR 0016 - F2/F3, lane and fidelity terms must stay globally forbidden
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_legacy_lane_and_fidelity_terms_are_globally_forbidden() -> None:
    """ADR 0016 reaction to the architect-reviewer round: the old
    sajtmaskin vocabulary about modes/lanes/fidelity must not creep
    back into sajtbyggaren. Canonical phase ordering lives in
    engine-run.v1.json (phase 1 understand / phase 2 plan / phase 3
    build); fix vocabulary is Quality Gate / Repair Pipeline /
    PreviewRuntime / Mechanical Fix / LLM Fix.
    """
    forbidden = set(_naming().get("globallyForbidden", []))
    for forbidden_term in [
        "F2",
        "F3",
        "F2-only",
        "F3-only",
        "verify lane",
        "preview lane",
        "verify-lane",
        "preview-lane",
        "fidelity",
        "fidelity levels",
    ]:
        assert forbidden_term in forbidden, (
            f"'{forbidden_term}' must stay in globallyForbidden "
            f"(ADR 0016 - no parallel vocabulary for phase/quality)."
        )


# ---------------------------------------------------------------------------
# Operator-flow lock: the eight-step flow must be representable with current terms
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_operator_flow_terms_exist() -> None:
    """ADR 0012's eight-step flow must be expressible in current terms."""
    ids = _term_ids()
    required = {
        "projectInput",
        "starter",
        "scaffold",
        "scaffoldVariant",
        "dossier",
        "generationPackage",
        "buildResult",
    }
    missing = required - ids
    assert not missing, f"ADR 0012 flow terms missing: {missing}"


# ---------------------------------------------------------------------------
# pipeline-mapping.md must not lie about what is in globallyForbidden
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_pipeline_mapping_does_not_misclaim_globally_forbidden() -> None:
    doc = (REPO_ROOT / "docs" / "architecture" / "pipeline-mapping.md").read_text(encoding="utf-8")
    forbidden = set(_naming().get("globallyForbidden", []))
    pattern = re.compile(r"`([^`]+)`\s+(?:och|och även|samt|,)?[^`]{0,40}?st(?:år|\u00e5r)\s+i\s+`?globallyForbidden")
    for match in pattern.finditer(doc):
        term = match.group(1)
        assert term in forbidden, (
            f"pipeline-mapping.md falsely claims `{term}` is in globallyForbidden"
        )


# ---------------------------------------------------------------------------
# dossier owner-path must exist on disk
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_dossier_owner_path_exists_on_disk() -> None:
    dossier_dir = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
    assert dossier_dir.is_dir(), "Dossier owner-path missing"
    assert (dossier_dir / "README.md").exists(), "Dossier folder must explain its layout"


# ---------------------------------------------------------------------------
# preview-runtime-policy must not say "no F2/F3 tier" then mention F3
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_preview_runtime_policy_self_consistent() -> None:
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
