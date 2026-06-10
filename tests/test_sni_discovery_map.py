"""Tests for SNI Discovery Map policy, schema och resolver-helper.

Policyn (``governance/policies/sni-discovery-map.v1.json``) är
operatörens handstyrda översättning från SNI 2025-prefix till kandidat
``wizardCategoryId`` i Discovery Taxonomy. Schemats förbjudna direktvals-
fält och helperns ``unknown``-fallback är hårda kontrakt; testerna här
låser båda.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.discovery import sni_map as sni  # noqa: E402
from packages.generation.discovery.taxonomy import (  # noqa: E402
    load_discovery_taxonomy,
)

POLICY_PATH = REPO_ROOT / "governance" / "policies" / "sni-discovery-map.v1.json"
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "sni-discovery-map.schema.json"


def _policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Policy alignment
# ---------------------------------------------------------------------------


def test_policy_validates_against_schema() -> None:
    validator = Draft202012Validator(_schema())
    errors = sorted(validator.iter_errors(_policy()), key=lambda e: list(e.path))

    assert errors == []


def test_policy_categories_exist_in_discovery_taxonomy() -> None:
    policy = _policy()
    taxonomy = load_discovery_taxonomy()

    referenced = {
        row["wizardCategoryId"]
        for row in policy["divisionMappings"] + (policy.get("groupOverrides") or [])
    }
    missing = referenced - taxonomy.known_category_ids()

    assert missing == set(), (
        "SNI Discovery Map pekar mot wizardCategoryId-värden som saknas i "
        f"Discovery Taxonomy: {sorted(missing)}"
    )


def test_policy_codes_have_correct_length_per_level() -> None:
    policy = _policy()
    for row in policy["divisionMappings"]:
        assert row["sniCode"].isdigit()
        assert len(row["sniCode"]) == 2
    for row in policy.get("groupOverrides") or []:
        assert row["sniCode"].isdigit()
        assert len(row["sniCode"]) == 3


def test_policy_has_no_direct_starter_or_scaffold_overrides() -> None:
    policy = _policy()
    text = json.dumps(policy)
    forbidden_keys = ("starterId", "scaffoldId", "variantId", "dossierId", "selectedDossiers")
    for key in forbidden_keys:
        assert f'"{key}"' not in text, (
            f"SNI Discovery Map får inte innehålla {key}; den styr inte runtime."
        )


# ---------------------------------------------------------------------------
# Schema forbids direct-pick keys via additionalProperties: false + false-schemas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden_field",
    ["starterId", "scaffoldId", "variantId", "dossierId", "selectedDossiers"],
)
def test_schema_rejects_direct_pick_fields_in_divisions(forbidden_field: str) -> None:
    payload = copy.deepcopy(_policy())
    payload["divisionMappings"][0][forbidden_field] = "marketing-base"

    validator = Draft202012Validator(_schema())
    errors = list(validator.iter_errors(payload))

    assert errors, (
        f"Schemat ska reject:a {forbidden_field} i divisionMappings — SNI "
        "ska inte kunna sätta direktvärden för starter/scaffold/variant/dossier."
    )


@pytest.mark.parametrize(
    "forbidden_field",
    ["starterId", "scaffoldId", "variantId", "dossierId", "selectedDossiers"],
)
def test_schema_rejects_direct_pick_fields_in_group_overrides(forbidden_field: str) -> None:
    payload = copy.deepcopy(_policy())
    overrides = payload.get("groupOverrides") or []
    assert overrides, "Policyn ska ha minst en group override för testet att vara meningsfull."
    overrides[0][forbidden_field] = "marketing-base"

    validator = Draft202012Validator(_schema())
    errors = list(validator.iter_errors(payload))

    assert errors


def test_schema_rejects_bad_division_code_length() -> None:
    payload = copy.deepcopy(_policy())
    payload["divisionMappings"][0]["sniCode"] = "561"  # 3 siffror = group, inte division

    validator = Draft202012Validator(_schema())
    errors = list(validator.iter_errors(payload))

    assert errors


def test_schema_rejects_bad_group_override_code_length() -> None:
    payload = copy.deepcopy(_policy())
    payload["groupOverrides"][0]["sniCode"] = "5611"

    validator = Draft202012Validator(_schema())
    errors = list(validator.iter_errors(payload))

    assert errors


# ---------------------------------------------------------------------------
# Resolver helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("56", "56"),
        ("56.1", "561"),
        ("56.10", "5610"),
        ("56.100", "56100"),
        ("  56  ", "56"),
        ("a", "A"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_sni_code(value: str | None, expected: str) -> None:
    assert sni.normalize_sni_code(value) == expected


@pytest.mark.parametrize(
    "value,expected_category,expected_level,expected_prefix",
    [
        ("43", "construction", "division", "43"),
        ("432", "construction", "group", "432"),
        ("43210", "construction", "group", "432"),
        ("56", "restaurant", "division", "56"),
        ("561", "restaurant", "group", "561"),
        ("56100", "restaurant", "group", "561"),
        ("62", "tech", "division", "62"),
        ("620", "tech", "division", "62"),
        ("62010", "tech", "division", "62"),
        ("691", "legal", "group", "691"),
        ("692", "accounting", "group", "692"),
        ("742", "photo", "group", "742"),
        ("931", "fitness", "group", "931"),
        ("932", "event", "group", "932"),
        ("962", "salon", "group", "962"),
        ("953", "auto", "group", "953"),
        ("47", "ecommerce", "division", "47"),
        ("478", "auto", "group", "478"),
    ],
)
def test_resolver_matches_expected_categories(
    value: str,
    expected_category: str,
    expected_level: str,
    expected_prefix: str,
) -> None:
    match = sni.resolve_sni_discovery_category(value)

    assert match.wizardCategoryId == expected_category
    assert match.matchedLevel == expected_level
    assert match.matchedSniCode == expected_prefix


@pytest.mark.parametrize(
    "value",
    # "44" och "45" är hål i SNI 2025-serien (ingen huvudgrupp finns) —
    # de förblir unknown även efter v2:s fulla 87-gruppstäckning
    # (ADR 0045). "99" och "abc123" togs bort ur listan när v2 gav dem
    # träffar ("abc123" normaliseras till "123" och prefix-matchar 12).
    ["", "   ", "foo", "A", "Z", "00", "44", "45", None, "-1", "abc"],
)
def test_resolver_unknown_codes_return_match_without_exception(value: str | None) -> None:
    match = sni.resolve_sni_discovery_category(value)

    assert match.matchedLevel == "unknown"
    assert match.matchedSniCode is None
    assert match.wizardCategoryId is None
    assert match.confidence is None


def test_resolver_match_never_includes_direct_pick_fields() -> None:
    match = sni.resolve_sni_discovery_category("56100")
    payload = sni.match_to_dict(match)

    for forbidden in ("starterId", "scaffoldId", "variantId", "dossierId", "selectedDossiers"):
        assert forbidden not in payload, (
            f"Resolver-resultat får inte exponera {forbidden}."
        )


def test_resolver_match_preserves_source_policy_id() -> None:
    match = sni.resolve_sni_discovery_category("56")

    assert match.sourcePolicy == "sni-discovery-map.v1"


def test_load_sni_discovery_map_indexes_division_and_group_separately() -> None:
    discovery_map = sni.load_sni_discovery_map()

    assert "56" in discovery_map.divisions
    assert discovery_map.divisions["56"].level == "division"
    assert "562" not in discovery_map.divisions
    assert "561" in discovery_map.groups
    assert discovery_map.groups["561"].level == "group"


def test_resolver_more_specific_prefix_wins_over_division_default() -> None:
    """Group override 932→event ska slå division 93→fitness."""
    division = sni.resolve_sni_discovery_category("93")
    group = sni.resolve_sni_discovery_category("932")
    deep = sni.resolve_sni_discovery_category("93290")

    assert division.wizardCategoryId == "fitness"
    assert group.wizardCategoryId == "event"
    assert deep.wizardCategoryId == "event"


def test_resolver_falls_through_to_division_when_group_override_absent() -> None:
    """SNI 562 saknas i overrides → resolvern ska fortsätta till division 56."""
    match = sni.resolve_sni_discovery_category("562")

    assert match.matchedLevel == "division"
    assert match.matchedSniCode == "56"
    assert match.wizardCategoryId == "restaurant"


# ---------------------------------------------------------------------------
# Full täckning (ADR 0045)
# ---------------------------------------------------------------------------

SNI_TAXONOMY_PATH = (
    REPO_ROOT / "data" / "taxonomies" / "sni" / "sni-2025.v1.json"
)


def test_every_sni_code_resolves_to_known_category() -> None:
    """ADR 0045 fas 1: 0 unknown över hela SNI 2025-spegeln.

    Varje division/group/class/subclass-item (1 860 st; section-bokstäverna
    A-V är medvetet utanför — de bär ingen sifferkod att prefix-matcha) ska
    resolva till en wizardCategoryId som finns i discovery-taxonomy.v1.json.
    Testet är regressionen som hindrar att en framtida SNI-uppdatering
    (nya huvudgrupper) tyst återinför unknown-hål.
    """
    items = json.loads(SNI_TAXONOMY_PATH.read_text(encoding="utf-8"))["items"]
    taxonomy = load_discovery_taxonomy()
    known = taxonomy.known_category_ids()
    discovery_map = sni.load_sni_discovery_map()

    unresolved: list[tuple[str, str, str | None]] = []
    for item in items:
        if item["level"] == "section":
            continue
        match = sni.resolve_sni_discovery_category(
            item["code"], sni_map=discovery_map
        )
        if match.wizardCategoryId is None or match.wizardCategoryId not in known:
            unresolved.append((item["code"], item["labelSv"], match.wizardCategoryId))

    assert unresolved == [], (
        f"{len(unresolved)} SNI-koder saknar känd kategori, "
        f"första 10: {unresolved[:10]}"
    )


def test_every_sni_division_has_explicit_mapping() -> None:
    """Alla 87 huvudgrupper ska ha en explicit divisionMappings-rad.

    Täckningstestet ovan skulle tekniskt passera även om en division
    bara täcks via gruppnivå-overrides, men då resolvar själva
    divisionskoden (t.ex. "69") till unknown i Backoffice-diagnostiken.
    Explicit rad per huvudgrupp är därför ett separat kontrakt.
    """
    items = json.loads(SNI_TAXONOMY_PATH.read_text(encoding="utf-8"))["items"]
    division_codes = {i["code"] for i in items if i["level"] == "division"}
    mapped = {row["sniCode"] for row in _policy()["divisionMappings"]}

    assert division_codes - mapped == set()
    # Inga föräldralösa rader som pekar på huvudgrupper utanför SNI 2025.
    assert mapped - division_codes == set()
