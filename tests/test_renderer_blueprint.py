"""kor-2: the deterministic renderer consumes the Generation Package blueprint.

Covers the kor-2 definition of done
(``docs/heavy-llm-flow/kor-2-renderer-konsumerar-blueprint.md``):

1. The four baseline branches (electrician, hair salon, naprapath clinic,
   ceramics e-commerce) render as four clearly different company types — hero
   copy, offer list and CTA all differ per branch when a grounded blueprint is
   present.
2. Trust-proof renders only grounded ``businessFacts.facts`` and never an
   ungrounded claim (fake cert / invented review) or a placeholder contact.
3. A missing blueprint (or a thin one whose fields fall back) reproduces the
   template output byte-for-byte — zero regression.
4. ``appliedVisibleEffect`` is True when the blueprint actually changed the
   render, and unset otherwise.

The blueprint inputs are the hand-authored baseline fixtures under
``tests/fixtures/blueprints/`` — they represent what a real briefModel +
planning enrichment produces (a richer offer list with summaries, an honest
hero, grounded facts). The renderer is exercised with a minimal Project Input
dossier so the test isolates the blueprint-vs-template behaviour.
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

from packages.generation.build.blueprint_render import (  # noqa: E402
    RenderBlueprint,
    apply_blueprint_to_dossier,
    blueprint_applied_effect,
)
from packages.generation.build.renderers import (  # noqa: E402
    _faq_pairs,
    render_booking,
    render_faq,
    render_home,
    render_menu,
    render_section_contact_cta,
    render_section_faq,
    render_section_hero,
    render_section_product_grid,
    render_section_service_list,
    render_section_treatment_list,
    render_section_trust_proof,
)

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "blueprints"

# branch -> (offer section id used by the scaffold)
BRANCHES = ("elektriker-malmo", "frisor-goteborg", "naprapat-stockholm", "keramik-ehandel")


def _fixture(branch: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / f"{branch}.blueprint.json").read_text(encoding="utf-8"))


def _blueprint(branch: str) -> RenderBlueprint:
    fx = _fixture(branch)
    return RenderBlueprint.from_artifacts(fx["generationPackage"], fx["siteBrief"])


def _dossier(branch: str) -> dict[str, Any]:
    """A minimal, valid Project Input dossier for the branch's scaffold.

    Deliberately generic company/service copy so any branch-specific copy that
    appears in the render must have come from the blueprint, not the dossier.
    """
    fx = _fixture(branch)
    brief = fx["siteBrief"]
    plan = fx["sitePlan"]
    dossier: dict[str, Any] = {
        "siteId": brief["runId"],
        "language": brief.get("language", "sv"),
        "scaffoldId": plan["scaffoldId"],
        "variantId": plan["variantId"],
        "company": {
            "name": brief.get("companyName") or "Företaget AB",
            "tagline": "Vi hjälper dig framåt.",
            "story": "En kort, generisk berättelse om företaget.",
            "businessType": brief.get("businessTypeGuess") or "business",
            "team": [],
        },
        "location": {
            "city": brief.get("locationHint") or "Sverige",
            "country": "Sverige",
            "serviceAreas": [brief.get("locationHint") or "Sverige"],
        },
        "contact": {
            "phone": "+46 70 123 45 67",
            "email": "hej@exempel.se",
            "addressLines": ["Gatan 1", "111 11 Orten"],
            "openingHours": "Mån-Fre 9-17",
        },
        "services": [
            {
                "id": "generisk-tjanst",
                "label": "Generisk tjänst",
                "summary": "En generisk tjänstebeskrivning som inte är branschspecifik.",
            }
        ],
        "trustSignals": [],
        "conversionGoals": list(brief.get("conversionGoals") or []),
    }
    if plan["scaffoldId"] == "ecommerce-lite":
        dossier["products"] = [
            {"id": "generisk-produkt", "label": "Generisk produkt", "summary": "En generisk produkt."}
        ]
    return dossier


def _hero(branch: str, *, with_blueprint: bool) -> str:
    dossier = _dossier(branch)
    return render_section_hero(
        dossier,
        dossier_routes=[],
        listing_route=None,
        contact_path="/kontakt",
        variant_id=dossier["variantId"],
        blueprint=_blueprint(branch) if with_blueprint else None,
    )


# ---------------------------------------------------------------------------
# DoD 1: four baselines render as four clearly different company types
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_four_baselines_render_distinct_heroes():
    headlines: list[str] = []
    for branch in BRANCHES:
        fx_hero = _fixture(branch)["generationPackage"]["contentBlocks"]["home.hero"]
        hero = _hero(branch, with_blueprint=True)
        assert fx_hero["headline"] in hero, (
            f"{branch}: blueprint headline must appear in the rendered hero"
        )
        headlines.append(fx_hero["headline"])
    assert len(set(headlines)) == 4, f"hero headlines must differ per branch: {headlines}"


@pytest.mark.tooling
def test_hero_subheadline_and_proof_line_from_blueprint():
    # elektriker + naprapat carry a proofLine; frisör + keramik do not.
    elektriker = _fixture("elektriker-malmo")["generationPackage"]["contentBlocks"]["home.hero"]
    hero = _hero("elektriker-malmo", with_blueprint=True)
    assert elektriker["subheadline"] in hero
    assert elektriker["proofLine"] in hero

    # A branch without a proofLine must not invent one (the proof <p> is absent).
    frisor_hero = _hero("frisor-goteborg", with_blueprint=True)
    assert "text-[color:var(--foreground)]/80 leading-relaxed" not in frisor_hero


@pytest.mark.tooling
def test_four_baselines_render_distinct_offer_lists():
    title_sets: list[tuple[str, ...]] = []
    for branch in BRANCHES:
        dossier = _dossier(branch)
        blueprint = _blueprint(branch)
        effective, changed = apply_blueprint_to_dossier(dossier, blueprint)
        assert changed, f"{branch}: rich blueprint offer list must override the dossier services"
        labels = tuple(svc["label"] for svc in effective["services"])
        title_sets.append(labels)
        # Every offer title + summary from the blueprint must be present.
        offer_items = next(
            value
            for value in _fixture(branch)["generationPackage"]["contentBlocks"].values()
            if isinstance(value, list)
        )
        expected_titles = tuple(item["title"] for item in offer_items)
        assert labels == expected_titles, f"{branch}: offer titles must come from the blueprint"
        for svc in effective["services"]:
            assert svc["summary"], f"{branch}: every overridden service keeps a non-empty summary"
    assert len(set(title_sets)) == 4, f"offer lists must differ per branch: {title_sets}"


@pytest.mark.tooling
def test_offer_list_renders_blueprint_titles_and_summaries():
    # local-service-business: service-list section.
    dossier = _dossier("elektriker-malmo")
    effective, _ = apply_blueprint_to_dossier(dossier, _blueprint("elektriker-malmo"))
    section = render_section_service_list(
        effective, contact_path="/kontakt", variant_id=dossier["variantId"]
    )
    assert "Elinstallationer" in section
    assert "Säkra installationer för hem och företag." in section
    assert "Generisk tjänst" not in section

    # clinic-healthcare: treatment-list section.
    nap = _dossier("naprapat-stockholm")
    nap_eff, _ = apply_blueprint_to_dossier(nap, _blueprint("naprapat-stockholm"))
    treatments = render_section_treatment_list(
        nap_eff, contact_path="/kontakta-oss", variant_id=nap["variantId"]
    )
    assert "Naprapati" in treatments
    assert "Behandling av besvär i muskler och leder." in treatments

    # ecommerce-lite: product-grid section reads dossier["products"].
    keramik = _dossier("keramik-ehandel")
    keramik_eff, _ = apply_blueprint_to_dossier(keramik, _blueprint("keramik-ehandel"))
    grid = render_section_product_grid(keramik_eff)
    assert "Skål i seladon" in grid
    assert "Handdrejad skål med matt glasyr." in grid


# ---------------------------------------------------------------------------
# DoD 2: honesty — trust-proof + CTA never render ungrounded claims
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_trust_proof_seeded_from_business_facts_when_dossier_empty():
    dossier = _dossier("elektriker-malmo")  # trustSignals = []
    section = render_section_trust_proof(dossier, blueprint=_blueprint("elektriker-malmo"))
    assert section, "facts should seed the trust-proof section when the dossier has none"
    # Confirmed facts render (capitalised); no placeholder / email leaked.
    assert "Verksam i Malmö" in section
    assert "@" not in section
    assert "08-000" not in section


@pytest.mark.tooling
def test_trust_proof_prefers_real_dossier_signals_over_blueprint():
    dossier = _dossier("elektriker-malmo")
    dossier["trustSignals"] = ["Tio år i branschen"]
    section = render_section_trust_proof(dossier, blueprint=_blueprint("elektriker-malmo"))
    assert "Tio år i branschen" in section
    assert "Verksam i Malmö" not in section, "real dossier signals win over blueprint facts"


@pytest.mark.tooling
def test_trust_proof_seeded_from_usps_before_business_facts():
    """Gap 1 (trust-honesty): with no explicit trustSignals but operator
    uniqueSellingPoints present, the home "Varför oss" section shows the
    operator's stated strengths instead of the auto-extracted businessFacts
    metadata narration ("Verksamhetstyp: ...", "Verksam i Malmö"). USPs are
    grounded operator claims, so this is honest and stronger copy.
    """
    dossier = _dossier("elektriker-malmo")  # trustSignals = []
    dossier["uniqueSellingPoints"] = ["25 års erfarenhet", "Jour dygnet runt"]
    section = render_section_trust_proof(dossier, blueprint=_blueprint("elektriker-malmo"))
    assert "25 års erfarenhet" in section
    assert "Jour dygnet runt" in section
    # The businessFacts metadata fallback must NOT be used when USPs exist.
    assert "Verksam i Malmö" not in section


@pytest.mark.tooling
def test_trust_proof_real_signals_win_over_usps():
    """Explicit trustSignals keep precedence over the USP fallback."""
    dossier = _dossier("elektriker-malmo")
    dossier["trustSignals"] = ["Tio år i branschen"]
    dossier["uniqueSellingPoints"] = ["25 års erfarenhet"]
    section = render_section_trust_proof(dossier, blueprint=_blueprint("elektriker-malmo"))
    assert "Tio år i branschen" in section
    assert "25 års erfarenhet" not in section


@pytest.mark.tooling
def test_trust_proof_usp_seed_does_not_mark_blueprint_applied():
    """USPs are dossier (operator) data, not blueprint data. Seeding the trust
    section from uniqueSellingPoints must NOT call blueprint.note_applied,
    otherwise appliedVisibleEffect would falsely credit the LLM blueprint for
    an operator-data change. The businessFacts fallback DOES mark it applied.
    """
    bp_usp = _blueprint("elektriker-malmo")
    dossier = _dossier("elektriker-malmo")  # trustSignals = []
    dossier["uniqueSellingPoints"] = ["Fast pris innan vi börjar"]
    render_section_trust_proof(dossier, blueprint=bp_usp)
    assert "home.trust-proof" not in bp_usp.applied_addresses, (
        "USP seeding is dossier-driven and must not mark the blueprint applied"
    )

    bp_facts = _blueprint("elektriker-malmo")
    render_section_trust_proof(_dossier("elektriker-malmo"), blueprint=bp_facts)
    assert "home.trust-proof" in bp_facts.applied_addresses, (
        "businessFacts fallback is blueprint-derived and must mark it applied"
    )


@pytest.mark.tooling
def test_usps_never_render_as_home_testimonials():
    """Honesty guard: uniqueSellingPoints feed only the neutral "Varför oss"
    strengths section, never the "Sagt om oss" testimonials cards (which would
    misframe an operator self-claim as a customer quote). The testimonials
    section keys off trustSignals alone, so 4 USPs with empty trustSignals
    must NOT produce a testimonials section.
    """
    from packages.generation.build.renderers import _render_home_testimonials_section

    dossier = _dossier("elektriker-malmo")  # trustSignals = []
    dossier["uniqueSellingPoints"] = ["A-fakta", "B-fakta", "C-fakta", "D-fakta"]
    assert _render_home_testimonials_section(dossier) == ""


@pytest.mark.tooling
def test_trust_proof_drops_facts_forbidden_by_quality_risks():
    """A fact that names a certification must not render when qualityRisks forbid
    fake certifications — honesty is structural, not decorative."""
    blueprint = RenderBlueprint(
        business_facts={
            "facts": ["Certifierad mästarelektriker", "Verksam i Malmö"],
            "unknowns": [],
        },
        quality_risks=["No fake certifications"],
    )
    signals = blueprint.honest_trust_signals()
    assert "Verksam i Malmö" in signals
    assert all(" certifierad" not in s.lower() for s in signals)


@pytest.mark.tooling
def test_trust_proof_drops_facts_matching_unknowns():
    blueprint = RenderBlueprint(
        business_facts={"facts": ["Öppettider varje dag", "Verksam i Malmö"], "unknowns": ["öppettider"]},
    )
    signals = blueprint.honest_trust_signals()
    assert "Verksam i Malmö" in signals
    assert all("öppettider" not in s.lower() for s in signals)


@pytest.mark.tooling
def test_contact_cta_follows_conversion_primary_cta():
    nap = _dossier("naprapat-stockholm")
    section = render_section_contact_cta(
        nap, contact_path="/kontakta-oss", blueprint=_blueprint("naprapat-stockholm")
    )
    assert ">Boka behandling<" in section, "the closing CTA follows conversion.primaryCta"

    elektriker = _dossier("elektriker-malmo")
    cta = render_section_contact_cta(
        elektriker, contact_path="/kontakt", blueprint=_blueprint("elektriker-malmo")
    )
    assert ">Be om offert<" in cta


@pytest.mark.tooling
def test_hero_cta_label_rejects_jsx_breaking_label():
    blueprint = RenderBlueprint(conversion={"primaryCta": "Boka <nu>"})
    assert blueprint.primary_cta() is None, "a TSX-breaking CTA label must be rejected"


# ---------------------------------------------------------------------------
# DoD 3: graceful fallback — missing blueprint reproduces the template
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_hero_without_blueprint_uses_company_template():
    dossier = _dossier("elektriker-malmo")
    hero = _hero("elektriker-malmo", with_blueprint=False)
    assert dossier["company"]["name"] in hero
    assert dossier["company"]["tagline"] in hero


@pytest.mark.tooling
@pytest.mark.parametrize("branch", BRANCHES)
def test_no_blueprint_is_byte_identical(branch: str):
    dossier = _dossier(branch)
    routes = ["/", "/tjanster", "/kontakt"]
    none_render = render_home(dossier, routes, variant_id=dossier["variantId"], blueprint=None)
    empty_render = render_home(
        dossier, routes, variant_id=dossier["variantId"], blueprint=RenderBlueprint()
    )
    assert none_render == empty_render, (
        f"{branch}: an empty blueprint must render byte-identically to no blueprint"
    )


@pytest.mark.tooling
def test_title_only_offer_does_not_override_services():
    """A kor-1c-shaped title-only offer (no summaries) must not override the
    dossier's summarised services — the gate that keeps the live pipeline
    byte-identical."""
    dossier = _dossier("elektriker-malmo")
    thin = RenderBlueprint(
        content_blocks={
            "home.hero": {"headline": "Företaget AB"},
            "services.service-list": [{"title": "Elinstallationer"}, {"title": "Felsökning"}],
        }
    )
    effective, changed = apply_blueprint_to_dossier(dossier, thin)
    assert not changed
    assert effective["services"] == dossier["services"]


# ---------------------------------------------------------------------------
# DoD 4: appliedVisibleEffect is true when the blueprint changed the render
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.parametrize("branch", BRANCHES)
def test_applied_visible_effect_true_on_real_change(branch: str):
    dossier = _dossier(branch)
    blueprint = _blueprint(branch)
    # Render the home hero + apply the offer/story so the tracker accumulates.
    render_section_hero(
        dossier,
        dossier_routes=[],
        listing_route=None,
        contact_path="/kontakt",
        variant_id=dossier["variantId"],
        blueprint=blueprint,
    )
    apply_blueprint_to_dossier(dossier, blueprint)
    assert blueprint.had_effect, f"{branch}: blueprint must report a visible effect"
    effect = blueprint_applied_effect(blueprint)
    assert effect is not None and effect["applied"] is True
    assert effect["addresses"], "applied addresses must be recorded"


@pytest.mark.tooling
def test_applied_visible_effect_none_without_change():
    empty = RenderBlueprint()
    assert empty.had_effect is False
    assert blueprint_applied_effect(empty) is None

    # A present blueprint whose hero headline equals the company name does not
    # count as a change.
    dossier = _dossier("elektriker-malmo")
    same = RenderBlueprint(content_blocks={"home.hero": {"headline": dossier["company"]["name"]}})
    render_section_hero(
        dossier,
        dossier_routes=[],
        listing_route=None,
        contact_path="/kontakt",
        variant_id=dossier["variantId"],
        blueprint=same,
    )
    assert same.had_effect is False
    assert blueprint_applied_effect(same) is None


# ---------------------------------------------------------------------------
# story + faq consumption (additive: kor-1c does not emit these yet, so a
# crafted blueprint proves the renderer reads them with template fallback)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_faq_from_blueprint_replaces_template_questions():
    dossier = _dossier("elektriker-malmo")
    blueprint = RenderBlueprint(
        content_blocks={
            "home.faq": [
                {"question": "Hur snabbt kan ni komma?", "answer": "Oftast inom en arbetsdag."},
                {"question": "Jobbar ni med laddboxar?", "answer": "Ja, installation av laddbox ingår."},
            ]
        }
    )
    pairs = _faq_pairs(dossier, blueprint)
    questions = [q for q, _ in pairs]
    assert "Hur snabbt kan ni komma?" in questions
    assert blueprint.had_effect
    # The real opening-hours pair is still appended (honest contact data kept).
    assert any("öppet" in q.lower() for q in questions)


@pytest.mark.tooling
def test_faq_without_blueprint_uses_template_defaults():
    dossier = _dossier("elektriker-malmo")
    template_pairs = _faq_pairs(dossier, None)
    empty_pairs = _faq_pairs(dossier, RenderBlueprint())
    assert template_pairs == empty_pairs
    assert template_pairs, "template FAQ defaults must still render without a blueprint"


@pytest.mark.tooling
def test_story_from_blueprint_overrides_company_story():
    dossier = _dossier("keramik-ehandel")
    blueprint = RenderBlueprint(
        content_blocks={"about.about-story": {"body": "Vi drejar varje pjäs för hand i vår lilla verkstad."}}
    )
    effective, changed = apply_blueprint_to_dossier(dossier, blueprint)
    assert changed
    assert effective["company"]["story"] == "Vi drejar varje pjäs för hand i vår lilla verkstad."
    # Original dossier is not mutated.
    assert dossier["company"]["story"] == "En kort, generisk berättelse om företaget."


# ===========================================================================
# Review fixes (PR #165): five findings, one locking test group each.
# ===========================================================================


# --- Finding 1: CTA honesty — phone-promising labels gated when phone missing


@pytest.mark.tooling
def test_phone_cta_gated_when_phone_missing_and_blueprint_flags_it():
    blueprint = RenderBlueprint(
        conversion={
            "primaryAction": "call",
            "primaryCta": "Ring oss",
            "ctaRules": ["visa inte telefon om telefon saknas"],
        },
        quality_risks=["Do not show phone if missing"],
    )
    # Phone missing + honesty signal -> the accessor must not return the label.
    assert blueprint.primary_cta(phone_available=False) is None
    assert blueprint.hero_cta("home", phone_available=False) is None
    # Phone present -> the label is fine.
    assert blueprint.primary_cta(phone_available=True) == "Ring oss"
    assert blueprint.hero_cta("home", phone_available=True) == "Ring oss"


@pytest.mark.tooling
def test_non_phone_cta_not_gated_when_phone_missing():
    blueprint = RenderBlueprint(
        conversion={"primaryAction": "request_quote", "primaryCta": "Be om offert"},
        quality_risks=["Do not show phone if missing"],
    )
    assert blueprint.primary_cta(phone_available=False) == "Be om offert"


@pytest.mark.tooling
def test_phone_cta_not_gated_without_honesty_signal():
    # No qualityRisk / ctaRule / unknown about phone -> keep the label even if
    # the caller reports no phone (no signal to gate on).
    blueprint = RenderBlueprint(conversion={"primaryAction": "call", "primaryCta": "Ring oss"})
    assert blueprint.primary_cta(phone_available=False) == "Ring oss"


@pytest.mark.tooling
def test_phone_cta_gated_via_unknowns():
    blueprint = RenderBlueprint(
        conversion={"primaryCta": "Ring oss"},
        business_facts={"facts": [], "unknowns": ["telefonnummer"]},
    )
    assert blueprint.primary_cta(phone_available=False) is None
    assert blueprint.primary_cta(phone_available=True) == "Ring oss"


@pytest.mark.tooling
def test_contact_cta_render_gates_phone_label_when_phone_missing():
    dossier = _dossier("elektriker-malmo")
    dossier["contact"]["phone"] = ""  # missing -> not a real phone
    blueprint = RenderBlueprint(
        conversion={
            "primaryAction": "call",
            "primaryCta": "Ring oss",
            "ctaRules": ["visa inte telefon om telefon saknas"],
        },
        quality_risks=["Do not show phone if missing"],
    )
    gated = render_section_contact_cta(dossier, contact_path="/kontakt", blueprint=blueprint)
    assert ">Ring oss<" not in gated
    assert ">Kontakta oss<" in gated  # honest template fallback

    dossier["contact"]["phone"] = "+46 70 111 22 33"  # real phone -> label allowed
    allowed = render_section_contact_cta(dossier, contact_path="/kontakt", blueprint=blueprint)
    assert ">Ring oss<" in allowed


@pytest.mark.tooling
def test_hero_render_gates_phone_label_when_phone_missing():
    dossier = _dossier("elektriker-malmo")
    dossier["contact"]["phone"] = ""
    blueprint = RenderBlueprint(
        content_blocks={"home.hero": {"headline": "Trygg el", "primaryCta": "Ring oss"}},
        conversion={"primaryAction": "call", "primaryCta": "Ring oss"},
        quality_risks=["Do not show phone if missing"],
    )
    hero = render_section_hero(
        dossier,
        dossier_routes=[],
        listing_route=None,
        contact_path="/kontakt",
        variant_id=dossier["variantId"],
        blueprint=blueprint,
    )
    assert "Ring oss" not in hero  # phone CTA gated; falls back to template label
    assert "home.hero.primaryCta" not in blueprint.applied_addresses


# --- Finding 2 (false positive lock): blueprint FAQ keeps /faq link + CTA


@pytest.mark.tooling
def test_faq_home_link_preserved_with_and_without_blueprint():
    """The home FAQ section's "Se alla frågor" → /faq link is gated solely by
    the presence of a /faq route (``dossier_routes``), independent of whether
    blueprint pairs replace the template defaults. Locks finding 2: blueprint
    FAQ never drops the /faq link behaviour."""
    dossier = _dossier("elektriker-malmo")
    blueprint = RenderBlueprint(
        content_blocks={
            "home.faq": [
                {"question": "Hur snabbt kan ni komma?", "answer": "Oftast inom en arbetsdag."},
                {"question": "Jobbar ni med laddboxar?", "answer": "Ja, det gör vi."},
            ]
        }
    )
    with_bp = render_section_faq(dossier, dossier_routes=["/faq"], blueprint=blueprint)
    without_bp = render_section_faq(dossier, dossier_routes=["/faq"], blueprint=None)
    for section in (with_bp, without_bp):
        assert 'href="/faq"' in section
        assert "Se alla frågor" in section
    assert "Hur snabbt kan ni komma?" in with_bp  # blueprint pairs do render
    # No /faq route -> no link, in both modes (no ghost link introduced).
    assert 'href="/faq"' not in render_section_faq(dossier, dossier_routes=[], blueprint=blueprint)


@pytest.mark.tooling
def test_dedicated_faq_route_keeps_contact_cta_with_blueprint():
    """The dedicated /faq route keeps its trailing contact CTA (and receives the
    blueprint pairs) so it stays consistent with the home section."""
    dossier = _dossier("elektriker-malmo")
    blueprint = RenderBlueprint(
        content_blocks={
            "home.faq": [{"question": "Hur snabbt kan ni komma?", "answer": "Oftast inom en arbetsdag."}]
        }
    )
    page = render_faq(dossier, contact_path="/kontakt", blueprint=blueprint)
    assert "Hur snabbt kan ni komma?" in page  # blueprint pair rendered
    assert 'href={"/kontakt"}' in page  # _wizard_contact_cta preserved
    # Without a blueprint the dedicated route still renders its CTA.
    assert 'href={"/kontakt"}' in render_faq(dossier, contact_path="/kontakt")


# --- Finding 3: appliedVisibleEffect only when proofLine adds new copy


@pytest.mark.tooling
def test_proof_line_not_marked_when_duplicate_of_subheadline():
    dossier = _dossier("elektriker-malmo")
    sub = "Personlig och trygg elhjälp i hela Malmö."
    blueprint = RenderBlueprint(
        content_blocks={"home.hero": {"headline": "Trygg el", "subheadline": sub, "proofLine": sub}}
    )
    hero = render_section_hero(
        dossier,
        dossier_routes=[],
        listing_route=None,
        contact_path="/kontakt",
        variant_id=dossier["variantId"],
        blueprint=blueprint,
    )
    # proofLine restates the subheadline -> not counted, not rendered twice.
    assert "home.hero.proofLine" not in blueprint.applied_addresses
    assert hero.count(sub) == 1
    # The subheadline itself still counts (it differs from the template tagline).
    assert "home.hero.subheadline" in blueprint.applied_addresses


@pytest.mark.tooling
def test_proof_line_marked_and_rendered_when_distinct():
    dossier = _dossier("elektriker-malmo")
    blueprint = RenderBlueprint(
        content_blocks={
            "home.hero": {
                "headline": "Trygg el",
                "subheadline": "Säker elhjälp i Malmö.",
                "proofLine": "Tydlig rådgivning och snabb återkoppling.",
            }
        }
    )
    hero = render_section_hero(
        dossier,
        dossier_routes=[],
        listing_route=None,
        contact_path="/kontakt",
        variant_id=dossier["variantId"],
        blueprint=blueprint,
    )
    assert "Tydlig rådgivning och snabb återkoppling." in hero
    assert "home.hero.proofLine" in blueprint.applied_addresses


# --- Finding 4: restaurant routes thread the blueprint to the contact CTA


@pytest.mark.tooling
def test_restaurant_routes_thread_blueprint_to_contact_cta():
    cafe = json.loads(
        (REPO_ROOT / "examples" / "cafe-bistro.project-input.json").read_text(encoding="utf-8")
    )
    blueprint = RenderBlueprint(conversion={"primaryAction": "book", "primaryCta": "Boka bord"})
    menu = render_menu(cafe, contact_path="/hitta-hit", blueprint=blueprint)
    booking = render_booking(cafe, contact_path="/hitta-hit", blueprint=blueprint)
    assert ">Boka bord<" in menu
    assert ">Boka bord<" in booking
    # Without a blueprint the closing CTA is the generic template label.
    assert ">Kontakta oss<" in render_menu(cafe, contact_path="/hitta-hit")
    assert ">Kontakta oss<" in render_booking(cafe, contact_path="/hitta-hit")


# --- Finding 5: offer-block selection never grabs an arbitrary list block


@pytest.mark.tooling
def test_offer_address_ignores_non_offer_list_blocks():
    blueprint = RenderBlueprint(
        content_blocks={
            "home.faq": [{"question": "Q?", "answer": "A."}],
            "home.hero": {"headline": "H"},
        }
    )
    assert blueprint.offer_address() is None
    assert blueprint.offer_items() == []


@pytest.mark.tooling
def test_offer_address_picks_offer_section_among_multiple_lists():
    blueprint = RenderBlueprint(
        content_blocks={
            "home.faq": [{"question": "Q?", "answer": "A."}],
            "services.service-list": [{"title": "Tjänst", "summary": "Beskrivning."}],
        }
    )
    assert blueprint.offer_address() == "services.service-list"


@pytest.mark.tooling
def test_non_offer_list_block_does_not_override_services():
    dossier = _dossier("elektriker-malmo")
    blueprint = RenderBlueprint(
        content_blocks={"home.faq": [{"question": "Q?", "answer": "A."}]}
    )
    effective, changed = apply_blueprint_to_dossier(dossier, blueprint)
    assert not changed
    assert effective["services"] == dossier["services"]
