"""Regression tests for B132 page-intent warnings.

Variant A is warning-only: wizard must-have pages may produce
``pageIntentWarnings`` when the selected scaffold does not emit the
corresponding route, but the builder must not create extra routes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from packages.generation.artifacts import validate_site_plan
from packages.generation.planning import produce_site_plan
from scripts.build_site import build
from scripts.prompt_to_project_input import generate, generate_followup


def _baseline_brief(**overrides: Any) -> dict[str, Any]:
    brief: dict[str, Any] = {
        "runId": "test-page-intent",
        "language": "sv",
        "rawPrompt": "Skapa hemsida för en lokal tjänstefirma",
        "tone": ["trustworthy"],
        "targetAudience": ["lokala kunder"],
        "requestedCapabilities": [],
        "conversionGoals": ["contact"],
        "servicesMentioned": [],
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "briefSource": "mock-no-key",
        "createdAt": "2026-05-19T12:00:00+00:00",
    }
    brief.update(overrides)
    return brief


def _local_service_pin() -> dict[str, str]:
    return {
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
    }


def _discovery_payload(must_have: list[str]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "rawPrompt": "Skapa hemsida för en lokal tjänstefirma",
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {
            "siteType": ["business"],
            "companyName": "Page Intent AB",
            "mustHave": must_have,
        },
    }


@pytest.mark.tooling
def test_page_intent_warns_for_unsupported_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B132 follow-up sprint 2026-05-21: wizard mustHave pages that the
    deterministic Builder cannot emit (booking integration, newsletter,
    blog) keep warning-only behaviour with a specific reason string so
    operators can tell "no integration yet" apart from "scaffold simply
    does not have this surface".
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = produce_site_plan(
        _baseline_brief(),
        run_id="page-intent-warn",
        pinned=_local_service_pin(),
        wizard_must_have=["Bokning online", "Blogg / Nyheter"],
    )

    warnings = result.site_plan["pageIntentWarnings"]
    assert [
        (warning["page"], warning["expectedPath"])
        for warning in warnings
    ] == [
        ("Bokning online", "/bokning"),
        ("Blogg / Nyheter", "/blogg"),
    ]
    # Specific reasons make the unsupported-integration case distinct
    # from the generic "scaffold has no such surface" fallback.
    by_page = {warning["page"]: warning["reason"] for warning in warnings}
    assert "booking integration" in by_page["Bokning online"]
    assert "editorial tooling" in by_page["Blogg / Nyheter"]
    assert {route["path"] for route in result.site_plan["routePlan"]} == {
        "/",
        "/tjanster",
        "/om-oss",
        "/kontakt",
    }
    validate_site_plan(result.site_plan)


@pytest.mark.tooling
def test_page_intent_silent_when_must_have_matches_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = produce_site_plan(
        _baseline_brief(),
        run_id="page-intent-match",
        pinned=_local_service_pin(),
        wizard_must_have=["Om oss / Om mig"],
    )

    assert result.site_plan["pageIntentWarnings"] == []
    validate_site_plan(result.site_plan)


@pytest.mark.tooling
def test_page_intent_silent_when_must_have_has_no_route_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = produce_site_plan(
        _baseline_brief(),
        run_id="page-intent-no-hint",
        pinned=_local_service_pin(),
        wizard_must_have=["Startsida / Hero"],
    )

    assert result.site_plan["pageIntentWarnings"] == []
    validate_site_plan(result.site_plan)


@pytest.mark.tooling
def test_page_intent_emits_routes_for_supported_wizard_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B132 follow-up sprint 2026-05-21: supported wizard mustHave pages
    (FAQ, Bildgalleri, Vårt team, Priser och paket, Portfolio / Case,
    Karta / Hitta hit) land on routePlan as real entries for local-
    service-business and no longer surface as pageIntentWarnings.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    must_have = [
        "FAQ",
        "Bildgalleri",
        "Vårt team",
        "Priser och paket",
        "Portfolio / Case",
        "Karta / Hitta hit",
    ]
    result = produce_site_plan(
        _baseline_brief(),
        run_id="page-intent-emit",
        pinned=_local_service_pin(),
        wizard_must_have=must_have,
    )

    routes_by_id = {route["id"]: route["path"] for route in result.site_plan["routePlan"]}
    for route_id, path in (
        ("faq", "/faq"),
        ("gallery", "/galleri"),
        ("team", "/team"),
        ("pricing", "/priser"),
        ("portfolio", "/portfolio"),
        ("map", "/karta"),
    ):
        assert routes_by_id.get(route_id) == path, (
            f"Expected routePlan to include {route_id!r} at {path!r}; "
            f"got {routes_by_id!r}"
        )
    assert result.site_plan["pageIntentWarnings"] == []
    validate_site_plan(result.site_plan)


@pytest.mark.tooling
def test_page_intent_emission_skipped_for_unsupported_scaffold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only ``local-service-business`` opts in to wizard-route emission
    in v1. ecommerce-lite must keep the warning-only behaviour so a
    future scaffold-renderer review can decide if its product-flavoured
    pages can host the same wizard-driven extras.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = produce_site_plan(
        _baseline_brief(),
        run_id="page-intent-ecommerce",
        pinned={"scaffoldId": "ecommerce-lite", "variantId": "clean-store"},
        wizard_must_have=["FAQ", "Bildgalleri"],
    )

    routes_by_id = {route["id"]: route["path"] for route in result.site_plan["routePlan"]}
    assert "faq" not in routes_by_id
    assert "gallery" not in routes_by_id
    warnings = {warning["page"] for warning in result.site_plan["pageIntentWarnings"]}
    assert warnings == {"FAQ", "Bildgalleri"}
    validate_site_plan(result.site_plan)


@pytest.mark.tooling
def test_page_intent_emission_keeps_page_count_warning_for_scaffold_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B138 + B132 interaction: brief.pageCount trims scaffold defaults
    but wizard-driven extras stay because they are the operator's
    explicit choice. Final routePlan therefore mixes a trimmed scaffold
    body with the wizard extras and the pageCountWarning still reports
    the scaffold-trim accurately.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = produce_site_plan(
        _baseline_brief(pageCount=2),
        run_id="page-intent-pagecount",
        pinned=_local_service_pin(),
        wizard_must_have=["FAQ", "Bildgalleri"],
    )

    paths = [route["path"] for route in result.site_plan["routePlan"]]
    assert paths[0] == "/"
    assert paths[-1] == "/kontakt"
    assert "/faq" in paths
    assert "/galleri" in paths
    assert "/tjanster" not in paths
    assert "/om-oss" not in paths
    warning = result.site_plan["pageCountWarning"]
    assert warning["requestedPageCount"] == 2
    assert warning["emittedRouteCount"] == 2
    validate_site_plan(result.site_plan)


@pytest.mark.tooling
def test_prompt_helper_persists_wizard_must_have_for_build_phase(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _project_input, meta, _project_input_path, meta_path = generate(
        "Skapa hemsida för Page Intent AB",
        output_dir=tmp_path,
        site_id="page-intent-meta",
        project_id="stable-project-id",
        discovery=_discovery_payload(["Bildgalleri", "Priser och paket"]),
    )

    assert meta["wizardMustHave"] == ["Bildgalleri", "Priser och paket"]
    written_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert written_meta["wizardMustHave"] == meta["wizardMustHave"]

    _followup_project_input, followup_meta, _followup_path, _followup_meta_path = (
        generate_followup(
            "Gör tonen varmare.",
            output_dir=tmp_path,
            site_id="page-intent-meta",
        )
    )
    assert followup_meta["wizardMustHave"] == meta["wizardMustHave"]


@pytest.mark.tooling
def test_build_result_emits_supported_wizard_routes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B132 follow-up sprint 2026-05-21: wizard mustHave pages that
    plan.py declares as supported land as real routes in build-result
    and as actual page.tsx files under the generated app dir.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _project_input, _meta, project_input_path, _meta_path = generate(
        "Skapa hemsida för Page Intent AB",
        output_dir=tmp_path,
        site_id="page-intent-build",
        project_id="stable-project-id",
        discovery=_discovery_payload(["Bildgalleri", "Karta / Hitta hit"]),
    )

    target, run_dir = build(
        project_input_path,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    site_plan = json.loads((run_dir / "site-plan.json").read_text(encoding="utf-8"))
    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )

    # Supported wizard mustHave pages must not produce warnings; the
    # route plan is now the operator-visible source of truth.
    assert build_result["pageIntentWarnings"] == []
    assert site_plan["pageIntentWarnings"] == []
    for path in ("/galleri", "/karta"):
        assert path in build_result["routes"], (
            f"Wizard-driven route {path!r} missing from build result"
        )
    assert (target / "app" / "galleri" / "page.tsx").exists()
    assert (target / "app" / "karta" / "page.tsx").exists()


@pytest.mark.tooling
def test_build_result_keeps_warning_for_unsupported_wizard_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``Bokning online`` stays warning-only because the deterministic
    Builder does not have a real booking integration; emitting a fake
    booking surface would mislead the visitor.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _project_input, _meta, project_input_path, _meta_path = generate(
        "Skapa hemsida för Page Intent AB",
        output_dir=tmp_path,
        site_id="page-intent-booking",
        project_id="stable-project-id",
        discovery=_discovery_payload(["Bokning online"]),
    )

    target, run_dir = build(
        project_input_path,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )

    assert [
        (warning["page"], warning["expectedPath"])
        for warning in build_result["pageIntentWarnings"]
    ] == [("Bokning online", "/bokning")]
    booking_warning = build_result["pageIntentWarnings"][0]
    assert "booking integration" in booking_warning["reason"]
    assert "/bokning" not in build_result["routes"]
    assert not (target / "app" / "bokning" / "page.tsx").exists()
