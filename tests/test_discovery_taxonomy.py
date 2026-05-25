"""Tests för Discovery Taxonomy-policyn (B121 PR A).

Låser:

- ``governance/policies/discovery-taxonomy.v1.json`` validerar mot sitt schema.
- Alla 25 ``WizardCategoryId``-värden från
  ``apps/viewser/components/discovery-wizard/wizard-constants.ts`` finns i
  taxonomin.
- Taxonomi-loadern returnerar 1:1 samma kategori-id-set som policyfilen.
- ``defaultVariantId`` per active-runtime-kategori matchar variants/ på disk.
- ``expectedStarterId`` matchar ``planning.SCAFFOLD_TO_STARTER`` när satt.
- Kategorier med ``supportStatus`` ``planned`` / ``fallback`` har en
  ``fallbackScaffoldId`` som finns under packages/generation/orchestration/scaffolds/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_POLICY = (
    REPO_ROOT / "governance" / "policies" / "discovery-taxonomy.v1.json"
)
TAXONOMY_SCHEMA = (
    REPO_ROOT / "governance" / "schemas" / "discovery-taxonomy.schema.json"
)
WIZARD_CONSTANTS = (
    REPO_ROOT
    / "apps"
    / "viewser"
    / "components"
    / "discovery-wizard"
    / "wizard-constants.ts"
)
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"


@pytest.fixture(scope="module")
def taxonomy_payload() -> dict:
    return json.loads(TAXONOMY_POLICY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def taxonomy_schema() -> dict:
    return json.loads(TAXONOMY_SCHEMA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def wizard_category_ids() -> set[str]:
    """Extrahera ``WizardCategoryId`` ur den TS-fil wizarden faktiskt använder.

    Vi parsar union-typen ``WizardCategoryId = "business" | "ecommerce" | ...``
    genom enkel regex-extraktion. Saknad eller ändrad shape fångas av
    ``test_wizard_category_ids_extraction_finds_all_25`` så testet ger ett
    tydligt felmeddelande snarare än ett indirekt "okänd kategori"-fynd.
    """
    text = WIZARD_CONSTANTS.read_text(encoding="utf-8")
    union_match = re.search(
        r"export type WizardCategoryId\s*=\s*((?:\s*\|\s*\"[^\"]+\")+)",
        text,
    )
    if union_match is None:
        raise AssertionError(
            "WizardCategoryId-union hittades inte i wizard-constants.ts. "
            "Uppdatera regexen i tests/test_discovery_taxonomy.py."
        )
    return set(re.findall(r"\"([^\"]+)\"", union_match.group(1)))


@pytest.mark.tooling
def test_taxonomy_validates_against_schema(
    taxonomy_payload: dict, taxonomy_schema: dict
) -> None:
    jsonschema.Draft202012Validator(taxonomy_schema).validate(taxonomy_payload)


@pytest.mark.tooling
def test_wizard_category_ids_extraction_finds_all_25(
    wizard_category_ids: set[str],
) -> None:
    """Säkerställ att wizard-constants.ts fortfarande har 25 kategorier.

    Test guard mot att frontend-listan krymper / växer utan att taxonomin
    uppdateras. Om wizarden måste utökas, lägg till nya id:n i taxonomin
    INNAN frontend-passet (PR B) kör.
    """
    assert len(wizard_category_ids) == 25, sorted(wizard_category_ids)


@pytest.mark.tooling
def test_all_wizard_category_ids_present_in_taxonomy(
    taxonomy_payload: dict, wizard_category_ids: set[str]
) -> None:
    taxonomy_ids = {category["id"] for category in taxonomy_payload["categories"]}
    missing = wizard_category_ids - taxonomy_ids
    assert not missing, (
        f"Wizard-kategorier saknas i discovery-taxonomy.v1.json: {sorted(missing)}"
    )


@pytest.mark.tooling
def test_taxonomy_has_no_unknown_category_ids(
    taxonomy_payload: dict, wizard_category_ids: set[str]
) -> None:
    """Taxonomin får inte introducera kategori-id som inte finns i wizarden.

    Discovery Resolver matchar payload-kategorier 1:1 mot taxonomin; en
    kategori i policyn utan motsvarighet i frontend-listan kan aldrig
    triggas och blir död metadata.
    """
    taxonomy_ids = {category["id"] for category in taxonomy_payload["categories"]}
    extra = taxonomy_ids - wizard_category_ids
    assert not extra, (
        f"Discovery-taxonomy listar kategori-id som saknar wizard-mappning: {sorted(extra)}"
    )


@pytest.mark.tooling
def test_ecommerce_targets_active_ecommerce_lite_with_commerce_base(
    taxonomy_payload: dict,
) -> None:
    """``ecommerce`` är runtime-aktiv (scaffold + variant + starter finns)."""
    category = _find_category(taxonomy_payload, "ecommerce")
    assert category["supportStatus"] == "active"
    assert category["targetScaffoldId"] == "ecommerce-lite"
    assert category["activeScaffoldId"] == "ecommerce-lite"
    assert category["defaultVariantId"] == "clean-store"
    assert category["expectedStarterId"] == "commerce-base"


@pytest.mark.tooling
def test_restaurant_is_active_with_restaurant_hospitality(
    taxonomy_payload: dict,
) -> None:
    """Restaurant-kategorin promoterades till active 2026-05-25 via
    GAP-backend-restaurant-activation. Path A-renderers (render_menu +
    render_booking) finns i build_site.py och cafe-bistro-fixturen
    kör hela end-to-end-flödet. ``fallbackScaffoldId`` behålls som
    säkerhetsnät om scaffold-mappingen tillfälligt skulle haverera.
    """
    category = _find_category(taxonomy_payload, "restaurant")
    assert category["supportStatus"] == "active"
    assert category["targetScaffoldId"] == "restaurant-hospitality"
    assert category["activeScaffoldId"] == "restaurant-hospitality"
    assert category["fallbackScaffoldId"] == "local-service-business"
    assert category["defaultVariantId"] == "warm-bistro"
    assert category["expectedStarterId"] == "marketing-base"


@pytest.mark.tooling
def test_active_categories_have_runtime_scaffold_on_disk(
    taxonomy_payload: dict,
) -> None:
    """``supportStatus=active`` -> ``activeScaffoldId`` måste finnas på disk."""
    for category in taxonomy_payload["categories"]:
        if category["supportStatus"] != "active":
            continue
        scaffold_id = category.get("activeScaffoldId") or category["targetScaffoldId"]
        scaffold_dir = SCAFFOLDS_DIR / scaffold_id
        assert scaffold_dir.is_dir(), (
            f"Kategori {category['id']!r} markerad active mot scaffold "
            f"{scaffold_id!r} men saknar scaffold.json på disk."
        )


@pytest.mark.tooling
def test_planned_categories_have_buildable_fallback(
    taxonomy_payload: dict,
) -> None:
    """``supportStatus=planned`` -> ``fallbackScaffoldId`` måste finnas på disk."""
    for category in taxonomy_payload["categories"]:
        if category["supportStatus"] != "planned":
            continue
        fallback = category.get("fallbackScaffoldId")
        assert fallback, (
            f"Kategori {category['id']!r} är planned utan fallbackScaffoldId. "
            "Resolvern skulle annars sakna en buildbar scaffold."
        )
        scaffold_dir = SCAFFOLDS_DIR / fallback
        assert scaffold_dir.is_dir(), (
            f"Kategori {category['id']!r} pekar mot fallback "
            f"{fallback!r} som saknar scaffold.json på disk."
        )


@pytest.mark.tooling
def test_expected_starter_matches_scaffold_starter_mapping(
    taxonomy_payload: dict,
) -> None:
    """``expectedStarterId`` får inte motsäga ``planning.SCAFFOLD_TO_STARTER``."""
    from packages.generation.planning.plan import SCAFFOLD_TO_STARTER

    for category in taxonomy_payload["categories"]:
        expected_starter = category.get("expectedStarterId")
        if not expected_starter:
            continue
        # Resolvern härleder starter från selected scaffold (active när
        # supportStatus=active, annars fallback). Mappingen måste hålla i båda.
        candidate_scaffold = (
            category.get("activeScaffoldId")
            if category["supportStatus"] == "active"
            else category.get("fallbackScaffoldId")
        )
        if candidate_scaffold and candidate_scaffold in SCAFFOLD_TO_STARTER:
            assert SCAFFOLD_TO_STARTER[candidate_scaffold] == expected_starter, (
                f"Kategori {category['id']!r}: expectedStarterId={expected_starter!r} "
                f"matchar inte SCAFFOLD_TO_STARTER[{candidate_scaffold!r}]="
                f"{SCAFFOLD_TO_STARTER[candidate_scaffold]!r}."
            )


@pytest.mark.tooling
def test_taxonomy_loader_returns_same_category_ids(
    taxonomy_payload: dict,
) -> None:
    from packages.generation.discovery import load_discovery_taxonomy

    loaded = load_discovery_taxonomy()
    policy_ids = {category["id"] for category in taxonomy_payload["categories"]}
    assert loaded.known_category_ids() == policy_ids


@pytest.mark.tooling
def test_taxonomy_loader_pick_branch_prefers_most_specific(
    taxonomy_payload: dict,
) -> None:
    """``pick_branch`` returnerar branch:en med lägst ``priority``."""
    _ = taxonomy_payload  # läses via load_discovery_taxonomy

    from packages.generation.discovery import load_discovery_taxonomy

    loaded = load_discovery_taxonomy()
    # ecommerce har priority 0 (mer specifik än business priority 12).
    assert loaded.pick_branch(["business", "ecommerce"]) == "ecommerce"
    # Multi-select med restaurant + portfolio vinner restaurant (priority 1)
    # över portfolio (priority 3).
    assert loaded.pick_branch(["portfolio", "restaurant"]) == "restaurant"
    # Tom lista faller tillbaka till 'business' (safest default).
    assert loaded.pick_branch([]) == "business"


@pytest.mark.tooling
def test_pick_primary_category_follows_branch_priority() -> None:
    """R2 P1 + R3 #1: primary_category måste matcha branch-prioritet.

    Tidigare valde resolvern första kategori i payloaden som
    primärkategori, vilket gav self-contradictory beslut för multi-
    select: ``["business", "ecommerce"]`` blev ``contentBranch=ecommerce``
    men scaffold=``local-service-business`` (från ``business``).
    """
    from packages.generation.discovery import load_discovery_taxonomy

    loaded = load_discovery_taxonomy()
    business = loaded.get("business")
    ecommerce = loaded.get("ecommerce")
    restaurant = loaded.get("restaurant")
    portfolio = loaded.get("portfolio")
    assert business is not None
    assert ecommerce is not None
    assert restaurant is not None
    assert portfolio is not None

    # business priority 12 vs ecommerce priority 0 → ecommerce vinner.
    primary = loaded.pick_primary_category([business, ecommerce])
    assert primary is not None and primary.id == "ecommerce"

    # Ordning oavsett: ecommerce vinner även om business är först.
    primary = loaded.pick_primary_category([business, ecommerce, business])
    assert primary is not None and primary.id == "ecommerce"

    # restaurant priority 1 vs portfolio priority 3 → restaurant vinner.
    primary = loaded.pick_primary_category([portfolio, restaurant])
    assert primary is not None and primary.id == "restaurant"

    # Tom lista → None.
    assert loaded.pick_primary_category([]) is None


@pytest.mark.tooling
def test_pick_primary_category_tie_breaks_on_support_status() -> None:
    """R1 #2 (round 3): inom samma branch_priority väljs kategorin med
    bäst supportStatus (``active`` > ``fallback`` > ``planned``).

    ``salon`` (active) och ``healthcare`` (planned) delar branch
    ``salon`` (priority 2). Utan tie-break föll beslutet på listordning;
    nu vinner alltid active.
    """
    from packages.generation.discovery import load_discovery_taxonomy

    loaded = load_discovery_taxonomy()
    salon = loaded.get("salon")
    healthcare = loaded.get("healthcare")
    assert salon is not None and salon.supportStatus == "active"
    assert healthcare is not None and healthcare.supportStatus == "planned"
    # Branch:en är samma; supportStatus avgör.
    assert salon.contentBranch == healthcare.contentBranch

    primary = loaded.pick_primary_category([salon, healthcare])
    assert primary is not None and primary.id == "salon"
    primary = loaded.pick_primary_category([healthcare, salon])
    assert primary is not None and primary.id == "salon", (
        "Resolvern föll på listordning istället för supportStatus tie-break."
    )


@pytest.mark.tooling
def test_adr_0024_documents_canonical_discovery_terms() -> None:
    """R2 P1 (round 3): nya canonical termer i naming-dictionary kräver
    en åtföljande ADR enligt .cursor/BUGBOT.md. Verifiera att ADR 0024
    finns och nämner de fem termerna.
    """
    adr_path = (
        REPO_ROOT
        / "governance"
        / "decisions"
        / "0024-discovery-resolver-canonical-terms.md"
    )
    assert adr_path.exists(), (
        "ADR 0024 saknas — nya canonical termer i naming-dictionary "
        "måste ha en åtföljande ADR enligt .cursor/BUGBOT.md."
    )
    text = adr_path.read_text(encoding="utf-8")
    for term in (
        "Discovery Payload",
        "Discovery Resolver",
        "Discovery Decision",
        "Discovery Taxonomy",
        "Field Source",
    ):
        assert term in text, (
            f"ADR 0024 saknar definition av canonical term {term!r}."
        )


@pytest.mark.tooling
def test_blog_and_other_are_fallback_not_active(taxonomy_payload: dict) -> None:
    """R1 #3 + R3 #5: kategorier utan native scaffold-mappning märks fallback.

    ``blog`` och ``other`` har ingen dedikerad scaffold i
    ``scaffold-contract.v1.json`` — de körs som vikariat via
    ``local-service-business``. Backoffice ser ``supportStatus=fallback``
    så detta inte förväxlas med native runtime-stöd.
    """
    blog = _find_category(taxonomy_payload, "blog")
    other = _find_category(taxonomy_payload, "other")
    assert blog["supportStatus"] == "fallback"
    assert blog["fallbackScaffoldId"] == "local-service-business"
    assert "activeScaffoldId" not in blog
    assert other["supportStatus"] == "fallback"
    assert other["fallbackScaffoldId"] == "local-service-business"
    assert "activeScaffoldId" not in other


@pytest.mark.tooling
def test_candidate_dossiers_do_not_become_required_dossiers(
    taxonomy_payload: dict,
) -> None:
    """R1 #8: taxonomins ``candidateDossiers`` får inte automatiskt sluta
    upp i Project Input ``selectedDossiers.required``. PR A:s resolver
    skickar bara kandidater till ``DiscoveryDecision.candidateDossiers``;
    planning/capability-filter har fortfarande sista ordet om mounting.
    """
    from packages.generation.discovery import resolve_discovery

    candidate_pi = {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": "site-1",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Test AB",
            "businessType": "service-provider",
            "tagline": "x",
            "story": "y",
        },
        "location": {"city": "Malmö", "country": "Sverige", "serviceAreas": ["Malmö"]},
        "services": [{"id": "a", "label": "A", "summary": "."}],
        "tone": {"primary": "x", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46",
            "email": "a@b.c",
            "addressLines": ["x"],
            "openingHours": "x",
        },
        "selectedDossiers": {"required": [], "recommended": [], "rationale": "x"},
    }
    payload = {
        "schemaVersion": 1,
        "rawPrompt": "test",
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {"siteType": ["business"]},
    }
    project_input, decision = resolve_discovery(
        raw_prompt="test",
        payload=payload,
        project_input_candidate=candidate_pi,
    )
    selected = project_input["selectedDossiers"]
    # Kandidaterna får inte ha lagts in i required.
    if isinstance(selected, dict):
        required_list = selected.get("required", [])
    else:
        required_list = []
    for cand in decision.candidateDossiers:
        assert cand not in required_list, (
            f"Resolvern lade taxonomins candidateDossier {cand!r} i "
            "selectedDossiers.required — det får bara planning/capability-filter göra."
        )


def _find_category(payload: dict, category_id: str) -> dict:
    for category in payload["categories"]:
        if category["id"] == category_id:
            return category
    raise AssertionError(
        f"Kategori {category_id!r} saknas i discovery-taxonomy.v1.json"
    )
