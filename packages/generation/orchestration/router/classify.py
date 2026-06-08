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

from packages.generation.followup.color_lexicon import (
    COLOR_NAMES,
    contains_compound_color,
)

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

# Create-verbs feed both route_add and component_add (fix 3). "ny"/"nytt" are
# intentionally NOT here - they are adjectives that would otherwise pull copy
# prompts like "skriv ny rubrik" into route_add/component_add (fix 4); they are
# handled as new-page cues below, gated on a page noun.
_CREATE_VERBS = ("skapa", "bygg", "bygga", "behöver", "vill ha", "create", "add")

# "New page" cues used ONLY for route_add (alongside a page noun).
_NEW_PAGE_CUES = ("ny", "nytt", "ytterligare", "extra")

# Change verbs that pair with a noun to disambiguate copy vs style vs layout.
_CHANGE_VERBS = ("ändra", "byt", "byt ut", "uppdatera", "justera")

# A bare style adjective ("premium") is only an edit when paired with one of
# these imperative/intensifier cues (or a site ref / change verb / style verb).
# Otherwise a question like "vad betyder premium?" must stay answer_only (fix 1).
_STYLE_INTENSIFIERS = (
    "gör", "göra", "make", "make it", "mer", "mindre", "lite", "mera",
    "extra", "väldigt", "mycket", "more", "less",
)

_STYLE_ADJECTIVES = (
    "premium", "lyxig", "lyxigare", "modern", "modernare", "snygg", "snyggare",
    "minimalistisk", "minimalistiskt", "clean", "ren", "professionell",
    "elegant", "elegantare", "fräsch", "fräschare", "exklusiv", "stilren",
    "stilrent", "lekfull", "färgglad", "mörk", "mörkare", "ljus", "ljusare",
    "dramatisk", "luftig", "luftigare", "levande", "polerad", "påkostad",
    "futuristisk", "varm", "varmare", "kall", "kallare", "seriös", "lugn",
    "lugnare", "modernt", "snyggt",
)

# Color names read as visual-style adjectives so "gör färgen rosa" / "gör den
# blå" classify as visual_style (the previous lexicon only had abstract
# adjectives like premium/modern/mörk, so a bare color fell through to
# unclear). A color still needs style CONTEXT to count as an edit (an
# intensifier like "gör"/"mer", a change/style verb, or a site ref), so
# "vad betyder rosa?" stays answer_only and "lägg till en blå knapp" stays
# component_add (the add verb + component noun win before the visual_style
# branch, and there is no style context). 2026-06-08 router slice.
_STYLE_COLORS = (
    "rosa", "röd", "rött", "röda", "blå", "blått", "blåa", "grön", "grönt",
    "gröna", "gul", "gult", "gula", "lila", "orange", "svart", "svarta",
    "vit", "vitt", "vita", "grå", "grått", "gråa", "brun", "brunt", "bruna",
    "beige", "turkos", "guld", "gyllene", "silver", "marinblå", "ljusblå",
    "mörkblå", "ljusgrön", "mörkgrön",
    "pink", "red", "blue", "green", "yellow", "purple", "black", "white",
    "gray", "grey", "brown", "teal", "navy", "gold",
)

# Union the central colour lexicon names so every lexicon colour (korall, mint,
# petrol, grå, ...) reads as a style adjective here too - one source of truth
# shared with the theme extractor (packages/generation/followup/color_lexicon).
# Kept as a SUPERSET of the legacy tuple so no previously-recognised name is
# dropped (the regressions in test_router_classify.py stay green). Compound
# colours like "grönvit" are matched separately via contains_compound_color.
_STYLE_COLORS = tuple(sorted(set(_STYLE_COLORS) | COLOR_NAMES))

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
# Unicode-aware: Swedish domains (å/ä/ö) must be captured in full, otherwise
# "www.någonannan.se" would only match the ASCII tail and look like a bogus
# domain. The label charset therefore includes å/ä/ö.
_DOMAIN_LABEL = r"[a-z0-9åäö][a-z0-9åäö-]*"
# The capture group keeps the full URL the user referenced - domain AND any
# path/query (fix 10) - so a reference like "aftonbladet.se/sport?x=1" is not
# silently truncated to the bare domain. The optional scheme/www are matched
# but excluded from the capture (they carry no routing signal).
_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(" + _DOMAIN_LABEL + r"(?:\." + _DOMAIN_LABEL + r")*\.(?:" + "|".join(_TLDS) + r")"
    r"(?:/[^\s]*)?)",
)

# General "som på <domän>" / "lik(adan) som ..." reference detector. NOT tied
# to any specific domain - any comparison cue paired with a real domain (see
# the reference branch in classify_message) is treated as a reference.
_COMPARISON_RE = re.compile(
    r"\bsom på\b|\bsom hos\b|\bliknande\b|\bliknar\b|\bprecis som\b"
    r"|\bi stil med\b|\binspirer|\bser ut som\b|\blikt\b|\blik\b|\blikadan\b"
    r"|\btyp som\b|\bà la\b|\bsamma\b[^.?!]*\bsom\b|\blike\b"
    r"|\bsom\s+(?:www\.)?" + _DOMAIN_LABEL + r"\.(?:" + "|".join(_TLDS) + r")\b",
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
    """Return the full referenced URL (domain + path/query) or None.

    Trailing sentence punctuation is trimmed so "som på example.com/path."
    yields "example.com/path", while a real query ("?x=1") is preserved.
    """
    match = _URL_RE.search(text)
    if not match:
        return None
    return match.group(1).rstrip(".,;:!?)")


def _is_question(raw: str, text: str) -> bool:
    """True when the message reads as a question.

    Defensive by contract: callers may pass ``None`` or an empty string, and
    ``str.startswith`` must only ever receive a tuple of non-empty ``str``
    prefixes (an empty prefix would match everything, a non-str prefix would
    raise). A question without a trailing '?' (e.g. "vad är klockan") is still
    detected via the leading question words.
    """
    raw_str = raw if isinstance(raw, str) else ""
    text_str = text if isinstance(text, str) else ""
    if raw_str.strip().endswith("?"):
        return True
    if not text_str:
        return False
    leads = tuple(lead for lead in _QUESTION_LEADS if isinstance(lead, str) and lead)
    return text_str.startswith(leads)


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


# Articles / pronouns / fillers that are not a concrete object on their own.
_OBJECT_STOPWORDS = frozenset(
    {
        "den", "det", "de", "dem", "denna", "detta", "dessa", "här", "där",
        "som", "en", "ett", "på", "till", "in", "dit", "från", "av", "med",
        "och", "the", "this", "that", "it", "them",
    }
)


def _clause_has_object(work: str, verbs: tuple[str, ...]) -> bool:
    """True when a concrete object noun remains after removing the verb phrases.

    Used so a bare "ta bort" (no object) is treated as ambiguous instead of a
    component_remove with an empty target (fix 2).
    """
    cleaned = work
    for phrase in verbs:
        cleaned = re.sub(
            r"(?<![\wåäö])" + re.escape(phrase) + r"(?![\wåäö])", " ", cleaned
        )
    tokens = re.findall(r"[a-z0-9åäö]{3,}", cleaned)
    return any(tok not in _OBJECT_STOPWORDS for tok in tokens)


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

    # fix 6: a preserve constraint in the SAME clause is recorded but does NOT
    # short-circuit classification. Strip the preserve span so its "ändra
    # texten" wording cannot masquerade as a copy edit, then classify the rest.
    preserve = bool(_PRESERVE_RE.search(clause))
    if preserve:
        result.constraint = "preserve_copy"
    work = _PRESERVE_RE.sub(" ", clause) if preserve else clause

    has_add = _any_word(work, _ADD_VERBS)
    has_remove = _any_word(work, _REMOVE_VERBS)
    has_create = _any_word(work, _CREATE_VERBS)
    has_new = _any_word(work, _NEW_PAGE_CUES)
    has_style_verb = _any_word(work, _STYLE_VERBS)
    has_style_adj = (
        _any_word(work, _STYLE_ADJECTIVES)
        or _any_word(work, _STYLE_COLORS)
        or contains_compound_color(work)
    )
    has_style_noun = _any_word(work, _STYLE_NOUNS)
    has_redesign = _any_word(work, _REDESIGN_VERBS)
    has_layout_verb = _any_word(work, _LAYOUT_VERBS)
    has_copy_verb = _any_word(work, _COPY_VERBS)
    has_change_verb = _any_word(work, _CHANGE_VERBS)
    has_page_noun = _any_word(work, _PAGE_NOUNS)
    component_intent, _component_word = _detect_component(work)
    target = _build_target(work, ctx)

    # fix 1: a bare style adjective is only an edit with surrounding context
    # (a style/redesign/change verb, a site ref, or an intensifier like "mer").
    style_context = (
        has_style_verb
        or has_redesign
        or has_change_verb
        or _has_site_ref(work)
        or _any_word(work, _STYLE_INTENSIFIERS)
    )
    is_visual_style = (
        has_style_verb
        or has_redesign
        or (has_style_adj and style_context)
        or (has_change_verb and has_style_noun)
    )

    # A bare adjective without context is NOT an edit verb, so a question like
    # "vad betyder premium?" can still resolve to answer_only.
    result.hasEditVerb = any(
        (
            has_add, has_remove, has_create, has_style_verb, has_redesign,
            has_layout_verb, has_copy_verb, has_change_verb,
            (has_style_adj and style_context),
        )
    )

    # route_add (fix 4 + 5): a NEW page. Requires a page noun + a create/add/
    # new cue AND no component noun (a component noun means the page word is a
    # location -> component_add, e.g. "lägg en klocka på sidan").
    if has_page_noun and (has_add or has_create or has_new) and component_intent is None:
        result.editKind = "route_add"
        result.scope = "route"
        return result

    # component_remove (fix 2): only with a concrete object - a bare "ta bort"
    # is ambiguous, not a remove with an empty target.
    if has_remove:
        if (
            component_intent is not None
            or target is not None
            or _clause_has_object(work, _REMOVE_VERBS)
        ):
            result.editKind = "component_remove"
            result.scope = "component"
            result.componentIntent = component_intent
            result.target = target
            return result
        result.ambiguous = True
        return result

    # component_add (fix 3): add OR create verb + (component noun OR target).
    if (has_add or has_create) and (component_intent is not None or target is not None):
        result.editKind = "component_add"
        result.scope = "component"
        result.componentIntent = component_intent
        result.target = target
        return result

    # layout_change (move / reorder / resize / columns).
    if has_layout_verb:
        result.editKind = "layout_change"
        result.scope = "section" if target is not None else "route"
        result.componentIntent = component_intent
        result.target = target
        return result

    # copy_change: explicit copy verb, or a change verb + a copy noun.
    if has_copy_verb or (has_change_verb and _any_word(work, _COPY_NOUNS)):
        result.editKind = "copy_change"
        result.scope = "component"
        return result

    # visual_style: a style/redesign verb, an adjective in style context, or a
    # change verb + a style noun.
    if is_visual_style:
        result.editKind = "visual_style"
        result.scope = (
            "global" if has_redesign or _has_site_ref(work) or target is None else "section"
        )
        result.target = target
        return result

    # An edit verb with no resolvable object -> ambiguous edit (ask later).
    if has_add or has_create or has_change_verb:
        result.ambiguous = True
    return result


def _propagate_coordinated_objects(
    clause_results: list[_ClauseIntent], ctx: RouterContext
) -> None:
    """Carry a bare add/remove verb over coordinated objects (fix 7).

    "lägg till en karta och ett kontaktformulär" splits into two clauses; the
    second ("ett kontaktformulär") has the object but not the verb. When a
    later object-only clause follows an add/remove edit, inherit that editKind
    so both become subtasks instead of dropping the second one.
    """
    last_kind: EditKind | None = None
    for cr in clause_results:
        if cr.editKind in ("component_add", "component_remove"):
            last_kind = cr.editKind
            continue
        if cr.editKind != "none" or cr.constraint or cr.ambiguous or cr.hasEditVerb:
            continue
        if last_kind is None:
            continue
        obj_intent, _word = _detect_component(cr.instruction)
        if obj_intent is None:
            continue
        cr.editKind = last_kind
        cr.scope = "component"
        cr.componentIntent = obj_intent
        cr.target = cr.target or _build_target(cr.instruction, ctx)


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
    _propagate_coordinated_objects(clause_results, ctx)
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
        detected_intent, object_word = _detect_component(text)
        component_intent = edits[0].componentIntent if edits else detected_intent
        edit_kind: EditKind = "component_add" if component_intent or object_word else "none"
        # fix 9: carry any parsed placement target into the reference decision.
        ref_target = edits[0].target if edits else _build_target(text, ctx)
        return RouterDecision(
            messageKind="reference_analysis",
            editKind=edit_kind,
            buildRequirement="plan_only",
            contextLevel="external_reference",
            target=ref_target,
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
        # fix 8: a multi-intent that ALSO references an external site keeps the
        # reference + risk and gates to plan_only (analyse the reference before
        # building) instead of auto-rebuilding.
        has_reference = bool(url and _COMPARISON_RE.search(text))
        reference: RouterReference | None = None
        risk: str | None = None
        if has_reference:
            _intent, object_word = _detect_component(text)
            build = "plan_only"
            context_level = "external_reference"
            reference = RouterReference(url=url, object=object_word)
            risk = "do_not_copy_exact"
        else:
            build = "targeted_rebuild"
            context_level = "artifacts_plus_sections"
        return RouterDecision(
            messageKind="multi_intent",
            editKind="none",
            buildRequirement=build,
            contextLevel=context_level,
            target=edits[0].target,
            subtasks=subtasks,
            constraints=constraints,
            reference=reference,
            risk=risk,
            shouldStartPreview=_should_start_preview(build, ctx),
            rationale=(
                f"Multiple intents ({len(edits)} edits"
                + (f", constraints={constraints}" if constraints else "")
                + (f", reference={url}" if has_reference else "")
                + ") - split into ordered subtasks"
                + (
                    "; analyse the external reference first (plan_only, "
                    "do_not_copy_exact)."
                    if has_reference
                    else ", preserve constraints, rebuild only the affected "
                    "routes/sections."
                )
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
