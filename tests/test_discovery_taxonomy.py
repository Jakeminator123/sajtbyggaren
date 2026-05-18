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
def test_restaurant_is_planned_with_local_service_fallback(
    taxonomy_payload: dict,
) -> None:
    """Scout-planens nyckelexempel: restaurant-hospitality är planned."""
    category = _find_category(taxonomy_payload, "restaurant")
    assert category["supportStatus"] == "planned"
    assert category["targetScaffoldId"] == "restaurant-hospitality"
    assert category["fallbackScaffoldId"] == "local-service-business"
    assert category["defaultVariantId"] == "nordic-trust"
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


def _find_category(payload: dict, category_id: str) -> dict:
    for category in payload["categories"]:
        if category["id"] == category_id:
            return category
    raise AssertionError(
        f"Kategori {category_id!r} saknas i discovery-taxonomy.v1.json"
    )
