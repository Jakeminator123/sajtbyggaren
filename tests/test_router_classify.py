"""Tests for the deterministic message router (KÖR-6a).

These lock the acceptance criteria from
docs/heavy-llm-flow/02-orchestrator-och-intent.md §3 (the clock examples
A-E) as regression tests, plus a broad coverage table (~45 prompts across
all eight message kinds). The router is pure and deterministic, so every
assertion is exact.

The two hard invariants this slice exists to protect:
- A pure question / discovery / reference / review never starts a build or
  a preview (``answer_only`` / ``plan_only`` -> ``shouldStartPreview`` is
  False, ``buildRequirement`` is ``none``/``plan_only``).
- A live user session (builder coexistence) forces ``shouldStartPreview``
  False even for a real rebuild.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.router import (  # noqa: E402
    RouterContext,
    RouterDecision,
    classify_message,
)

# ---------------------------------------------------------------------------
# Clock examples A-E (02 §3) - the canonical acceptance criteria
# ---------------------------------------------------------------------------


def test_clock_a_pure_question_is_answer_only_no_build():
    """A: "vad är klockan?" -> answer_only, no build, no preview."""
    d = classify_message("vad är klockan?")
    assert d.messageKind == "answer_only"
    assert d.buildRequirement == "none"
    assert d.contextLevel == "none"
    assert d.shouldStartPreview is False
    assert d.editKind == "none"
    # The router can explain why it does not start a build.
    assert "answer" in d.rationale.lower()


def test_clock_b_component_add_resolves_target_and_rebuilds():
    """B: "lägg en klocka i andra sektionen till vänster" -> edit_instruction,
    component_add, targeted_rebuild, target resolved (ordinal 2, left)."""
    d = classify_message("lägg en klocka i andra sektionen till vänster")
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "component_add"
    assert d.buildRequirement == "targeted_rebuild"
    assert d.contextLevel == "artifacts_plus_sections"
    assert d.componentIntent == "clock_widget"
    assert d.target is not None
    assert d.target.routeId == "home"
    assert d.target.sectionOrdinal == 2
    assert d.target.position == "left"
    assert d.shouldStartPreview is True


def test_clock_c_discovery_lists_options_no_build():
    """C: "vilka klockor finns att tillgå?" -> component_discovery, none,
    component_registry."""
    d = classify_message("vilka klockor finns att tillgå?")
    assert d.messageKind == "component_discovery"
    assert d.editKind == "none"
    assert d.buildRequirement == "none"
    assert d.contextLevel == "component_registry"
    assert d.shouldStartPreview is False


def test_clock_d_reference_is_plan_only_with_do_not_copy():
    """D: "samma klocka som på aftonbladet.se" -> reference_analysis,
    plan_only, external_reference, risk do_not_copy_exact."""
    d = classify_message("samma klocka som på aftonbladet.se")
    assert d.messageKind == "reference_analysis"
    assert d.buildRequirement == "plan_only"
    assert d.contextLevel == "external_reference"
    assert d.risk == "do_not_copy_exact"
    assert d.reference is not None
    assert d.reference.url == "aftonbladet.se"
    assert d.shouldStartPreview is False


def test_clock_e_multi_intent_preserves_copy_constraint():
    """E: "gör sidan mer premium, lägg en klocka i andra sektionen, ändra
    inte texterna" -> multi_intent with preserve_copy constraint."""
    d = classify_message(
        "gör sidan mer premium, lägg en klocka i andra sektionen, "
        "ändra inte texterna"
    )
    assert d.messageKind == "multi_intent"
    assert d.buildRequirement == "targeted_rebuild"
    assert "preserve_copy" in d.constraints
    # The three deluppgifter: a style change, a component add, a constraint.
    kinds = [s.editKind for s in d.subtasks]
    assert "visual_style" in kinds
    assert "component_add" in kinds
    assert any(s.constraint == "preserve_copy" for s in d.subtasks)


# ---------------------------------------------------------------------------
# Broad coverage table (~45 prompts across all eight message kinds)
# ---------------------------------------------------------------------------

COVERAGE: list[tuple[str, str, str]] = [
    # answer_only - pure questions unrelated to the site
    ("vad är klockan", "answer_only", "none"),
    ("vad är klockan?", "answer_only", "none"),
    ("hur mycket är klockan just nu?", "answer_only", "none"),
    ("vad är huvudstaden i Frankrike?", "answer_only", "none"),
    ("förklara hur fotosyntes fungerar", "answer_only", "none"),
    ("vem skrev Hamlet?", "answer_only", "none"),
    ("berätta en rolig fakta", "answer_only", "none"),
    ("vad är klockan och vad är datumet?", "answer_only", "none"),
    # component_discovery
    ("vilka klockor finns att tillgå?", "component_discovery", "none"),
    ("vilka klockor finns?", "component_discovery", "none"),
    ("vilka komponenter finns att välja på?", "component_discovery", "none"),
    ("vad finns det för widgets?", "component_discovery", "none"),
    ("finns det några kontaktformulär jag kan använda?", "component_discovery", "none"),
    ("vilka alternativ har jag för galleri?", "component_discovery", "none"),
    ("vilka typsnitt kan jag välja?", "component_discovery", "none"),
    # reference_analysis
    ("samma klocka som på aftonbladet.se", "reference_analysis", "plan_only"),
    ("gör en hero liknande stripe.com", "reference_analysis", "plan_only"),
    ("jag vill ha en meny som på mcdonalds.se", "reference_analysis", "plan_only"),
    ("kan du kolla in apple.com och göra något liknande?", "reference_analysis", "plan_only"),
    # edit_instruction - component add/remove
    ("lägg en klocka i andra sektionen till vänster", "edit_instruction", "targeted_rebuild"),
    ("lägg till en kontaktknapp överst", "edit_instruction", "targeted_rebuild"),
    ("ta bort knappen", "edit_instruction", "targeted_rebuild"),
    ("lägg till en faq-sektion", "edit_instruction", "targeted_rebuild"),
    # edit_instruction - visual_style
    ("gör sidan mer premium", "edit_instruction", "targeted_rebuild"),
    ("ändra färgen till blått", "edit_instruction", "targeted_rebuild"),
    ("gör färgen rosa", "edit_instruction", "targeted_rebuild"),
    ("gör den rosa", "edit_instruction", "targeted_rebuild"),
    ("gör sidan blå", "edit_instruction", "targeted_rebuild"),
    ("gör om hela sidan från grunden", "edit_instruction", "full_rebuild"),
    # edit_instruction - copy_change
    ("skriv om rubriken på startsidan", "edit_instruction", "artifact_patch_only"),
    ("uppdatera texten i hero-sektionen", "edit_instruction", "artifact_patch_only"),
    # edit_instruction - layout_change
    ("flytta klockan till höger", "edit_instruction", "targeted_rebuild"),
    ("centrera rubriken", "edit_instruction", "targeted_rebuild"),
    # edit_instruction - route_add
    ("lägg till en kontaktsida", "edit_instruction", "targeted_rebuild"),
    # multi_intent
    (
        "gör sidan mer premium, lägg en klocka i andra sektionen, ändra inte texterna",
        "multi_intent",
        "targeted_rebuild",
    ),
    ("lägg till en kontaktknapp och gör sidan mörkare", "multi_intent", "targeted_rebuild"),
    ("ta bort galleriet och lägg till ett kontaktformulär", "multi_intent", "targeted_rebuild"),
    ("byt färg på knappen och flytta den till höger", "multi_intent", "targeted_rebuild"),
    # bug_report
    ("knappen funkar inte", "bug_report", "plan_only"),
    ("sidan kraschar när jag klickar på menyn", "bug_report", "plan_only"),
    ("kontaktformuläret fungerar inte", "bug_report", "plan_only"),
    # site_review
    ("vad tycker du om sidan?", "site_review", "none"),
    ("kan du granska designen?", "site_review", "none"),
    ("vad tycker du om hemsidan?", "site_review", "none"),
    ("hur ser startsidan ut?", "site_review", "none"),
    # unclear
    ("", "unclear", "none"),
    ("hej", "unclear", "none"),
    ("ändra", "unclear", "none"),
    ("fixa det där", "unclear", "none"),
]


@pytest.mark.parametrize("prompt,message_kind,build_requirement", COVERAGE)
def test_coverage_table(prompt: str, message_kind: str, build_requirement: str):
    d = classify_message(prompt)
    assert d.messageKind == message_kind, f"{prompt!r} -> {d.messageKind} ({d.rationale})"
    assert d.buildRequirement == build_requirement, (
        f"{prompt!r} -> {d.buildRequirement} ({d.rationale})"
    )


@pytest.mark.parametrize("prompt,message_kind,build_requirement", COVERAGE)
def test_no_preview_without_a_real_rebuild(prompt, message_kind, build_requirement):
    """The hard rule: answer_only / plan_only (and anything that is not a
    real rebuild) must never set shouldStartPreview."""
    d = classify_message(prompt)
    if d.buildRequirement in ("none", "plan_only", "artifact_patch_only"):
        assert d.shouldStartPreview is False, (
            f"{prompt!r}: {d.buildRequirement} must not start preview"
        )


@pytest.mark.parametrize("prompt,message_kind,build_requirement", COVERAGE)
def test_every_decision_is_schema_shaped(prompt, message_kind, build_requirement):
    """Every classification returns a fully-formed RouterDecision."""
    d = classify_message(prompt)
    assert isinstance(d, RouterDecision)
    assert d.rationale  # non-empty explanation always present


# ---------------------------------------------------------------------------
# Builder coexistence + context-driven target resolution
# ---------------------------------------------------------------------------


def test_active_user_session_blocks_preview_even_for_rebuild():
    """Coexistence (02 §8): a live session on the same site must never get a
    router-started preview, even when a rebuild is otherwise required."""
    ctx = RouterContext(siteId="elektriker-malmo", hasActiveUserSession=True)
    d = classify_message("lägg en klocka i andra sektionen till vänster", context=ctx)
    assert d.messageKind == "edit_instruction"
    assert d.buildRequirement == "targeted_rebuild"
    assert d.shouldStartPreview is False


def test_context_route_sections_resolve_section_id():
    """When a caller supplies a route/section map, the ordinal resolves to a
    concrete sectionId - without the router reading disk itself."""
    ctx = RouterContext(routeSections={"home": ["hero", "services", "about"]})
    d = classify_message("lägg en klocka i andra sektionen", context=ctx)
    assert d.target is not None
    assert d.target.sectionOrdinal == 2
    assert d.target.sectionId == "services"


def test_without_context_section_id_stays_none():
    """No context -> the router parses the ordinal but does not invent a
    sectionId (that mapping is the context layer's job, kor-7a)."""
    d = classify_message("lägg en klocka i andra sektionen")
    assert d.target is not None
    assert d.target.sectionOrdinal == 2
    assert d.target.sectionId is None


def test_preserve_constraint_on_single_edit_is_not_multi_intent():
    """A single edit plus a preserve constraint stays edit_instruction (one
    actionable change) but carries the constraint."""
    d = classify_message("gör sidan mer premium men ändra inte texterna")
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "visual_style"
    assert "preserve_copy" in d.constraints


def test_pure_questions_never_require_a_build():
    """Regression: the whole point of kor-6a is that pure questions stop the
    chat from rebuilding. Lock it for the canonical trio."""
    for prompt in ("vad är klockan", "vilka klockor finns?", "vad tycker du om sidan?"):
        d = classify_message(prompt)
        assert d.buildRequirement in ("none",)
        assert d.shouldStartPreview is False


# ---------------------------------------------------------------------------
# FIX 1 regression (Bug Review blocker) - _is_question must be crash-safe
# ---------------------------------------------------------------------------


def test_is_question_is_robust_to_none_empty_and_tuple_inputs():
    """_is_question must never raise on None / empty input and must still
    detect a question that lacks a trailing '?'. str.startswith only ever
    sees a tuple of non-empty str prefixes."""
    from packages.generation.orchestration.router.classify import _is_question

    # A question WITHOUT '?' is still detected via the leading question word.
    assert _is_question("vad är klockan", "vad är klockan") is True
    # None / empty must resolve to False without raising.
    assert _is_question(None, None) is False  # type: ignore[arg-type]
    assert _is_question("", "") is False
    assert _is_question("ingen fråga alls", "ingen fråga alls") is False


def test_question_without_question_mark_classifies_without_crashing():
    """End-to-end: "vad är klockan" (no '?') classifies as answer_only and
    never raises (the reported blocker)."""
    decision = classify_message("vad är klockan")
    assert isinstance(decision, RouterDecision)
    assert decision.messageKind == "answer_only"
    assert decision.buildRequirement == "none"
    assert decision.shouldStartPreview is False


# ---------------------------------------------------------------------------
# FIX 2 regression (Bug Review blocker) - general "som på <domän>" detector
# ---------------------------------------------------------------------------

REFERENCE_PROMPTS = [
    "samma klocka som på aftonbladet.se",
    "som på aftonbladet.se",
    "likadan sektion som på example.com",
    "gör den lik www.någonannan.se",
    "gör en hero som på stripe.com",
    "jag vill ha en meny liknande mcdonalds.se",
    "bygg en sektion i stil med apple.com",
]


@pytest.mark.parametrize("prompt", REFERENCE_PROMPTS)
def test_reference_analysis_is_domain_agnostic(prompt: str):
    """Any "som på <domän>" / "lik(adan)" reference across several distinct
    domains (Unicode included) -> reference_analysis, plan_only, no preview.
    Proves the detector is general, not hardcoded to aftonbladet."""
    d = classify_message(prompt)
    assert d.messageKind == "reference_analysis", f"{prompt!r} -> {d.messageKind} ({d.rationale})"
    assert d.buildRequirement == "plan_only"
    assert d.shouldStartPreview is False
    assert d.reference is not None and d.reference.url
    assert d.risk == "do_not_copy_exact"


def test_reference_detector_recognises_multiple_distinct_domains():
    """A future hardcode regression (only aftonbladet) must fail here: several
    different domains, including a Swedish å-domain, must be extracted."""
    urls = {classify_message(p).reference.url for p in REFERENCE_PROMPTS}
    assert {"aftonbladet.se", "example.com", "någonannan.se", "stripe.com"} <= urls


def test_url_without_comparison_stays_an_edit_not_a_reference():
    """Guard: a URL without a comparison cue ("lägg till en länk till X") is an
    edit, not a reference - the detector keys on the comparison, not the URL."""
    d = classify_message("lägg till en länk till aftonbladet.se")
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "component_add"


# ---------------------------------------------------------------------------
# P2 Bug Review regressions (chatgpt-codex-connectors, 10 findings)
# ---------------------------------------------------------------------------


def test_p2_1_bare_style_adjective_question_is_answer_only():
    """Finding 1 (HIGH): a bare style adjective with no edit context must NOT
    become an edit. "vad betyder premium?" -> answer_only, no preview."""
    d = classify_message("vad betyder premium?")
    assert d.messageKind == "answer_only"
    assert d.buildRequirement == "none"
    assert d.shouldStartPreview is False
    # Sanity: the same adjective WITH context (site ref + "mer") is still an edit.
    d2 = classify_message("gör sidan mer premium")
    assert d2.messageKind == "edit_instruction"
    assert d2.editKind == "visual_style"


@pytest.mark.parametrize(
    "prompt",
    ["vad betyder premium?", "vad är minimalistisk design?", "är modern bättre än elegant?"],
)
def test_p2_1_style_word_questions_never_start_preview(prompt):
    d = classify_message(prompt)
    assert d.shouldStartPreview is False
    assert d.buildRequirement == "none"
    assert d.messageKind in ("answer_only", "site_review", "unclear")


def test_p2_2_bare_remove_verb_is_clarification_not_empty_remove():
    """Finding 2 (HIGH): "ta bort" with no object -> unclear/clarification, not
    a component_remove with an empty target."""
    d = classify_message("ta bort")
    assert d.messageKind == "unclear"
    assert d.requiresClarification is True
    assert d.shouldStartPreview is False


@pytest.mark.parametrize(
    "prompt", ["ta bort knappen", "ta bort galleriet", "radera kontaktformuläret"]
)
def test_p2_2_remove_with_object_is_component_remove(prompt):
    d = classify_message(prompt)
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "component_remove"


@pytest.mark.parametrize(
    "prompt",
    ["skapa en klocka i andra sektionen", "bygg en kontaktknapp", "skapa en karta till vänster"],
)
def test_p2_3_create_verb_is_component_add(prompt):
    """Finding 3: create-verbs (skapa/bygg) + a component -> component_add."""
    d = classify_message(prompt)
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "component_add"
    assert d.buildRequirement == "targeted_rebuild"


@pytest.mark.parametrize("prompt", ["skriv ny rubrik", "skriv om rubriken", "uppdatera texten"])
def test_p2_4_copy_prompts_are_copy_change_not_route_add(prompt):
    """Finding 4: "ny/nytt" must not pull copy prompts into route_add before
    copy_change."""
    d = classify_message(prompt)
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "copy_change"
    assert d.buildRequirement == "artifact_patch_only"


def test_p2_4_new_page_cue_still_routes_with_page_noun():
    """A genuine new page ("lägg till en ny sida") still becomes route_add."""
    d = classify_message("lägg till en ny sida")
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "route_add"


def test_p2_5_component_on_page_is_component_add_not_route_add():
    """Finding 5: a component noun beats a generic page-noun. "lägg en klocka
    på sidan" -> component_add (the page word is a location, not a new page)."""
    d = classify_message("lägg en klocka på sidan")
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "component_add"
    assert d.componentIntent == "clock_widget"


def test_p2_6_inline_preserve_keeps_edit_and_constraint():
    """Finding 6: a preserve constraint in the SAME clause is recorded AND the
    edit is still classified (the "ändra texten" wording does not become a
    copy edit)."""
    d = classify_message("gör sidan mörkare utan att ändra texten")
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "visual_style"
    assert "preserve_copy" in d.constraints


def test_p2_7_coordinated_objects_keep_both_subtasks():
    """Finding 7: a bare edit verb carries over coordinated objects -> both
    objects become subtasks."""
    d = classify_message("lägg till en karta och ett kontaktformulär")
    assert d.messageKind == "multi_intent"
    intents = {s.componentIntent for s in d.subtasks}
    assert {"map_embed", "contact_form"} <= intents
    assert all(s.editKind == "component_add" for s in d.subtasks)


def test_p2_8_multi_intent_with_reference_stays_plan_only():
    """Finding 8: multi-intent + an external reference keeps reference + risk
    and gates to plan_only (no auto-rebuild, no preview)."""
    d = classify_message("gör sidan mer premium och lägg en klocka som på aftonbladet.se")
    assert d.messageKind == "multi_intent"
    assert d.buildRequirement == "plan_only"
    assert d.reference is not None and d.reference.url == "aftonbladet.se"
    assert d.risk == "do_not_copy_exact"
    assert d.shouldStartPreview is False
    assert len(d.subtasks) >= 2


def test_p2_9_reference_with_placement_carries_target():
    """Finding 9: a reference that includes placement carries the parsed target
    in the RouterDecision."""
    d = classify_message("lägg en klocka i andra sektionen till vänster som på aftonbladet.se")
    assert d.messageKind == "reference_analysis"
    assert d.target is not None
    assert d.target.sectionOrdinal == 2
    assert d.target.position == "left"
    assert d.reference is not None and d.reference.url == "aftonbladet.se"


@pytest.mark.parametrize(
    "prompt,expected_url",
    [
        ("samma klocka som på aftonbladet.se/sport?x=1", "aftonbladet.se/sport?x=1"),
        ("gör en hero som på stripe.com/pricing", "stripe.com/pricing"),
        ("som på example.com/path.", "example.com/path"),
    ],
)
def test_p2_10_find_url_keeps_full_path_and_query(prompt, expected_url):
    """Finding 10: the referenced URL keeps its path/query (trailing sentence
    punctuation trimmed), not just the domain."""
    d = classify_message(prompt)
    assert d.messageKind == "reference_analysis"
    assert d.reference is not None
    assert d.reference.url == expected_url


def test_p2_10_find_url_unit_keeps_path_strips_scheme_and_punctuation():
    from packages.generation.orchestration.router.classify import _find_url

    assert _find_url("se aftonbladet.se/sport?x=1 nu") == "aftonbladet.se/sport?x=1"
    assert _find_url("kolla www.någonannan.se/a/b") == "någonannan.se/a/b"
    assert _find_url("ingen url här alls") is None


# ---------------------------------------------------------------------------
# 2026-06-08 router slice: color names are visual_style adjectives so the
# "gör <noun> <color>" / "gör den <color>" family classifies as a style edit
# (previously only "ändra färgen till X" worked). The hard regression: an
# additive component request that happens to mention a color ("lägg till en
# blå knapp") must stay component_add and must NEVER restyle the whole site.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt",
    [
        "gör färgen rosa",
        "gör den rosa",
        "gör sidan blå",
        "gör bakgrunden grön",
        "make it pink",
    ],
)
def test_color_make_phrasing_is_visual_style(prompt: str):
    """"gör färgen rosa" and friends -> edit_instruction / visual_style /
    targeted_rebuild (the slice that completes "ändra färgen…" parity)."""
    d = classify_message(prompt)
    assert d.messageKind == "edit_instruction", f"{prompt!r} -> {d.messageKind} ({d.rationale})"
    assert d.editKind == "visual_style"
    assert d.buildRequirement == "targeted_rebuild"


@pytest.mark.parametrize(
    "prompt,intent",
    [
        ("lägg till en blå knapp", "button"),
        ("lägg till ett rött kontaktformulär", "contact_form"),
    ],
)
def test_colored_component_add_is_not_a_global_restyle(prompt: str, intent: str):
    """Regression: an ADD request that mentions a color is component_add, NOT
    visual_style - a colored component must never restyle the whole site."""
    d = classify_message(prompt)
    assert d.messageKind == "edit_instruction", f"{prompt!r} -> {d.messageKind} ({d.rationale})"
    assert d.editKind == "component_add"
    assert d.componentIntent == intent


def test_bare_color_word_question_is_not_an_edit():
    """A bare color with no style context stays answer_only (same fix-1 guard
    as bare style adjectives like "premium")."""
    d = classify_message("vad betyder rosa?")
    assert d.editKind == "none"
    assert d.buildRequirement == "none"
    assert d.shouldStartPreview is False


# ---------------------------------------------------------------------------
# 2026-06-08 stylist slice: the router shares the central colour lexicon, so
# lexicon colours ("korall") and compound colours ("grönvit") read as
# visual_style adjectives. The same fix-1 guard holds: a bare/compound colour
# without style context is no edit, and an additive request that mentions a
# (compound) colour stays component_add - never a global restyle.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt",
    [
        "gör sajten grönvit",
        "gör den svartvit",
        "gör den mintgrön",
        "gör färgen korall",
        "ändra färgen till grönvitt",
    ],
)
def test_compound_and_lexicon_colours_are_visual_style(prompt: str):
    """Free/compound colour expressions classify as a global visual_style edit
    (so the stylist's theme path runs), with a real targeted rebuild."""
    d = classify_message(prompt)
    assert d.messageKind == "edit_instruction", f"{prompt!r} -> {d.messageKind} ({d.rationale})"
    assert d.editKind == "visual_style"
    assert d.buildRequirement == "targeted_rebuild"


def test_compound_colour_add_request_stays_component_add():
    """Regression: an ADD request that mentions a compound colour is
    component_add, never a global restyle."""
    d = classify_message("lägg till en grönvit knapp")
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "component_add"
    assert d.componentIntent == "button"


def test_bare_compound_colour_question_is_not_an_edit():
    """fix-1 holds for compounds too: "vad betyder grönvit?" is not an edit."""
    d = classify_message("vad betyder grönvit?")
    assert d.editKind == "none"
    assert d.buildRequirement == "none"
    assert d.shouldStartPreview is False


# ---------------------------------------------------------------------------
# 2026-06-08 section_builder slice: "lägg till en sektion om <typ>" /
# "lägg till en <typ>-sektion" classifies as section_add with a type slug
# (team/faq/trust/reviews), distinct from component_add (a widget) and route_add
# (a new page). An unknown type still classifies as section_add (the apply chain
# does the honest no-op). Guards: a positional reference to an existing section
# ("i andra sektionen") stays component_add; questions never become edits.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt,slug",
    [
        ("lägg till en sektion om garantier", "trust"),
        ("lägg till en FAQ-sektion", "faq"),
        ("lägg till en team-sektion", "team"),
        ("lägg till en sektion om teamet", "team"),
        ("lägg till en sektion med recensioner", "reviews"),
        ("skapa en sektion med vanliga frågor", "faq"),
        ("lägg till en sektion om trygghet", "trust"),
        # section_builder broadening (2026-06-08): the module-drag-and-drop types
        # that reuse an existing Dossier + renderer route as section_add too.
        ("lägg till en galleri-sektion", "gallery"),
        ("lägg till en sektion med priser", "pricing"),
        ("lägg till en öppettider-sektion", "hours"),
        ("lägg till en sektion med en karta", "map"),
        ("lägg till en kontaktformulär-sektion", "contact-form"),
    ],
)
def test_section_add_classifies_with_type_slug(prompt: str, slug: str):
    """A sanctioned section add -> edit_instruction / section_add / targeted_rebuild,
    with the type slug carried on componentIntent."""
    d = classify_message(prompt)
    assert d.messageKind == "edit_instruction", f"{prompt!r} -> {d.messageKind} ({d.rationale})"
    assert d.editKind == "section_add"
    assert d.buildRequirement == "targeted_rebuild"
    assert d.componentIntent == slug
    assert d.shouldStartPreview is True


def test_section_add_unknown_type_still_section_add():
    """An unrecognised section type still classifies as section_add (the apply
    chain does the honest no-op); the router never invents a type slug."""
    d = classify_message("lägg till en sektion om färger")
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "section_add"
    assert d.componentIntent is None


def test_section_add_does_not_steal_colored_button():
    """Regression: an add of a colored widget is component_add, never section_add
    (no section noun present)."""
    d = classify_message("lägg till en blå knapp")
    assert d.editKind == "component_add"
    assert d.componentIntent == "button"


def test_section_add_does_not_steal_new_page():
    """Regression: "lägg till en sida om X" is route_add, never section_add."""
    d = classify_message("lägg till en sida om vårt team")
    assert d.editKind == "route_add"


def test_widget_into_named_section_stays_component_add():
    """A different widget added INTO a named section ("i andra sektionen") is a
    component_add at that location, not a section_add."""
    d = classify_message("lägg till ett kontaktformulär i sista sektionen")
    assert d.editKind == "component_add"
    assert d.componentIntent == "contact_form"


def test_section_word_as_location_is_not_section_add():
    """"lägg en klocka i andra sektionen" uses the section word as a LOCATION
    (ordinal), so it stays component_add."""
    d = classify_message("lägg en klocka i andra sektionen")
    assert d.editKind == "component_add"
    assert d.componentIntent == "clock_widget"


def test_section_add_question_is_not_an_edit():
    """A question about a section type never becomes a section_add edit."""
    d = classify_message("vad är en faq-sektion?")
    assert d.editKind == "none"
    assert d.buildRequirement == "none"
    assert d.shouldStartPreview is False
