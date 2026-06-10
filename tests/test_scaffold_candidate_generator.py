"""Tester för ``scripts/generate_scaffold_candidate.py``.

Täcker den deterministiska vägen (ingen OPENAI_API_KEY behövs i CI),
branschspecifika sid-uppsättningar (fotograf → portfolio, webbutik →
produkter), filkontraktet (sex scaffold-filer + spec + meta), schema-
validering, output-guarden mot packages/-trädet och scaffoldModel-
rollens policy-resolution.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_scaffold_candidate import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    ORCHESTRATION_DIR,
    SCAFFOLD_ROLE_ID,
    ScaffoldCandidateError,
    generate_scaffold_candidate,
    load_industry_context,
    resolve_scaffold_model,
    slugify_scaffold_id,
)

REQUIRED_FILES = (
    "scaffold.json",
    "routes.json",
    "sections.json",
    "quality-contract.json",
    "compatible-dossiers.json",
    "selection-profile.json",
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _generate(tmp_path: Path, **kwargs):
    defaults = {
        "output_dir": tmp_path / "scaffold-candidates",
        "use_llm": False,
    }
    defaults.update(kwargs)
    return generate_scaffold_candidate(**defaults)


def test_default_output_dir_is_data_scaffold_candidates() -> None:
    assert DEFAULT_OUTPUT_DIR == REPO_ROOT / "data" / "scaffold-candidates"


def test_photographer_candidate_gets_portfolio_route(tmp_path: Path) -> None:
    result = _generate(
        tmp_path, sni_code="74.201", scaffold_id="photographer-portfolio"
    )
    routes = _read(result.candidate_dir / "routes.json")
    paths = [route["path"] for route in routes["defaultRoutes"]]
    assert "/portfolio" in paths
    assert paths[0] == "/"
    assert "/kontakt" in paths


def test_ecommerce_candidate_gets_products_route(tmp_path: Path) -> None:
    result = _generate(tmp_path, sni_code="47.752", scaffold_id="beauty-webshop")
    routes = _read(result.candidate_dir / "routes.json")
    paths = [route["path"] for route in routes["defaultRoutes"]]
    assert "/produkter" in paths


def test_restaurant_candidate_gets_menu_and_booking(tmp_path: Path) -> None:
    result = _generate(tmp_path, sni_code="56.110", scaffold_id="pizzeria-draft")
    routes = _read(result.candidate_dir / "routes.json")
    paths = [route["path"] for route in routes["defaultRoutes"]]
    assert "/meny" in paths
    assert "/bokning" in paths


def test_candidate_dir_contains_full_file_contract(tmp_path: Path) -> None:
    result = _generate(
        tmp_path, sni_code="74.201", scaffold_id="photographer-portfolio"
    )
    for file_name in REQUIRED_FILES:
        assert (result.candidate_dir / file_name).is_file(), file_name
    assert (result.candidate_dir / "spec.json").is_file()
    assert (result.candidate_dir / "meta.json").is_file()
    assert (result.candidate_dir / "variants" / "draft-default.json").is_file()


def test_candidate_variant_is_disabled_draft(tmp_path: Path) -> None:
    result = _generate(
        tmp_path, sni_code="74.201", scaffold_id="photographer-portfolio"
    )
    variant = _read(result.candidate_dir / "variants" / "draft-default.json")
    assert variant["enabled"] is False
    assert "tokens" in variant and "tone" in variant


def test_scaffold_json_validates_against_schema(tmp_path: Path) -> None:
    from jsonschema import Draft202012Validator

    result = _generate(
        tmp_path, sni_code="74.201", scaffold_id="photographer-portfolio"
    )
    scaffold_doc = _read(result.candidate_dir / "scaffold.json")
    schema = _read(REPO_ROOT / "governance" / "schemas" / "scaffold.schema.json")
    Draft202012Validator(schema).validate(scaffold_doc)
    assert scaffold_doc["id"] == "photographer-portfolio"
    assert scaffold_doc["defaultPageCount"] == len(
        _read(result.candidate_dir / "routes.json")["defaultRoutes"]
    )


def test_sections_keys_match_default_route_ids(tmp_path: Path) -> None:
    result = _generate(tmp_path, sni_code="47.752", scaffold_id="beauty-webshop")
    routes = _read(result.candidate_dir / "routes.json")
    sections = _read(result.candidate_dir / "sections.json")
    default_ids = {route["id"] for route in routes["defaultRoutes"]}
    assert set(sections.keys()) == default_ids
    for payload in sections.values():
        assert payload["requiredSections"]


def test_recommended_dossiers_are_known_ids(tmp_path: Path) -> None:
    result = _generate(
        tmp_path, sni_code="74.201", scaffold_id="photographer-portfolio"
    )
    compatible = _read(result.candidate_dir / "compatible-dossiers.json")
    soft_dir = ORCHESTRATION_DIR / "dossiers" / "soft"
    known = {path.name for path in soft_dir.iterdir() if path.is_dir()}
    assert set(compatible["recommended"]).issubset(known)


def test_meta_has_traceability_without_raw_brief(tmp_path: Path) -> None:
    secret_brief = "hemlig kundkontext som inte får läcka"
    result = _generate(
        tmp_path,
        sni_code="74.201",
        scaffold_id="photographer-portfolio",
        brief=secret_brief,
    )
    meta = _read(result.candidate_dir / "meta.json")
    assert meta["candidateType"] == "scaffold"
    # sniCode lagras digit-normaliserad (samma som DiscoveryDecision).
    assert meta["sniCode"] == "74201"
    assert meta["modelRole"] == SCAFFOLD_ROLE_ID
    assert meta["source"] == "deterministic-v1"
    assert meta["operatorBriefHash"].startswith("sha256:")
    raw = (result.candidate_dir / "meta.json").read_text(encoding="utf-8")
    assert secret_brief not in raw


def test_no_llm_without_key_reports_mock_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = _generate(
        tmp_path,
        sni_code="74.201",
        scaffold_id="photographer-portfolio",
        use_llm=True,
    )
    assert result.source == "mock-no-key"


def test_guard_refuses_orchestration_output_dir(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldCandidateError):
        generate_scaffold_candidate(
            sni_code="74.201",
            scaffold_id="photographer-portfolio",
            output_dir=ORCHESTRATION_DIR / "scaffolds",
            use_llm=False,
        )


def test_existing_canonical_scaffold_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldCandidateError, match="canonical scaffold"):
        _generate(
            tmp_path, sni_code="56.110", scaffold_id="restaurant-hospitality"
        )


def test_existing_candidate_requires_force(tmp_path: Path) -> None:
    _generate(tmp_path, sni_code="74.201", scaffold_id="photographer-portfolio")
    with pytest.raises(ScaffoldCandidateError, match="--force"):
        _generate(
            tmp_path, sni_code="74.201", scaffold_id="photographer-portfolio"
        )
    result = _generate(
        tmp_path,
        sni_code="74.201",
        scaffold_id="photographer-portfolio",
        force=True,
    )
    assert result.candidate_dir.is_dir()


def test_invalid_sni_code_raises(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldCandidateError, match="SNI"):
        _generate(tmp_path, sni_code="abc", scaffold_id="nope")


def test_resolve_scaffold_model_reads_policy() -> None:
    model = resolve_scaffold_model()
    assert isinstance(model, str) and model.strip()


def test_industry_context_reuses_resolver_seam() -> None:
    # 74.201 (foto) träffar grupp-override 742 -> photo; divisionsprofilen
    # sni-74 gateas bort precis som i Discovery Resolver (Gate 1).
    photo_context = load_industry_context("74.201")
    assert photo_context.category.id == "photo"
    assert photo_context.profile_id is None
    assert (
        ORCHESTRATION_DIR / "scaffolds" / photo_context.reference_scaffold_id
    ).is_dir()

    # 56.110 (restaurang): profilen matchar kategorin och överlever gaten.
    restaurant_context = load_industry_context("56.110")
    assert restaurant_context.category.id == "restaurant"
    assert restaurant_context.profile_id == "sni-56"


def test_slugify_scaffold_id_handles_swedish_labels() -> None:
    assert slugify_scaffold_id("Foto & Video AB") == "foto-video-ab"
    assert slugify_scaffold_id("Hälsa/Skönhet") == "halsa-skonhet"
    assert slugify_scaffold_id("123") == "scaffold-123"
