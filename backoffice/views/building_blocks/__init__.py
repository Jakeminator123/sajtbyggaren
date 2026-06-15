"""Building Blocks-block: Scaffolds, Variants, Dossiers, Reference Templates.

Tunt nav för delpaketet. Re-exporterar samma `VIEWS`-dict och samma vy-labels
som den tidigare building_blocks-modulen, och äger de delade kandidat- och
asset-hjälparna som vyerna och testerna förlitar sig på (inkl. de
monkeypatch-bara `*_from_ui`-omslagen). Vy-render-koden bor i undermodulerna
kontrollplan, scaffolds, variants, dossiers och reference_templates.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from scripts.dossier_candidate_intake import (
    analyze_dossier_source,
    build_safe_intake_evidence,
    review_dossier_intake_with_model,
)
from scripts.generate_dossier_candidate import generate_dossier_candidate
from scripts.generate_variant_candidate import generate_variant_candidates

from ... import asset_graph
from ...paths import REPO_ROOT
from .._helpers import safe_render

SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
REFERENCE_TEMPLATES_DIR = REPO_ROOT / "data" / "reference-templates"
VARIANT_CANDIDATES_DIR = REPO_ROOT / "data" / "variant-candidates"
DOSSIER_CANDIDATES_DIR = REPO_ROOT / "data" / "dossier-candidates"
SCAFFOLD_CANDIDATES_DIR = REPO_ROOT / "data" / "scaffold-candidates"
PLACEHOLDER_MARKER = asset_graph.PLACEHOLDER_MARKER


def is_placeholder_file(path: Path) -> bool:
    """Return True if file looks like a placeholder created by the builder."""
    return asset_graph.is_placeholder_file(path)


def scaffold_is_real(scaffold_dir: Path) -> bool:
    """Scaffold is real iff every required contract file exists."""
    return asset_graph.scaffold_is_real(scaffold_dir)


def _list_scaffold_dirs() -> list:
    return asset_graph.list_scaffold_dirs(SCAFFOLDS_DIR)


def _list_dossier_dirs(classes: list[str] | None = None) -> list:
    return asset_graph.list_dossier_dirs(classes=classes)


def _scaffold_options() -> list[str]:
    return [path.name for path in _list_scaffold_dirs()]


def create_variant_candidate_from_ui(
    *,
    scaffold_id: str,
    brief: str,
    variant_id: str | None,
    use_llm: bool,
    force: bool,
):
    """Generate a Variant candidate from Backoffice without touching canonical files."""
    return generate_variant_candidates(
        scaffold_id=scaffold_id,
        brief=brief,
        variant_id=variant_id,
        output_dir=VARIANT_CANDIDATES_DIR,
        enabled=False,
        force=force,
        use_llm=use_llm,
    )


def create_dossier_candidate_from_ui(
    *,
    brief: str,
    candidate_id: str | None,
    capability: str | None,
    use_llm: bool,
    force: bool,
    intake_report: dict | None = None,
):
    """Generate a Dossier candidate from Backoffice without touching canonical files."""
    return generate_dossier_candidate(
        brief=brief,
        candidate_id=candidate_id,
        capability=capability,
        output_dir=DOSSIER_CANDIDATES_DIR,
        force=force,
        use_llm=use_llm,
        intake_report=intake_report,
    )


def analyze_dossier_source_from_ui(
    *,
    source_path: str,
    operator_brief: str,
) -> dict:
    """Analyse a local source path from Backoffice without writing files."""
    return analyze_dossier_source(
        source_path,
        operator_brief=operator_brief,
    )


def review_dossier_intake_from_ui(
    *,
    operator_brief: str,
    intake_report: dict,
    source_path: str,
    use_llm: bool,
) -> dict:
    """Review a Dossier intake report with safe evidence only."""
    safe_evidence = build_safe_intake_evidence(intake_report, source_path)
    return review_dossier_intake_with_model(
        operator_brief=operator_brief,
        intake_report=intake_report,
        safe_evidence=safe_evidence,
        use_llm=use_llm,
    )


def _render_candidate_source_help() -> None:
    st.info(
        "`real` = skapad via policyregistrerad modellroll. "
        "`deterministic-v1` = lokal deterministisk fallback. "
        "`mock-no-key` = ingen API-nyckel fanns. "
        "`mock-llm-error` = modellfel, fallback användes. "
        "Candidates är inte canonical och promoteras aldrig automatiskt."
    )


def _warn_non_real_sources(rows: list[dict]) -> None:
    sources = sorted(
        {
            str(row.get("source") or "")
            for row in rows
            if str(row.get("source") or "") not in {"", "real"}
        }
    )
    if sources:
        st.warning(
            "Minst en kandidat är inte verifierat skapad av en riktig modellcall: "
            + ", ".join(f"`{source}`" for source in sources)
        )


# Vy-render-koden bor i undermodulerna. Importeras EFTER hjälparna ovan eftersom
# undermodulerna re-importerar de monkeypatch-bara *_from_ui-omslagen härifrån
# (cykeln är avsiktlig och ofarlig vid den här ordningen) -> E402 väntat.
from .dossiers import view_dossier_candidates, view_dossiers  # noqa: E402
from .kontrollplan import (  # noqa: E402
    _render_asset_graph,
    _render_industry_coverage,
    _render_sni_discovery_mapping,
    view_control_plane,
)
from .reference_templates import view_reference_templates  # noqa: E402
from .scaffolds import view_scaffolds  # noqa: E402
from .variants import (  # noqa: E402
    view_selection_profiles,
    view_variant_candidates,
    view_variants,
)

VIEWS = {
    "Kontrollplan": lambda: safe_render(view_control_plane),
    "Scaffolds": lambda: safe_render(view_scaffolds),
    "Selection Profiles": lambda: safe_render(view_selection_profiles),
    "Variants": lambda: safe_render(view_variants),
    "Variant Candidates": lambda: safe_render(view_variant_candidates),
    "Dossiers": lambda: safe_render(view_dossiers),
    "Dossier Candidates": lambda: safe_render(view_dossier_candidates),
    "Reference Templates": lambda: safe_render(view_reference_templates),
}

# Publik yta. Inkluderar de privata _render_*-vyerna som test-sviten inspekterar
# på paketet (tests/test_backoffice_asset_graph.py m.fl.).
__all__ = [
    "VIEWS",
    "_render_asset_graph",
    "_render_industry_coverage",
    "_render_sni_discovery_mapping",
    "is_placeholder_file",
    "scaffold_is_real",
    "view_control_plane",
    "view_dossier_candidates",
    "view_dossiers",
    "view_reference_templates",
    "view_scaffolds",
    "view_selection_profiles",
    "view_variant_candidates",
    "view_variants",
]
