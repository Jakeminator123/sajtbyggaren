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
from packages.generation.discovery.resolve import _apply_contact_fields  # noqa: E402


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


@pytest.mark.tooling
def test_apply_contact_fields_sets_default_for_placeholder_phone() -> None:
    candidate = _candidate_project_input()
    field_sources: dict[str, str] = {}

    _apply_contact_fields(
        candidate,
        answers={},
        scrape=None,
        field_sources=field_sources,
        placeholder_fields={"phone"},
    )

    assert candidate["contact"]["phone"] == "+46 8 000 00 00"
    assert field_sources["contact.phone"] == "default"


@pytest.mark.tooling
def test_apply_contact_fields_keeps_brief_when_value_is_real() -> None:
    candidate = _candidate_project_input()
    candidate["contact"]["phone"] = "0701234567"
    field_sources: dict[str, str] = {}

    _apply_contact_fields(
        candidate,
        answers={},
        scrape=None,
        field_sources=field_sources,
    )

    assert candidate["contact"]["phone"] == "0701234567"
    assert field_sources["contact.phone"] == "brief"


@pytest.mark.tooling
def test_resolve_discovery_field_sources_distinguish_placeholder(
    decision_schema: dict,
) -> None:
    payload = _payload("business")
    candidate = _candidate_project_input()
    candidate["contact"] = {
        "phone": "+46 8 000 00 00",
        "email": "kontakt@example.se",
        "addressLines": ["Adress lämnas på förfrågan"],
        "openingHours": "Mån-Fre 09:00-17:00",
    }

    _, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
        placeholder_fields=["phone", "email", "addressLines", "openingHours"],
    )

    assert decision.fieldSources["contact.phone"] == "default"
    assert decision.fieldSources["contact.email"] == "default"
    assert decision.fieldSources["contact.addressLines"] == "default"
    assert decision.fieldSources["contact.openingHours"] == "default"
    assert decision.operatorReviewRequired is True
    jsonschema.Draft202012Validator(decision_schema).validate(decision.to_dict())


# ---------------------------------------------------------------------------
# Capabilities & fallbackWarnings
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_taxonomy_capabilities_merge_with_wizard_must_have() -> None:
    """Wizard mustHave + taxonomy capabilities slås ihop, gap vs unknown.

    Efter fix-passet (R2 P1 + R3 #2) skiljer resolvern på:

    - ``contact-form`` finns i capability-map men har tom dossiers-lista
      → ``capability-gap``.
    - ``gallery`` finns inte alls i capability-map → ``capability-unknown``.
    """
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
    assert "gallery" in caps  # från wizard mustHave
    codes = {warning.code for warning in decision.fallbackWarnings}
    assert "capability-unknown" in codes  # gallery saknar i capability-map
    assert "capability-gap" in codes  # contact-form har tom dossiers-lista
    by_code: dict[str, set[str]] = {}
    for warning in decision.fallbackWarnings:
        if warning.capabilityId:
            by_code.setdefault(warning.code, set()).add(warning.capabilityId)
    assert "contact-form" in by_code.get("capability-gap", set())
    assert "gallery" in by_code.get("capability-unknown", set())


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
def test_resolve_capabilities_dedups_via_alias() -> None:
    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {"mustHave": ["Bokning online"]},
    }
    candidate = _candidate_project_input()
    candidate["requestedCapabilities"] = ["online-booking"]

    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )

    assert project_input["requestedCapabilities"] == ["booking"]
    assert decision.requestedCapabilities == ["booking"]
    assert "online-booking" not in {
        warning.capabilityId for warning in decision.fallbackWarnings
    }


@pytest.mark.tooling
def test_resolve_capabilities_preserves_unknown_slug_when_no_alias() -> None:
    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {},
    }
    candidate = _candidate_project_input()
    candidate["requestedCapabilities"] = ["custom-widget"]

    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )

    assert project_input["requestedCapabilities"] == ["custom-widget"]
    by_code: dict[str, set[str]] = {}
    for warning in decision.fallbackWarnings:
        if warning.capabilityId:
            by_code.setdefault(warning.code, set()).add(warning.capabilityId)
    assert "custom-widget" in by_code.get("capability-unknown", set())


@pytest.mark.tooling
def test_resolve_capabilities_alias_keeps_priority_source() -> None:
    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {"mustHave": ["Bokning online"]},
    }
    candidate = _candidate_project_input()
    candidate["requestedCapabilities"] = ["online-booking"]

    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )

    assert project_input["requestedCapabilities"] == ["booking"]
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
    assert decision["fieldSources"]["contact.phone"] == "default"
    assert decision["fieldSources"]["contact.email"] == "default"
    assert decision["fieldSources"]["contact.addressLines"] == "default"
    assert decision["fieldSources"]["contact.openingHours"] == "default"
    assert decision["operatorReviewRequired"] is True
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


# ---------------------------------------------------------------------------
# Review-fix-pass på PR #34 (B121)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_multi_select_primary_category_follows_branch_priority() -> None:
    """R2 P1 + R3 #1: ``["business", "ecommerce"]`` ska ge ecommerce-lite.

    Tidigare gav primary_category=business (första i listan) men
    pick_branch returnerade ``ecommerce`` (lägst priority), vilket gav
    self-contradictory beslut: ``contentBranch=ecommerce`` men
    scaffold=``local-service-business``. Resolvern måste nu välja
    primary_category med samma priority.
    """
    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "ecommerce",
        "scaffoldHint": "ecommerce-lite",
        "answers": {"siteType": ["business", "ecommerce"]},
    }
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )
    assert project_input["scaffoldId"] == "ecommerce-lite"
    assert project_input["variantId"] == "clean-store"
    assert decision.selectedScaffoldId == "ecommerce-lite"
    assert decision.contentBranch == "ecommerce"
    assert decision.expectedStarterId == "commerce-base"


@pytest.mark.tooling
def test_multi_select_picks_restaurant_over_portfolio() -> None:
    """Restaurant priority 1 vs portfolio priority 3 → restaurant vinner."""
    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "restaurant",
        "scaffoldHint": "local-service-business",
        "answers": {"siteType": ["portfolio", "restaurant"]},
    }
    _, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )
    # Båda är planned med fallback local-service-business; vi kollar
    # bara att primary_category-id i fallback-warning är restaurant.
    category_warnings = [
        w for w in decision.fallbackWarnings if w.code == "category-planned"
    ]
    primary_ids = {w.categoryId for w in category_warnings if w.categoryId}
    assert "restaurant" in primary_ids
    assert decision.contentBranch == "restaurant"
    assert decision.targetScaffoldId == "restaurant-hospitality"


@pytest.mark.tooling
def test_capability_gap_flagged_as_warning_but_not_review_trigger() -> None:
    """R2 P1 + R3 #2 (round 2): ``payments`` / ``contact-form`` finns i
    capability-map men har tom dossier-lista — det är en **gap**, inte
    unknown. Resolvern lägger en ``capability-gap``-warning så Backoffice
    ser planerade Dossier-importer.

    R1 #1 + huvudreviewer #4 (round 3): gap triggar dock INTE
    ``operatorReviewRequired``. Gap är samma signal för alla runs av
    samma kategori och skulle annars göra review-flaggan bullrig
    ("True för nästan alla normala runs"). Bara unknown/planned/disabled
    och okänd kategori kräver per-run-review.
    """
    payload = _payload("ecommerce")  # taxonomin lägger payments + contact-form
    _, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )
    gap_codes = [w.code for w in decision.fallbackWarnings]
    gap_capabilities = {
        w.capabilityId
        for w in decision.fallbackWarnings
        if w.code == "capability-gap" and w.capabilityId
    }
    assert "capability-gap" in gap_codes
    assert "payments" in gap_capabilities
    assert "contact-form" in gap_capabilities
    # ecommerce är active och taxonomy-capabilities är bara gap, inte
    # unknown — review krävs inte. (R1 #1 round 3.)
    assert decision.operatorReviewRequired is False


@pytest.mark.tooling
def test_capability_unknown_separate_from_gap() -> None:
    """``gallery`` finns inte i capability-map → capability-unknown.
    ``contact-form`` finns men har inga dossiers → capability-gap.
    Båda måste flaggas, var och en med sin kod.
    """
    payload = _payload(
        "business",
        mustHave=["Kontaktformulär", "Bildgalleri"],
    )
    _, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )
    by_code: dict[str, set[str]] = {}
    for warning in decision.fallbackWarnings:
        if warning.capabilityId:
            by_code.setdefault(warning.code, set()).add(warning.capabilityId)
    assert "contact-form" in by_code.get("capability-gap", set())
    assert "gallery" in by_code.get("capability-unknown", set())


@pytest.mark.tooling
def test_resolver_reads_capability_map_runtime_not_hardcoded(tmp_path: Path) -> None:
    """R3 #2: capability-classification måste komma från
    ``capability-map.v1.json``, inte en hårdkodad slug-lista i Python.

    Vi injekterar en alternativ capability-map med en känd och en
    saknad slug, och verifierar att resolvern klassificerar enligt
    den map:en.
    """
    custom_map = {
        "contact-form": {
            "dossiers": ["fake-implemented-dossier"],
            "default": "fake-implemented-dossier",
        }
    }
    payload = _payload(
        "business",
        mustHave=["Kontaktformulär"],
    )
    _, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=_candidate_project_input(),
        capability_map=custom_map,
    )
    cap_warnings = [
        w for w in decision.fallbackWarnings if w.capabilityId == "contact-form"
    ]
    # Med implementerad dossier får contact-form ingen warning alls.
    assert not cap_warnings


@pytest.mark.tooling
def test_scaffold_hint_used_when_site_type_empty() -> None:
    """R3 #4: bakåtkompatibilitet — payload utan ``siteType`` men med
    ``scaffoldHint`` ska ändå sätta scaffold/variant (samma kontrakt som
    pre-B121 ``_apply_discovery_overrides`` hade).
    """
    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "ecommerce",
        "scaffoldHint": "ecommerce-lite",
        "answers": {"companyName": "Hint Co"},  # ingen siteType
    }
    candidate = _candidate_project_input()
    candidate["scaffoldId"] = "local-service-business"  # ska överskridas av hint
    candidate["variantId"] = "nordic-trust"
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )
    assert project_input["scaffoldId"] == "ecommerce-lite"
    assert project_input["variantId"] == "clean-store"
    assert decision.fieldSources["scaffoldId"] == "wizard"
    assert decision.fieldSources["variantId"] == "wizard"
    assert decision.expectedStarterId == "commerce-base"
    # R2 P2 (round 3): selectionSource måste matcha fieldSources.
    # Wizardens hint pinnar scaffoldId med "wizard"-källa, så top-level
    # selectionSource ska också vara "wizard" (inte "default" som
    # tidigare lekt självmotsägande mot fieldSources).
    assert decision.selectionSource == "wizard"
    # Inget category-warning eftersom hint pekade mot en runtime-aktiv scaffold.
    assert decision.operatorReviewRequired is False


@pytest.mark.tooling
def test_scaffold_hint_ignored_when_pointing_at_non_runtime_scaffold() -> None:
    """``scaffoldHint`` accepteras bara för local-service-business och
    ecommerce-lite — dessa är de två par som planning.SCAFFOLD_TO_STARTER
    faktiskt mappar idag.
    """
    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "restaurant",
        "scaffoldHint": "restaurant-hospitality",  # planned, inte runtime
        "answers": {},
    }
    candidate = _candidate_project_input()
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
    )
    # Resolvern faller tillbaka till project_input_candidate-scaffold.
    assert project_input["scaffoldId"] == candidate["scaffoldId"]
    assert decision.selectionSource == "default"


@pytest.mark.tooling
def test_followup_inherits_discovery_decision_into_v2_meta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R2 P2: discoveryDecision från v1 ska ärvas till v2-meta.

    Followup-runs får inte ny discovery-payload (CLI förbjuder
    ``--discovery`` + ``--followup-site-id`` tillsammans), så om
    resolvern inte också persisterar decisionen vidare till v2 förlorar
    Backoffice/Doctor synlighet för categoryIds, fieldSources och
    fallbackWarnings.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.prompt_to_project_input import generate, generate_followup

    discovery_payload = {
        "schemaVersion": 1,
        "rawPrompt": "webshop som säljer keramik",
        "contentBranch": "ecommerce",
        "scaffoldHint": "ecommerce-lite",
        "answers": {
            "siteType": ["ecommerce"],
            "companyName": "Keramikbutiken AB",
        },
    }
    generate(
        "webshop som säljer keramik",
        output_dir=tmp_path,
        site_id="keramik-shop",
        project_id="stable-project",
        discovery=discovery_payload,
    )

    _, v2_meta, _, v2_meta_path = generate_followup(
        "lägg till en blogg-sektion",
        output_dir=tmp_path,
        site_id="keramik-shop",
    )

    assert "discoveryDecision" in v2_meta, (
        "Followup-meta måste ärva discoveryDecision från v1; annars tappar "
        "Backoffice/Doctor synlighet för categoryIds och fieldSources."
    )
    v2_decision = v2_meta["discoveryDecision"]
    assert v2_decision["selectedScaffoldId"] == "ecommerce-lite"
    assert v2_decision["categoryIds"] == ["ecommerce"]
    assert v2_decision["expectedStarterId"] == "commerce-base"

    sidecar = json.loads(v2_meta_path.read_text(encoding="utf-8"))
    assert sidecar["discoveryDecision"]["categoryIds"] == ["ecommerce"]


@pytest.mark.tooling
def test_followup_without_v1_discovery_decision_omits_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """När v1 inte hade discoveryDecision ska v2 också sakna det.

    Prompt-only runs (utan ``--discovery``) genererar ingen decision i
    v1; followup ska inte uppfinna en.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.prompt_to_project_input import generate, generate_followup

    generate(
        "elektriker Malmö",
        output_dir=tmp_path,
        site_id="el-malmo",
        project_id="stable-project",
    )

    _, v2_meta, _, _ = generate_followup(
        "lägg till priser",
        output_dir=tmp_path,
        site_id="el-malmo",
    )
    assert "discoveryDecision" not in v2_meta


@pytest.mark.tooling
def test_blog_uses_fallback_status_not_active() -> None:
    """R1 #3 + R3 #5: blog markeras fallback eftersom ingen native
    magasin-scaffold finns i scaffold-contract. Resolvern returnerar
    selectionSource=fallback och en category-fallback-warning.
    """
    payload = _payload("blog")
    _, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )
    assert decision.selectionSource == "fallback"
    codes = {w.code for w in decision.fallbackWarnings}
    assert "category-fallback" in codes


# ---------------------------------------------------------------------------
# Review-fix-pass round 3 på PR #34
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_multi_select_within_same_branch_prefers_active_over_planned() -> None:
    """R1 #2 (round 3): ``salon`` (active) och ``healthcare`` (planned)
    delar branch ``salon``. Tie-break på supportStatus måste välja
    active så scaffold/variant inte tappas till planned-kategori bara
    pga inmatningsordningen.
    """
    # Båda ordningarna ska ge salon som primary.
    for order in (["salon", "healthcare"], ["healthcare", "salon"]):
        payload = {
            "schemaVersion": 1,
            "rawPrompt": "test",
            "contentBranch": "salon",
            "scaffoldHint": "local-service-business",
            "answers": {"siteType": order},
        }
        _, decision = resolve_discovery(
            raw_prompt="test",
            payload=payload,
            project_input_candidate=_candidate_project_input(),
        )
        # Salon är active mot local-service-business (target == active).
        assert decision.selectedScaffoldId == "local-service-business"
        assert decision.targetScaffoldId == "local-service-business", (
            f"Med ordning {order} föll resolvern på healthcare (planned) "
            "istället för salon (active)."
        )
        assert decision.selectionSource == "taxonomy"


@pytest.mark.tooling
def test_disabled_category_bypasses_taxonomy_scaffold() -> None:
    """R2 P2 (round 3): disabled-kategori får inte pinna icke-byggbar
    scaffold via ``runtime_scaffold_id``. Resolvern behandlar disabled
    som om kategorin är okänd — varning loggas, men scaffold/variant
    faller till scaffoldHint eller candidate Project Input.
    """
    from packages.generation.discovery.taxonomy import (
        DiscoveryTaxonomy,
        TaxonomyCategory,
    )

    # Bygg en syntetisk taxonomy där "broken-category" är disabled och
    # pekar mot en icke-byggbar scaffold.
    fake_taxonomy = DiscoveryTaxonomy(
        policy_id="discovery-taxonomy.test",
        version=1,
        categories={
            "broken-category": TaxonomyCategory(
                id="broken-category",
                labelSv="Broken",
                contentBranch="business",
                supportStatus="disabled",
                targetScaffoldId="restaurant-hospitality",  # icke-runtime
                defaultVariantId="non-existent-variant",
                requestedCapabilities=[],
                candidateDossiers=[],
                rationale="test only",
            )
        },
        branch_priority={"business": 12},
    )

    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "business",
        "scaffoldHint": "ecommerce-lite",  # runtime-OK
        "answers": {"siteType": ["broken-category"]},
    }
    candidate = _candidate_project_input()
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
        taxonomy=fake_taxonomy,
    )
    # Resolvern ska inte ha pinnat den icke-byggbara scaffolden.
    assert project_input["scaffoldId"] != "restaurant-hospitality"
    assert project_input["variantId"] != "non-existent-variant"
    # scaffoldHint hoppar in eftersom primary_category är disabled →
    # behandlad som None.
    assert project_input["scaffoldId"] == "ecommerce-lite"
    assert decision.selectionSource == "wizard"
    # category-disabled warning ska fortfarande loggas.
    codes = {w.code for w in decision.fallbackWarnings}
    assert "category-disabled" in codes
    # Disabled kräver alltid review.
    assert decision.operatorReviewRequired is True


@pytest.mark.tooling
def test_disabled_category_without_scaffold_hint_keeps_candidate() -> None:
    """När disabled-kategori används utan användbar scaffoldHint
    behåller resolvern Project Input candidate-scaffolden (samma
    kontrakt som okänd kategori).
    """
    from packages.generation.discovery.taxonomy import (
        DiscoveryTaxonomy,
        TaxonomyCategory,
    )

    fake_taxonomy = DiscoveryTaxonomy(
        policy_id="discovery-taxonomy.test",
        version=1,
        categories={
            "broken-category": TaxonomyCategory(
                id="broken-category",
                labelSv="Broken",
                contentBranch="business",
                supportStatus="disabled",
                targetScaffoldId="restaurant-hospitality",
                defaultVariantId="non-existent-variant",
                requestedCapabilities=[],
                candidateDossiers=[],
                rationale="test only",
            )
        },
        branch_priority={"business": 12},
    )

    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "business",
        "answers": {"siteType": ["broken-category"]},
        # ingen scaffoldHint
    }
    candidate = _candidate_project_input()
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate,
        taxonomy=fake_taxonomy,
    )
    assert project_input["scaffoldId"] == candidate["scaffoldId"]
    assert project_input["variantId"] == candidate["variantId"]
    assert decision.selectionSource == "default"
    codes = {w.code for w in decision.fallbackWarnings}
    assert "category-disabled" in codes
    assert decision.operatorReviewRequired is True


@pytest.mark.tooling
def test_multi_select_with_disabled_secondary_still_triggers_review() -> None:
    """R1 round 4: ``category-disabled`` ska trigga ``operatorReviewRequired``
    även när primary_category vann tie-break som active.

    ``["good-cat" (active), "broken-cat" (disabled)]`` gav tidigare
    ``operatorReviewRequired=False`` eftersom ``primary_disabled``-grenen
    bara kollade om resolverns slutgiltiga primary var disabled — inte
    om någon kategori i multi-select-listan loggade en
    ``category-disabled``-warning. Fixen läser warning-listan direkt så
    review krävs oavsett vilken position den disablade kategorin hade.
    """
    from packages.generation.discovery.taxonomy import (
        DiscoveryTaxonomy,
        TaxonomyCategory,
    )

    fake_taxonomy = DiscoveryTaxonomy(
        policy_id="discovery-taxonomy.test",
        version=1,
        categories={
            "good-cat": TaxonomyCategory(
                id="good-cat",
                labelSv="Good",
                contentBranch="business",
                supportStatus="active",
                targetScaffoldId="local-service-business",
                activeScaffoldId="local-service-business",
                defaultVariantId="nordic-trust",
                expectedStarterId="marketing-base",
                requestedCapabilities=[],
                candidateDossiers=[],
                rationale="active",
            ),
            "broken-cat": TaxonomyCategory(
                id="broken-cat",
                labelSv="Broken",
                contentBranch="business",
                supportStatus="disabled",
                targetScaffoldId="restaurant-hospitality",
                defaultVariantId="non-existent",
                requestedCapabilities=[],
                candidateDossiers=[],
                rationale="disabled",
            ),
        },
        branch_priority={"business": 12},
    )

    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "business",
        "answers": {"siteType": ["good-cat", "broken-cat"]},
    }
    _, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=_candidate_project_input(),
        taxonomy=fake_taxonomy,
    )
    # Active vinner tie-break — primary blev good-cat.
    assert decision.selectedScaffoldId == "local-service-business"
    assert decision.selectionSource == "taxonomy"
    # Men disabled-warningen från broken-cat ska fortfarande trigga review.
    codes = {w.code for w in decision.fallbackWarnings}
    assert "category-disabled" in codes
    assert decision.operatorReviewRequired is True, (
        "category-disabled-warning för en sekundär multi-select-entry "
        "ska trigga operatorReviewRequired oavsett om disabled-kategorin "
        "blev primary eller inte."
    )


@pytest.mark.tooling
def test_followup_marks_inherited_decision_with_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R1 #5 (round 3): ärvd ``discoveryDecision`` ska markeras med
    ``inheritedFromVersion`` så Backoffice/Doctor skiljer initial
    decision från aktuell provenance för v2+-fält.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.prompt_to_project_input import generate, generate_followup

    discovery_payload = {
        "schemaVersion": 1,
        "rawPrompt": "webshop som säljer keramik",
        "contentBranch": "ecommerce",
        "scaffoldHint": "ecommerce-lite",
        "answers": {
            "siteType": ["ecommerce"],
            "companyName": "Keramikbutiken AB",
        },
    }
    _, v1_meta, _, _ = generate(
        "webshop som säljer keramik",
        output_dir=tmp_path,
        site_id="keramik-shop",
        project_id="stable-project",
        discovery=discovery_payload,
    )
    # v1 är färsk så får inte inheritedFromVersion.
    assert "inheritedFromVersion" not in v1_meta["discoveryDecision"]

    _, v2_meta, _, _ = generate_followup(
        "lägg till en blogg-sektion",
        output_dir=tmp_path,
        site_id="keramik-shop",
    )
    v2_decision = v2_meta["discoveryDecision"]
    assert v2_decision["inheritedFromVersion"] == 1

    # Kedja: v3 ärver från v2:s discoveryDecision (som redan har
    # inheritedFromVersion=1). Värdet ska bevaras till första
    # producerande versionen, inte föregående version.
    _, v3_meta, _, _ = generate_followup(
        "lägg till priser",
        output_dir=tmp_path,
        site_id="keramik-shop",
    )
    v3_decision = v3_meta["discoveryDecision"]
    assert v3_decision["inheritedFromVersion"] == 1


@pytest.mark.tooling
def test_inherited_decision_validates_against_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, decision_schema: dict
) -> None:
    """``inheritedFromVersion`` är optional men måste validera mot
    discovery-decision.schema.json."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.prompt_to_project_input import generate, generate_followup

    generate(
        "test",
        output_dir=tmp_path,
        site_id="schema-test",
        project_id="stable",
        discovery={
            "schemaVersion": 1,
            "rawPrompt": "test",
            "contentBranch": "business",
            "scaffoldHint": "local-service-business",
            "answers": {"siteType": ["business"]},
        },
    )
    _, v2_meta, _, _ = generate_followup(
        "v2",
        output_dir=tmp_path,
        site_id="schema-test",
    )
    jsonschema.Draft202012Validator(decision_schema).validate(
        v2_meta["discoveryDecision"]
    )
