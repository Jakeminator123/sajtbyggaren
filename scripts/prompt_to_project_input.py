"""Convert a free-form prompt into a minimal Project Input for build_site.py.

Wires Phase 1 (briefModel via packages.generation.brief.extract_site_brief)
to a deterministic Site Brief -> Project Input mapping so the operator can
go from "skriv en mening" -> riktig sajt-build via the existing builder.

Why this lives in scripts/ and not packages/generation/brief/:

- ``packages/generation/brief/`` owns prompt -> Site Brief (Phase 1
  Understand). Its mustNotDo list (repo-boundaries.v1.json) explicitly
  excludes "välja Scaffold". Picking a scaffoldId/variantId for the
  Project Input is a scaffold-selection-shaped decision, even when the
  heuristic is intentionally tiny.
- ``apps/viewser/`` mustNotDo includes writing to data/ or examples/.
  This script writes the generated Project Input to a scratch directory
  that viewser's POST /api/prompt route hands to scripts/build_site.py
  via the existing build-runner spawn pattern. Scripts may write to data/.

Output contract (for callers like apps/viewser/app/api/prompt/route.ts):

- Prints these stdout keys, one per line, for Viewser's regex-based parser:
  ``siteId: <id>``, ``projectId: <id>``, ``dossierPath: <abs-path>``,
  ``metaPath: <abs-path>``, ``version: <number>``, and
  ``briefSource: <source>``. Mirrors build_site.py's run id contract so the
  same parser pattern works in build-runner.ts.
- Writes ``data/prompt-inputs/<siteId>.project-input.json`` (validates
  against governance/schemas/project-input.schema.json before writing).
- Writes ``data/prompt-inputs/<siteId>.meta.json`` with projectId,
  version, originalPrompt, briefSource. Follow-up mode reads that sidecar,
  reuses projectId, increments version and writes a fresh Project Input
  from the operator's latest prompt without changing the Project Input schema.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.brief import (  # noqa: E402
    detect_language,
    extract_site_brief,
    site_brief_to_artifact,
)
from packages.generation.brief.models import resolve_brief_model  # noqa: E402
from packages.generation.discovery import (  # noqa: E402
    DiscoveryDecision,
    apply_discovery_overrides,
    resolve_discovery,
)
from packages.generation.discovery.resolve import (  # noqa: E402
    _offer_looks_like_ui_directive,
)

DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "prompt-inputs"
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"

# Mirrors apps/viewser/lib/project-inputs.ts SITE_ID_PATTERN. Lower-case
# letters, digits and dashes, must start and end with alphanumeric.
# Centralising the pattern in two languages is a known duplication; a
# future sprint can hoist it into a shared policy if more tools need it.
_SITE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")
_SLUG_DASHES = re.compile(r"-{2,}")
_MASTER_PROMPT_OPERATOR_HEADER = "[Operatörens beskrivning]"

# Small Swedish business-type dictionary used to produce a readable
# company name on the generated H1 instead of leaking the raw prompt.
# Demo-baseline-fix 1A: briefModel returns kebab-case English slugs for
# `businessTypeGuess`, but a Swedish first-build site reads better with
# a Swedish noun. Operator can override the name in the Project Input
# file before re-building. The map covers the demo-baseline branches
# (electrician / hairdresser / naprapat / ceramics) plus a handful of
# common small-business types AND the hyphenated variants briefModel
# actually returns in production ("e-commerce", "naprapath-clinic",
# "electrical-services", "plumbing-services" - B63, demo-baseline-fix
# 1A-hotfix). Unknown slugs fall through `_company_business_label` to
# the "företag som arbetar med <slug>" branch so the H1 still reads as
# Swedish prose rather than dev jargon.
_BUSINESS_TYPE_LABEL_SV: dict[str, str] = {
    "electrician": "elektriker",
    "electrical-services": "elektriker",
    "electrical-contractor": "elektriker",
    "plumber": "rörmokare",
    "plumbing-services": "rörmokare",
    "hairdresser": "frisör",
    "hair-salon": "frisör",
    "barber": "barberare",
    "barber-shop": "barberare",
    "dentist": "tandläkare",
    "dental-clinic": "tandläkare",
    "naprapat": "naprapatklinik",
    "naprapath": "naprapatklinik",
    "naprapath-clinic": "naprapatklinik",
    "naprapat-clinic": "naprapatklinik",
    "naprapatklinik": "naprapatklinik",
    "chiropractor": "kiropraktor",
    "chiropractic-clinic": "kiropraktor",
    "physiotherapist": "sjukgymnast",
    "physiotherapy-clinic": "sjukgymnast",
    "painter": "målare",
    "painting-services": "målare",
    "carpenter": "snickare",
    "carpentry-services": "snickare",
    "construction": "byggfirma",
    "construction-company": "byggfirma",
    "restaurant": "restaurang",
    "cafe": "café",
    "bakery": "bageri",
    "florist": "blomsterhandel",
    "flower-shop": "blomsterhandel",
    "photographer": "fotograf",
    "photo-studio": "fotostudio",
    "ceramics-studio": "keramikstudio",
    "pottery": "krukmakeri",
    "yoga-studio": "yogastudio",
    "gym": "gym",
    "service-provider": "tjänsteföretag",
    "consultant": "konsult",
    "shop": "butik",
    "online-shop": "webbshop",
    "ecommerce": "webbshop",
    "e-commerce": "webbshop",
    "ecommerce-shop": "webbshop",
    "ecommerce-store": "webbshop",
    "boat-dealer": "båthandel",
    "egg-farm": "äggproducent",
}

_ECOMMERCE_BUSINESS_TYPES = frozenset(
    {
        "shop",
        "online-shop",
        "ecommerce",
        "e-commerce",
        "ecommerce-shop",
        "ecommerce-store",
        "webshop",
        "webbshop",
    }
)

_TAGLINE_BY_BUSINESS_TYPE_SV: dict[str, str] = {
    "electrician": "Tydlig hjälp med elarbeten",
    "electrical-services": "Tydlig hjälp med elarbeten",
    "electrical-contractor": "Tydlig hjälp med elarbeten",
    "hairdresser": "Klippning, färg och styling med enkel bokning",
    "hair-salon": "Klippning, färg och styling med enkel bokning",
    "frisör": "Klippning, färg och styling med enkel bokning",
    "barber": "Klippning och skäggvård med enkel bokning",
    "barber-shop": "Klippning och skäggvård med enkel bokning",
    "naprapat": "Behandling och rådgivning med enkel bokning",
    "naprapath": "Behandling och rådgivning med enkel bokning",
    "naprapath-clinic": "Behandling och rådgivning med enkel bokning",
    "naprapat-clinic": "Behandling och rådgivning med enkel bokning",
    "naprapatklinik": "Behandling och rådgivning med enkel bokning",
    "chiropractor": "Behandling och rådgivning med enkel bokning",
    "physiotherapist": "Behandling och rådgivning med enkel bokning",
    "physiotherapy-clinic": "Behandling och rådgivning med enkel bokning",
    "shop": "Utvalt sortiment med enkel beställning",
    "online-shop": "Utvalt sortiment med enkel beställning",
    "ecommerce": "Utvalt sortiment med enkel beställning",
    "e-commerce": "Utvalt sortiment med enkel beställning",
    "ecommerce-shop": "Utvalt sortiment med enkel beställning",
    "ecommerce-store": "Utvalt sortiment med enkel beställning",
    "webbshop": "Utvalt sortiment med enkel beställning",
    "ceramics-studio": "Keramik med tydlig känsla och enkel kontakt",
    "pottery": "Keramik med tydlig känsla och enkel kontakt",
}

_SERVICE_LABEL_BY_BUSINESS_TYPE_SV: dict[str, str] = {
    "electrician": "Elservice",
    "electrical-services": "Elservice",
    "electrical-contractor": "Elservice",
    "hairdresser": "Frisörtjänster",
    "hair-salon": "Frisörtjänster",
    "frisör": "Frisörtjänster",
    "barber": "Klippning och skäggvård",
    "barber-shop": "Klippning och skäggvård",
    "naprapat": "Behandlingar",
    "naprapath": "Behandlingar",
    "naprapath-clinic": "Behandlingar",
    "naprapat-clinic": "Behandlingar",
    "naprapatklinik": "Behandlingar",
    "chiropractor": "Behandlingar",
    "physiotherapist": "Behandlingar",
    "physiotherapy-clinic": "Behandlingar",
    "shop": "Sortiment",
    "online-shop": "Sortiment",
    "ecommerce": "Sortiment",
    "e-commerce": "Sortiment",
    "ecommerce-shop": "Sortiment",
    "ecommerce-store": "Sortiment",
    "webbshop": "Sortiment",
}

_SERVICE_SUMMARY_BY_BUSINESS_TYPE_SV: dict[str, str] = {
    "electrician": "Tydlig hjälp med elarbeten, felsökning och nästa steg.",
    "electrical-services": "Tydlig hjälp med elarbeten, felsökning och nästa steg.",
    "electrical-contractor": "Tydlig hjälp med elarbeten, felsökning och nästa steg.",
    "hairdresser": "Klippning, färg och styling med enkel bokning.",
    "hair-salon": "Klippning, färg och styling med enkel bokning.",
    "frisör": "Klippning, färg och styling med enkel bokning.",
    "barber": "Klippning och skäggvård med enkel bokning.",
    "barber-shop": "Klippning och skäggvård med enkel bokning.",
    "naprapat": "Behandling och rådgivning med enkel bokning.",
    "naprapath": "Behandling och rådgivning med enkel bokning.",
    "naprapath-clinic": "Behandling och rådgivning med enkel bokning.",
    "naprapat-clinic": "Behandling och rådgivning med enkel bokning.",
    "naprapatklinik": "Behandling och rådgivning med enkel bokning.",
    "chiropractor": "Behandling och rådgivning med enkel bokning.",
    "physiotherapist": "Behandling och rådgivning med enkel bokning.",
    "physiotherapy-clinic": "Behandling och rådgivning med enkel bokning.",
    "shop": "Utvalt sortiment med tydlig produktväg och enkel beställning.",
    "online-shop": "Utvalt sortiment med tydlig produktväg och enkel beställning.",
    "ecommerce": "Utvalt sortiment med tydlig produktväg och enkel beställning.",
    "e-commerce": "Utvalt sortiment med tydlig produktväg och enkel beställning.",
    "ecommerce-shop": "Utvalt sortiment med tydlig produktväg och enkel beställning.",
    "ecommerce-store": "Utvalt sortiment med tydlig produktväg och enkel beställning.",
    "webbshop": "Utvalt sortiment med tydlig produktväg och enkel beställning.",
}

_SERVICE_SUMMARY_BY_BUSINESS_TYPE_EN: dict[str, str] = {
    "electrician": "Clear help with electrical work, troubleshooting and the next step.",
    "electrical-services": "Clear help with electrical work, troubleshooting and the next step.",
    "electrical-contractor": "Clear help with electrical work, troubleshooting and the next step.",
    "hairdresser": "Haircuts, colour and styling with simple booking.",
    "hair-salon": "Haircuts, colour and styling with simple booking.",
    "barber": "Haircuts and grooming with simple booking.",
    "barber-shop": "Haircuts and grooming with simple booking.",
    "naprapat": "Treatment and guidance with simple booking.",
    "naprapath": "Treatment and guidance with simple booking.",
    "naprapath-clinic": "Treatment and guidance with simple booking.",
    "naprapat-clinic": "Treatment and guidance with simple booking.",
    "chiropractor": "Treatment and guidance with simple booking.",
    "physiotherapist": "Treatment and guidance with simple booking.",
    "physiotherapy-clinic": "Treatment and guidance with simple booking.",
    "shop": "A curated range with a clear product path and simple ordering.",
    "online-shop": "A curated range with a clear product path and simple ordering.",
    "ecommerce": "A curated range with a clear product path and simple ordering.",
    "e-commerce": "A curated range with a clear product path and simple ordering.",
    "ecommerce-shop": "A curated range with a clear product path and simple ordering.",
    "ecommerce-store": "A curated range with a clear product path and simple ordering.",
}

_TAGLINE_BY_BUSINESS_TYPE_EN: dict[str, str] = {
    "electrician": "Clear help with electrical work",
    "electrical-services": "Clear help with electrical work",
    "electrical-contractor": "Clear help with electrical work",
    "hairdresser": "Haircuts, colour and styling with simple booking",
    "hair-salon": "Haircuts, colour and styling with simple booking",
    "barber": "Haircuts and grooming with simple booking",
    "barber-shop": "Haircuts and grooming with simple booking",
    "naprapat": "Treatment and guidance with simple booking",
    "naprapath": "Treatment and guidance with simple booking",
    "naprapath-clinic": "Treatment and guidance with simple booking",
    "naprapat-clinic": "Treatment and guidance with simple booking",
    "chiropractor": "Treatment and guidance with simple booking",
    "physiotherapist": "Treatment and guidance with simple booking",
    "physiotherapy-clinic": "Treatment and guidance with simple booking",
    "shop": "A curated range with simple ordering",
    "online-shop": "A curated range with simple ordering",
    "ecommerce": "A curated range with simple ordering",
    "e-commerce": "A curated range with simple ordering",
    "ecommerce-shop": "A curated range with simple ordering",
    "ecommerce-store": "A curated range with simple ordering",
    "ceramics-studio": "Ceramics with a clear style and simple ordering",
    "pottery": "Ceramics with a clear style and simple ordering",
}

_PLANNER_NOTE_BLOCKLIST = frozenset(
    {
        "likely",
        "prompt",
        "brief",
        "planner",
        "project input",
        "phase",
        "keep scope",
        "minimal",
        "replace this",
        "site",
        "website",
        "webbplats",
        "hemsida",
        "sajt",
        "företagswebb",
        "selling",
        "focus on",
        "byt ut",
        "uppdatera",
        # B128 (re-Verifierings-Scout 2026-05-19): Swedish operator/
        # planner-lingo som lät en instruktion av typen "Bygg en liten
        # e-handel ... med fokus på köpkonvertering." passera B99-grindens
        # blocklist och landa rakt på /om-oss. "konvertering" och
        # "köpkonvertering" är operator-terminologi som småföretagskunder
        # inte använder om sig själva i kundcopy; "på svenska" / "på
        # engelska" är ren språk-direktiv från operatör till modell.
        "konvertering",
        "köpkonvertering",
        "på svenska",
        "på engelska",
        "in english",
        "in swedish",
    }
)

# B128 (re-Verifierings-Scout 2026-05-19): planner-noten startar ofta med
# en svensk/engelsk imperativ ("Bygg en liten e-handel ...", "Skapa en
# hemsida för ...", "Make a clean shop..."). Ingen riktig /om-oss-copy
# inleds med en order till modellen, så vi avvisar hela noten när första
# tokenet är en känd build-imperativ. Token-listan är medvetet tajt så
# legitima fraser som "Bygger fortfarande på 10 års erfarenhet" passerar
# - imperativen står typiskt utan utfyllnad efteråt och första bokstaven
# är ofta versal, men vi nfkc-foldar och lowercaser innan vi jämför så
# stavning inte skapar gap.
_PLANNER_IMPERATIVE_TOKENS: frozenset[str] = frozenset(
    {
        # Svensk build-imperativ
        "bygg",
        "skapa",
        "gör",
        "gor",
        "generera",
        "designa",
        "skriv",
        "tillverka",
        "konstruera",
        "producera",
        "utveckla",
        "forma",
        "programmera",
        "rita",
        # Engelsk build-imperativ
        "build",
        "create",
        "make",
        "design",
        "write",
        "develop",
        "generate",
        "construct",
        "produce",
        "draft",
    }
)

_PLANNER_IMPERATIVE_PHRASES: tuple[str, ...] = (
    "lägg upp",
    "sätt upp",
    "set up",
)

_SCAFFOLD_LOCAL_SERVICE = ("local-service-business", "nordic-trust")
_SCAFFOLD_ECOMMERCE = ("ecommerce-lite", "clean-store")

FollowupIntent = Literal[
    "tone-shift",
    "story-emphasize",
    "tagline-update",
    "positioning-shift",
    "no-semantic-change",
    "clarify",
]

_FOLLOWUP_INTENT_VALUES: set[str] = {
    "tone-shift",
    "story-emphasize",
    "tagline-update",
    "positioning-shift",
    "no-semantic-change",
    "clarify",
}

_FOLLOWUP_ADD_ONLY_KEYWORDS = (
    "lägg till",
    "lagg till",
    "add ",
    "new service",
    "new product",
    "ny produkt",
    "nytt produkt",
    "ny tjänst",
    "ny tjanst",
    "ny sida",
    "skapa sida",
    "personalsida",
    "faq",
    "pris",
    "priser",
    "price",
    "gallery",
    "galleri",
)

_FOLLOWUP_TAGLINE_KEYWORDS = (
    "tagline",
    "taglinen",
    "slogan",
    "rubrik",
    "underrubrik",
    "hero-text",
    "hero text",
    "herotext",
    "headline",
)

_FOLLOWUP_STORY_KEYWORDS = (
    "story",
    "storyn",
    "berättelse",
    "berattelse",
    "historia",
    "historien",
    "familjeföretag",
    "familjeforetag",
    "familjär",
    "familjar",
    "grundare",
    "grundaren",
    "tradition",
    "hantverk",
    "erfarenhet",
)

_FOLLOWUP_POSITIONING_KEYWORDS = (
    "positionering",
    "positionera",
    "positioning",
    "marknadsposition",
    "nisch",
    "niche",
)

_FOLLOWUP_TONE_SCOPE_KEYWORDS = (
    "ton",
    "tonen",
    "tone",
    "röst",
    "rösten",
    "rost",
    "rosten",
    "voice",
    "känsla",
    "känslan",
    "kansla",
    "kanslan",
    "uttryck",
    "uttrycket",
    "stil",
    "stilen",
    "style",
)

_FOLLOWUP_CONTENT_SCOPE_KEYWORDS = (
    "text",
    "texten",
    "copy",
    "sidtext",
    "page text",
    "page copy",
    "innehåll",
    "innehall",
    "content",
    "språk",
    "sprak",
)

_FOLLOWUP_TONE_DESCRIPTOR_KEYWORDS = (
    "premium",
    "varmare",
    "warm",
    "personligare",
    "personlig",
    "professionell",
    "professional",
    "lekfull",
    "playful",
    "lugnare",
    "lugn",
    "calmer",
    "calm",
    "förtroendeingivande",
    "fortroendeingivande",
    "förtroende",
    "fortroende",
    "tryggare",
    "trygg",
    "trustworthy",
    "modern",
)

_FOLLOWUP_STRONG_TONE_DESCRIPTOR_KEYWORDS = (
    "lugnare",
    "lugn",
    "calmer",
    "calm",
    "förtroendeingivande",
    "fortroendeingivande",
    "förtroende",
    "fortroende",
    "tryggare",
    "trygg",
    "trustworthy",
)

_FOLLOWUP_TONE_PHRASES = (
    "mer premium",
    "more premium",
    "mer personlig",
    "more personal",
    "mer professionell",
    "more professional",
    "mer lekfull",
    "more playful",
    "mer modern",
    "more modern",
    "varmare",
    "warmer",
    "lugnare",
    "mer lugn",
    "calmer",
    "more calm",
    "mer förtroendeingivande",
    "mer fortroendeingivande",
    "more trustworthy",
    "tryggare",
    "mer trygg",
)

_FOLLOWUP_TONE_KEYWORDS = (
    *_FOLLOWUP_TONE_SCOPE_KEYWORDS,
    *_FOLLOWUP_TONE_DESCRIPTOR_KEYWORDS,
)

_TONE_KEYWORD_MAP_SV: tuple[tuple[str, str], ...] = (
    ("premium", "premium"),
    ("professionell", "professionell"),
    ("professional", "professionell"),
    ("personligare", "personlig"),
    ("personlig", "personlig"),
    ("varmare", "varm"),
    ("varm", "varm"),
    ("warm", "varm"),
    ("lekfull", "lekfull"),
    ("playful", "lekfull"),
    ("lugnare", "lugn"),
    ("lugn", "lugn"),
    ("calmer", "lugn"),
    ("calm", "lugn"),
    ("förtroendeingivande", "förtroendeingivande"),
    ("fortroendeingivande", "förtroendeingivande"),
    ("förtroende", "förtroendeingivande"),
    ("fortroende", "förtroendeingivande"),
    ("tryggare", "förtroendeingivande"),
    ("trygg", "förtroendeingivande"),
    ("trustworthy", "förtroendeingivande"),
    ("modern", "modern"),
)

_TONE_KEYWORD_MAP_EN: tuple[tuple[str, str], ...] = (
    ("premium", "premium"),
    ("professional", "professional"),
    ("professionell", "professional"),
    ("personal", "personal"),
    ("personligare", "personal"),
    ("personlig", "personal"),
    ("warm", "warm"),
    ("varmare", "warm"),
    ("varm", "warm"),
    ("playful", "playful"),
    ("lekfull", "playful"),
    ("calmer", "calm"),
    ("calm", "calm"),
    ("lugnare", "calm"),
    ("lugn", "calm"),
    ("trustworthy", "trustworthy"),
    ("förtroendeingivande", "trustworthy"),
    ("fortroendeingivande", "trustworthy"),
    ("tryggare", "trustworthy"),
    ("trygg", "trustworthy"),
    ("modern", "modern"),
)

# Tokens that flip the default scaffold to ecommerce-lite. Kept tiny on
# purpose: real Scaffold Selector logic belongs in
# packages/generation/orchestration/selection/ (not in scripts/) and
# blocked behind an ADR. Until that lands, pick the more generic
# local-service-business scaffold unless the prompt clearly says "shop".
_ECOMMERCE_TOKENS = frozenset(
    {
        "butik",
        "butikssajt",
        "ehandel",
        "e-handel",
        "ecommerce",
        "checkout",
        "store",
        "produkter",
        "products",
        "shop",
        "webshop",
        "webbshop",
        "sortiment",
    }
)


def _site_id_text_without_master_prompt_header(text: str) -> str:
    stripped = (text or "").strip()
    lines = stripped.splitlines()
    if lines and lines[0].strip() == _MASTER_PROMPT_OPERATOR_HEADER:
        return "\n".join(lines[1:]).strip()
    return stripped


def slugify_site_id(
    text: str,
    *,
    suffix: str | None = None,
    company_name: str | None = None,
) -> str:
    """Produce a siteId that satisfies _SITE_ID_PATTERN.

    The first 24 chars come from the resolved company name when one is
    available, otherwise from the prompt (or a fallback "site" when the
    source has no usable letters). A short uuid suffix is always
    appended so two sources that slugify to the same stem do not collide
    in data/prompt-inputs/. Operators that already know the exact id
    they want can pass it via the meta-sidecar tooling in a later
    sprint.

    Demo-baseline-fix 1A (T3): the helper now NFKD-folds Swedish
    characters before applying the `[^a-z0-9-]+` substitution. A prompt
    like "elektriker i Malmö" previously produced
    `elektriker-i-malm-<tail>` (with `ö` collapsed to a dash); after
    the fold it becomes `elektriker-i-malmo-<tail>`, which is readable
    and still satisfies `_SITE_ID_PATTERN`.
    """
    source = (company_name or "").strip()
    if not source:
        source = _site_id_text_without_master_prompt_header(text)

    folded = _ascii_fold(source).lower()
    cleaned = _SLUG_CLEAN.sub("-", folded).strip("-")
    cleaned = _SLUG_DASHES.sub("-", cleaned)
    stem = cleaned[:24].strip("-") or "site"
    tail = suffix or uuid.uuid4().hex[:6]
    candidate = f"{stem}-{tail}"
    if not _SITE_ID_PATTERN.match(candidate):
        # Fallback: prompt produced something unusable (e.g. only
        # punctuation / non-Latin script). Use plain "site-<tail>".
        candidate = f"site-{tail}"
    return candidate


def pick_scaffold(prompt: str, brief_business_type: str | None) -> tuple[str, str]:
    """Heuristic Scaffold + Variant pick for the generated Project Input.

    Returns (scaffoldId, variantId). Defaults to local-service-business
    /nordic-trust because every Site Brief field can be mapped onto it
    and the renderer always produces a 4-page site with services /
    contact. Flips to ecommerce-lite only when the prompt or detected
    business type clearly mentions a shop. The intent is to keep the
    MVP loop honest: a wrong scaffold is editable in the generated
    Project Input file before the operator re-builds.
    """
    haystack = (prompt or "").lower()
    business = (brief_business_type or "").lower()
    if any(token in haystack for token in _ECOMMERCE_TOKENS):
        return _SCAFFOLD_ECOMMERCE
    if "shop" in business or "store" in business or "ecommerce" in business:
        return _SCAFFOLD_ECOMMERCE
    return _SCAFFOLD_LOCAL_SERVICE


def _capitalize_first(text: str) -> str:
    """Capitalize the first character and keep the rest verbatim.

    `str.capitalize()` lower-cases the rest of the string, which
    destroys mid-string proper nouns (e.g. "färska ägg från Hälsingland"
    -> "Färska ägg från hälsingland"). We only want to lift the first
    character, so the helper keeps `text[1:]` byte-for-byte.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def _ascii_fold(text: str) -> str:
    """Strip accents via NFKD so the result is ASCII-safe for slugs.

    Used only for the slug (id), never for the label - labels keep
    Swedish characters (å/ä/ö) so the rendered service grid reads
    naturally. The slug is the React key / route segment / file id
    and therefore must stay within `[a-z0-9-]`.
    """
    normalised = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in normalised if not unicodedata.combining(ch))


def _slugify_label(text: str) -> str:
    """Produce a `[a-z0-9-]+` slug from any natural-language phrase.

    Demo-baseline-fix 1A (T3): the previous `_SLUG_CLEAN` substitution
    treated Swedish characters as separators, which turned
    "färska ägg direkt från gården" into `f-rska-gg-direkt-fr-n-g-rden`
    and the operator-visible label into the unreadable `F Rska Gg
    Direkt Fr N G Rden`. NFKD-folding the source string first preserves
    "f" + "a" + "r" instead of "f" + "" + "r", so the slug becomes
    `farska-agg-direkt-fran-garden` and the label stays human.
    """
    folded = _ascii_fold(text or "").lower()
    slug = _SLUG_CLEAN.sub("-", folded).strip("-")
    slug = _SLUG_DASHES.sub("-", slug)
    return slug


def _derive_company_name(
    *,
    company_name: str | None = None,
    business_type: str | None,
    location_hint: str | None,
    services_mentioned: list[str] | None = None,
    language: str,
) -> str:
    """Build a readable company name from brief signals only.

    Demo-baseline-fix 1A (T2): the previous helper used
    `prompt[:60].rstrip(' ,.!?')` as the H1, which leaked the operator
    prompt verbatim onto the generated `/`-page (e.g. an H1 reading
    "Skapa en varm och tydlig hemsida för Gula Gårdens Ägg, en li" -
    truncated mid-name, mixed with the meta-instruction). The new
    derivation only reads brief signals, so the raw prompt cannot
    surface on customer-facing copy. Operators still edit the Project
    Input file to override the name before sharing the build.
    """
    explicit_name = (company_name or "").strip()
    if explicit_name:
        return explicit_name

    business_slug = (business_type or "").strip().lower()
    if language != "en" and business_slug in _ECOMMERCE_BUSINESS_TYPES:
        product_name = _product_category_name(services_mentioned)
        if product_name:
            return f"{product_name}butik"

    business_label = _company_business_label(business_type, language)
    location = (location_hint or "").strip()
    if language == "en":
        if business_label and location:
            return f"{business_label.capitalize()} in {location}"
        if business_label:
            return business_label.capitalize()
        if location:
            return f"New site in {location}"
        return "New site"

    if business_label and location:
        return f"{_capitalize_first(business_label)} i {location}"
    if business_label:
        return _capitalize_first(business_label)
    if location:
        return f"Sajt i {location}"
    return "Ny sajt"


def _product_category_name(services_mentioned: list[str] | None) -> str | None:
    """Return a short product category for ecommerce fallback names.

    Multi-word service labels ("handgjord keramik", "ekologisk mat") used
    to be concat:ed via ``"".join(label.split())``, which produced garbled
    compound words like ``"Handgjordkeramikbutik"`` once ``"butik"`` was
    appended by ``_derive_company_name``. Swedish reads compound nouns
    naturally as ``<noun>butik`` (``"Keramikbutik"``, ``"Matbutik"``), so
    pick the trailing noun of the label and let ``_derive_company_name``
    append the ``"butik"`` suffix to that single word.
    """
    for service in services_mentioned or []:
        if not isinstance(service, str):
            continue
        label = _service_label_from_text(service)
        if not label:
            continue
        lowered = label.lower()
        if lowered in {"konsultation", "consultation", "e-commerce", "webbshop", "webshop"}:
            continue
        words = label.split()
        if not words:
            continue
        primary_noun = words[-1]
        return _capitalize_first(primary_noun)
    return None


def _company_business_label(
    business_type: str | None, language: str
) -> str | None:
    """Return a human label for the brief's businessTypeGuess slug.

    Swedish builds look up the slug in `_BUSINESS_TYPE_LABEL_SV` first.
    Unknown slugs fall back to a "företag som arbetar med <slug>"-
    phrased reading so the H1 still reads as a deliberate Swedish
    placeholder rather than an English slug masquerading as a company
    name. Pre-1A-hotfix the fallback emitted "Sajt för <slug>", which
    rendered as "Sajt för e commerce" / "Sajt för naprapath clinic"
    when briefModel returned hyphenated slugs the map had not yet
    learned (B63, demo-baseline-fix 1A-hotfix).
    """
    if not business_type:
        return None
    slug = business_type.strip().lower()
    if not slug:
        return None
    if language == "en":
        return slug.replace("-", " ").replace("_", " ").strip() or None
    swedish = _BUSINESS_TYPE_LABEL_SV.get(slug)
    if swedish:
        return swedish
    readable = slug.replace("-", " ").replace("_", " ").strip()
    if not readable:
        return None
    return f"företag som arbetar med {readable}"


def _derive_story(
    *,
    business_type: str | None,
    location_hint: str | None,
    notes_for_planner: str | None,
    language: str,
) -> str:
    """Build customer-facing `/om-oss` story copy from brief signals only.

    Demo-baseline-fix 1A (T2) replaced the raw-prompt-as-story regression
    with a `notes_for_planner`-preferred derivation. Verifierings-Scout
    2026-05-15 then caught the follow-up regression: `notes_for_planner`
    is briefModel's INTERNAL English orientation for Phase 2 ("Likely a
    Swedish electrician website targeting Malmö; prompt is minimal, so
    keep scope conservative and local."), and rendering it on `/om-oss`
    surfaced English planner instructions to end customers (B61,
    demo-baseline-fix 1A-hotfix).

    B99 extends the B61 fix: planner notes may be useful when they are
    already customer-safe, but internal orientation ("Likely...", "prompt
    is minimal", etc.) must still never render. If the note is not safe
    customer copy, fall back to neutral public copy rather than an
    operator instruction such as "Byt ut den här texten...".
    """
    note = _customer_safe_planner_note(notes_for_planner)
    if note:
        return note[:600]

    business_label = _company_business_label(business_type, language)
    location = (location_hint or "").strip()
    if language == "en":
        if business_label and location:
            base = (
                f"{_capitalize_first(business_label)} in {location} with "
                "a clear offer, simple contact route and a focused first "
                "step for visitors."
            )
        elif business_label:
            base = (
                f"{_capitalize_first(business_label)} with a clear offer, "
                "simple contact route and a focused first step for visitors."
            )
        elif location:
            base = (
                f"A local business in {location} with a clear offer and "
                "simple contact route for visitors."
            )
        else:
            base = (
                "A business website with a clear offer, simple contact "
                "route and focused next step for visitors."
            )
        return base[:600]

    if business_label and location:
        base = (
            f"{_capitalize_first(business_label)} i {location} med tydligt "
            "erbjudande, enkel kontaktväg och ett fokuserat nästa steg för "
            "besökaren."
        )
    elif business_label:
        base = (
            f"{_capitalize_first(business_label)} med tydligt erbjudande, "
            "enkel kontaktväg och ett fokuserat nästa steg för besökaren."
        )
    elif location:
        base = (
            f"Lokalt företag i {location} med tydligt erbjudande och enkel "
            "kontaktväg för besökaren."
        )
    else:
        base = (
            "Företagshemsida med tydligt erbjudande, enkel kontaktväg och "
            "ett fokuserat nästa steg för besökaren."
        )
    return base[:600]


def _customer_safe_planner_note(note: str | None) -> str | None:
    """Return planner note text only when it is safe public copy.

    B128 (re-Verifierings-Scout 2026-05-19): noten avvisas också om den
    inleds med en svensk/engelsk build-imperativ (``"Bygg en liten
    e-handel ..."``, ``"Skapa en hemsida ..."``, ``"Make a clean shop
    ..."``). B99-blocklistan fokuserar på arbets-/dev-jargong och fångade
    inte rena planner-direktiv som tonade ner sig själva. En riktig
    /om-oss-copy börjar aldrig med ett verb i imperativ riktat till
    modellen, så grinden är säker att stänga.
    """
    cleaned = " ".join((note or "").split())
    if not cleaned:
        return None
    lower = cleaned.lower()
    if any(token in lower for token in _PLANNER_NOTE_BLOCKLIST):
        return None
    if _starts_with_planner_imperative(lower):
        return None
    if not cleaned.endswith((".", "!", "?")):
        cleaned = f"{cleaned}."
    return cleaned


def _starts_with_planner_imperative(lower_note: str) -> bool:
    """Return True when ``lower_note`` opens with a build-imperative.

    Called by ``_customer_safe_planner_note`` for B128. The helper takes
    the already lower-cased note (the caller has done ``.lower()`` once
    on a whitespace-collapsed string) so we can token-match without
    re-folding case here. Single-word tokens are checked with a word
    boundary so ``"byggfirma"`` does not match ``"bygg"``; multi-word
    phrases (``"lägg upp"``) are matched as prefix strings.

    B128 hardening (post-Composer-2.5-review 2026-05-19): a leading
    run of non-letter characters (markdown markers, list dashes,
    numerals, parentheses) used to bypass the guard because
    ``re.match(r"[a-zåäöéü]+", ...)`` returns ``None`` when the very
    first character is punctuation. We now strip one run of leading
    non-letter characters before the token match so a build-imperative
    sitting behind a leading dash, bold-marker or list numeral is
    blocked identically to a build-imperative at position 0. We do not
    scan further into the note (e.g. past a sentence preamble like
    "OK. Bygg ...") because that broadens the imperative surface
    enough to risk false-blocking present-tense customer copy that
    legitimately mentions a build-verb mid-sentence.
    """
    if not lower_note:
        return False
    stripped = lower_note.lstrip()
    if not stripped:
        return False
    head = re.sub(r"^[^a-zåäöéü]+", "", stripped, count=1)
    if not head:
        return False
    for phrase in _PLANNER_IMPERATIVE_PHRASES:
        if head.startswith(phrase + " ") or head == phrase:
            return True
    first_token_match = re.match(r"[a-zåäöéü]+", head)
    if first_token_match is None:
        return False
    return first_token_match.group(0) in _PLANNER_IMPERATIVE_TOKENS


def _derive_tagline(
    *,
    business_type: str | None,
    location_hint: str | None,
    notes_for_planner: str | None = None,
    services_mentioned: list[str] | None = None,
    language: str,
) -> str:
    """Build a short customer-facing tagline from brief signals only.

    Demo-baseline-fix 1A-hotfix (B61): pre-hotfix `site_brief_to_project_input`
    used `(brief.notesForPlanner or tagline_default)[:140]` for
    `company.tagline`. Since `notesForPlanner` is briefModel's English
    planner orientation, taglines on Swedish sites read as English meta
    instructions ("Likely a Swedish electrician website targeting
    Malmö..."). The new derivation never reads notesForPlanner; it
    builds a short tagline from `businessTypeGuess` + `locationHint`
    instead, falling back to a generic Swedish/English placeholder when
    both signals are missing. Operators override the tagline in the
    Project Input file before sharing the build.

    The schema requires `company.tagline` with minLength=1, maxLength=140,
    so the helper always returns a non-empty string capped at 140 chars.
    """
    _ = notes_for_planner  # B61: never render planner orientation in tagline.
    slug = (business_type or "").strip().lower()
    mapped = (
        _TAGLINE_BY_BUSINESS_TYPE_EN.get(slug)
        if language == "en"
        else _TAGLINE_BY_BUSINESS_TYPE_SV.get(slug)
    )
    if mapped:
        return mapped[:140]

    services = [
        _service_label_from_text(service)
        for service in (services_mentioned or [])
        if isinstance(service, str) and service.strip()
    ]
    if services:
        first_service = services[0].lower()
        tagline = (
            f"Help with {first_service}"
            if language == "en"
            else f"Hjälp med {first_service}"
        )
        return tagline[:140]

    business_label = _company_business_label(business_type, language)
    location = (location_hint or "").strip()
    if language == "en":
        if business_label:
            tagline = f"Clear next step for {business_label}"
        elif location:
            tagline = f"Clear local help in {location}"
        else:
            tagline = "Welcome"
    else:
        if business_label:
            tagline = f"Tydlig väg vidare för {business_label}"
        elif location:
            tagline = f"Tydlig lokal hjälp i {location}"
        else:
            tagline = "Välkommen"
    return tagline[:140]


def _service_label_from_text(text: str) -> str:
    """Human-readable service label that preserves Swedish characters.

    Used when the brief's `servicesMentioned` field already contains
    natural-language phrases ("färska ägg direkt från gården"). We
    capitalise the first character and keep the rest verbatim so å/ä/ö
    survive into the rendered service grid.
    """
    cleaned = " ".join((text or "").split())
    return _capitalize_first(cleaned)


def _service_label_from_slug(slug: str) -> str:
    """Fallback label when the brief item still looks like a kebab slug.

    Pre-T3 briefs (or any future caller that hands us a slug instead of
    a phrase) end up here. `slug.replace("-"," ").title()` is intentional
    for the legacy path - it produces "Akut Elservice" from
    `akut-elservice`. We keep this branch so older prompt-inputs in
    `data/prompt-inputs/` still render with the old shape after a
    rebuild instead of regressing to bare slugs.
    """
    return slug.replace("-", " ").replace("_", " ").strip().title() or slug


def _looks_like_slug(text: str) -> bool:
    """True when the input is already kebab-case ASCII (legacy brief).

    Used to dispatch between `_service_label_from_text` (preserve
    Swedish casing) and `_service_label_from_slug` (legacy fallback).
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if " " in cleaned:
        return False
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", cleaned))


def _service_summary(
    label: str,
    language: str,
    *,
    business_type: str | None = None,
) -> str:
    """Return a neutral customer-facing summary for a service entry.

    Demo-baseline-fix 1A-hotfix (B61): the previous summaries leaked
    dev jargon onto rendered service cards ("placeholder generated
    from your prompt - edit the Project Input to refine" / "Justera
    Project Input för att förbättra texten"). The hotfix replaces the
    second sentence with a short, customer-readable call to action so
    the rendered services grid no longer broadcasts the operator's
    workflow to end users. Operators still edit the Project Input
    file to expand the description before sharing the build.
    """
    slug = (business_type or "").strip().lower()
    mapped = (
        _SERVICE_SUMMARY_BY_BUSINESS_TYPE_EN.get(slug)
        if language == "en"
        else _SERVICE_SUMMARY_BY_BUSINESS_TYPE_SV.get(slug)
    )
    if mapped:
        return mapped
    if language == "en":
        return f"Clear help with {label.lower()} and a simple next step."
    return f"Tydlig hjälp med {label.lower()} och enkel väg vidare."


def _placeholder_services(
    language: str,
    *,
    business_type: str | None = None,
) -> list[dict[str, str]]:
    """Schema-required service when the brief mentioned none.

    The schema requires `services` with minItems=1, so the helper always
    returns at least one entry. Demo-baseline-fix 1A-hotfix (B61): the
    summary text is now plain customer copy instead of the previous
    "placeholder generated from your prompt"-flavoured dev jargon.
    """
    slug = (business_type or "").strip().lower()
    if language == "en":
        label = (slug.replace("-", " ").replace("_", " ").strip() or "Service").title()
        summary = _service_summary(label, language, business_type=business_type)
        return [{"id": _slugify_label(label), "label": label, "summary": summary}]
    label = _SERVICE_LABEL_BY_BUSINESS_TYPE_SV.get(slug, "Tjänster")
    summary = _service_summary(label, language, business_type=business_type)
    return [
        {
            "id": _slugify_label(label),
            "label": label,
            "summary": summary,
        }
    ]


def _build_services(
    services_mentioned: list[str],
    language: str,
    *,
    business_type: str | None = None,
) -> list[dict[str, str]]:
    """Map the brief's services_mentioned phrases onto Project Input services.

    Demo-baseline-fix 1A (T3): briefModel is now asked to return
    natural-language phrases in the prompt's original language for the
    `services_mentioned` field. Each phrase becomes a service with:

    - `id`: ASCII-folded slug (`färska ägg` -> `farska-agg`) so it stays
      safe as a React key / route segment.
    - `label`: capitalised original phrase so å/ä/ö survive on the
      rendered service grid.

    The helper also accepts legacy kebab-case slugs (pre-T3 briefs and
    follow-up prompts replayed on top of older Project Inputs) and
    routes them through `_service_label_from_slug` so an existing
    Project Input does not regress to bare slugs after a rebuild.

    Returns at least one service so the schema's ``services minItems: 1``
    constraint is satisfied even when the brief is empty. Caps at five
    so the home page services grid stays visually balanced.
    """
    seen: set[str] = set()
    services: list[dict[str, str]] = []
    for raw in services_mentioned[:8]:
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if not text:
            continue
        base_slug = _slugify_label(text)
        if not base_slug:
            continue
        slug = base_slug
        suffix = 2
        while slug in seen:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        seen.add(slug)
        if _looks_like_slug(text):
            label = _service_label_from_slug(text)
        else:
            label = _service_label_from_text(text)
        services.append(
            {
                "id": slug,
                "label": label,
                "summary": _service_summary(
                    label,
                    language,
                    business_type=business_type,
                ),
            }
        )
        if len(services) >= 5:
            break
    if not services:
        services = _placeholder_services(language, business_type=business_type)
    return services


# B88-fallback strängar för kontaktblocket. Lyfta till modulnivå så
# ``_recompute_placeholder_contact_fields`` kan jämföra slutligt
# Project Input mot exakt samma värden som ``_placeholder_contact``
# skriver in. Operatören kan fortfarande skriva över via Project Input
# eller via wizard/scrape genom Discovery Resolver innan publicering.
_PLACEHOLDER_CONTACT_PHONE = "+46 8 000 00 00"
_PLACEHOLDER_CONTACT_OPENING_HOURS_SV = "Mån-Fre 09:00-17:00"
_PLACEHOLDER_CONTACT_OPENING_HOURS_EN = "Mon-Fri 09:00-17:00"
_PLACEHOLDER_CONTACT_EMAIL_SV = "kontakt@example.se"
_PLACEHOLDER_CONTACT_EMAIL_EN = "contact@example.se"
_PLACEHOLDER_CONTACT_ADDRESS_SV = "Adress lämnas på förfrågan"
_PLACEHOLDER_CONTACT_ADDRESS_EN = "Address available on request"


def _placeholder_contact_defaults(language: str) -> dict[str, Any]:
    """Return the dummy contact-block values for ``language``.

    Used by ``_placeholder_contact`` to fill in missing fields and by
    ``_recompute_placeholder_contact_fields`` to detect which fields in
    a final Project Input are still placeholder values after wizard/
    scrape/follow-up merging.
    """
    if language == "en":
        return {
            "phone": _PLACEHOLDER_CONTACT_PHONE,
            "email": _PLACEHOLDER_CONTACT_EMAIL_EN,
            "addressLines": [_PLACEHOLDER_CONTACT_ADDRESS_EN],
            "openingHours": _PLACEHOLDER_CONTACT_OPENING_HOURS_EN,
        }
    return {
        "phone": _PLACEHOLDER_CONTACT_PHONE,
        "email": _PLACEHOLDER_CONTACT_EMAIL_SV,
        "addressLines": [_PLACEHOLDER_CONTACT_ADDRESS_SV],
        "openingHours": _PLACEHOLDER_CONTACT_OPENING_HOURS_SV,
    }


def _placeholder_contact(
    language: str,
    *,
    contact_phone: str | None = None,
    contact_email: str | None = None,
    contact_address: str | None = None,
    contact_opening_hours: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Schema-required contact block when the brief has no real values.

    Returns a tuple ``(contact_dict, placeholder_fields)`` where
    ``placeholder_fields`` lists which top-level keys of ``contact_dict``
    were filled with dummy fallback values because the caller did not
    pass a real value. When the operator supplied a real value in
    ``contact_phone`` / ``contact_email`` / ``contact_address`` /
    ``contact_opening_hours`` the corresponding field is NOT in the list
    — that is the signal ``site_brief_to_project_input`` propagates
    further so Viewser can warn the operator about fields the end user
    will see as dummy data (B133, 2026-05-19).

    ``openingHours`` was added to the tracked set in the Codex P2 review
    follow-up 2026-05-19. The brief itself never carries opening hours,
    but the resolver's wizard layer can supply them; until the operator
    fills it in, the contact page renders ``Mån-Fre 09:00-17:00`` /
    ``Mon-Fri 09:00-17:00`` next to the phone number and the visitor
    has no way to know those are not real business hours.

    Demo-baseline-fix 1C (B88): the previous placeholders for `address`
    were operator-facing dev jargon ("Adress saknas - uppdatera Project
    Input"), which leaked verbatim into the public ``<address>`` tag on
    every generated /kontakt page in the re-Scout 2026-05-15 run.
    Schema constraint ``addressLines minItems=1 + items minLength=1``
    forbids an empty value, so the fallback is now a brand-neutral
    Swedish/English phrase that reads acceptably to a real visitor.
    The operator can still override it in the generated Project Input
    before sharing the build, but B133 surfaces that the values are
    placeholders so the operator does not unknowingly publish a site
    with `+46 8 000 00 00` and `kontakt@example.se` as if they were
    real contact details.
    """
    phone = (contact_phone or "").strip()
    email = (contact_email or "").strip()
    address = (contact_address or "").strip()
    opening_hours = (contact_opening_hours or "").strip()
    defaults = _placeholder_contact_defaults(language)
    placeholder_fields: list[str] = []
    if phone:
        final_phone = phone
    else:
        final_phone = defaults["phone"]
        placeholder_fields.append("phone")
    if email:
        final_email = email
    else:
        final_email = defaults["email"]
        placeholder_fields.append("email")
    if address:
        address_lines = [address]
    else:
        address_lines = list(defaults["addressLines"])
        placeholder_fields.append("addressLines")
    if opening_hours:
        final_opening_hours = opening_hours
    else:
        final_opening_hours = defaults["openingHours"]
        placeholder_fields.append("openingHours")
    contact_dict: dict[str, Any] = {
        "phone": final_phone,
        "email": final_email,
        "addressLines": address_lines,
        "openingHours": final_opening_hours,
    }
    return contact_dict, placeholder_fields


def _recompute_placeholder_contact_fields(
    contact: dict[str, Any] | None, language: str
) -> list[str]:
    """Return which contact fields still equal the B88 fallback values.

    Used after wizard/scrape merging in Discovery Resolver and after
    ``merge_followup_project_input`` so the placeholder-warning list
    reflects the final Project Input rather than the state that
    ``_placeholder_contact`` produced before any operator-supplied data
    overwrote it. A field is still a placeholder iff its current value
    is byte-identical to the fallback that ``_placeholder_contact``
    would have written for the same language.
    """
    if not isinstance(contact, dict):
        return []
    defaults = _placeholder_contact_defaults(language)
    fields: list[str] = []
    if contact.get("phone") == defaults["phone"]:
        fields.append("phone")
    if contact.get("email") == defaults["email"]:
        fields.append("email")
    address_lines = contact.get("addressLines")
    if (
        isinstance(address_lines, list)
        and list(address_lines) == defaults["addressLines"]
    ):
        fields.append("addressLines")
    if contact.get("openingHours") == defaults["openingHours"]:
        fields.append("openingHours")
    return fields


# Demo-baseline-fix 1C (B95): values that the brief sometimes returns as
# `locationHint` even though they are country names, not cities. When we
# see one of these we treat the location as "country only" and let the
# renderer drop the city tag on hero rather than surfacing the country
# name as an ortstag. Comparison is case-insensitive on the stripped
# string.
_COUNTRY_NAME_LOCATION_HINTS: set[str] = {
    "sweden",
    "sverige",
    "norway",
    "norge",
    "denmark",
    "danmark",
    "finland",
    "iceland",
    "island",
}


def _normalize_location_hint(
    location_hint: str | None, language: str
) -> str | None:
    """Normalise location hints, treating country names as "no city".

    Two jobs:

    1. Demo-baseline-fix 1A-hotfix (B62): rewrite the rare
       ``locationHint="Sweden"`` from briefModel to ``"Sverige"`` on
       Swedish builds. After the B95 change this only matters as a
       transitional translation because country names now fall through
       to step 2.
    2. Demo-baseline-fix 1C (B95): if the cleaned value matches one of
       ``_COUNTRY_NAME_LOCATION_HINTS`` (sv + en variants for the
       Nordic countries we actually see today) we return ``None`` on
       both languages so ``_placeholder_location`` falls back to its
       country-only city and the renderer can suppress the hero
       ortstag. This is broader than B91 / the previous
       ``Sweden -> Sverige`` map because it also catches
       ``locationHint="Sverige"`` (no city) which surfaced as a hero
       ortstag for the e-commerce prompt in the re-Verifierings-Scout
       2026-05-15 run.
    """
    if not location_hint:
        return location_hint
    cleaned = location_hint.strip()
    if not cleaned:
        return None
    if cleaned.lower() in _COUNTRY_NAME_LOCATION_HINTS:
        return None
    return cleaned


def _placeholder_location(
    location_hint: str | None, language: str
) -> dict[str, Any]:
    """Schema-required location block.

    serviceAreas requires at least one entry. When the brief has no
    location hint (or the hint is a country name per B95) we fall back
    to a city == country marker so ``scripts/build_site.py`` can
    detect "country only" and suppress the hero ortstag rather than
    rendering the country as if it were a city.
    """
    normalized = _normalize_location_hint(location_hint, language)
    country = "Sweden" if language == "en" else "Sverige"
    city = normalized or country
    return {
        "city": city,
        "country": country,
        "serviceAreas": [city],
    }


def site_brief_to_project_input(
    brief: dict[str, Any],
    *,
    site_id: str,
    scaffold_id: str,
    variant_id: str,
    original_prompt: str,
) -> tuple[dict[str, Any], list[str]]:
    """Deterministic Site Brief -> Project Input mapping.

    Operates on the canonical Site Brief artefakt shape (the dict that
    site_brief_to_artifact returns) so this helper works regardless of
    whether briefModel ran as 'real', 'mock-no-key' or 'mock-llm-error'.
    Missing fields fall back to schema-valid placeholders that the
    operator can edit in the generated Project Input file before
    re-building.

    Returns a tuple ``(project_input, placeholder_contact_fields)``
    where ``placeholder_contact_fields`` lists contact-block keys
    (``phone``, ``email``, ``addressLines``) that were filled with B88
    dummy values because briefModel did not return a real value. The
    list flows through ``generate()`` onto the meta sidecar so
    ``scripts/build_site.py`` can include ``placeholderContactFields``
    in ``build-result.json`` and Viewser Run Details can warn the
    operator that the published site shows dummy contact info (B133,
    2026-05-19).
    """
    language = brief.get("language") or "sv"
    business_type = brief.get("businessTypeGuess") or (
        "shop" if scaffold_id == "ecommerce-lite" else "service-provider"
    )
    # Demo-baseline-fix 1A-hotfix (B62): rewrite `locationHint="Sweden"`
    # to "Sverige" on Swedish builds before deriving any copy from it,
    # so H1, tagline and serviceArea all read in the prompt language.
    location_hint = _normalize_location_hint(
        brief.get("locationHint"), language
    )
    # Demo-baseline-fix 1A (T2) + 1A-hotfix (B61): name, tagline and
    # story are derived from brief signals only. `original_prompt` is not
    # used (would re-introduce raw-prompt-on-H1). B99 allows
    # notesForPlanner into story only when it is already safe public copy;
    # internal planner orientation still gets discarded.
    _ = original_prompt
    company_name = _derive_company_name(
        company_name=brief.get("companyName"),
        business_type=business_type,
        location_hint=location_hint,
        services_mentioned=brief.get("servicesMentioned") or [],
        language=language,
    )
    tagline = _derive_tagline(
        business_type=business_type,
        location_hint=location_hint,
        notes_for_planner=brief.get("notesForPlanner"),
        services_mentioned=brief.get("servicesMentioned") or [],
        language=language,
    )
    story = _derive_story(
        business_type=business_type,
        location_hint=location_hint,
        notes_for_planner=brief.get("notesForPlanner"),
        language=language,
    )

    services = _build_services(
        brief.get("servicesMentioned") or [],
        language,
        business_type=business_type,
    )

    contact_block, placeholder_contact_fields = _placeholder_contact(
        language,
        contact_phone=brief.get("contactPhone"),
        contact_email=brief.get("contactEmail"),
        contact_address=brief.get("contactAddress"),
    )

    tone_words = list(brief.get("tone") or [])
    project_input: dict[str, Any] = {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": site_id,
        "scaffoldId": scaffold_id,
        "variantId": variant_id,
        "language": language,
        "company": {
            "name": company_name,
            "businessType": business_type,
            "tagline": tagline,
            "story": story,
        },
        "location": _placeholder_location(location_hint, language),
        "services": services,
        "tone": {
            "primary": tone_words[0] if tone_words else "trustworthy",
            "secondary": tone_words[1:5],
            "avoid": [],
        },
        "trustSignals": [],
        "conversionGoals": list(brief.get("conversionGoals") or []),
        "requestedCapabilities": list(
            brief.get("requestedCapabilities") or []
        ),
        "contact": contact_block,
        "selectedDossiers": {
            "required": [],
            "recommended": [],
            "rationale": (
                "Auto-genererat från prompt; operatören kan lägga till "
                "Dossiers i Project Input-filen före ny build."
                if language == "sv"
                else "Auto-generated from prompt; operator may add Dossiers "
                "in the Project Input file before re-building."
            ),
        },
    }
    return project_input, placeholder_contact_fields


def _validate_against_schema(payload: dict[str, Any]) -> None:
    """Schema-lock the generated Project Input before writing to disk.

    A drift between this generator and project-input.schema.json must
    fail loudly here, not later inside build_site.py - the operator
    otherwise sees a confusing builder KeyError instead of a clear
    schema-validation message pointing at the missing field.
    """
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if not errors:
        return
    first = errors[0]
    location = first.json_path or "$"
    raise SystemExit(
        f"Generated Project Input failed schema check at {location}: "
        f"{first.message} (and {len(errors) - 1} more)"
    )


def _current_project_input_path(output_dir: Path, site_id: str) -> Path:
    return output_dir / f"{site_id}.project-input.json"


def _current_meta_path(output_dir: Path, site_id: str) -> Path:
    return output_dir / f"{site_id}.meta.json"


def _versioned_project_input_path(
    output_dir: Path, site_id: str, version: int
) -> Path:
    return output_dir / f"{site_id}.v{version}.project-input.json"


def _versioned_meta_path(output_dir: Path, site_id: str, version: int) -> Path:
    return output_dir / f"{site_id}.v{version}.meta.json"


def _write_immutable_snapshot(path: Path, payload: str) -> None:
    """Write a versioned snapshot file with O_EXCL semantics.

    `.vN.project-input.json` / `.vN.meta.json` must be immutable so older
    versions stay byte-stable across rebuilds and concurrent follow-ups.
    `open(..., "x")` raises FileExistsError when the target path already
    exists; we surface that as a SystemExit so a stale or racing call
    cannot silently overwrite a previously-written version snapshot
    (B60 fynd 1).
    """
    try:
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise SystemExit(
            f"Versioned snapshot already exists: {path}. "
            "Snapshots are immutable; bump the version or remove the "
            "existing file manually."
        ) from exc


def _atomic_write_text(path: Path, payload: str) -> None:
    """Write to a sibling tempfile and atomically replace the target.

    Pointer files (`<siteId>.project-input.json` / `<siteId>.meta.json`)
    are mutable, but readers must never observe a half-written or
    truncated payload. Staging to a tempfile in the same directory and
    then `os.replace`-ing onto the target gives a single atomic step on
    POSIX and a near-atomic one on Windows (B60 fynd 3).
    """
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def write_project_input(
    project_input: dict[str, Any],
    meta: dict[str, Any],
    *,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write immutable version snapshots plus current-pointer files.

    Returns the VERSIONED (project_input_path, meta_path) tuple so the
    caller builds the exact Project Input snapshot for this run. The
    unversioned ``<siteId>.project-input.json`` / ``<siteId>.meta.json``
    files remain as the operator-visible "latest" pointers for Viewser
    selection and follow-up lookup.

    Versioned snapshots are written with `_write_immutable_snapshot`
    (refuses to overwrite an existing version) and pointer files via
    `_atomic_write_text` (tempfile + rename, never half-written). See
    B60 fynd 1 + 3 for context.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    site_id = project_input["siteId"]
    version = meta.get("version")
    if not isinstance(version, int) or version < 1:
        raise SystemExit("Project Input meta must include version >= 1.")

    project_input_payload = (
        json.dumps(project_input, ensure_ascii=False, indent=2) + "\n"
    )
    meta_payload = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"

    versioned_project_input_path = _versioned_project_input_path(
        output_dir, site_id, version
    )
    versioned_meta_path = _versioned_meta_path(output_dir, site_id, version)
    current_project_input_path = _current_project_input_path(output_dir, site_id)
    current_meta_path = _current_meta_path(output_dir, site_id)

    _write_immutable_snapshot(versioned_project_input_path, project_input_payload)
    _write_immutable_snapshot(versioned_meta_path, meta_payload)
    _atomic_write_text(current_project_input_path, project_input_payload)
    _atomic_write_text(current_meta_path, meta_payload)
    return versioned_project_input_path, versioned_meta_path


def read_existing_meta(site_id: str, *, output_dir: Path) -> dict[str, Any]:
    """Read the sidecar meta that anchors follow-up prompt versions."""
    if not _SITE_ID_PATTERN.match(site_id):
        raise SystemExit(
            f"Follow-up siteId {site_id!r} does not match the lower-case "
            "alphanumeric/dash pattern required by Viewser."
        )

    meta_path = _current_meta_path(output_dir, site_id)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(
            f"Follow-up meta sidecar saknas: {meta_path}. Kör först en "
            "prompt-build som skapar data/prompt-inputs/<siteId>.meta.json."
        ) from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Follow-up meta sidecar är inte giltig JSON: {meta_path}"
        ) from exc

    project_id = meta.get("projectId")
    version = meta.get("version")
    if not isinstance(project_id, str) or not project_id.strip():
        raise SystemExit(f"Follow-up meta saknar projectId: {meta_path}")
    if not isinstance(version, int) or version < 1:
        raise SystemExit(f"Follow-up meta har ogiltig version: {meta_path}")

    meta_site_id = meta.get("siteId")
    if isinstance(meta_site_id, str) and meta_site_id != site_id:
        raise SystemExit(
            f"Follow-up meta siteId mismatch: path={site_id!r}, meta={meta_site_id!r}"
        )
    return meta


def read_existing_project_input(site_id: str, *, output_dir: Path) -> dict[str, Any]:
    """Read the latest Project Input snapshot for a follow-up prompt."""
    project_input_path = _current_project_input_path(output_dir, site_id)
    try:
        project_input = json.loads(project_input_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(
            f"Follow-up Project Input saknas: {project_input_path}. Kör först "
            "en prompt-build som skapar data/prompt-inputs/<siteId>.project-input.json."
        ) from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Follow-up Project Input är inte giltig JSON: {project_input_path}"
        ) from exc

    if project_input.get("siteId") != site_id:
        raise SystemExit(
            "Follow-up Project Input siteId mismatch: "
            f"path={site_id!r}, payload={project_input.get('siteId')!r}"
        )
    return project_input


def _unique_strings(*values: list[Any]) -> list[str]:
    """Return a stable union of non-empty string values."""
    seen: set[str] = set()
    merged: list[str] = []
    for group in values:
        for value in group:
            if not isinstance(value, str):
                continue
            cleaned = value.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            merged.append(cleaned)
    return merged


def _merge_services(
    existing_services: list[dict[str, Any]],
    candidate_services: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append new follow-up services without rewriting existing ones."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for service in [*existing_services, *candidate_services]:
        if not isinstance(service, dict):
            continue
        service_id = service.get("id")
        if not isinstance(service_id, str) or not service_id.strip():
            continue
        if service_id in seen:
            continue
        seen.add(service_id)
        merged.append(copy.deepcopy(service))
    return (
        merged
        or copy.deepcopy(existing_services)
        or copy.deepcopy(candidate_services)
    )


def _normalise_followup_text(text: str) -> str:
    """Collapse operator formatting before deterministic intent matching."""
    normalised = unicodedata.normalize("NFKC", text or "").lower()
    normalised = re.sub(r"[\[\]()`*_\"'“”‘’]+", " ", normalised)
    normalised = re.sub(r"\s+", " ", normalised)
    return normalised.strip()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _contains_word(text: str, keyword: str) -> bool:
    pattern = rf"(?<![a-zåäöéü0-9]){re.escape(keyword)}(?![a-zåäöéü0-9])"
    return bool(re.search(pattern, text))


def _contains_any_word(text: str, keywords: tuple[str, ...]) -> bool:
    return any(_contains_word(text, keyword) for keyword in keywords)


def _has_tone_shift_signal(text: str) -> bool:
    has_scope = _contains_any_word(text, _FOLLOWUP_TONE_SCOPE_KEYWORDS)
    has_descriptor = _contains_any_word(text, _FOLLOWUP_TONE_DESCRIPTOR_KEYWORDS)
    has_strong_descriptor = _contains_any_word(text, _FOLLOWUP_STRONG_TONE_DESCRIPTOR_KEYWORDS)
    has_phrase = _contains_any(text, _FOLLOWUP_TONE_PHRASES)
    has_content_scope = _contains_any(text, _FOLLOWUP_CONTENT_SCOPE_KEYWORDS)
    if has_content_scope and not has_scope and not has_strong_descriptor:
        return False
    if _contains_any(text, _FOLLOWUP_ADD_ONLY_KEYWORDS) and not has_scope and not has_phrase:
        return False
    return has_scope or has_descriptor or has_phrase


def classify_followup_intent(
    follow_up_prompt: str,
    *,
    language: str,
) -> FollowupIntent:
    """Classify semantic follow-up scope without an LLM call.

    V1 keeps the table intentionally small and whitelist-based. Unknown
    prompts remain additive/conservative so B60's no-leak guarantees stay
    stronger than the desire to infer every possible operator phrasing.
    """
    _ = language
    text = _normalise_followup_text(follow_up_prompt)
    if not text or len(text) < 4:
        return "clarify"

    has_additive_keyword = _contains_any(text, _FOLLOWUP_ADD_ONLY_KEYWORDS)
    if (
        has_additive_keyword
        and _contains_any_word(text, _FOLLOWUP_TONE_SCOPE_KEYWORDS)
        and _has_tone_shift_signal(text)
    ):
        return "tone-shift"
    if has_additive_keyword:
        return "no-semantic-change"
    if _contains_any(text, _FOLLOWUP_TAGLINE_KEYWORDS):
        return "tagline-update"
    if _contains_any(text, _FOLLOWUP_STORY_KEYWORDS):
        return "story-emphasize"
    if _contains_any(text, _FOLLOWUP_POSITIONING_KEYWORDS):
        return "positioning-shift"
    if _has_tone_shift_signal(text):
        return "tone-shift"
    return "no-semantic-change"


def _string_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _looks_like_raw_followup_prompt(text: str, follow_up_prompt: str) -> bool:
    """Return True when candidate copy is just the operator instruction."""
    candidate = _normalise_followup_text(text)
    prompt = _normalise_followup_text(follow_up_prompt)
    if not candidate or not prompt:
        return False
    if candidate == prompt or candidate in prompt or prompt in candidate:
        return True
    prompt_words = [word for word in re.findall(r"[a-zåäöéü0-9]+", prompt)]
    if len(prompt_words) < 4:
        return False
    first_clause = " ".join(prompt_words[:4])
    return first_clause in candidate


def _safe_semantic_text(
    value: Any,
    *,
    follow_up_prompt: str,
    max_length: int,
    reject_ui_directive: bool = False,
) -> str | None:
    """Filter candidate semantic copy through the existing public-copy guards."""
    cleaned = _string_value(value)
    if not cleaned:
        return None
    if reject_ui_directive and _offer_looks_like_ui_directive(cleaned):
        return None
    safe = _customer_safe_planner_note(cleaned)
    if not safe:
        return None
    if _looks_like_raw_followup_prompt(safe, follow_up_prompt):
        return None
    safe = safe.removesuffix(".") if max_length <= 140 else safe
    return safe[:max_length]


def _explicit_semantic_copy_from_prompt(
    follow_up_prompt: str,
    *,
    max_length: int,
    reject_ui_directive: bool = False,
) -> str | None:
    """Allow explicit public copy after a narrow ``till``/``to`` marker."""
    match = re.search(
        r"(?:\btill\b|\bto\b)\s*[:：]\s*(.+)$",
        follow_up_prompt.strip(),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    candidate = match.group(1).strip().strip("\"'“”‘’")
    if not candidate:
        return None
    if reject_ui_directive and _offer_looks_like_ui_directive(candidate):
        return None
    safe = _customer_safe_planner_note(candidate)
    if not safe:
        return None
    safe = safe.removesuffix(".") if max_length <= 140 else safe
    return safe[:max_length]


def _tone_keyword_pairs(language: str) -> tuple[tuple[str, str], ...]:
    return _TONE_KEYWORD_MAP_EN if language == "en" else _TONE_KEYWORD_MAP_SV


def _tone_words_from_prompt(
    follow_up_prompt: str,
    *,
    language: str,
) -> list[str]:
    text = _normalise_followup_text(follow_up_prompt)
    words: list[str] = []
    for keyword, tone_word in _tone_keyword_pairs(language):
        if _contains_word(text, keyword) and tone_word not in words:
            words.append(tone_word)
    return words


def _avoid_words_from_prompt(
    follow_up_prompt: str,
    *,
    language: str,
) -> list[str]:
    text = _normalise_followup_text(follow_up_prompt)
    candidates = (
        ("kall", "kall"),
        ("stel", "stel"),
        ("krånglig", "krånglig"),
        ("kranglig", "krånglig"),
        ("opersonlig", "opersonlig"),
        ("säljig", "säljig"),
        ("saljig", "säljig"),
        ("cold", "cold"),
        ("stiff", "stiff"),
        ("complicated", "complicated"),
        ("impersonal", "impersonal"),
        ("salesy", "salesy"),
    )
    avoid_markers = (
        "undvik",
        "inte ",
        "mindre ",
        "utan ",
        "avoid",
        "not ",
        "less ",
        "without ",
    )
    if not any(marker in text for marker in avoid_markers):
        return []
    words: list[str] = []
    for keyword, value in candidates:
        if keyword in text and value not in words:
            words.append(value)
    if language == "en":
        return [
            {
                "kall": "cold",
                "stel": "stiff",
                "krånglig": "complicated",
                "opersonlig": "impersonal",
                "säljig": "salesy",
            }.get(word, word)
            for word in words
        ]
    return [
        {
            "cold": "kall",
            "stiff": "stel",
            "complicated": "krånglig",
            "impersonal": "opersonlig",
            "salesy": "säljig",
        }.get(word, word)
        for word in words
    ]


def _fallback_tagline_for_prompt(
    follow_up_prompt: str,
    *,
    language: str,
) -> str:
    text = _normalise_followup_text(follow_up_prompt)
    if language == "en":
        if "premium" in text:
            return "Premium feel with dependable help"
        if "famil" in text:
            return "Personal help with a family feel"
        if "person" in text:
            return "Personal help with a clear next step"
        if "warm" in text:
            return "Warm guidance and a clear next step"
        return "Clear help with a personal touch"
    if "premium" in text:
        return "Premiumkänsla med trygg hjälp"
    if "famil" in text:
        return "Personlig hjälp med familjär känsla"
    if "person" in text:
        return "Personlig hjälp med tydlig väg vidare"
    if "varm" in text:
        return "Varm vägledning och tydlig hjälp"
    return "Tydlig hjälp med personlig känsla"


def _story_sentence_for_prompt(
    follow_up_prompt: str,
    *,
    language: str,
) -> str:
    text = _normalise_followup_text(follow_up_prompt)
    if language == "en":
        if "famil" in text:
            return (
                "The story highlights the family-business feel: close "
                "relationships, responsibility and long-term trust."
            )
        if "tradition" in text or "craft" in text:
            return (
                "The story highlights craft, continuity and care in every "
                "customer relationship."
            )
        return (
            "The story gives the business a clearer human context and makes "
            "the promise feel more concrete."
        )
    if "famil" in text:
        return (
            "Berättelsen lyfter fram familjeföretagets närhet, ansvar och "
            "långsiktiga relationer."
        )
    if "tradition" in text or "hantverk" in text:
        return (
            "Berättelsen lyfter fram hantverk, kontinuitet och omsorg i "
            "varje kundrelation."
        )
    return (
        "Berättelsen ger företaget en tydligare mänsklig kontext och gör "
        "löftet mer konkret."
    )


def _append_story_sentence(previous_story: str, sentence: str) -> str:
    if sentence in previous_story:
        return previous_story[:1200]
    separator = " " if previous_story.endswith((".", "!", "?")) else ". "
    return f"{previous_story}{separator}{sentence}"[:1200]


def _positioning_for_prompt(
    follow_up_prompt: str,
    *,
    language: str,
) -> str:
    text = _normalise_followup_text(follow_up_prompt)
    if language == "en":
        if "premium" in text:
            return "Positioned as a premium, dependable local choice."
        if "niche" in text:
            return "Positioned around a clearer niche and sharper customer promise."
        return "Positioned with a clearer promise for the intended customer."
    if "premium" in text:
        return "Positioneras som ett premiumval med trygg lokal förankring."
    if "nisch" in text:
        return "Positioneras kring en tydligare nisch och ett skarpare kundlöfte."
    return "Positioneras med ett tydligare löfte till rätt kund."


def _semantic_source_entry(
    *,
    value: Any,
    last_updated_version: int,
    source: str,
) -> dict[str, Any]:
    return {
        "value": copy.deepcopy(value),
        "lastUpdatedVersion": last_updated_version,
        "source": source,
    }


def _apply_semantic_patch(
    merged: dict[str, Any],
    candidate: dict[str, Any],
    *,
    intent: FollowupIntent,
    follow_up_prompt: str,
) -> None:
    """Apply the smallest semantic Project Input patch allowed by intent."""
    if intent in {"no-semantic-change", "clarify"}:
        return

    language = merged.get("language") if isinstance(merged.get("language"), str) else "sv"
    company = merged.setdefault("company", {})
    candidate_company = candidate.get("company") if isinstance(candidate.get("company"), dict) else {}

    if intent == "tagline-update":
        explicit_tagline = _explicit_semantic_copy_from_prompt(
            follow_up_prompt,
            max_length=140,
            reject_ui_directive=True,
        )
        candidate_tagline = _safe_semantic_text(
            candidate_company.get("tagline"),
            follow_up_prompt=follow_up_prompt,
            max_length=140,
            reject_ui_directive=True,
        )
        # The mock brief path cannot infer a new tagline from the follow-up.
        # Prefer a controlled prompt-derived line so V1 changes the Project
        # Input deterministically without leaking the raw instruction.
        fallback_tagline = _fallback_tagline_for_prompt(
            follow_up_prompt,
            language=language,
        )
        prompt_tone_words = _tone_words_from_prompt(
            follow_up_prompt,
            language=language,
        )
        candidate_lower = _normalise_followup_text(candidate_tagline or "")
        if explicit_tagline:
            company["tagline"] = explicit_tagline
        elif candidate_tagline and any(word in candidate_lower for word in prompt_tone_words):
            company["tagline"] = candidate_tagline
        elif candidate_tagline:
            company["tagline"] = fallback_tagline
        else:
            company["tagline"] = fallback_tagline
        return

    if intent == "story-emphasize":
        previous_story = _string_value(company.get("story")) or ""
        explicit_story = _explicit_semantic_copy_from_prompt(
            follow_up_prompt,
            max_length=1200,
        )
        candidate_story = _safe_semantic_text(
            candidate_company.get("story"),
            follow_up_prompt=follow_up_prompt,
            max_length=1200,
        )
        if explicit_story and explicit_story != previous_story:
            company["story"] = explicit_story
        elif candidate_story and candidate_story != previous_story:
            company["story"] = candidate_story
        else:
            company["story"] = _append_story_sentence(
                previous_story,
                _story_sentence_for_prompt(follow_up_prompt, language=language),
            )
        return

    if intent == "tone-shift":
        previous_tone = merged.get("tone") if isinstance(merged.get("tone"), dict) else {}
        candidate_tone = candidate.get("tone") if isinstance(candidate.get("tone"), dict) else {}
        prompt_tones = _tone_words_from_prompt(follow_up_prompt, language=language)
        primary = prompt_tones[0] if prompt_tones else _string_value(candidate_tone.get("primary"))
        if not primary:
            primary = _string_value(previous_tone.get("primary")) or "trustworthy"
        secondary = prompt_tones[1:5]
        if not secondary:
            candidate_secondary = candidate_tone.get("secondary")
            if isinstance(candidate_secondary, list):
                secondary = [
                    item.strip()
                    for item in candidate_secondary
                    if isinstance(item, str) and item.strip()
                ][:4]
        if not secondary and primary == "premium":
            secondary = (
                ["professional", "dependable"]
                if language == "en"
                else ["professionell", "förtroendeingivande"]
            )
        avoid = _avoid_words_from_prompt(follow_up_prompt, language=language)
        if not avoid:
            candidate_avoid = candidate_tone.get("avoid")
            if isinstance(candidate_avoid, list):
                avoid = [
                    item.strip()
                    for item in candidate_avoid
                    if isinstance(item, str) and item.strip()
                ][:4]
        merged["tone"] = {
            "primary": primary[:80],
            "secondary": secondary[:4],
            "avoid": avoid[:4],
        }
        return

    if intent == "positioning-shift":
        # Project Input has no positioning field in V1. The meta-sidecar
        # snapshot records this intent; runtime projection is V2 scope.
        return


def _field_entry_from_previous(
    previous_entry: Any,
    *,
    fallback_value: Any,
    fallback_version: int,
    fallback_source: str,
) -> dict[str, Any]:
    if isinstance(previous_entry, dict) and {
        "value",
        "lastUpdatedVersion",
        "source",
    } <= set(previous_entry):
        return copy.deepcopy(previous_entry)
    return _semantic_source_entry(
        value=fallback_value,
        last_updated_version=fallback_version,
        source=fallback_source,
    )


def _build_project_dna_snapshot(
    project_input: dict[str, Any],
    *,
    previous_project_input: dict[str, Any] | None,
    previous_project_dna: dict[str, Any] | None,
    version: int,
    mode: str,
    follow_up_prompt: str | None,
) -> dict[str, Any]:
    """Build the V1 Project DNA snapshot stored in the meta sidecar."""
    language = project_input.get("language") if isinstance(project_input.get("language"), str) else "sv"
    intent: FollowupIntent = "no-semantic-change"
    if mode == "followup":
        intent = classify_followup_intent(follow_up_prompt or "", language=language)
        if intent in {"no-semantic-change", "clarify"} and isinstance(previous_project_dna, dict):
            snapshot = copy.deepcopy(previous_project_dna)
            snapshot["followUpIntent"] = {
                "id": intent,
                "confidence": "medium",
                "rationale": "No semantic Project DNA field changed in this follow-up.",
            }
            return snapshot

    company = project_input.get("company") if isinstance(project_input.get("company"), dict) else {}
    previous_company = (
        previous_project_input.get("company")
        if isinstance(previous_project_input, dict)
        and isinstance(previous_project_input.get("company"), dict)
        else {}
    )
    tone = project_input.get("tone") if isinstance(project_input.get("tone"), dict) else {}
    previous_tone = (
        previous_project_input.get("tone")
        if isinstance(previous_project_input, dict)
        and isinstance(previous_project_input.get("tone"), dict)
        else {}
    )
    previous_dna = previous_project_dna if isinstance(previous_project_dna, dict) else {}
    previous_dna_tone = (
        previous_dna.get("tone")
        if isinstance(previous_dna.get("tone"), dict)
        else {}
    )
    created_at_version = previous_dna.get("createdAtVersion")
    if not isinstance(created_at_version, int):
        created_at_version = 1 if mode == "init" else version

    def field(
        key: str,
        *,
        current_value: Any,
        previous_value: Any,
        previous_entry: Any,
        affected_intents: set[FollowupIntent],
    ) -> dict[str, Any]:
        entry = _field_entry_from_previous(
            previous_entry,
            fallback_value=previous_value if previous_value is not None else current_value,
            fallback_version=created_at_version,
            fallback_source="brief",
        )
        if mode == "followup" and intent in affected_intents and current_value != previous_value:
            return _semantic_source_entry(
                value=current_value,
                last_updated_version=version,
                source="followup",
            )
        if key not in previous_dna:
            entry["value"] = copy.deepcopy(current_value)
        return entry

    snapshot = {
        "schemaVersion": 1,
        "createdAtVersion": created_at_version,
        "story": field(
            "story",
            current_value=company.get("story"),
            previous_value=previous_company.get("story"),
            previous_entry=previous_dna.get("story"),
            affected_intents={"story-emphasize"},
        ),
        "tagline": field(
            "tagline",
            current_value=company.get("tagline"),
            previous_value=previous_company.get("tagline"),
            previous_entry=previous_dna.get("tagline"),
            affected_intents={"tagline-update"},
        ),
        "tone": {
            "primary": field(
                "primary",
                current_value=tone.get("primary"),
                previous_value=previous_tone.get("primary"),
                previous_entry=previous_dna_tone.get("primary"),
                affected_intents={"tone-shift"},
            ),
            "secondary": field(
                "secondary",
                current_value=tone.get("secondary", []),
                previous_value=previous_tone.get("secondary", []),
                previous_entry=previous_dna_tone.get("secondary"),
                affected_intents={"tone-shift"},
            ),
            "avoid": field(
                "avoid",
                current_value=tone.get("avoid", []),
                previous_value=previous_tone.get("avoid", []),
                previous_entry=previous_dna_tone.get("avoid"),
                affected_intents={"tone-shift"},
            ),
        },
        "positioning": previous_dna.get("positioning")
        if "positioning" in previous_dna
        else None,
        "followUpIntent": {
            "id": intent,
            "confidence": "medium" if mode == "followup" else "high",
            "rationale": (
                "Deterministic keyword match in follow-up prompt."
                if mode == "followup"
                else "Initial Project DNA snapshot."
            ),
        },
    }

    if mode == "followup" and intent == "positioning-shift":
        snapshot["positioning"] = _semantic_source_entry(
            value=_positioning_for_prompt(follow_up_prompt or "", language=language),
            last_updated_version=version,
            source="followup",
        )

    return snapshot


def merge_followup_project_input(
    previous: dict[str, Any],
    candidate: dict[str, Any],
    *,
    follow_up_prompt: str,
) -> dict[str, Any]:
    """Preserve prior site context while applying a follow-up prompt.

    Follow-up mode is a new version of the same prompt-generated site
    track, not a fresh init. The generated candidate contributes
    additive signals (new services, capabilities and conversion goals).
    Story, tagline and tone remain byte-stable for unclear/additive
    prompts, but Project DNA semantic patching may update exactly the
    field targeted by a known follow-up intent.
    """
    merged = copy.deepcopy(previous)
    merged["siteId"] = previous["siteId"]
    merged["scaffoldId"] = previous["scaffoldId"]
    merged["variantId"] = previous["variantId"]
    merged["language"] = previous["language"]
    merged["location"] = copy.deepcopy(previous.get("location", {}))
    merged["contact"] = copy.deepcopy(previous.get("contact", {}))
    merged["selectedDossiers"] = copy.deepcopy(
        previous.get("selectedDossiers", {})
    )

    company = copy.deepcopy(previous.get("company", {}))
    candidate_company = candidate.get("company", {})
    if not company.get("businessType") and isinstance(candidate_company, dict):
        company["businessType"] = candidate_company.get("businessType")
    if not company.get("tagline") and isinstance(candidate_company, dict):
        company["tagline"] = candidate_company.get("tagline")

    # B60 fynd 2: never inject the follow-up prompt into `company.story`.
    # That field is rendered as customer-facing copy on /om-oss
    # (`render_about` in build_site.py); pre-B60 the merge appended an
    # English `Follow-up request: ...`-suffix, which leaked internal
    # workflow context onto the public site. The follow-up prompt is
    # already preserved via `meta.followUpPrompt`, so the renderer-side
    # copy stays clean and Viewser can still surface the operator's
    # latest prompt from the sidecar.
    merged["company"] = company

    merged["services"] = _merge_services(
        list(previous.get("services") or []),
        list(candidate.get("services") or []),
    )
    merged["conversionGoals"] = _unique_strings(
        list(previous.get("conversionGoals") or []),
        list(candidate.get("conversionGoals") or []),
    )
    merged["requestedCapabilities"] = _unique_strings(
        list(previous.get("requestedCapabilities") or []),
        list(candidate.get("requestedCapabilities") or []),
    )
    if "tone" not in merged or not isinstance(merged["tone"], dict):
        merged["tone"] = copy.deepcopy(candidate.get("tone", {}))
    if "trustSignals" not in merged:
        merged["trustSignals"] = copy.deepcopy(candidate.get("trustSignals", []))
    intent = classify_followup_intent(
        follow_up_prompt,
        language=merged.get("language", "sv"),
    )
    _apply_semantic_patch(
        merged,
        candidate,
        intent=intent,
        follow_up_prompt=follow_up_prompt,
    )
    return merged


def _apply_discovery_overrides(
    project_input: dict[str, Any],
    discovery: dict[str, Any],
) -> dict[str, Any]:
    """Bakåtkompatibel tunn wrapper runt Discovery Resolver.

    B121: konkret discovery-konfliktlösning bor nu i
    ``packages/generation/discovery/resolve.py``. Hela tidigare fältmapping
    (company/contact/services/brand/assets/scaffold/location +
    must-have/CTA-kapaciteter) bor i resolvern med spårning via
    ``DiscoveryDecision.fieldSources`` och ``fallbackWarnings``.

    Denna wrapper bevaras för callers som bara behöver det resolverat
    Project Input dict-result (t.ex. ``tests/test_operator_uploads.py``).
    Den nya canonical entry point:en är ``resolve_discovery`` i
    ``packages.generation.discovery``, som även returnerar
    ``DiscoveryDecision`` så Backoffice/meta-sidecar får full provenance.
    """
    return apply_discovery_overrides(project_input, discovery)


def _load_discovery_file(path: Path) -> dict[str, Any]:
    """Läs en discovery-payload-JSON från disk och validera shape."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"--discovery filen saknas: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--discovery filen är inte giltig JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("--discovery filen måste vara ett JSON-objekt.")
    schema_version = payload.get("schemaVersion")
    if schema_version not in (1, 2):
        raise SystemExit("--discovery payload måste ha schemaVersion 1 eller 2.")
    if schema_version == 2:
        directives = payload.get("directives")
        if not isinstance(directives, dict):
            raise SystemExit("--discovery schemaVersion=2 kräver directives.")
        language = directives.get("language")
        if not isinstance(language, str) or not language.strip():
            raise SystemExit(
                "--discovery schemaVersion=2 kräver directives.language."
            )
    return payload


def _mock_brief_artifact_after_failure(
    prompt: str,
    *,
    language: str,
    model: str,
    error: Exception,
) -> dict[str, Any]:
    """Return a schema-shaped mock Site Brief when brief extraction fails.

    ``extract_site_brief`` already catches the expected OpenAI failure
    path, but this helper covers bugs or unexpected exceptions in either
    ``extract_site_brief`` itself or ``site_brief_to_artifact``. The
    prompt-driven flow should degrade to a schema-valid placeholder
    Project Input, not crash the whole Viewser request.
    """
    message = f"{type(error).__name__}: {error}"
    return {
        "runId": "prompt-helper",
        "language": language,
        "rawPrompt": prompt,
        "businessTypeGuess": None,
        "pageCount": None,
        "tone": [],
        "targetAudience": [],
        "requestedCapabilities": [],
        "locationHint": None,
        "conversionGoals": [],
        "servicesMentioned": [],
        "contentDepth": None,
        "notesForPlanner": f"Mock brief after prompt helper failure: {message}",
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "briefSource": "mock-llm-error",
        "briefError": message,
        "attemptedModel": model,
        "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def _clean_wizard_must_have(raw_must_have: Any) -> list[str]:
    """Return ordered, non-empty wizard page labels from untrusted input."""
    if not isinstance(raw_must_have, list):
        return []
    labels: list[str] = []
    seen: set[str] = set()
    for item in raw_must_have:
        if not isinstance(item, str):
            continue
        label = item.strip()
        if not label or label in seen:
            continue
        labels.append(label)
        seen.add(label)
    return labels


def _wizard_must_have_from_discovery(
    discovery: dict[str, Any] | None,
) -> list[str]:
    """Extract wizard page labels for downstream page-intent warnings."""
    if not isinstance(discovery, dict):
        return []
    answers = discovery.get("answers")
    if not isinstance(answers, dict):
        return []
    return _clean_wizard_must_have(answers.get("mustHave"))


def generate(
    prompt: str,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    site_id: str | None = None,
    project_id: str | None = None,
    version: int = 1,
    mode: str = "init",
    base_project_input: dict[str, Any] | None = None,
    previous_project_dna: dict[str, Any] | None = None,
    meta_overrides: dict[str, Any] | None = None,
    discovery: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    """End-to-end: prompt -> Site Brief -> Project Input on disk.

    Returns (project_input, meta, project_input_path, meta_path). Used
    by both the CLI main() and the unit tests so the test path doesn't
    have to assemble argv-shaped input.
    """
    language = detect_language(prompt)
    try:
        model = resolve_brief_model()
    except Exception as exc:  # noqa: BLE001
        # Mirror dev_generate.py's tolerance: a misconfigured llm-models
        # policy must not block the prompt-driven loop entirely.
        model = "gpt-5.4"
        print(
            "briefModel resolution failed; using fallback model "
            f"{model}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

    try:
        brief_result = extract_site_brief(
            prompt, model=model, language_hint=language
        )
        brief_artifact = site_brief_to_artifact(
            brief_result,
            run_id="prompt-helper",
            model=model,
        )
    except Exception as exc:  # noqa: BLE001
        brief_artifact = _mock_brief_artifact_after_failure(
            prompt,
            language=language,
            model=model,
            error=exc,
        )

    has_explicit_site_id = site_id is not None
    candidate_site_id = site_id or "site"
    if not _SITE_ID_PATTERN.match(candidate_site_id):
        raise SystemExit(
            f"Generated siteId {candidate_site_id!r} does not match the "
            "lower-case alphanumeric/dash pattern required by "
            "apps/viewser/lib/project-inputs.ts and build_site.py."
        )

    scaffold_id, variant_id = pick_scaffold(
        prompt, brief_artifact.get("businessTypeGuess")
    )
    # B136 (2026-05-19, post-PR-#45 follow-up review): tuple-unpacking bevarad
    # för site_brief_to_project_input-kontraktet, men candidate-listan
    # konsumeras inte längre vid resolve-tid. Pre-resolve placeholder_fields
    # beräknas i stället mot post-merge project_input.contact (se nedan) så
    # follow-up-flödet inte felaktigt markerar v1-bevarade kontaktvärden som
    # "default" när merge_followup_project_input behåller dem byte-stabilt.
    candidate_project_input, _candidate_placeholder_contact_fields = (
        site_brief_to_project_input(
            brief_artifact,
            site_id=candidate_site_id,
            scaffold_id=scaffold_id,
            variant_id=variant_id,
            original_prompt=prompt,
        )
    )
    if base_project_input is not None:
        project_input = merge_followup_project_input(
            base_project_input,
            candidate_project_input,
            follow_up_prompt=prompt,
        )
    else:
        project_input = candidate_project_input

    # Discovery Resolver (B121): konsoliderar wizard/scrape/brief/taxonomy
    # till ett deterministiskt Project Input + ``DiscoveryDecision``-sidecar
    # med ``fieldSources`` och ``fallbackWarnings``. Decision-payloaden
    # skrivs som extra fält ``discoveryDecision`` på meta-sidecaren — ingen
    # ny Engine Run-artefakt eftersom run-kontraktet är åtta filer.
    # B136 (2026-05-19, post-PR-#45 follow-up review): placeholder_fields
    # måste beräknas mot post-merge ``project_input.contact``, inte mot
    # candidate brief-kandidaten. Annars markerar Discovery Resolverns
    # ``_apply_contact_fields`` v1-bevarade real contact-värden som
    # ``"default"`` i ``fieldSources`` när follow-up-läget kör — eftersom
    # ``merge_followup_project_input`` håller previous contact byte-stabilt,
    # så candidate-listan från brief-kandidaten flaggar phone/email/openingHours
    # som placeholder trots att den slutliga contact:en är riktig från v1.
    # Recomputen använder samma ``_recompute_placeholder_contact_fields``-helper
    # som B133-flödet kör post-resolve för meta-sidecaren, och föredrar
    # ``project_input["language"]`` (bevaras av ``merge_followup``) framför
    # den prompt-detekterade när språket bytt mellan versioner.
    pre_resolve_language = (
        project_input.get("language")
        if isinstance(project_input, dict)
        and isinstance(project_input.get("language"), str)
        else language
    )
    pre_resolve_placeholder_fields = _recompute_placeholder_contact_fields(
        project_input.get("contact") if isinstance(project_input, dict) else None,
        pre_resolve_language,
    )

    discovery_decision: DiscoveryDecision | None = None
    if discovery is not None:
        project_input, discovery_decision = resolve_discovery(
            raw_prompt=prompt,
            payload=discovery,
            project_input_candidate=project_input,
            placeholder_fields=pre_resolve_placeholder_fields,
        )
    wizard_must_have = _wizard_must_have_from_discovery(discovery)

    if has_explicit_site_id:
        final_site_id = candidate_site_id
    else:
        company = project_input.get("company")
        company_name = (
            company.get("name") if isinstance(company, dict) else None
        )
        final_site_id = slugify_site_id(prompt, company_name=company_name)
    project_input["siteId"] = final_site_id

    if not _SITE_ID_PATTERN.match(final_site_id):
        raise SystemExit(
            f"Generated siteId {final_site_id!r} does not match the "
            "lower-case alphanumeric/dash pattern required by "
            "apps/viewser/lib/project-inputs.ts and build_site.py."
        )

    # B133 (2026-05-19): efter alla wizard/scrape/follow-up-merger kan
    # vissa contact-fält fortfarande vara B88-fallback. Recompute mot
    # final project_input så listan reflekterar vad operatören faktiskt
    # publicerar, inte initial briefModel-state. Tom lista = ingen
    # placeholder kvar → ingen warning skrivs i build-result.json.
    #
    # B133 follow-up-fix (Codex P2 review 2026-05-19): använd final
    # ``project_input["language"]`` istället för den prompt-detekterade
    # ``language``. ``merge_followup_project_input`` bevarar previous
    # ``language`` + ``contact`` byte-stabilt, så en svensk v1 + engelsk
    # följdprompt skulle annars jämföra svenska placeholder-strängar mot
    # engelska defaults → false negative → varning tappad trots att
    # ``kontakt@example.se`` / ``Adress lämnas på förfrågan`` ligger kvar.
    final_language = (
        project_input.get("language")
        if isinstance(project_input, dict)
        and isinstance(project_input.get("language"), str)
        else language
    )
    placeholder_contact_fields = _recompute_placeholder_contact_fields(
        project_input.get("contact") if isinstance(project_input, dict) else None,
        final_language,
    )

    _validate_against_schema(project_input)

    now = datetime.now(UTC).isoformat(timespec="seconds")
    meta = {
        "projectId": project_id or uuid.uuid4().hex,
        "version": version,
        "mode": mode,
        "siteId": final_site_id,
        "originalPrompt": prompt,
        "scaffoldId": project_input["scaffoldId"],
        "variantId": project_input["variantId"],
        "briefSource": brief_artifact.get("briefSource"),
        "briefError": brief_artifact.get("briefError"),
        "modelUsed": brief_artifact.get("modelUsed"),
        "createdAt": now,
    }
    meta["projectDna"] = _build_project_dna_snapshot(
        project_input,
        previous_project_input=base_project_input,
        previous_project_dna=previous_project_dna,
        version=version,
        mode=mode,
        follow_up_prompt=prompt if mode == "followup" else None,
    )
    if discovery_decision is not None:
        meta["discoveryDecision"] = discovery_decision.to_dict()
    # B133: surfaces only when there is actually a placeholder field —
    # keeps meta + downstream build-result.json clean for runs where
    # operator/scrape filled every contact field.
    if placeholder_contact_fields:
        meta["placeholderContactFields"] = list(placeholder_contact_fields)
    # B132 (Scout-orchestrator merge 2026-05-19): wizardMustHave från
    # _wizard_must_have_from_discovery() flödar genom meta-sidecaren och
    # konsumeras av _prompt_meta_wizard_must_have() i build_site.py för
    # pageIntentWarnings-emit. Ortogonal mot B133.
    if wizard_must_have:
        meta["wizardMustHave"] = wizard_must_have
    if meta_overrides:
        safe_meta_overrides = dict(meta_overrides)
        if discovery is not None:
            safe_meta_overrides.pop("wizardMustHave", None)
        if discovery_decision is not None:
            safe_meta_overrides.pop("discoveryDecision", None)
        meta.update(safe_meta_overrides)

    project_input_path, meta_path = write_project_input(
        project_input, meta, output_dir=output_dir
    )
    return project_input, meta, project_input_path, meta_path


def generate_followup(
    prompt: str,
    *,
    site_id: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    discovery: dict[str, Any] | None = None,
    reset_wizard_must_have: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    """Generate a new Project Input version from an existing meta sidecar.

    Followup-flödet ärver ``discoveryDecision`` från föregående version
    (R2 P2 på PR #34): wizard-init-runs får inte ny discovery-payload, så
    om resolvern inte också persisterar decisionen vidare till v2 förlorar
    Backoffice/Doctor synlighet för categoryIds, fieldSources och
    fallbackWarnings i den aktuella versionen.
    """
    language = detect_language(prompt)
    if classify_followup_intent(prompt, language=language) == "clarify":
        raise SystemExit(
            "Follow-up prompt is too unclear to create a new version. "
            "Please clarify what should change."
        )
    existing_meta = read_existing_meta(site_id, output_dir=output_dir)
    previous_project_input = read_existing_project_input(
        site_id, output_dir=output_dir
    )
    previous_version = existing_meta["version"]
    now = datetime.now(UTC).isoformat(timespec="seconds")
    meta_overrides: dict[str, Any] = {
        "originalPrompt": existing_meta.get("originalPrompt", prompt),
        "followUpPrompt": prompt,
        "previousVersion": previous_version,
        "createdAt": existing_meta.get("createdAt", now),
        "updatedAt": now,
    }
    # Ärv discoveryDecision från föregående version så Backoffice/Doctor
    # kan visa categoryIds + fieldSources + fallbackWarnings även för v2+.
    # R1 #5 på PR #34 (round 3): markera ärvda decisioner med
    # ``inheritedFromVersion`` så Backoffice kan skilja på initial
    # discovery decision och aktuell provenance för v2+-fält.
    inherited_decision = existing_meta.get("discoveryDecision")
    if discovery is None and isinstance(inherited_decision, dict):
        inherited_copy = copy.deepcopy(inherited_decision)
        # Bevara den ursprungliga inheritedFromVersion om den redan finns
        # (kedja av v1 -> v2 -> v3 ska peka till första versionen som
        # producerade decisionen, inte föregående version).
        if "inheritedFromVersion" not in inherited_copy:
            inherited_copy["inheritedFromVersion"] = previous_version
        meta_overrides["discoveryDecision"] = inherited_copy
    if discovery is None and not reset_wizard_must_have:
        wizard_must_have = _clean_wizard_must_have(
            existing_meta.get("wizardMustHave")
        )
        if wizard_must_have:
            meta_overrides["wizardMustHave"] = wizard_must_have
    return generate(
        prompt,
        output_dir=output_dir,
        site_id=site_id,
        project_id=existing_meta["projectId"],
        version=previous_version + 1,
        mode="followup",
        base_project_input=previous_project_input,
        previous_project_dna=existing_meta.get("projectDna")
        if isinstance(existing_meta.get("projectDna"), dict)
        else None,
        meta_overrides=meta_overrides,
        discovery=discovery,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a minimal Project Input from a free-form prompt."
    )
    parser.add_argument("prompt", help="The operator prompt to convert.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=(
            "Where to write <siteId>.project-input.json + <siteId>.meta.json. "
            f"Default: {DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)}"
        ),
    )
    parser.add_argument(
        "--site-id",
        default=None,
        help=(
            "Override the auto-generated siteId. Must match "
            "[a-z0-9](?:[a-z0-9-]*[a-z0-9])? - same pattern that "
            "apps/viewser/lib/project-inputs.ts enforces."
        ),
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help=(
            "Reuse an existing projectId for follow-up flows. Defaults "
            "to a fresh uuid hex when omitted."
        ),
    )
    parser.add_argument(
        "--followup-site-id",
        default=None,
        help=(
            "Read data/prompt-inputs/<siteId>.meta.json, reuse its projectId "
            "and increment version for a follow-up prompt."
        ),
    )
    parser.add_argument(
        "--discovery",
        default=None,
        help=(
            "Path to a discovery-payload JSON file written by the wizard. "
            "Deterministic wizard answers patch the Project Input after "
            "LLM extraction so operator clicks always win over LLM guesses."
        ),
    )
    args = parser.parse_args()

    if args.followup_site_id and args.discovery:
        raise SystemExit(
            "--discovery cannot be combined with --followup-site-id. "
            "Discovery payloads only apply to initial Project Input "
            "generation; follow-up runs inherit discovery state from "
            "the previous version."
        )

    discovery_payload: dict[str, Any] | None = None
    if args.discovery:
        discovery_payload = _load_discovery_file(Path(args.discovery))

    try:
        from packages.generation.maintenance import auto_prune_all

        auto_prune_all()
    except Exception as exc:  # noqa: BLE001
        print(f"auto-prune: skipped due to error: {exc}", file=sys.stderr)

    output_dir = Path(args.output_dir).resolve()
    if args.followup_site_id:
        if args.site_id or args.project_id:
            raise SystemExit(
                "--followup-site-id cannot be combined with --site-id "
                "or --project-id."
            )
        project_input, meta, project_input_path, meta_path = generate_followup(
            args.prompt,
            output_dir=output_dir,
            site_id=args.followup_site_id,
        )
    else:
        project_input, meta, project_input_path, meta_path = generate(
            args.prompt,
            output_dir=output_dir,
            site_id=args.site_id,
            project_id=args.project_id,
            discovery=discovery_payload,
        )

    # Output contract: emit the same key/value shape that build_site.py
    # uses for runId so apps/viewser/lib/build-runner.ts can parse it
    # with the same regex pattern.
    print(f"siteId: {project_input['siteId']}")
    print(f"projectId: {meta['projectId']}")
    print(f"dossierPath: {project_input_path}")
    print(f"metaPath: {meta_path}")
    print(f"version: {meta['version']}")
    print(f"briefSource: {meta['briefSource']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
