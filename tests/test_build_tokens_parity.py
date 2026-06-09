"""Byte-parity lock for the color/token system before it moves modules.

``docs/refactor/megafiles-plan.md`` (Del 2, slice 1) requires a focused unit
test that freezes the color/token output (scale + css block) for a
representative project input *before* the system is extracted from
``scripts/build_site.py`` into ``packages/generation/build/tokens.py``. With
this lock in place the extraction can be proven behavior-preserving: the test
passes against the pre-move code (it generated the golden) and must keep
passing against the post-move re-export.

The golden CSS in ``tests/fixtures/tokens/painter-palma.nordic-trust.variant.css``
was generated from the unmodified builder. ``variant_css`` output is pure ASCII
(hex colors, font names, plain CSS), so a committed golden file gives a clean
diff without escaping concerns.

All symbols are imported via ``scripts.build_site`` on purpose: that spelling
must keep resolving through the re-export façade after the move, so the test
doubles as a guard that the façade stays intact.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

GOLDEN_CSS = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "tokens"
    / "painter-palma.nordic-trust.variant.css"
)


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


def _painter_palma_project_input() -> dict:
    path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.tooling
def test_painter_palma_variant_css_is_byte_locked(
    nordic_trust_variant: dict,
) -> None:
    """Full ``variant_css`` output for the canonical painter-palma input +
    nordic-trust variant must equal the committed golden byte-for-byte.

    This is the core behavior-preserving guarantee for slice 1: it covers the
    color tokens, the generated 10-step brand color scales and the tone-driven
    typography overlay in a single locked string.
    """
    from scripts.build_site import (
        _token_overrides_from_project_input,
        _typography_overlay_for_tone,
        variant_css,
    )

    project_input = _painter_palma_project_input()
    overrides, _warnings = _token_overrides_from_project_input(project_input)
    overlay = _typography_overlay_for_tone(project_input)
    css = variant_css(nordic_trust_variant, overrides, typography_overlay=overlay)

    golden = GOLDEN_CSS.read_text(encoding="utf-8")
    assert css == golden, (
        "variant_css output drifted from the golden lock. If this change is "
        "intentional, regenerate "
        "tests/fixtures/tokens/painter-palma.nordic-trust.variant.css; if you "
        "are mid-refactor (slice 1 token extraction) this means the move was "
        "NOT behavior-preserving."
    )


@pytest.mark.tooling
def test_painter_palma_token_overrides_are_empty_and_overlay_present() -> None:
    """painter-palma has no explicit brand hex and a tone (``lugn``) that is
    not a ``_TONE_COLOR_TOKENS`` color keyword, so color overrides stay empty
    while the typography overlay (calm -> Cormorant Garamond) is applied.

    Locking this documents which code paths the golden exercises: variant
    default colors + scale + typography overlay (not the hex-override path).
    """
    from scripts.build_site import (
        _token_overrides_from_project_input,
        _typography_overlay_for_tone,
    )

    project_input = _painter_palma_project_input()
    assert _token_overrides_from_project_input(project_input) == ({}, [])

    overlay = _typography_overlay_for_tone(project_input)
    assert overlay is not None
    assert overlay["display"] == "'Cormorant Garamond', Georgia, serif"


@pytest.mark.tooling
def test_variant_css_emits_locked_color_scale(
    nordic_trust_variant: dict,
) -> None:
    """The 10-step brand scale must be deterministic and emitted into the CSS.

    Locks ``_build_color_scale`` (scale shape + values) and that the
    ``--primary-*`` / ``--accent-*`` tokens are present in ``variant_css``
    output, derived from the variant's primary/accent colors.
    """
    from scripts.build_site import _build_color_scale, variant_css

    color = nordic_trust_variant["tokens"]["color"]
    primary_scale = _build_color_scale(color["primary"])
    accent_scale = _build_color_scale(color["accent"])

    expected_steps = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900"]
    assert list(primary_scale.keys()) == expected_steps
    assert list(accent_scale.keys()) == expected_steps

    css = variant_css(nordic_trust_variant)
    for step, value in primary_scale.items():
        assert f"--primary-{step}: {value};" in css
    for step, value in accent_scale.items():
        assert f"--accent-{step}: {value};" in css
