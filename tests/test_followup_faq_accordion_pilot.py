"""E2E proof for the Component Catalog lager-3 accordion pilot (ADR 0040/0054).

The full chain proven here:

    curated intake (accordion) -> capability-map components + marketing-base
    component-manifest confirm accordion -> /faq render path emits the vendored
    Accordion component.

End-to-end via the REAL user path (``run_followup_chain``): a "lägg till en
FAQ-sektion" follow-up on the local-service-business scaffold (painter-palma)
surfaces the grounded /faq page with ``appliedVisibleEffect=true`` AND the
emitted ``app/faq/page.tsx`` imports the vendored accordion component - with ZERO
new npm dependencies (the upgraded marketing-base accordion.tsx is native
<details> + cn).

Mock-safe: ``OPENAI_API_KEY`` is removed so brief/plan fall back to the mock and
the router/context/patch/apply chain (deterministic) never calls an LLM; the
build runs with ``do_build=False`` (no npm), like the other follow-up chain E2Es.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ACCORDION_IMPORT = (
    'import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } '
    'from "@/components/ui/accordion";'
)


def _seed_painter_palma(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Init-build the LSB painter-palma example (no npm), isolated dirs."""
    from scripts.build_site import build

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"
    build(
        REPO_ROOT / "examples" / "painter-palma.project-input.json",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs_dir=prompt_inputs,
    )
    return prompt_inputs, runs_dir, generated_dir


def _newest_build_dir(generated_dir: Path, site_id: str) -> Path:
    builds = sorted((generated_dir / site_id / "builds").glob("*"))
    assert builds, "expected at least one build directory"
    return builds[-1]


def test_faq_followup_emits_accordion_component_on_lsb(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The visible /faq pilot: a FAQ follow-up on LSB emits the accordion import.

    Proves the lager-3 chain end-to-end: capability-map faq-section.components +
    marketing-base manifest both confirm accordion, so the /faq render path emits
    the vendored Accordion component (not the native <article> fallback)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "lägg till en FAQ-sektion",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    # Visible effect: a new grounded /faq page was surfaced.
    assert result["stage"] == "built", result
    assert result["editKind"] == "section_add"
    assert result["appliedVisibleEffect"] is True, result
    assert result["affectedRoutes"] == ["faq"]

    faq_page = _newest_build_dir(generated_dir, site_id) / "app" / "faq" / "page.tsx"
    markup = faq_page.read_text(encoding="utf-8")
    # The pilot payload: the vendored accordion component import + markup.
    assert ACCORDION_IMPORT in markup, markup
    assert "<AccordionItem" in markup
    assert "<AccordionTrigger>" in markup
    assert "<AccordionContent>" in markup
    # Grounded FAQ content is preserved (same questions as the native path).
    assert "Vanliga frågor" in markup
    # No native <article> FAQ cards remain when the accordion path is taken.
    assert 'className="rounded-xl border border-[color:var(--border)] p-6"' not in markup


def test_render_faq_gate_native_vs_accordion() -> None:
    """Unit-level gate proof: LSB scaffold -> accordion; no scaffold -> native.

    Locks the per-build precision directly on render_faq so a regression in the
    Component Catalog gate is caught without a full build."""
    from scripts.build_site import render_faq

    dossier = {
        "company": {"name": "X"},
        "contact": {"openingHours": "Mån-Fre 8-17"},
        "location": {"city": "Malmö"},
    }
    # No scaffoldId -> native fallback, byte-stable (no accordion import).
    native = render_faq(dossier)
    assert ACCORDION_IMPORT not in native
    assert "<article" in native

    # local-service-business -> marketing-base vendors accordion -> accordion mode.
    lsb = {**dossier, "scaffoldId": "local-service-business"}
    accordion = render_faq(lsb)
    assert ACCORDION_IMPORT in accordion
    assert "<AccordionItem" in accordion

    # Explicit override wins (defensive): forcing False keeps native on LSB.
    assert ACCORDION_IMPORT not in render_faq(lsb, accordion_component=False)


def test_intake_candidate_fixture_is_committed_and_zero_dep() -> None:
    """The committed accordion intake candidate is the pilot's provenance proof:
    real intake output, zero new npm deps (the model chose a native pattern)."""
    info_path = (
        REPO_ROOT / "data" / "component-candidates" / "accordion" / "intake-info.json"
    )
    assert info_path.exists(), "the real intake candidate must be committed as proof"
    info = json.loads(info_path.read_text(encoding="utf-8"))
    assert info["shadcnItemsUsed"] == ["accordion"]
    assert info["requiredNpmDeps"] == [], "the pilot must be zero new npm deps"
    assert info["contentHash"].startswith("sha256:")
