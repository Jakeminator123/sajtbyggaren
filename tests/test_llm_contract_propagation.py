"""Regressionstester för brief→render-kontraktets signal-propagering.

ADR 0026 säger att embeddings är parkerade tills befintliga brief→render-
signaler inte tappas. Filen är ett samlat regressionsskydd över de fem
kontrakts-läckor som B137-B141 stängde:

1. ``company.tagline`` får inte läcka rå prompttext eller UI-direktiv
   ut till Hero (B137).
2. ``brief.pageCount`` ska påverka ``routePlan`` ELLER emittera explicit
   ``pageCountWarning`` (B138).
3. ``tone`` (``primary`` + ``secondary``) ska nå brand-tokens i
   ``variant_css`` där relevant (B139). Saknar ``tone.primary`` color-
   signal men ``tone.secondary`` har en, ska secondary fungera som
   fallback.
4. ``brand.primaryColorHex`` ska inte ignoreras när den finns och är
   giltig hex (B140).
5. ``siteBrief`` ska vara levande ref nedströms genom ``siteBriefRef``,
   inte tappas av silent dispatch via stale inline-kopia (B141).

De individuella enhets-testerna bor i ``test_discovery_resolver.py``,
``test_planning.py``, ``test_builder_smoke.py`` och ``test_codegen.py``.
Den här filen är ett kontrakts-skydd ovanpå dem så en framtida
ändring som råkar bryta signalpropageringen aldrig glider igenom utan
att fånga regressionerna här.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _baseline_brief(**overrides: Any) -> dict[str, Any]:
    """Minimal Site Brief som validerar mot site-brief.schema.json.

    Speglar ``_baseline_brief`` i ``test_planning.py`` så regressionstesterna
    här kan jämföras direkt med plannings-enhetstester.
    """
    brief: dict[str, Any] = {
        "runId": "test-contract-run",
        "language": "sv",
        "rawPrompt": "Skapa hemsida för en elektriker i Malmö",
        "tone": ["trustworthy"],
        "targetAudience": ["lokala fastighetsägare"],
        "requestedCapabilities": [],
        "conversionGoals": ["call"],
        "servicesMentioned": [],
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "briefSource": "mock-no-key",
        "createdAt": "2026-05-25T00:00:00+00:00",
    }
    brief.update(overrides)
    return brief


@pytest.fixture
def nordic_trust_variant() -> dict[str, Any]:
    """Lokal kopia av ``local-service-business/nordic-trust`` så testerna
    inte är beroende av att test_builder_smoke kör först."""
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


# ---------------------------------------------------------------------------
# B137: company.tagline får inte läcka rå prompt-/UI-direktiv-text
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b137_offer_with_ui_directives_does_not_leak_to_company_tagline() -> None:
    """B137-kontrakt: när wizardens ``offer`` är ett UI-direktiv (sidantal,
    färg-instruktion, "hemsida om"-prefix) ska Discovery Resolver INTE
    skriva texten rakt till ``company.tagline``.

    Driver hela _apply_company_fields-vägen så regressionsbeviset täcker
    både resolverns detektor-helper och fallback-priorityn (brief →
    derived → wizard).
    """
    from packages.generation.discovery.resolve import _apply_company_fields

    project_input: dict[str, Any] = {
        "language": "sv",
        "company": {
            "name": "Karlssons matservice",
            "businessType": "restaurant",
            "tagline": "Lokal mat och varm service",
        },
    }
    answers: dict[str, Any] = {
        "offer": "Hemsida om sköldpaddssoppa, mat, 2 sidor, gröna färger",
    }
    field_sources: dict[str, str] = {}

    _apply_company_fields(project_input, answers, field_sources)

    leaked = answers["offer"]
    final_tagline = project_input["company"]["tagline"]
    assert final_tagline != leaked, (
        f"B137 regression: rå wizard-offer läcker till tagline: {final_tagline!r}"
    )
    assert "2 sidor" not in final_tagline.lower(), (
        f"Sidantals-direktiv läcker fortfarande till tagline: {final_tagline!r}"
    )
    assert "gröna färger" not in final_tagline.lower(), (
        f"Färg-direktiv läcker fortfarande till tagline: {final_tagline!r}"
    )
    assert field_sources["company.tagline"] in {"brief", "derived"}, (
        f"Tagline-källan ska vara 'brief' eller 'derived' när offer är "
        f"UI-direktiv, fick {field_sources['company.tagline']!r}."
    )


@pytest.mark.tooling
def test_b137_clean_offer_still_reaches_tagline_when_brief_lacks_one() -> None:
    """Komplementärt skydd: en ren marknadsföringsfras får INTE filtreras.

    Garanterar att UI-direktiv-detektorn inte är överivrig — när operatören
    skriver en seriös beskrivning på 8-120 tecken utan sidantals/färg-
    direktiv ska wizard-källan vinna när brief saknar tagline.
    """
    from packages.generation.discovery.resolve import _apply_company_fields

    project_input: dict[str, Any] = {
        "language": "sv",
        "company": {
            "name": "Elektriker Malmö",
            "businessType": "electrician",
            "tagline": "",
        },
    }
    answers: dict[str, Any] = {
        "offer": "Snabb och trygg elservice för bostadsrätter i centrala Malmö",
    }
    field_sources: dict[str, str] = {}

    _apply_company_fields(project_input, answers, field_sources)

    assert project_input["company"]["tagline"] == answers["offer"]
    assert field_sources["company.tagline"] == "wizard"


# ---------------------------------------------------------------------------
# B138: brief.pageCount → routePlan eller pageCountWarning
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b138_brief_page_count_propagates_into_route_plan_with_warning(
    monkeypatch,
) -> None:
    """B138-kontrakt: brief.pageCount=2 ska antingen trimma routePlan ner
    till 2 routes ELLER lämna en explicit ``pageCountWarning`` i
    site-plan.json. Ingen tyst förlust av sidantalet är tillåten.
    """
    from packages.generation.brief.models import OPENAI_API_KEY_ENV
    from packages.generation.planning import produce_site_plan

    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(pageCount=2)
    result = produce_site_plan(brief, run_id="test-b138-page-count-2")
    site_plan = result.site_plan

    route_count = len(site_plan["routePlan"])
    warning = site_plan.get("pageCountWarning")

    assert route_count == 2 or warning is not None, (
        f"B138 regression: pageCount=2 propageras varken till routePlan "
        f"({route_count} routes) eller till pageCountWarning ({warning!r})."
    )
    if warning is not None:
        assert warning["requestedPageCount"] == 2
        assert warning["emittedRouteCount"] == route_count
        assert warning["reason"] in {
            "trimmed-to-brief-page-count",
            "below-minimum-keeping-default",
        }


@pytest.mark.tooling
def test_b138_page_count_high_value_keeps_defaults_without_silent_drop(
    monkeypatch,
) -> None:
    """Komplementärt skydd: pageCount > scaffold-defaults ska INTE tappas
    tyst — defaults ligger kvar och ingen warning emitteras (för stort
    sidantal är inte ett operatör-uttryck som planner kan honour:a).
    """
    from packages.generation.brief.models import OPENAI_API_KEY_ENV
    from packages.generation.planning import produce_site_plan

    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(pageCount=8)
    result = produce_site_plan(brief, run_id="test-b138-page-count-8")
    site_plan = result.site_plan

    assert len(site_plan["routePlan"]) >= 4, (
        "Höga pageCount-värden ska inte trimma scaffold-defaults bort."
    )
    assert "pageCountWarning" not in site_plan, (
        "pageCount >= scaffold-defaults ska INTE producera warning."
    )


# ---------------------------------------------------------------------------
# B139: tone (primary + secondary) → brand-tokens i variant_css
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b139_tone_primary_color_keyword_reaches_variant_css_primary_token(
    nordic_trust_variant: dict[str, Any],
) -> None:
    """B139-kontrakt: ``tone.primary`` med en color-keyword ('grön') ska
    skriva ``--primary``-token i emitterad CSS. Locks i fix:`eb5a81d`."""
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {"tone": {"primary": "grön", "secondary": [], "avoid": []}}
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert warnings == []
    assert "  --primary: #166534;" in css, (
        f"B139 regression: tone.primary='grön' nådde inte --primary-token. "
        f"overrides={overrides}"
    )


@pytest.mark.tooling
def test_b139_tone_secondary_color_keyword_falls_through_when_primary_lacks_signal(
    nordic_trust_variant: dict[str, Any],
) -> None:
    """B139 cross-axis: när ``tone.primary`` är en generisk wizard-tag
    ('professionell', 'lugn och förtroendeingivande') utan färgsignal
    men ``tone.secondary`` har en color-keyword, ska secondary fungera
    som fallback för brand-tokens.

    Annars läcker färgsignalen i secondary tyst — operatören som skriver
    "Professionell hemsida med gröna toner" får sin gröna ton ignorerad
    eftersom ``primary='professionell'`` mappar till typografi men inte
    till en color-token, och ``secondary=['grön']`` läses inte alls av
    ``_token_overrides_from_project_input``.
    """
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {
            "tone": {
                "primary": "professionell",
                "secondary": ["grön"],
                "avoid": [],
            }
        }
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert warnings == []
    assert "  --primary: #166534;" in css, (
        f"B139 regression: tone.secondary=['grön'] tappades när "
        f"tone.primary='professionell' inte hade color-signal. "
        f"overrides={overrides}"
    )


@pytest.mark.tooling
def test_b139_tone_primary_color_keyword_wins_over_secondary(
    nordic_trust_variant: dict[str, Any],
) -> None:
    """Locks tone-precedensen: när BÅDE primary och secondary innehåller
    color-keywords ska primary alltid vinna. Skydd mot att en framtida
    fallback-implementering råkar invertera prioritetsordningen."""
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, _warnings = _token_overrides_from_project_input(
        {
            "tone": {
                "primary": "blå",
                "secondary": ["grön"],
                "avoid": [],
            }
        }
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert "  --primary: #1d4ed8;" in css, (
        "tone.primary='blå' ska vinna över tone.secondary=['grön'] för "
        "primary-token."
    )
    assert "#166534" not in css.split("--primary-foreground")[0], (
        "Sekundärens 'grön' får inte krocka med primary-tokenen när "
        "primary redan vann."
    )


# ---------------------------------------------------------------------------
# B140: brand.primaryColorHex ignoreras inte när giltig
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b140_valid_brand_primary_color_hex_overrides_variant_css_token(
    nordic_trust_variant: dict[str, Any],
) -> None:
    """B140-kontrakt: en giltig ``brand.primaryColorHex`` ska skriva
    ``--primary``-token, vinna över tone-keywords och inte krascha
    typescript-build:n. Locks i fix:`eb5a81d`."""
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {
            "brand": {"primaryColorHex": "#3366CC"},
            "tone": {"primary": "grön", "secondary": [], "avoid": []},
        }
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert warnings == []
    assert "  --primary: #3366cc;" in css, (
        f"B140 regression: brand.primaryColorHex='#3366CC' nådde inte "
        f"--primary-token. overrides={overrides}"
    )
    assert "#166534" not in css.split("--accent-foreground")[0], (
        "Explicit brand-hex ska vinna över tone-keyword 'grön' i "
        "primary-token."
    )


@pytest.mark.tooling
def test_b140_invalid_brand_primary_color_hex_does_not_break_emit(
    nordic_trust_variant: dict[str, Any],
) -> None:
    """Komplementärt skydd: ogiltig hex (operatör skriver 'darkgreen' i
    fältet) får INTE krascha CSS-emit och får INTE läcka det ogiltiga
    värdet rakt in i token-strängen. Variantens default ska bevaras."""
    from scripts.build_site import _token_overrides_from_project_input, variant_css

    overrides, warnings = _token_overrides_from_project_input(
        {"brand": {"primaryColorHex": "darkgreen"}}
    )
    css = variant_css(nordic_trust_variant, overrides)

    assert overrides == {}
    assert warnings == [
        "brand.primaryColorHex invalid; variant primary token kept"
    ]
    assert "  --primary: darkgreen;" not in css
    assert "  --primary: #1f3b5b;" in css


# ---------------------------------------------------------------------------
# B141: siteBrief ska vara live-ref nedströms (ingen stale inline-kopia)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b141_generation_package_emits_site_brief_ref_not_inline_copy(
    monkeypatch,
) -> None:
    """B141-kontrakt: ``_assemble_generation_package`` ska skriva
    ``siteBriefRef = 'site-brief.json'`` och INTE inlinen ``siteBrief``-
    objektet. Skydd mot att en framtida refaktor återinför inline-kopia
    som blir stale när briefen senare patchas av Discovery Resolver."""
    from packages.generation.brief.models import OPENAI_API_KEY_ENV
    from packages.generation.planning import produce_site_plan

    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(
        businessTypeGuess="electrician",
        tone=["trustworthy", "lokal"],
    )
    result = produce_site_plan(brief, run_id="test-b141-by-ref")

    package = result.generation_package
    assert package["siteBriefRef"] == "site-brief.json"
    assert "siteBrief" not in package, (
        "B141 regression: generation-package.json har återigen inline "
        "siteBrief-kopia. Behåll by-reference-kontraktet."
    )


@pytest.mark.tooling
def test_b141_codegen_summary_loads_site_brief_via_live_ref_not_stale_inline(
    tmp_path: Path,
) -> None:
    """B141 cross-axis: codegen-summaryns Site Brief-uppslag ska prefera
    ``siteBriefRef`` (live på disk) över en eventuellt stale inline-kopia.

    Vi skriver site-brief.json med riktigt innehåll och en
    generation-package.json med BÅDA en stale inline siteBrief OCH en
    live siteBriefRef. Helpern ska välja live-data — annars är vi
    tillbaka i case-4-läget där downstream läser från död pipeline.
    """
    from packages.generation.codegen import codegen as codegen_module

    run_id = "test-b141-live-ref-vs-stale-inline"
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)

    live_brief = {
        "runId": run_id,
        "language": "sv",
        "businessTypeGuess": "electrician",
        "tone": ["trustworthy", "lokal"],
        "conversionGoals": ["call"],
        "servicesMentioned": ["akut elservice"],
    }
    (run_dir / "site-brief.json").write_text(
        json.dumps(live_brief, ensure_ascii=False),
        encoding="utf-8",
    )

    stale_inline_brief = {
        "language": "sv",
        "businessTypeGuess": "STALE-CACHED-DO-NOT-USE",
        "tone": ["STALE"],
        "conversionGoals": ["STALE"],
        "servicesMentioned": ["STALE"],
    }
    package = {
        "runId": run_id,
        "siteBriefRef": "site-brief.json",
        "siteBrief": stale_inline_brief,
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "selectedDossiers": [],
    }

    original_runs_dir = codegen_module.RUNS_DIR
    codegen_module.RUNS_DIR = runs_dir
    try:
        summary = codegen_module._summarise_generation_package(
            package, ["/", "/kontakt"], [], "marketing-base"
        )
    finally:
        codegen_module.RUNS_DIR = original_runs_dir

    assert "STALE" not in summary, (
        f"B141 regression: codegen läser stale inline siteBrief "
        f"trots live siteBriefRef. Summary:\n{summary}"
    )
    assert "electrician" in summary
    assert "trustworthy" in summary
    assert "akut elservice" in summary


# ---------------------------------------------------------------------------
# Cross-cutting: contract-stickiness end-to-end via produce_site_plan
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_brief_signals_survive_planning_helper_into_artefakts(monkeypatch) -> None:
    """Korsskydd: ett brief med fyllda kontrakts-fält ska gå in i
    helpern och komma ut i ``site-plan`` + ``generation-package`` med
    samma signaler bevarade — inte tappade av silent dispatch.

    Locks det "samlade" brief→plan→package-flödet så att en framtida
    ändring som råkar tappa t.ex. ``language`` eller ``runId`` mellan
    fas 1 och fas 2 fångas direkt.
    """
    from packages.generation.brief.models import OPENAI_API_KEY_ENV
    from packages.generation.planning import produce_site_plan

    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(
        businessTypeGuess="electrician",
        tone=["trustworthy", "lokal"],
        pageCount=3,
        servicesMentioned=["akut elservice", "paneldragning"],
    )
    result = produce_site_plan(brief, run_id="test-cross-cutting")

    assert result.site_plan["runId"] == "test-cross-cutting"
    assert result.generation_package["runId"] == "test-cross-cutting"
    assert result.generation_package["language"] == brief["language"]
    assert result.generation_package["siteBriefRef"] == "site-brief.json"
    assert "siteBrief" not in result.generation_package

    # pageCount=3 ska resultera i trim eller warning (B138)
    route_count = len(result.site_plan["routePlan"])
    warning = result.site_plan.get("pageCountWarning")
    assert route_count == 3 or warning is not None
