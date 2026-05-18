"""Tests för Discovery Resolver (B121 PR A).

Låser kärnkontrakten:

- ``DiscoveryDecision`` validerar mot
  ``governance/schemas/discovery-decision.schema.json``.
- Field-source-prioritet ``wizard > scrape > brief`` per fält.
- ``fallbackWarnings`` skapas för ``supportStatus=planned`` och okända
  kategorier.
- ``ecommerce`` resulterar i ecommerce-lite + clean-store + expected starter
  commerce-base.
- ``restaurant`` ger target=restaurant-hospitality men selected=local-service-
  business + warning ``category-planned``.
- ``scripts/prompt_to_project_input.generate`` skriver
  ``meta["discoveryDecision"]`` när payload skickas.
- Befintlig ``apply_discovery_overrides``-wrapper bevarar
  ``test_apply_discovery_overrides_maps_assets_to_brand_and_gallery``-shapen.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DECISION_SCHEMA = (
    REPO_ROOT / "governance" / "schemas" / "discovery-decision.schema.json"
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.discovery import (  # noqa: E402
    apply_discovery_overrides,
    load_discovery_taxonomy,
    resolve_discovery,
)
from packages.generation.discovery.models import DiscoveryDecision  # noqa: E402


@pytest.fixture(scope="module")
def decision_schema() -> dict:
    return json.loads(DECISION_SCHEMA.read_text(encoding="utf-8"))


def _candidate_project_input() -> dict[str, Any]:
    """Minimal Site Brief-derived Project Input som resolvern startar från."""
    return {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": "site-test-1",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Brief Company AB",
            "businessType": "service-provider",
            "tagline": "Brief tagline",
            "story": "Brief story",
        },
        "location": {
            "city": "Malmö",
            "country": "Sverige",
            "serviceAreas": ["Malmö"],
        },
        "services": [
            {"id": "elservice", "label": "Elservice", "summary": "Elservice."}
        ],
        "tone": {"primary": "trustworthy", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46 8 000 00 00",
            "email": "brief@example.se",
            "addressLines": ["Brief adress"],
            "openingHours": "Mån-Fre 09:00-17:00",
        },
        "selectedDossiers": {"required": [], "recommended": [], "rationale": "x"},
    }


def _payload(category: str, **answers_overrides: Any) -> dict[str, Any]:
    answers: dict[str, Any] = {"siteType": [category]}
    answers.update(answers_overrides)
    return {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": answers,
    }


# ---------------------------------------------------------------------------
# Schema-validation
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_decision_validates_against_schema(decision_schema: dict) -> None:
    project_input, decision = resolve_discovery(
        raw_prompt="elektriker Malmö",
        payload=_payload("business", companyName="Wizard Co"),
        project_input_candidate=_candidate_project_input(),
    )
    jsonschema.Draft202012Validator(decision_schema).validate(decision.to_dict())
    assert project_input["scaffoldId"] == "local-service-business"


# ---------------------------------------------------------------------------
# Scaffold-/variant-/starter-mapping per kategori
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_ecommerce_category_picks_ecommerce_lite_and_commerce_base() -> None:
    project_input, decision = resolve_discovery(
        raw_prompt="webshop som säljer keramik",
        payload=_payload("ecommerce"),
        project_input_candidate=_candidate_project_input(),
    )
    assert project_input["scaffoldId"] == "ecommerce-lite"
    assert project_input["variantId"] == "clean-store"
    assert decision.selectedScaffoldId == "ecommerce-lite"
    assert decision.targetScaffoldId == "ecommerce-lite"
    assert decision.selectedVariantId == "clean-store"
    assert decision.expectedStarterId == "commerce-base"
    assert decision.selectionSource == "taxonomy"
    assert decision.fallbackScaffoldId is None
    assert decision.fieldSources["scaffoldId"] == "taxonomy"
    assert decision.fieldSources["variantId"] == "taxonomy"


@pytest.mark.tooling
def test_restaurant_falls_back_to_local_service_with_warning() -> None:
    project_input, decision = resolve_discovery(
        raw_prompt="restaurang i Stockholm",
        payload=_payload("restaurant"),
        project_input_candidate=_candidate_project_input(),
    )
    assert project_input["scaffoldId"] == "local-service-business"
    assert project_input["variantId"] == "nordic-trust"
    assert decision.selectedScaffoldId == "local-service-business"
    assert decision.targetScaffoldId == "restaurant-hospitality"
    assert decision.selectionSource == "fallback"
    assert decision.expectedStarterId == "marketing-base"
    codes = {warning.code for warning in decision.fallbackWarnings}
    assert "category-planned" in codes
    assert decision.operatorReviewRequired is True


@pytest.mark.tooling
def test_unknown_category_yields_warning_and_default_scaffold() -> None:
    project_input, decision = resolve_discovery(
        raw_prompt="okänd verksamhet",
        payload=_payload("definitely-not-a-real-category"),
        project_input_candidate=_candidate_project_input(),
    )
    # Project Input scaffoldId behålls från Site Brief eftersom resolvern
    # inte rör fältet utan giltig kategori (behavior identisk med pre-B121).
    assert project_input["scaffoldId"] == "local-service-business"
    assert decision.categoryIds == ["definitely-not-a-real-category"]
    codes = {warning.code for warning in decision.fallbackWarnings}
    assert "category-unknown" in codes
    assert decision.operatorReviewRequired is True


# ---------------------------------------------------------------------------
# Field-source-prioritet (wizard > scrape > brief)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_wizard_company_name_wins_over_brief() -> None:
    payload = _payload("business", companyName="Wizard Co")
    candidate = _candidate_project_input()
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )
    assert project_input["company"]["name"] == "Wizard Co"
    assert decision.fieldSources["company.name"] == "wizard"


@pytest.mark.tooling
def test_brief_company_name_kept_when_wizard_blank() -> None:
    payload = _payload("business")  # ingen companyName
    candidate = _candidate_project_input()
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )
    assert project_input["company"]["name"] == "Brief Company AB"
    assert decision.fieldSources["company.name"] == "brief"


@pytest.mark.tooling
def test_scrape_email_only_wins_when_wizard_email_blank() -> None:
    payload = _payload("business")  # tom contact.email
    candidate = _candidate_project_input()
    scrape = {"contact": {"email": "scraped@example.se"}}
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
        scrape=scrape,
    )
    assert project_input["contact"]["email"] == "scraped@example.se"
    assert decision.fieldSources["contact.email"] == "scrape"


@pytest.mark.tooling
def test_wizard_email_beats_scrape_email() -> None:
    payload = _payload(
        "business",
        contact={"email": "wizard@example.se"},
    )
    candidate = _candidate_project_input()
    scrape = {"contact": {"email": "scraped@example.se"}}
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
        scrape=scrape,
    )
    assert project_input["contact"]["email"] == "wizard@example.se"
    assert decision.fieldSources["contact.email"] == "wizard"


@pytest.mark.tooling
def test_brief_email_kept_when_wizard_and_scrape_blank() -> None:
    payload = _payload("business")
    candidate = _candidate_project_input()
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )
    assert project_input["contact"]["email"] == "brief@example.se"
    assert decision.fieldSources["contact.email"] == "brief"


# ---------------------------------------------------------------------------
# Capabilities & fallbackWarnings
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_taxonomy_capabilities_merge_with_wizard_must_have() -> None:
    payload = _payload(
        "business",
        mustHave=["Kontaktformulär", "Bildgalleri"],
    )
    candidate = _candidate_project_input()
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )
    caps = project_input["requestedCapabilities"]
    assert "contact-form" in caps  # från både wizard mustHave och taxonomy
    assert "gallery" in caps  # från wizard mustHave (capability-unknown warning)
    codes = {warning.code for warning in decision.fallbackWarnings}
    assert "capability-unknown" in codes
    # Kapacitet som ligger i capability-map (contact-form) får ingen warning.
    cap_ids_warned = {w.capabilityId for w in decision.fallbackWarnings if w.capabilityId}
    assert "contact-form" not in cap_ids_warned


@pytest.mark.tooling
def test_requested_capabilities_field_source_reflects_winner() -> None:
    payload = _payload(
        "business",
        mustHave=["Kontaktformulär"],
    )
    candidate = _candidate_project_input()
    _, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )
    assert decision.fieldSources["requestedCapabilities"] == "wizard"


@pytest.mark.tooling
def test_decision_records_candidate_dossiers_from_taxonomy() -> None:
    """Taxonomy candidate-dossier-listor surface in decision.candidateDossiers."""
    payload = _payload("business")
    candidate = _candidate_project_input()
    _, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )
    taxonomy = load_discovery_taxonomy()
    business_category = taxonomy.get("business")
    assert business_category is not None
    assert decision.candidateDossiers == business_category.candidateDossiers


# ---------------------------------------------------------------------------
# Brand/asset-overrides bevaras
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_brand_colors_and_logo_pass_through_to_project_input() -> None:
    asset_ref = {
        "assetId": "01HXYZ1234567890ABCDEFGHJK",
        "filename": "logo.webp",
        "mimeType": "image/webp",
        "sizeBytes": 1234,
        "role": "logo",
    }
    payload = _payload(
        "business",
        brand={"primaryColorHex": "#123456", "accentColorHex": "#abcdef"},
        assets={"logo": asset_ref},
    )
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )
    assert project_input["brand"]["primaryColorHex"] == "#123456"
    assert project_input["brand"]["accentColorHex"] == "#abcdef"
    assert project_input["brand"]["logo"]["assetId"] == asset_ref["assetId"]
    assert decision.fieldSources["brand.logo"] == "wizard"
    assert decision.fieldSources["brand.primaryColorHex"] == "wizard"


@pytest.mark.tooling
def test_apply_discovery_overrides_wrapper_keeps_backward_compat_shape() -> None:
    """Pre-B121-shape: empty Project Input + assets-only payload."""
    base_pi: dict[str, Any] = {}
    discovery = {
        "answers": {
            "assets": {
                "logo": {
                    "assetId": "01HXYZ1234567890ABCDEFGHJK",
                    "filename": "logo.webp",
                    "mimeType": "image/webp",
                    "sizeBytes": 1234,
                    "role": "logo",
                },
                "heroImage": {
                    "assetId": "01HXYZ8R0XYZ0PQRSTUV9876543",
                    "filename": "hero.webp",
                    "mimeType": "image/webp",
                    "sizeBytes": 1234,
                    "role": "hero",
                },
                "gallery": [
                    {
                        "assetId": "01HXYZ9S0AAAA1234567890ABCD",
                        "filename": "g.webp",
                        "mimeType": "image/webp",
                        "sizeBytes": 1234,
                        "role": "gallery",
                        "placement": "about",
                    }
                ],
            }
        }
    }
    out = apply_discovery_overrides(base_pi, discovery)
    assert out["brand"]["logo"]["assetId"] == discovery["answers"]["assets"]["logo"]["assetId"]
    assert out["brand"]["heroImage"]["role"] == "hero"
    assert len(out["gallery"]) == 1
    assert out["gallery"][0]["placement"] == "about"


# ---------------------------------------------------------------------------
# Address-parsing och services
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_postcode_in_address_updates_location_city() -> None:
    payload = _payload(
        "business",
        contact={"address": "Storgatan 1, 211 22 Malmö"},
    )
    candidate = _candidate_project_input()
    candidate["location"]["city"] = "Stockholm"  # överskrivs av postcode-match
    project_input, _ = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )
    assert project_input["location"]["city"] == "Malmö"
    assert project_input["contact"]["addressLines"] == ["Storgatan 1, 211 22 Malmö"]


@pytest.mark.tooling
def test_wizard_services_replace_brief_services_when_provided() -> None:
    payload = _payload(
        "business",
        services=[
            {"id": "1", "name": "Paneldragning", "description": "Säkra installationer"},
            {"id": "2", "name": "Laddbox", "description": "Installation av laddbox"},
        ],
    )
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )
    labels = {svc["label"] for svc in project_input["services"]}
    assert labels == {"Paneldragning", "Laddbox"}
    assert decision.fieldSources["services"] == "wizard"


# ---------------------------------------------------------------------------
# CTA → conversionGoals
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_primary_cta_appends_conversion_goal_with_wizard_source() -> None:
    payload = _payload("business", primaryCta="Boka tid")
    candidate = _candidate_project_input()
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )
    assert "booking" in project_input["conversionGoals"]
    assert decision.fieldSources["conversionGoals"] == "wizard"


# ---------------------------------------------------------------------------
# Integration med scripts/prompt_to_project_input.generate
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_generate_writes_discovery_decision_to_meta_sidecar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end: ``generate(..., discovery=payload)`` skriver
    ``meta["discoveryDecision"]`` till prompt-input meta-sidecaren.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.prompt_to_project_input import generate

    discovery_payload = {
        "schemaVersion": 1,
        "rawPrompt": "webshop som säljer keramik",
        "contentBranch": "ecommerce",
        "scaffoldHint": "ecommerce-lite",
        "answers": {
            "siteType": ["ecommerce"],
            "companyName": "Keramikbutiken AB",
            "mustHave": ["Kontaktformulär"],
            "primaryCta": "Köp nu",
        },
    }
    project_input, meta, _, meta_path = generate(
        "webshop som säljer keramik",
        output_dir=tmp_path,
        discovery=discovery_payload,
    )
    assert project_input["scaffoldId"] == "ecommerce-lite"
    assert project_input["variantId"] == "clean-store"
    assert project_input["company"]["name"] == "Keramikbutiken AB"

    assert "discoveryDecision" in meta
    decision = meta["discoveryDecision"]
    assert decision["selectedScaffoldId"] == "ecommerce-lite"
    assert decision["expectedStarterId"] == "commerce-base"
    assert decision["selectionSource"] == "taxonomy"
    assert decision["categoryIds"] == ["ecommerce"]
    assert "purchase" in project_input["conversionGoals"]

    sidecar = json.loads(meta_path.read_text(encoding="utf-8"))
    assert sidecar["discoveryDecision"]["selectedScaffoldId"] == "ecommerce-lite"


@pytest.mark.tooling
def test_generate_without_discovery_omits_decision_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.prompt_to_project_input import generate

    _project, meta, _, _ = generate(
        "elektriker Malmö",
        output_dir=tmp_path,
    )
    assert "discoveryDecision" not in meta


@pytest.mark.tooling
def test_decision_dataclass_to_dict_omits_none_fields() -> None:
    """Serialise-helpern lämnar bort ``None``-fält så schemat accepterar dict:en."""
    decision = DiscoveryDecision(
        categoryIds=["business"],
        contentBranch="business",
        selectedScaffoldId="local-service-business",
        targetScaffoldId="local-service-business",
        selectedVariantId="nordic-trust",
        requestedCapabilities=["contact-form"],
        candidateDossiers=[],
    )
    payload = decision.to_dict()
    assert "fallbackScaffoldId" not in payload
    assert "expectedStarterId" not in payload
    assert "confidence" not in payload
    assert payload["fieldSources"] == {}
    assert payload["fallbackWarnings"] == []


# ---------------------------------------------------------------------------
# Project Input shape oförändrad
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_resolver_does_not_introduce_unknown_keys_in_project_input() -> None:
    """Resolved Project Input får bara fält som ``project-input.schema.json`` tillåter."""
    schema_path = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    allowed = set(schema["properties"].keys())

    payload = _payload(
        "business",
        companyName="Wizard Co",
        contact={"phone": "0701234567", "email": "hej@example.se"},
        primaryCta="Boka tid",
        brand={"toneTags": ["Professionell"]},
    )
    project_input, _ = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )
    extra = set(project_input.keys()) - allowed
    assert not extra, f"Resolvern introducerade okända Project Input-fält: {extra}"


@pytest.mark.tooling
def test_resolver_is_idempotent_on_double_invocation() -> None:
    """Två anrop med samma payload ska producera samma decision-dict."""
    payload = _payload("business", companyName="Idempotent AB")
    candidate = _candidate_project_input()

    pi_a, decision_a = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=copy.deepcopy(candidate),
    )
    pi_b, decision_b = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=copy.deepcopy(candidate),
    )
    assert pi_a == pi_b
    assert decision_a.to_dict() == decision_b.to_dict()
