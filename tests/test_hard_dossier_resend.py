"""Hard dossier contracts + resend-contact-form regression tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _minimal_dossier() -> dict:
    return {
        "siteId": "test-hard-dossier",
        "language": "sv",
        "company": {
            "name": "Testbolaget AB",
            "businessType": "painter",
            "tagline": "Tagline",
            "story": "Kort story",
            "team": [],
        },
        "location": {
            "city": "Stockholm",
            "country": "Sverige",
            "serviceAreas": ["Stockholm"],
        },
        "services": [
            {"id": "svc-1", "label": "Tjanst 1", "summary": "Kort beskrivning"}
        ],
        "trustSignals": [],
        "conversionGoals": [],
        "contact": {
            "phone": "+46 70 111 22 33",
            "email": "hej@test.se",
            "addressLines": ["Storgatan 1", "111 11 Stockholm"],
            "openingHours": "Man-Fre 09-17",
        },
    }


@pytest.mark.tooling
def test_resend_dossier_uses_design_mode_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.build_site import load_selected_dossier_manifests

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    selected = load_selected_dossier_manifests(
        {"selectedDossiers": {"required": ["resend-contact-form"]}}
    )
    assert len(selected) == 1
    runtime = selected[0]["hardRuntime"]
    assert runtime["mode"] == "design"
    assert runtime["missingEnv"] == ["RESEND_API_KEY"]
    assert runtime["submitTarget"] == "/api/contact/resend"


@pytest.mark.tooling
def test_resend_dossier_uses_integration_mode_when_env_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.build_site import load_selected_dossier_manifests

    monkeypatch.setenv("RESEND_API_KEY", "re_test_dummy")
    selected = load_selected_dossier_manifests(
        {"selectedDossiers": {"required": ["resend-contact-form"]}}
    )
    runtime = selected[0]["hardRuntime"]
    assert runtime["mode"] == "integration"
    assert runtime["missingEnv"] == []


@pytest.mark.tooling
def test_resend_dossier_mounts_component_and_emits_server_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.build_site import (
        load_selected_dossier_manifests,
        mount_dossier_components,
        write_dossier_routes,
    )

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    project_input = {
        "selectedDossiers": {"required": ["resend-contact-form"]},
        "contact": {"email": "owner@example.se"},
    }
    selected = load_selected_dossier_manifests(project_input)
    copied = mount_dossier_components(tmp_path, selected)
    assert "components/resend-contact-form.tsx" in copied

    routes = write_dossier_routes(tmp_path, selected, project_input)
    assert routes == []

    route_file = tmp_path / "app" / "api" / "contact" / "resend" / "route.ts"
    assert route_file.exists()
    source = route_file.read_text(encoding="utf-8")
    assert "RESEND_API_KEY" in source
    assert 'mode: "design"' in source
    assert "ok: false" in source
    assert "https://api.resend.com/emails" in source
    assert "re_test_dummy" not in source


@pytest.mark.tooling
def test_render_contact_injects_resend_form_in_honest_design_mode() -> None:
    from scripts.build_site import render_contact

    dossier = _minimal_dossier()
    dossier["dossierRuntime"] = {
        "hardDossiers": {
            "resend-contact-form": {
                "provider": "resend",
                "submitTarget": "/api/contact/resend",
                "mode": "design",
                "missingEnv": ["RESEND_API_KEY"],
                "designModeBehavior": "Design mode active: no-op submit.",
                "integrationModeBehavior": "Integration mode active.",
            }
        }
    }
    output = render_contact(dossier)

    assert 'import { ResendContactForm } from "@/components/resend-contact-form";' in output
    assert "<ResendContactForm" in output
    assert "designModeAtBuild={true}" in output
    assert "Design mode active: no-op submit." in output
    assert "RESEND_API_KEY" not in output


@pytest.mark.tooling
def test_build_with_resend_design_mode_is_not_quality_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.build_site import build

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    fixture_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["selectedDossiers"] = {
        "required": ["resend-contact-form"],
        "recommended": [],
        "conditional": [],
        "rejected": [],
    }

    project_input_path = tmp_path / "resend-design-mode.project-input.json"
    project_input_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _target, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path / "runs")

    quality = json.loads((run_dir / "quality-result.json").read_text(encoding="utf-8"))
    assert quality["status"] in {"ok", "degraded"}, quality
