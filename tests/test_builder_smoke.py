"""Smoke test for the Builder MVP.

Runs `scripts.build_site.build` with `do_build=False` so the test does not
require Node, npm or network. Verifies that the deterministic happy path
writes:

- the four required Next.js page files under `.generated/painter-palma/app/`
- the six canonical Engine Run artefakter under `data/runs/<runId>/`
- a trace with at least three Engine Events covering all three phases
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _last_css_token(css: str, token_name: str) -> str | None:
    matches = re.findall(rf"--{re.escape(token_name)}:\s*([^;]+);", css)
    return matches[-1].strip() if matches else None


@pytest.mark.tooling
def test_builder_smoke_writes_routes_and_run_artifacts(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from scripts.build_site import build  # imported lazily to avoid heavy import on collection

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input_path = (
        REPO_ROOT / "examples" / "painter-palma.project-input.json"
    )
    assert project_input_path.exists(), "painter-palma project input must exist"

    target, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)

    # Generated routes
    expected_pages = [
        target / "app" / "page.tsx",
        target / "app" / "tjanster" / "page.tsx",
        target / "app" / "om-oss" / "page.tsx",
        target / "app" / "kontakt" / "page.tsx",
    ]
    for page in expected_pages:
        assert page.exists(), f"Expected page missing: {page}"

    # Engine Run artefakter under data/runs/<runId>/
    expected_artifacts = [
        "input.json",
        "site-brief.json",
        "site-plan.json",
        "generation-package.json",
        "build-result.json",
        "trace.ndjson",
    ]
    for name in expected_artifacts:
        assert (run_dir / name).exists(), f"Expected artefakt missing: {name}"

    # Trace must have engine events from all three phases
    events: list[dict] = []
    with (run_dir / "trace.ndjson").open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    assert len(events) >= 3, f"Expected >=3 trace events, got {len(events)}"
    phases = {e["phase"] for e in events}
    assert {"understand", "plan", "build"}.issubset(phases), (
        f"Trace must cover all three phases. Got: {phases}"
    )

    # Build result reflects --skip-build and dossier identity
    result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))
    assert result["siteId"] == "painter-palma"
    assert result["scaffoldId"] == "local-service-business"
    assert result["variantId"] == "nordic-trust"
    assert result["status"] == "skipped", "skip-build should mark status=skipped"
    assert result["npmSteps"] == []

    # Site brief mock contract
    brief = json.loads((run_dir / "site-brief.json").read_text(encoding="utf-8"))
    assert brief["briefSource"] == "mock-no-key"
    assert brief["modelUsed"] == "mock"
    assert brief["language"] == "sv"
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.out
    assert "mock Site Brief" in captured.out


@pytest.mark.tooling
def test_builder_assertion_blocks_env_writes() -> None:
    """Builder helper must refuse to write secret .env files."""
    from scripts.build_site import resolve_generated_dir, write

    preview_root = resolve_generated_dir()
    target = preview_root / "painter-palma" / ".env"
    with pytest.raises(AssertionError):
        write(target, "SECRET=oops\n")

    target_local = preview_root / "painter-palma" / ".env.local"
    with pytest.raises(AssertionError):
        write(target_local, "SECRET=oops\n")

    # `.env.example` must still be allowed - it is the canonical placeholder.
    safe = preview_root / "painter-palma" / ".env.example"
    write(safe, "# safe placeholder\n")
    assert safe.exists()
    safe.unlink()


@pytest.fixture
def nordic_trust_variant() -> dict:
    variant_path = (
        REPO_ROOT
        / "packages"
        / "generation"
        / "orchestration"
        / "scaffolds"
        / "local-service-business"
        / "variants"
        / "nordic-trust.json"
    )
    return json.loads(variant_path.read_text(encoding="utf-8"))


@pytest.mark.tooling
def test_brand_primary_color_hex_overrides_primary_css_token(
    nordic_trust_variant: dict,
) -> None:
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {"brand": {"primaryColorHex": "#22AA44"}}
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert warnings == []
    assert "  --primary: #22aa44;" in css
    assert "  --primary-foreground: #1c1c1a;" in css
    assert "  --accent: #cdb98a;" in css


@pytest.mark.tooling
def test_brand_accent_color_hex_overrides_accent_css_token(
    nordic_trust_variant: dict,
) -> None:
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {"brand": {"accentColorHex": "#CC7722"}}
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert warnings == []
    assert "  --primary: #1f3b5b;" in css
    assert "  --accent: #cc7722;" in css
    assert "  --accent-foreground: #1c1c1a;" in css


@pytest.mark.tooling
def test_tone_primary_green_maps_to_stable_green_token_when_hex_missing(
    nordic_trust_variant: dict,
) -> None:
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {"tone": {"primary": "grön"}}
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert warnings == []
    assert "  --primary: #166534;" in css
    assert "  --primary-foreground: #fafaf9;" in css
    assert "  --accent: #dcfce7;" in css
    assert "  --accent-foreground: #1c1c1a;" in css


@pytest.mark.tooling
def test_explicit_brand_hex_wins_over_tone_keyword(
    nordic_trust_variant: dict,
) -> None:
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {
            "brand": {"primaryColorHex": "#445566"},
            "tone": {"primary": "grön"},
        }
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert warnings == []
    assert "  --primary: #445566;" in css
    assert "  --primary-foreground: #fafaf9;" in css
    assert "  --accent: #cdb98a;" in css


@pytest.mark.tooling
def test_light_brand_primary_hex_gets_dark_foreground_token(
    nordic_trust_variant: dict,
) -> None:
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {"brand": {"primaryColorHex": "#fef3c7"}}
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert warnings == []
    assert "  --primary: #fef3c7;" in css
    assert "  --primary-foreground: #1c1c1a;" in css


@pytest.mark.tooling
def test_invalid_brand_hex_is_ignored_and_variant_default_is_preserved(
    nordic_trust_variant: dict,
) -> None:
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {"brand": {"primaryColorHex": "not-a-color"}}
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert overrides == {}
    assert warnings == ["brand.primaryColorHex invalid; variant primary token kept"]
    assert "  --primary: #1f3b5b;" in css
    assert "  --primary-foreground: #fafaf9;" in css
    assert "  --accent: #cdb98a;" in css


@pytest.mark.tooling
def test_invalid_explicit_brand_hex_does_not_fall_through_to_tone_keyword(
    nordic_trust_variant: dict,
) -> None:
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {
            "brand": {"primaryColorHex": "green"},
            "tone": {"primary": "grön"},
        }
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert overrides == {}
    assert warnings == ["brand.primaryColorHex invalid; variant primary token kept"]
    assert "  --primary: #1f3b5b;" in css
    assert "  --primary-foreground: #fafaf9;" in css
    assert "  --accent: #cdb98a;" in css


@pytest.mark.tooling
def test_variant_css_default_is_byte_stable_without_brand_or_tone(
    nordic_trust_variant: dict,
) -> None:
    from scripts.build_site import variant_css

    assert variant_css(nordic_trust_variant) == variant_css(nordic_trust_variant, {})


@pytest.mark.tooling
def test_build_writes_brand_token_overrides_to_generated_globals_css(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input = json.loads(
        (REPO_ROOT / "examples" / "painter-palma.project-input.json").read_text(
            encoding="utf-8"
        )
    )
    project_input["siteId"] = "brand-token-site"
    project_input["brand"] = {
        "primaryColorHex": "#224466",
        "accentColorHex": "#ddaa33",
    }
    project_input_path = tmp_path / "brand-token-site.project-input.json"
    project_input_path.write_text(
        json.dumps(project_input, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    target, _run_dir = build(
        project_input_path,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )
    css = (target / "app" / "globals.css").read_text(encoding="utf-8")

    assert "  --primary: #224466;" in css
    assert "  --primary-foreground: #fafaf9;" in css
    assert "  --accent: #ddaa33;" in css
    assert "  --accent-foreground: #1c1c1a;" in css
    assert _last_css_token(css, "primary") == "#224466"
    assert _last_css_token(css, "accent") == "#ddaa33"


@pytest.mark.tooling
def test_build_traces_invalid_brand_hex_and_keeps_variant_defaults(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input = json.loads(
        (REPO_ROOT / "examples" / "painter-palma.project-input.json").read_text(
            encoding="utf-8"
        )
    )
    project_input["siteId"] = "invalid-token-site"
    project_input["brand"] = {"primaryColorHex": "green"}
    project_input_path = tmp_path / "invalid-token-site.project-input.json"
    project_input_path.write_text(
        json.dumps(project_input, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    target, run_dir = build(
        project_input_path,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )
    css = (target / "app" / "globals.css").read_text(encoding="utf-8")
    trace_text = (run_dir / "trace.ndjson").read_text(encoding="utf-8")

    assert "  --primary: #1f3b5b;" in css
    assert "variant_tokens.warning" in trace_text
    assert "brand.primaryColorHex invalid" in trace_text
