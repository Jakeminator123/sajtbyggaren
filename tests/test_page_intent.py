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
def test_page_intent_warns_when_wizard_must_have_not_in_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = produce_site_plan(
        _baseline_brief(),
        run_id="page-intent-warn",
        pinned=_local_service_pin(),
        wizard_must_have=["Bildgalleri", "Karta / Hitta hit"],
    )

    warnings = result.site_plan["pageIntentWarnings"]
    assert [
        (warning["page"], warning["expectedPath"])
        for warning in warnings
    ] == [
        ("Bildgalleri", "/galleri"),
        ("Karta / Hitta hit", "/karta"),
    ]
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
def test_build_result_carries_page_intent_warnings_without_extra_routes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
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

    assert build_result["pageIntentWarnings"] == site_plan["pageIntentWarnings"]
    assert [
        (warning["page"], warning["expectedPath"])
        for warning in build_result["pageIntentWarnings"]
    ] == [
        ("Bildgalleri", "/galleri"),
        ("Karta / Hitta hit", "/karta"),
    ]
    assert "/galleri" not in build_result["routes"]
    assert "/karta" not in build_result["routes"]
    assert not (target / "app" / "galleri" / "page.tsx").exists()
    assert not (target / "app" / "karta" / "page.tsx").exists()
