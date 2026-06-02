"""Deterministic message classifier for the router (KÖR-6a).

No LLM, no model role, no OpenAI call. Pure Unicode-aware heuristics over
the user message that produce a structured ``RouterDecision``. The whole
point is that pure questions ("vad är klockan"), component discovery
("vilka klockor finns?") and external references ("som på aftonbladet.se")
never trigger a build, an adapter or an iframe refresh - only real edit
instructions do.

Design notes:
- ``classify_message`` is pure: it reads the message (and optional, caller
  supplied ``RouterContext``) and returns a decision. It never touches
  disk and never starts anything.
- Swedish is the primary language; a few common English cues are included
  because end-user prompts may arrive in any language. Regexes run on the
  lower-cased string, so Swedish ``å/ä/ö`` are matched directly.
- ``shouldStartPreview`` is the only actuation flag and is gated by both
  the build requirement and builder coexistence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import (
    BuildRequirement,
    ContextLevel,
    EditKind,
    RouterContext,
    RouterDecision,
    RouterReference,
    RouterSubtask,
    RouterTarget,
    SubtaskScope,
)

# ---------------------------------------------------------------------------
# Lexicons (Swedish-first, with a handful of English cues)
# ---------------------------------------------------------------------------

_ADD_VERBS = (
    "lägg till", "lägg in", "lägg dit", "lägg",
    "sätt in", "sätt dit", "sätt",
    "placera", "infoga", "addera", "inför", "introducera",
    "stoppa in", "få in", "ha en", "ha med", "vill ha", "vill lägga",
    "add", "insert", "place",
)

_REMOVE_VERBS = (
    "ta bort", "ta ut", "plocka bort", "radera", "avlägsna", "släng",
    "remove", "delete",
)

_CREATE_VERBS = ("skapa", "bygg", "behöver", "vill ha", "ny", "nytt", "create", "add")

_STYLE_ADJECTIVES = (
    "premium", "lyxig", "lyxigare", "modern", "modernare", "snygg", "snyggare",
    "minimalistisk", "minimalistiskt", "clean", "ren", "professionell",
    "elegant", "elegantare", "fräsch", "fräschare", "exklusiv", "stilren",
    "stilrent", "lekfull", "färgglad", "mörk", "mörkare", "ljus", "ljusare",
    "dramatisk", "luftig", "luftigare", "levande", "polerad", "påkostad",
    "futuristisk", "varm", "varmare", "kall", "kallare", "seriös", "lugn",
    "lugnare", "modernt", "snyggt",
)

_STYLE_VERBS = (
    "snygga till", "fräscha upp", "modernisera", "restyla", "restyle",
    "piffa upp", "piffa", "polera", "styla om", "designa om", "snygga",
)

_STYLE_NOUNS = (
    "färg", "färgen", "färger", "färgerna", "färgschema", "typsnitt",
    "typsnittet", "font", "fonten", "tema", "temat", "stil", "stilen",
    "utseende", "utseendet", "look", "design", "designen", "palett",
    "paletten", "bakgrundsfärg",
)

_COPY_NOUNS = (
    "texten", "texterna", "texter", "text", "rubriken", "rubrikerna",
    "rubriker", "rubrik", "underrubrik", "titeln", "titel", "slogan",
    "sloganen", "beskrivningen", "beskrivning", "stycket", "stycken",
    "stycke", "brödtext", "ingressen", "ingress", "tagline", "copyn", "copy",
)

_COPY_VERBS = (
    "skriv om", "formulera om", "skriv ny", "skriv en ny", "byt ut texten",
    "ändra texten", "uppdatera texten", "korrigera", "redigera texten",
)

_LAYOUT_VERBS = (
    "flytta", "byt plats", "byt ordning", "ändra ordningen", "ändra ordning",
    "omorganisera", "omplacera", "centrera", "vänsterjustera", "högerjustera",
    "ändra layout", "ändra layouten", "byt layout", "ändra placeringen",
    "ändra placering", "förstora", "förminska", "gör bredare", "gör smalare",
    "gör större", "gör mindre", "två kolumner", "tre kolumner", "stapla",
)

_REDESIGN_VERBS = (
    "gör om hela", "bygg om hela", "gör om", "bygg om", "designa om",
    "rita om", "börja om", "skrota allt",
)

_PAGE_NOUNS = (
    "undersida", "undersidor", "kontaktsida", "kontaktsidan", "landningssida",
    "tjänstesida", "prissida", "webbsida", "sida", "sidan", "sidor", "page",
)

_SITE_REFS = (
    "hela sidan", "hela sajten", "startsidan", "hemsidan", "webbplatsen",
    "webbsidan", "sajten", "siten", "sidan", "designen", "layouten", "site",
)

# Component noun -> componentIntent slug. Best-effort; an unknown component
# noun still classifies as component_add via the verb + location, just with
# componentIntent=None (the context/registry layer resolves the rest).
_COMPONENT_INTENTS = {
    "klocka": "clock_widget", "klockan": "clock_widget", "klockor": "clock_widget",
    "kontaktknapp": "contact_button", "knapp": "button", "knappen": "button",
    "kontaktformulär": "contact_form", "formulär": "form", "formuläret": "form",
    "karta": "map_embed", "kartan": "map_embed",
    "bildgalleri": "image_gallery", "galleri": "image_gallery",
    "bild": "image", "bilder": "image", "video": "video", "film": "video",
    "meny": "menu", "menyn": "menu", "prislista": "pricing_table",
    "priser": "pricing_table", "faq": "faq_accordion", "öppettider": "opening_hours",
    "recensioner": "reviews_display", "omdömen": "reviews_display",
    "nyhetsbrev": "newsletter_signup", "länk": "link", "länken": "link",
    "telefonnummer": "phone", "logga": "logo", "logotyp": "logo",
    "logotypen": "logo", "countdown": "countdown", "nedräkning": "countdown",
    "kontaktuppgifter": "contact_info", "banner": "banner",
}

_ORDINAL_WORDS = {
    "första": 1, "andra": 2, "tredje": 3, "fjärde": 4, "femte": 5,
    "sjätte": 6, "sjunde": 7, "åttonde": 8, "nionde": 9, "tionde": 10,
    "sista": -1,
}

# Multi-word positions first so "till vänster" wins over a bare token.
_POSITION_PHRASES = (
    ("längst upp", "top"), ("högst upp", "top"), ("i toppen", "top"),
    ("längst ner", "bottom"), ("längst ned", "bottom"), ("i botten", "bottom"),
    ("till vänster", "left"), ("till höger", "right"), ("i mitten", "center"),
    ("vänstra", "left"), ("högra", "right"), ("vänster", "left"),
    ("höger", "right"), ("centrerat", "center"), ("centrerad", "center"),
    ("mitten", "center"), ("center", "center"), ("överst", "top"),
    ("toppen", "top"), ("nederst", "bottom"), ("botten", "bottom"),
)

# ---------------------------------------------------------------------------
# Regexes (compiled once)
# ---------------------------------------------------------------------------

_TLDS = (
    "se", "com", "net", "org", "nu", "io", "dev", "app", "co", "eu", "de",
    "fr", "uk", "us", "info", "biz", "tv", "me", "ai", "shop", "store",
)
_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"([a-z0-9][a-z0-9-]{1,}(?:\.[a-z0-9-]+)*\.(?:" + "|".join(_TLDS) + r"))"
    r"(?:/[^\s]*)?",
)

_COMPARISON_RE = re.compile(
    r"\bsom på\b|\bsom hos\b|\bliknande\b|\bprecis som\b|\bi stil med\b"
    r"|\binspirer|\bser ut som\b|\blikt\b|\btyp som\b|\bà la\b"
    r"|\bsamma\b[^.?!]*\bsom\b|\blike\b",
)

_DISCOVERY_RE = re.compile(
    r"\bvilka\s+\w+[^.?!]*\b(finns|går att|kan jag|kan man|kan väljas|stöds"
    r"|erbjuds|tillgå|tillgängliga|har ni|har du)\b"
    r"|\bvad\s+finns\s+det\s+för\b"
    r"|\bvad\s+för\s+\w+\s+finns\b"
    r"|\bfinns\s+det\s+(några|någon|nåt|något)\b"
    r"|\bvilka\s+(alternativ|möjligheter|val|varianter|typer|sorter"
    r"|komponenter|moduler|funktioner|widgets)\b"
    r"|\bvad\s+kan\s+jag\s+(välja|lägga till|använda)\b"
    r"|\bwhat\s+\w+[^.?!]*\b(are available|options|can i (add|use|choose))\b"
    r"|\bwhich\s+\w+[^.?!]*\b(are available|exist)\b",
)

_PRESERVE_RE = re.compile(
    r"(ändra|rör|peta|pilla|ändr|röra)\s+(inte|ej)\s+(på\s+)?"
    r"(text|texten|texter|texterna|copy|copyn|rubrik|rubriken|innehåll"
    r"|innehållet|orden|ord)"
    r"|(inte|ej)\s+(ändra|röra|peta på|ändr)\s+(på\s+)?"
    r"(text|texten|texterna|copy|innehåll|rubriken)"
    r"|behåll\s+(text|texten|texterna|copyn?|innehållet|rubriken|orden"
    r"|samma text)"
    r"|lämna\s+(text|texten|texterna|copyn?)"
    r"|utan att ändra (text|texten|texterna|copy|innehåll)"
    r"|(don'?t|do not)\s+(change|touch|modify)\s+the\s+"
    r"(text|copy|content|wording)"
    r"|keep\s+the\s+(text|copy|wording|content)"
    r"|leave\s+the\s+(text|copy)\b",
)

_BUG_PHRASES = (
    "funkar inte", "fungerar inte", "fungerar ej", "funkar ej", "går inte att",
    "går ej att", "kraschar", "krasch", "kraschen", "felmeddelande",
    "fel meddelande", "buggar", "bugg", "är trasig", "trasig", "trasigt",
    "slutar fungera", "laddar inte", "laddas inte", "syns inte", "visas inte",
    "det blir fel", "blir fel", "något är fel", "nåt är fel", "stämmer inte",
    "är sönder", "sönder", "white screen", "vit skärm", "doesn't work",
    "does not work", "not working", "is broken", "throws an error", "fastnar",
)

_FULL_REDESIGN_RE = re.compile(
    r"\bgör om hela\b|\bbygg om hela\b|\bdesigna om allt\b|\bdesigna om hela\b"
    r"|\bbörja om\b|\bhelt ny design\b|\bredesigna?\b|\bfrån grunden\b"
    r"|\bgör om sidan från\b|\bskrota allt\b|\bbygg om allt\b",
)

_QUESTION_LEADS = (
    "vad ", "vem ", "var ", "vart ", "när ", "hur ", "vilka ", "vilken ",
    "vilket ", "varför ", "kan du", "kan man", "kan jag", "vet du",
    "finns det", "är det", "är ", "berätta", "förklara", "what ", "how ",
    "why ", "when ", "where ", "which ", "who ", "is ", "are ", "can you",
    "do you", "tell me", "explain",
)

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", (message or "").strip().lower())


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _word_present(text: str, phrase: str) -> bool:
    return re.search(r"(?<![\wåäö])" + re.escape(phrase) + r"(?![\wåäö])", text) is not None


def _any_word(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_word_present(text, p) for p in phrases)


def _find_url(text: str) -> str | None:
    match = _URL_RE.search(text)
    return match.group(1) if match else None


def _is_question(raw: str, text: str) -> bool:
    if raw.strip().endswith("?"):
        return True
    return text.startswith(_QUESTION_LEADS)


def _has_site_ref(text: str) -> bool:
    return _any_word(text, _SITE_REFS)


def _detect_component(text: str) -> tuple[str | None, str | None]:
    """Return (componentIntent, raw_noun) for the first known component noun."""
    for noun, intent in _COMPONENT_INTENTS.items():
        if _word_present(text, noun):
            return intent, noun
    return None, None


def _detect_position(text: str) -> str | None:
    for phrase, value in _POSITION_PHRASES:
        if _word_present(text, phrase):
            return value
    return None


def _detect_ordinal(text: str) -> int | None:
    numeric = re.search(r"\bsektion(?:en)?\s*(\d{1,2})\b", text) or re.search(
        r"\b(\d{1,2})\s*(?::a|:e)?\s*sektion", text
    ) or re.search(r"\bsection\s*(\d{1,2})\b", text)
    if numeric:
        return int(numeric.group(1))
    for word, value in _ORDINAL_WORDS.items():
        if _word_present(text, word):
            return value
    return None


def _build_target(text: str, ctx: RouterContext) -> RouterTarget | None:
    ordinal = _detect_ordinal(text)
    position = _detect_position(text)
    if ordinal is None and position is None:
        return None
    route_id = ctx.defaultRouteId
    section_id = None
    sections = ctx.routeSections.get(route_id)
    if ordinal is not None and ordinal > 0 and sections and ordinal <= len(sections):
        section_id = sections[ordinal - 1]
    return RouterTarget(
        routeId=route_id,
        sectionId=section_id,
        sectionOrdinal=ordinal,
        position=position,
    )


# ---------------------------------------------------------------------------
# Clause-level classification
# ---------------------------------------------------------------------------

_CLAUSE_SPLIT_RE = re.compile(
    r"\s*(?:,|;|\boch även\b|\boch sedan\b|\boch\b|\bsamt\b|\bmen\b|\bplus\b"
    r"|\bdärefter\b|\n)\s*",
)


def _split_clauses(text: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT_RE.split(text) if c.strip()]


@dataclass
class _ClauseIntent:
    editKind: EditKind = "none"
    componentIntent: str | None = None
    scope: SubtaskScope | None = None
    target: RouterTarget | None = None
    constraint: str | None = None
    instruction: str = ""
    hasEditVerb: bool = False
    ambiguous: bool = False
    fields_seen: tuple[str, ...] = field(default_factory=tuple)


def _classify_clause(clause: str, ctx: RouterContext) -> _ClauseIntent:
    result = _ClauseIntent(instruction=clause)

    if _PRESERVE_RE.search(clause):
        result.constraint = "preserve_copy"
        return result

    has_add = _any_word(clause, _ADD_VERBS)
    has_remove = _any_word(clause, _REMOVE_VERBS)
    has_create = _any_word(clause, _CREATE_VERBS)
    has_style_verb = _any_word(clause, _STYLE_VERBS)
    has_style_adj = _any_word(clause, _STYLE_ADJECTIVES)
    has_style_noun = _any_word(clause, _STYLE_NOUNS)
    has_redesign = _any_word(clause, _REDESIGN_VERBS)
    has_layout_verb = _any_word(clause, _LAYOUT_VERBS)
    has_copy_verb = _any_word(clause, _COPY_VERBS)
    has_change_verb = _any_word(clause, ("ändra", "byt", "byt ut", "uppdatera", "justera"))
    has_page_noun = _any_word(clause, _PAGE_NOUNS)
    component_intent, _component_word = _detect_component(clause)

    result.hasEditVerb = any(
        (has_add, has_remove, has_style_verb, has_style_adj, has_redesign,
         has_layout_verb, has_copy_verb, has_change_verb)
    )

    # 1. route_add: add/create verb + page noun ("lägg till en kontaktsida").
    if (has_add or has_create) and has_page_noun:
        result.editKind = "route_add"
        result.scope = "route"
        return result

    # 2. component_remove
    if has_remove:
        result.editKind = "component_remove"
        result.scope = "component"
        result.componentIntent = component_intent
        result.target = _build_target(clause, ctx)
        return result

    # 3. component_add: add verb + (component noun OR a placement target).
    target = _build_target(clause, ctx)
    if has_add and (component_intent is not None or target is not None):
        result.editKind = "component_add"
        result.scope = "component"
        result.componentIntent = component_intent
        result.target = target
        return result

    # 4. layout_change (move / reorder / resize / columns).
    if has_layout_verb:
        result.editKind = "layout_change"
        result.scope = "section" if target is not None else "route"
        result.componentIntent = component_intent
        result.target = target
        return result

    # 5. copy_change: explicit copy verb, or a change verb + a copy noun.
    if has_copy_verb or (has_change_verb and _any_word(clause, _COPY_NOUNS)):
        result.editKind = "copy_change"
        result.scope = "component"
        return result

    # 6. visual_style: a style verb/adjective, a redesign verb, or
    #    change-verb + style noun.
    if has_style_verb or has_style_adj or has_redesign or (has_change_verb and has_style_noun):
        result.editKind = "visual_style"
        result.scope = (
            "global"
            if has_redesign or _has_site_ref(clause) or target is None
            else "section"
        )
        result.target = target
        return result

    # 7. add verb but no recognizable object -> ambiguous edit (ask later).
    if has_add or has_change_verb:
        result.ambiguous = True
    return result


# ---------------------------------------------------------------------------
# Build-requirement / context-level mapping for a single edit
# ---------------------------------------------------------------------------

_BUILD_BY_EDIT: dict[EditKind, BuildRequirement] = {
    "component_add": "targeted_rebuild",
    "component_remove": "targeted_rebuild",
    "layout_change": "targeted_rebuild",
    "route_add": "targeted_rebuild",
    "visual_style": "targeted_rebuild",
    "copy_change": "artifact_patch_only",
    "none": "none",
}

_CONTEXT_BY_EDIT: dict[EditKind, ContextLevel] = {
    "component_add": "artifacts_plus_sections",
    "component_remove": "artifacts_plus_sections",
    "layout_change": "artifacts_plus_sections",
    "route_add": "artifacts_plus_sections",
    "visual_style": "artifacts",
    "copy_change": "artifacts",
    "none": "none",
}


def _should_start_preview(build: BuildRequirement, ctx: RouterContext) -> bool:
    if ctx.hasActiveUserSession:
        return False
    return build in ("targeted_rebuild", "full_rebuild")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def classify_message(message: str, *, context: RouterContext | None = None) -> RouterDecision:
    """Classify a single user message into a structured ``RouterDecision``.

    Pure and deterministic: same input (and context) always yields the same
    decision. Never reads disk, never starts a build or preview.
    """
    ctx = context or RouterContext()
    raw = message or ""
    text = _normalize(raw)
    if not text:
        return RouterDecision(
            messageKind="unclear",
            requiresClarification=True,
            rationale="Empty message - nothing to classify.",
        )

    url = _find_url(text)
    has_site_ref = _has_site_ref(text)
    is_question = _is_question(raw, text)

    clauses = _split_clauses(text)
    clause_results = [_classify_clause(c, ctx) for c in clauses]
    edits = [c for c in clause_results if c.editKind != "none"]
    constraints: list[str] = []
    for c in clause_results:
        if c.constraint and c.constraint not in constraints:
            constraints.append(c.constraint)
    if not constraints and _PRESERVE_RE.search(text):
        constraints.append("preserve_copy")
    ambiguous_present = any(c.ambiguous for c in clause_results)
    had_edit_verb = any(c.hasEditVerb for c in clause_results) or ambiguous_present

    # 1. reference_analysis - external reference, propose own variant, no build.
    if url and _COMPARISON_RE.search(text) and len(edits) < 2:
        component_intent = edits[0].componentIntent if edits else None
        object_word = None
        if component_intent is None:
            component_intent, object_word = _detect_component(text)
        else:
            _intent, object_word = _detect_component(text)
        edit_kind: EditKind = "component_add" if component_intent or object_word else "none"
        return RouterDecision(
            messageKind="reference_analysis",
            editKind=edit_kind,
            buildRequirement="plan_only",
            contextLevel="external_reference",
            reference=RouterReference(url=url, object=object_word),
            componentIntent=component_intent,
            constraints=constraints,
            risk="do_not_copy_exact",
            shouldStartPreview=False,
            rationale=(
                f"External reference ({url}) - analyse it and propose an own "
                "variant; never copy the exact design or code. No build until "
                "the user confirms placement."
            ),
        )

    # 2. component_discovery - list options, build nothing until the user picks.
    if _DISCOVERY_RE.search(text):
        return RouterDecision(
            messageKind="component_discovery",
            editKind="none",
            buildRequirement="none",
            contextLevel="component_registry",
            shouldStartPreview=False,
            rationale=(
                "Discovery question - list available components/capabilities "
                "from the registry and ask about placement. No build until the "
                "user chooses."
            ),
        )

    # 3. multi_intent - two or more actionable edits in one message.
    if len(edits) >= 2:
        subtasks = _build_subtasks(clause_results)
        build = "targeted_rebuild"
        return RouterDecision(
            messageKind="multi_intent",
            editKind="none",
            buildRequirement=build,
            contextLevel="artifacts_plus_sections",
            subtasks=subtasks,
            constraints=constraints,
            shouldStartPreview=_should_start_preview(build, ctx),
            rationale=(
                f"Multiple intents ({len(edits)} edits"
                + (f", constraints={constraints}" if constraints else "")
                + ") - split into ordered subtasks, preserve constraints, "
                "rebuild only the affected routes/sections."
            ),
        )

    # 4. edit_instruction - exactly one actionable edit.
    if len(edits) == 1:
        return _decide_single_edit(edits[0], constraints, text, ctx)

    # 5. bug_report - a problem report with no actionable edit verb.
    if _contains_any(text, _BUG_PHRASES):
        return RouterDecision(
            messageKind="bug_report",
            editKind="none",
            buildRequirement="plan_only",
            contextLevel="selected_files",
            shouldStartPreview=False,
            rationale=(
                "Problem report - inspect the relevant files and propose a fix; "
                "do not rebuild or start preview before diagnosing."
            ),
        )

    # 6. ambiguous edit verb but no resolvable object -> ask for clarification.
    if ambiguous_present and not edits:
        return RouterDecision(
            messageKind="unclear",
            buildRequirement="none",
            contextLevel="none",
            requiresClarification=True,
            constraints=constraints,
            shouldStartPreview=False,
            rationale=(
                "An edit verb was present but the target/object is ambiguous - "
                "ask the user what to change before doing anything."
            ),
        )

    # 7. site_review - a question/opinion about the site, no edit.
    if has_site_ref and (is_question or _any_word(text, ("tycker", "tror", "åsikt", "feedback", "granska", "bedöm", "recensera"))):
        return RouterDecision(
            messageKind="site_review",
            editKind="none",
            buildRequirement="none",
            contextLevel="artifacts_plus_sections",
            shouldStartPreview=False,
            rationale=(
                "Review/inquiry about the current site - answer from artefacts; "
                "no patch, no build, no preview start."
            ),
        )

    # 8. answer_only - a pure question unrelated to the site.
    if is_question and not has_site_ref and not had_edit_verb:
        return RouterDecision(
            messageKind="answer_only",
            editKind="none",
            buildRequirement="none",
            contextLevel="none",
            shouldStartPreview=False,
            rationale=(
                "Pure question unrelated to the site - answer only. No context, "
                "no patch, no preview, no run created."
            ),
        )

    # 9. unclear - fallback.
    return RouterDecision(
        messageKind="unclear",
        buildRequirement="none",
        contextLevel="none",
        requiresClarification=True,
        constraints=constraints,
        shouldStartPreview=False,
        rationale="Could not confidently classify the message - ask the user to clarify.",
    )


def _decide_single_edit(
    edit: _ClauseIntent,
    constraints: list[str],
    text: str,
    ctx: RouterContext,
) -> RouterDecision:
    edit_kind = edit.editKind
    build = _BUILD_BY_EDIT.get(edit_kind, "targeted_rebuild")
    context_level = _CONTEXT_BY_EDIT.get(edit_kind, "artifacts_plus_sections")

    # An explicit full redesign of a visual_style edit escalates the build.
    if edit_kind == "visual_style" and _FULL_REDESIGN_RE.search(text):
        build = "full_rebuild"
    if edit_kind == "visual_style" and edit.target is not None:
        context_level = "artifacts_plus_sections"

    return RouterDecision(
        messageKind="edit_instruction",
        editKind=edit_kind,
        buildRequirement=build,
        contextLevel=context_level,
        target=edit.target,
        componentIntent=edit.componentIntent,
        constraints=constraints,
        shouldStartPreview=_should_start_preview(build, ctx),
        rationale=(
            f"Single edit instruction ({edit_kind}) - "
            f"{build.replace('_', ' ')}"
            + (f", constraints={constraints}" if constraints else "")
            + "."
        ),
    )


def _build_subtasks(clause_results: list[_ClauseIntent]) -> list[RouterSubtask]:
    subtasks: list[RouterSubtask] = []
    for c in clause_results:
        if c.editKind != "none":
            subtasks.append(
                RouterSubtask(
                    editKind=c.editKind,
                    instruction=c.instruction,
                    scope=c.scope,
                    componentIntent=c.componentIntent,
                    target=c.target,
                )
            )
        elif c.constraint:
            subtasks.append(
                RouterSubtask(
                    editKind="none",
                    instruction=c.instruction,
                    constraint=c.constraint,
                )
            )
    return subtasks
