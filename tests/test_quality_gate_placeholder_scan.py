"""Lock the Quality Gate placeholder / generic-AI-copy scan.

This file is the regression lock for ``run_placeholder_copy_scan_check``
in ``packages/generation/quality_gate/checks.py``. It pins BOTH lanes:

- positive cases: strings that MUST be flagged (status=failed) because
  they are placeholder / generic-AI boilerplate that leaked into the
  customer-facing render (``.tsx`` / ``.jsx`` only).
- negative cases: legitimate Swedish business copy (and look-alike code
  identifiers) that MUST NOT be flagged.

The check is a ``warning``-severity lane: a finding never lowers the
aggregate ``QualityResult.status`` below ``ok`` (locked separately in
``tests/test_quality_gate_placeholder_copy.py``), so this file asserts
the per-check ``status`` on ``run_placeholder_copy_scan_check`` directly.

Scope guard: this file does NOT register a new check name. The registered
check-name set stays the six-name invariant locked by
``tests/test_build_site_size.py`` and ``tests/test_quality_gate.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.generation.quality_gate.checks import (
    run_placeholder_copy_scan_check,
)


def _write_page(root: Path, body: str, *, suffix: str = "tsx") -> Path:
    """Write a minimal customer-rendering page so the scan picks it up."""
    page = root / "app" / f"page.{suffix}"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(body, encoding="utf-8")
    return page


# ---------------------------------------------------------------------------
# Positive cases - MUST be flagged.
# ---------------------------------------------------------------------------
# Kept lowercase where the regex is re.IGNORECASE so the test source does
# not trip check_term_coverage --strict on capitalized multi-word phrases.
POSITIVE_CASES = [
    "lorem ipsum dolor sit amet",
    "Lorem Ipsum dolor",
    "this is tbd before launch",
    "platshållare för ingressen",
    "replace_me",
    "<insert customer quote here>",
    # Newly hardened generic-AI English boilerplate.
    "welcome to your company website",
    "your company has served the region for years",
    "company name goes here",
    "[company name]",
    # Imperative insert scaffolding.
    "insert your tagline here",
    "insert the company description",
    "insert business address",
    "insert logo above",
    # Empty section headings (structural placeholders).
    "<h1></h1>",
    "<h2>   </h2>",
    "<h3>&nbsp;</h3>",
    '<h2 className="hero-title"></h2>',
]


@pytest.mark.parametrize("copy", POSITIVE_CASES)
def test_placeholder_scan_flags_positive(tmp_path: Path, copy: str) -> None:
    _write_page(tmp_path, copy)
    result = run_placeholder_copy_scan_check(tmp_path)
    assert result.status == "failed", f"expected flag for: {copy!r}"
    assert result.findings, f"expected at least one finding for: {copy!r}"


def test_placeholder_scan_reports_path_and_line(tmp_path: Path) -> None:
    """A finding must carry ``relative/path:line`` so Repair Pipeline can
    locate the offending render string."""
    _write_page(tmp_path, "intro\nlorem ipsum dolor\nslut")
    result = run_placeholder_copy_scan_check(tmp_path)
    assert result.status == "failed"
    assert any("page.tsx:2" in finding for finding in result.findings)


# ---------------------------------------------------------------------------
# Negative cases - legitimate copy / identifiers, MUST NOT be flagged.
# ---------------------------------------------------------------------------
NEGATIVE_CASES = [
    # Real Swedish business prose (mirrors examples/cafe-bistro copy).
    "En liten kvarterskrog som öppnade 2019 på Södermalm.",
    "Vi lagar mat på det vi handlar samma vecka och håller menyn kort.",
    "Naturvin från småskaliga producenter, urvalet byts varje månad.",
    "Ankbröst med svartvinbärssås, potatisrösti och blanchad grönkål.",
    "Boka bord eller hör av dig så återkommer vi inom en arbetsdag.",
    # Swedish equivalents of the English placeholders must stay clean.
    "Ditt företag förtjänar en bättre hemsida.",
    "Vårt företagsnamn står för kvalitet sedan 1999.",
    # Substring look-alikes that the word boundaries must NOT catch.
    "notbd is a single token, not a marker.",
    "replace_meeting room booking är ett vanligt ord.",
    "your companyship metaphor",
    # Code identifiers with "insert" must not match (no determiner).
    "rows.insertBefore(node, ref);",
    "const inserted = arr.insert(item);",
    # A populated heading is fine.
    "<h1>Välkommen till Bistro Linnea</h1>",
    "<h2>Säsongsmat och naturvin på Södermalm</h2>",
]


@pytest.mark.parametrize("copy", NEGATIVE_CASES)
def test_placeholder_scan_ignores_negative(tmp_path: Path, copy: str) -> None:
    _write_page(tmp_path, copy)
    result = run_placeholder_copy_scan_check(tmp_path)
    assert result.status == "ok", (
        f"false positive on legitimate copy: {copy!r} -> {result.findings!r}"
    )


def test_placeholder_scan_ignores_dev_markers(tmp_path: Path) -> None:
    """Dev-markers (TODO:/FIXME) stay OUT of the scan by design.

    Re-asserted here alongside the new patterns so a future widening of
    _PLACEHOLDER_PATTERNS cannot silently re-introduce code-comment noise
    (reviewer findings on PR #129 + #133).
    """
    for dev_marker in ["TODO: skriv klart hero", "FIXME after review", "// TODO senare"]:
        _write_page(tmp_path, dev_marker)
        assert run_placeholder_copy_scan_check(tmp_path).status == "ok", dev_marker


def test_placeholder_scan_only_reads_customer_render_files(tmp_path: Path) -> None:
    """The scan is limited to .tsx/.jsx. A placeholder in a non-render
    file (e.g. a JSON fixture or markdown) must NOT be flagged - that
    keeps the warning lane focused on customer-facing output."""
    (tmp_path / "app").mkdir(parents=True, exist_ok=True)
    (tmp_path / "app" / "data.json").write_text(
        '{"hero": "lorem ipsum dolor"}', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("lorem ipsum in docs", encoding="utf-8")
    assert run_placeholder_copy_scan_check(tmp_path).status == "ok"


def test_placeholder_scan_skips_generated_dirs(tmp_path: Path) -> None:
    """node_modules / .next placeholders must not surface - they are not
    product output and would only add runtime + noise."""
    for skip_dir in ("node_modules", ".next"):
        page = tmp_path / skip_dir / "page.tsx"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("lorem ipsum dolor", encoding="utf-8")
    assert run_placeholder_copy_scan_check(tmp_path).status == "ok"
