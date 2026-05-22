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


@pytest.mark.tooling
def test_build_renders_directive_hero_layout_and_usps(
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
    project_input["siteId"] = "directive-hero-site"
    project_input["directives"] = {"layoutHint": "centered"}
    project_input["uniqueSellingPoints"] = [
        "25 års erfarenhet",
        "Lokala hantverkare",
        "Tecken < och { escapade",
    ]
    project_input_path = tmp_path / "directive-hero-site.project-input.json"
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

    page = (target / "app" / "page.tsx").read_text(encoding="utf-8")
    hero = page.split("</section>", 1)[0]
    assert "text-center" in hero
    assert "justify-center" in hero
    assert "<Check" in hero
    assert '{"25 års erfarenhet"}' in hero
    assert '{"Lokala hantverkare"}' in hero
    assert '{"Tecken < och { escapade"}' in hero


@pytest.mark.tooling
def test_build_renders_media_metadata_and_background_video(
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
    project_input["siteId"] = "media-render-site"
    project_input["media"] = {
        "favicon": {
            "assetId": "favicon-1",
            "filename": "favicon.webp",
            "mimeType": "image/webp",
            "sizeBytes": 4096,
            "role": "favicon",
        },
        "ogImage": {
            "assetId": "og-1",
            "filename": "og.webp",
            "mimeType": "image/webp",
            "sizeBytes": 120000,
            "role": "ogImage",
            "alt": "Delningsbild",
        },
        "backgroundVideo": {
            "assetId": "video-1",
            "filename": "hero-loop.mp4",
            "mimeType": "video/mp4",
            "sizeBytes": 2400000,
            "role": "backgroundVideo",
            "placement": "home",
        },
    }
    project_input_path = tmp_path / "media-render-site.project-input.json"
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

    layout = (target / "app" / "layout.tsx").read_text(encoding="utf-8")
    page = (target / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "icons: {" in layout
    assert 'icon: "/uploads/favicon.webp"' in layout
    assert 'apple: "/uploads/favicon.webp"' in layout
    assert "openGraph: {" in layout
    assert 'url: "/uploads/og.webp"' in layout
    assert 'images: ["/uploads/og.webp"]' in layout
    assert "<video" in page
    assert 'src={"/uploads/hero-loop.mp4"}' in page
    assert "autoPlay loop muted playsInline" in page


# ─── Fas 4: brand color scales ──────────────────────────────────────────


@pytest.mark.tooling
def test_hex_to_hsl_round_trips_through_hsl_to_hex() -> None:
    """Hex→HSL→hex ska ge tillbaka (i princip) samma hex. Round-trip
    säkerställer att vi inte tappar precision vid skalbygget — om en
    färg ändras mer än ±1 enhet per kanal är HSL-matematiken trasig."""
    from scripts.build_site import _hex_to_hsl, _hsl_to_hex

    samples = [
        "#1f3b5b",  # variant primary (nordic-trust)
        "#cdb98a",  # variant accent
        "#22aa44",  # mid green
        "#ff0000",  # full saturation red
        "#0066ff",  # token-defaults accent
        "#f5e6d3",  # warm light
        "#000000",  # black
        "#ffffff",  # white
    ]
    for hex_in in samples:
        h, s, ell = _hex_to_hsl(hex_in)
        hex_out = _hsl_to_hex(h, s, ell)
        # Tillåt 1-step avvikelse per channel pga flyttalsavrundning.
        for i in (1, 3, 5):
            in_val = int(hex_in[i : i + 2], 16)
            out_val = int(hex_out[i : i + 2], 16)
            assert abs(in_val - out_val) <= 1, (
                f"round-trip för {hex_in!r} gav {hex_out!r} (skillnad i kanal {i})"
            )


@pytest.mark.tooling
def test_build_color_scale_preserves_hue_and_returns_ten_stops() -> None:
    """Skalan ska ha exakt 10 nycklar (50-900) och alla stops ska ha
    samma (eller mycket nära) hue som input. Lightness ska monotont
    minska från 50 till 900 så palette:n går från ljus till mörk."""
    from scripts.build_site import _build_color_scale, _hex_to_hsl

    scale = _build_color_scale("#1f3b5b")
    expected_steps = ("50", "100", "200", "300", "400", "500", "600", "700", "800", "900")
    assert tuple(scale.keys()) == expected_steps

    base_hue, _, _ = _hex_to_hsl("#1f3b5b")
    prev_l = 101.0
    for step in expected_steps:
        value = scale[step]
        assert value.startswith("#") and len(value) == 7, value
        hue, _, lightness = _hex_to_hsl(value)
        # Hue kan avvika med ±2° pga grayscale-stop (lightness 97% kan
        # exempelvis tappa hue helt). Vi accepterar det för ytter-
        # stops men kräver bevarad hue för mid-range.
        if step in ("300", "400", "500", "600", "700"):
            assert abs(hue - base_hue) <= 2, (
                f"hue för steg {step} drev (förv. {base_hue}, fick {hue})"
            )
        assert lightness < prev_l + 0.5, (
            f"lightness ska monotont minska, men steg {step} ({lightness}) >= förra ({prev_l})"
        )
        prev_l = lightness


@pytest.mark.tooling
def test_build_color_scale_caps_saturation_for_neon_inputs() -> None:
    """Fullt mättade input som #ff0000 ska ge en mer dämpad 500-band
    (saturation cap:as vid 85%) så CTA-knappar inte ser neon-aktiga
    ut. Detta är skillnaden mellan "branded" och "screaming"."""
    from scripts.build_site import _build_color_scale, _hex_to_hsl

    scale = _build_color_scale("#ff0000")
    _, saturation_500, _ = _hex_to_hsl(scale["500"])
    assert saturation_500 <= 86, (
        f"500-bandet ska ha cap:ad saturation, fick {saturation_500}"
    )


@pytest.mark.tooling
def test_variant_css_emits_primary_and_accent_color_scales(
    nordic_trust_variant: dict,
) -> None:
    """variant_css ska emittera --primary-50..900 och --accent-50..900
    som CSS-tokens. Generated render-funktioner kan sedan referera
    var(--primary-50) för subtila bakgrunder utan att hårdkoda hex."""
    from scripts.build_site import variant_css

    css = variant_css(nordic_trust_variant)
    for step in ("50", "100", "200", "300", "400", "500", "600", "700", "800", "900"):
        assert f"--primary-{step}:" in css, f"missing --primary-{step}"
        assert f"--accent-{step}:" in css, f"missing --accent-{step}"
    # Befintliga tokens ska kvarstå exakt som idag.
    assert "  --primary: #1f3b5b;" in css
    assert "  --accent: #cdb98a;" in css


@pytest.mark.tooling
def test_brand_override_propagates_into_color_scale(
    nordic_trust_variant: dict,
) -> None:
    """När operatören anger brand.primaryColorHex ska skalan baseras
    på den färgen, inte variant-defaulten. Annars är hela poängen
    med palette:n förlorad."""
    from scripts.build_site import (
        _build_color_scale,
        _token_overrides_from_project_input,
        variant_css,
    )

    overrides, _ = _token_overrides_from_project_input(
        {"brand": {"primaryColorHex": "#22AA44"}}
    )
    css = variant_css(nordic_trust_variant, overrides)

    expected = _build_color_scale("#22aa44")
    for step, value in expected.items():
        assert f"  --primary-{step}: {value};\n" in css, (
            f"--primary-{step} ska vara {value!r} i CSS"
        )
