"""Regression tests for B143 Intent Guard slug-aware mismatch detection.

The intent guard compares the wizard's ``categoryIds`` (from
``discoveryDecision`` on prompt_meta) against ``site_brief.businessTypeGuess``
and ``site_brief.servicesMentioned``. When the two signals point at
incompatible industry buckets a warning is emitted.
"""

from __future__ import annotations

from scripts.build_site import _intent_guard_warnings


def _brief(business_type: str, services: list[str] | None = None) -> dict:
    return {
        "businessTypeGuess": business_type,
        "servicesMentioned": services if services is not None else [],
    }


def _meta(category_ids: list[str]) -> dict:
    return {"discoveryDecision": {"categoryIds": category_ids}}


# ------------------------------------------------------------------
# Cases that MUST produce a warning
# ------------------------------------------------------------------


class TestConflictCases:
    """Scenarios where wizard category and businessTypeGuess conflict."""

    def test_fitness_vs_restaurant(self) -> None:
        warnings = _intent_guard_warnings(
            _brief("restaurant"), _meta(["fitness"])
        )
        assert len(warnings) == 1
        w = warnings[0]
        assert w["code"] == "intent-guard-mismatch"
        assert w["categoryBucket"] == "fitness"
        assert w["slugBucket"] == "food"

    def test_beauty_vs_electrician(self) -> None:
        warnings = _intent_guard_warnings(
            _brief("electrician"), _meta(["salon"])
        )
        assert len(warnings) == 1
        w = warnings[0]
        assert w["code"] == "intent-guard-mismatch"
        assert w["categoryBucket"] == "beauty"
        assert w["slugBucket"] == "construction"

    def test_construction_vs_hairdresser(self) -> None:
        warnings = _intent_guard_warnings(
            _brief("hairdresser"), _meta(["construction"])
        )
        assert len(warnings) == 1
        w = warnings[0]
        assert w["code"] == "intent-guard-mismatch"
        assert w["categoryBucket"] == "construction"
        assert w["slugBucket"] == "beauty"

    def test_construction_vs_hair_salon(self) -> None:
        warnings = _intent_guard_warnings(
            _brief("hair-salon"), _meta(["construction"])
        )
        assert len(warnings) == 1
        w = warnings[0]
        assert w["code"] == "intent-guard-mismatch"
        assert w["categoryBucket"] == "construction"
        assert w["slugBucket"] == "beauty"

    def test_food_category_vs_mat_services(self) -> None:
        """Existing sköldpaddssoppa/mat-case: restaurant category with
        services suggesting a completely different industry."""
        warnings = _intent_guard_warnings(
            _brief("restaurant", ["sköldpaddssoppa"]),
            _meta(["fitness"]),
        )
        assert len(warnings) == 1
        assert warnings[0]["slugBucket"] == "food"

    def test_fitness_vs_cafe(self) -> None:
        warnings = _intent_guard_warnings(
            _brief("cafe"), _meta(["fitness"])
        )
        assert len(warnings) == 1
        assert warnings[0]["slugBucket"] == "food"

    def test_beauty_vs_plumber(self) -> None:
        warnings = _intent_guard_warnings(
            _brief("plumber"), _meta(["salon"])
        )
        assert len(warnings) == 1
        assert warnings[0]["slugBucket"] == "construction"


# ------------------------------------------------------------------
# Cases that MUST be silent (consistent)
# ------------------------------------------------------------------


class TestConsistentCases:
    """Scenarios where category and businessTypeGuess are compatible."""

    def test_business_category_with_electrician(self) -> None:
        """Generic 'business' category does not conflict with any slug."""
        warnings = _intent_guard_warnings(
            _brief("electrician"), _meta(["business"])
        )
        assert warnings == []

    def test_construction_with_construction_slug(self) -> None:
        """construction + electrician is consistent."""
        warnings = _intent_guard_warnings(
            _brief("electrician"), _meta(["construction"])
        )
        assert warnings == []

    def test_construction_with_painter(self) -> None:
        warnings = _intent_guard_warnings(
            _brief("painter"), _meta(["construction"])
        )
        assert warnings == []

    def test_beauty_with_hairdresser(self) -> None:
        """salon category + hairdresser slug is consistent."""
        warnings = _intent_guard_warnings(
            _brief("hairdresser"), _meta(["salon"])
        )
        assert warnings == []

    def test_fitness_with_personal_trainer(self) -> None:
        warnings = _intent_guard_warnings(
            _brief("personal-trainer"), _meta(["fitness"])
        )
        assert warnings == []

    def test_restaurant_with_restaurant(self) -> None:
        warnings = _intent_guard_warnings(
            _brief("restaurant"), _meta(["restaurant"])
        )
        assert warnings == []

    def test_no_discovery_decision(self) -> None:
        """No discoveryDecision in prompt_meta - silent."""
        warnings = _intent_guard_warnings(
            _brief("restaurant"), {"someOtherField": True}
        )
        assert warnings == []

    def test_no_prompt_meta(self) -> None:
        """No prompt_meta at all - silent."""
        warnings = _intent_guard_warnings(_brief("restaurant"), None)
        assert warnings == []

    def test_empty_category_ids(self) -> None:
        """Empty categoryIds - silent."""
        warnings = _intent_guard_warnings(
            _brief("restaurant"),
            {"discoveryDecision": {"categoryIds": []}},
        )
        assert warnings == []

    def test_unknown_slug_is_silent(self) -> None:
        """A businessTypeGuess that maps to no known bucket - silent."""
        warnings = _intent_guard_warnings(
            _brief("consulting-firm"), _meta(["fitness"])
        )
        assert warnings == []

    def test_unknown_category_is_silent(self) -> None:
        """A categoryId not in the bucket map - silent."""
        warnings = _intent_guard_warnings(
            _brief("restaurant"), _meta(["unknown-category"])
        )
        assert warnings == []

    def test_empty_business_type(self) -> None:
        """Empty businessTypeGuess - silent."""
        warnings = _intent_guard_warnings(_brief(""), _meta(["fitness"]))
        assert warnings == []


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and robustness."""

    def test_services_mentioned_provides_bucket(self) -> None:
        """When businessTypeGuess is unmapped but servicesMentioned contains
        a mapped slug, the bucket is derived from services."""
        warnings = _intent_guard_warnings(
            _brief("unknown-type", ["electrician"]),
            _meta(["salon"]),
        )
        assert len(warnings) == 1
        assert warnings[0]["slugBucket"] == "construction"

    def test_case_insensitive_slug(self) -> None:
        """businessTypeGuess is normalized to lowercase."""
        warnings = _intent_guard_warnings(
            _brief("Restaurant"), _meta(["fitness"])
        )
        assert len(warnings) == 1

    def test_whitespace_trimmed(self) -> None:
        """Leading/trailing whitespace is stripped from slug."""
        warnings = _intent_guard_warnings(
            _brief("  restaurant  "), _meta(["fitness"])
        )
        assert len(warnings) == 1

    def test_multiple_categories_one_conflict(self) -> None:
        """Multiple categoryIds, only one conflicts - one warning."""
        warnings = _intent_guard_warnings(
            _brief("restaurant"), _meta(["business", "fitness"])
        )
        assert len(warnings) == 1
        assert warnings[0]["categoryId"] == "fitness"

    def test_multiple_categories_all_conflict(self) -> None:
        """Multiple conflicting categories - multiple warnings."""
        warnings = _intent_guard_warnings(
            _brief("restaurant"), _meta(["fitness", "construction"])
        )
        assert len(warnings) == 2
        codes = {w["categoryBucket"] for w in warnings}
        assert codes == {"fitness", "construction"}
