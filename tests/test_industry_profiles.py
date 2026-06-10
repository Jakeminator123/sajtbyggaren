"""Tester för Industry Profiles-policyn och dess loader (ADR 0045).

Profilernas hårda kontrakt:

1. Alla 87 SNI-huvudgrupper har en profil (full branschberedskap).
2. ``wizardCategoryId`` i profilen är identisk med vad
   ``resolve_sni_discovery_category`` ger för samma huvudgrupp — en
   profil kan inte smyg-omdirigera en bransch till en annan kategori.
3. ``extraCapabilities`` använder bara canonical slugs ur
   ``capability-map.v1.json``.
4. ``primaryCta`` är en av wizardens CTA-etiketter så prefill kan sätta
   ``answers.primaryCta`` utan översättningstabell.
5. Schemat avvisar direktvals-fält (starterId/scaffoldId/variantId/...).
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

from packages.generation.discovery import industry_profiles as profiles_mod  # noqa: E402
from packages.generation.discovery import sni_map as sni  # noqa: E402
from packages.generation.discovery.resolve import (  # noqa: E402
    get_cta_to_conversion_goal_mapping,
)

POLICY_PATH = REPO_ROOT / "governance" / "policies" / "industry-profiles.v1.json"
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "industry-profiles.schema.json"
CAPABILITY_MAP_PATH = (
    REPO_ROOT / "governance" / "policies" / "capability-map.v1.json"
)
SNI_TAXONOMY_PATH = REPO_ROOT / "data" / "taxonomies" / "sni" / "sni-2025.v1.json"


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


def test_every_sni_division_has_profile() -> None:
    items = json.loads(SNI_TAXONOMY_PATH.read_text(encoding="utf-8"))["items"]
    division_codes = {i["code"] for i in items if i["level"] == "division"}
    profiled = {row["sniCode"] for row in _policy()["divisionProfiles"]}

    assert division_codes - profiled == set()
    assert profiled - division_codes == set()


def test_profile_category_matches_sni_map_resolution() -> None:
    """Kontrakt 2: profilen får inte omdirigera kategorivalet."""
    discovery_map = sni.load_sni_discovery_map()
    mismatches: list[tuple[str, str, str | None]] = []
    for row in _policy()["divisionProfiles"]:
        match = sni.resolve_sni_discovery_category(
            row["sniCode"], sni_map=discovery_map
        )
        if match.wizardCategoryId != row["wizardCategoryId"]:
            mismatches.append(
                (row["sniCode"], row["wizardCategoryId"], match.wizardCategoryId)
            )

    assert mismatches == []


def test_extra_capabilities_exist_in_capability_map() -> None:
    capability_map = json.loads(
        CAPABILITY_MAP_PATH.read_text(encoding="utf-8")
    )["capabilities"]
    unknown: list[tuple[str, str]] = []
    for row in _policy()["divisionProfiles"]:
        for slug in row.get("extraCapabilities", []):
            if slug not in capability_map:
                unknown.append((row["sniCode"], slug))

    assert unknown == []


def test_primary_cta_is_known_wizard_cta() -> None:
    known_ctas = set(get_cta_to_conversion_goal_mapping().keys())
    bad = [
        (row["sniCode"], row["primaryCta"])
        for row in _policy()["divisionProfiles"]
        if row["primaryCta"] not in known_ctas
    ]

    assert bad == []


def test_profile_ids_are_stable_and_unique() -> None:
    rows = _policy()["divisionProfiles"]
    ids = [row["profileId"] for row in rows]

    assert len(ids) == len(set(ids))
    for row in rows:
        assert row["profileId"] == f"sni-{row['sniCode']}"


@pytest.mark.parametrize(
    "forbidden_field",
    ["starterId", "scaffoldId", "variantId", "dossierId", "selectedDossiers"],
)
def test_schema_rejects_direct_pick_fields(forbidden_field: str) -> None:
    payload = copy.deepcopy(_policy())
    payload["divisionProfiles"][0][forbidden_field] = "some-direct-pick"

    validator = Draft202012Validator(_schema())
    errors = list(validator.iter_errors(payload))

    assert errors


# ---------------------------------------------------------------------------
# Loader / resolver helper
# ---------------------------------------------------------------------------


def test_load_industry_profiles_indexes_all_divisions() -> None:
    policy = profiles_mod.load_industry_profiles()

    assert policy.policy_id == "industry-profiles.v1"
    assert len(policy.profiles) == 87
    assert policy.get("41") is not None
    assert policy.get("41").wizardCategoryId == "construction"


@pytest.mark.parametrize(
    "value,expected_division",
    [
        ("41", "41"),
        ("41.2", "41"),
        ("43210", "43"),
        ("96.021", "96"),
        ("56100", "56"),
    ],
)
def test_resolve_industry_profile_matches_division(
    value: str, expected_division: str
) -> None:
    profile = profiles_mod.resolve_industry_profile(value)

    assert profile is not None
    assert profile.sniCode == expected_division


@pytest.mark.parametrize("value", ["", "   ", None, "A", "4", "44", "abc"])
def test_resolve_industry_profile_unknown_returns_none(value: str | None) -> None:
    assert profiles_mod.resolve_industry_profile(value) is None


def test_profile_to_dict_has_no_direct_pick_fields() -> None:
    profile = profiles_mod.resolve_industry_profile("41")
    assert profile is not None
    payload = profiles_mod.profile_to_dict(profile)

    for forbidden in (
        "starterId",
        "scaffoldId",
        "variantId",
        "dossierId",
        "selectedDossiers",
    ):
        assert forbidden not in payload
