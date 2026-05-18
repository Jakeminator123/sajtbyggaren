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

- Prints ``siteId: <id>`` and ``dossierPath: <abs-path>`` on stdout, one
  per line. Mirrors the ``runId: <id>`` contract that build_site.py uses
  so the same regex-based parser pattern works in build-runner.ts.
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
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.brief import (  # noqa: E402
    detect_language,
    extract_site_brief,
    site_brief_to_artifact,
)
from packages.generation.brief.models import resolve_brief_model  # noqa: E402

DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "prompt-inputs"
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"

# Mirrors apps/viewser/lib/project-inputs.ts SITE_ID_PATTERN. Lower-case
# letters, digits and dashes, must start and end with alphanumeric.
# Centralising the pattern in two languages is a known duplication; a
# future sprint can hoist it into a shared policy if more tools need it.
_SITE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")
_SLUG_DASHES = re.compile(r"-{2,}")

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
    }
)

_SCAFFOLD_LOCAL_SERVICE = ("local-service-business", "nordic-trust")
_SCAFFOLD_ECOMMERCE = ("ecommerce-lite", "clean-store")

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


def slugify_site_id(text: str, *, suffix: str | None = None) -> str:
    """Produce a siteId that satisfies _SITE_ID_PATTERN.

    The first 24 chars come from the prompt (or a fallback "site" when
    the prompt has no usable letters). A short uuid suffix is always
    appended so two prompts that slugify to the same stem do not collide
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
    folded = _ascii_fold((text or "").strip()).lower()
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
    """Return planner note text only when it is safe public copy."""
    cleaned = " ".join((note or "").split())
    if not cleaned:
        return None
    lower = cleaned.lower()
    if any(token in lower for token in _PLANNER_NOTE_BLOCKLIST):
        return None
    if not cleaned.endswith((".", "!", "?")):
        cleaned = f"{cleaned}."
    return cleaned


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


def _placeholder_contact(
    language: str,
    *,
    contact_phone: str | None = None,
    contact_email: str | None = None,
    contact_address: str | None = None,
) -> dict[str, Any]:
    """Schema-required contact block when the brief has no real values.

    Demo-baseline-fix 1C (B88): the previous placeholders for `address`
    were operator-facing dev jargon ("Adress saknas - uppdatera Project
    Input"), which leaked verbatim into the public ``<address>`` tag on
    every generated /kontakt page in the re-Scout 2026-05-15 run.
    Schema constraint ``addressLines minItems=1 + items minLength=1``
    forbids an empty value, so the fallback is now a brand-neutral
    Swedish/English phrase that reads acceptably to a real visitor.
    The operator can still override it in the generated Project Input
    before sharing the build.
    """
    phone = (contact_phone or "").strip()
    email = (contact_email or "").strip()
    address = (contact_address or "").strip()
    if language == "en":
        return {
            "phone": phone or "+46 8 000 00 00",
            "email": email or "contact@example.se",
            "addressLines": [address or "Address available on request"],
            "openingHours": "Mon-Fri 09:00-17:00",
        }
    return {
        "phone": phone or "+46 8 000 00 00",
        "email": email or "kontakt@example.se",
        "addressLines": [address or "Adress lämnas på förfrågan"],
        "openingHours": "Mån-Fre 09:00-17:00",
    }


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
) -> dict[str, Any]:
    """Deterministic Site Brief -> Project Input mapping.

    Operates on the canonical Site Brief artefakt shape (the dict that
    site_brief_to_artifact returns) so this helper works regardless of
    whether briefModel ran as 'real', 'mock-no-key' or 'mock-llm-error'.
    Missing fields fall back to schema-valid placeholders that the
    operator can edit in the generated Project Input file before
    re-building.
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
        "contact": _placeholder_contact(
            language,
            contact_phone=brief.get("contactPhone"),
            contact_email=brief.get("contactEmail"),
            contact_address=brief.get("contactAddress"),
        ),
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
    return project_input


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


def merge_followup_project_input(
    previous: dict[str, Any],
    candidate: dict[str, Any],
    *,
    follow_up_prompt: str,
) -> dict[str, Any]:
    """Preserve prior site context while applying a follow-up prompt.

    This is deliberately conservative: follow-up mode is a new version
    of the same prompt-generated site track, not a fresh init. The
    generated candidate contributes additive signals (new services,
    capabilities and conversion goals) while the identity, scaffold,
    variant, language, location, contact data, story, tagline, tone and
    existing content survive byte-stably unless a later Project DNA
    sprint introduces semantic patching.
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
    _ = follow_up_prompt  # kept on the API for future semantic-patch hooks

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
    return merged


def _apply_discovery_overrides(
    project_input: dict[str, Any],
    discovery: dict[str, Any],
) -> dict[str, Any]:
    """Patcha Project Input med deterministiska discovery-fält.

    Wizardens fält vinner alltid över LLM-extraktion när de är ifyllda —
    operatorn har klickat och skrivit, så vi ska inte överskugga det med
    en LLM-gissning. Fält som wizarden lämnat tomma fortsätter använda
    LLM/site-brief-värdet, så avoid/imagery/goal/tone behåller sin
    befintliga heuristik.
    """
    if not isinstance(discovery, dict):
        return project_input
    answers = discovery.get("answers")
    if not isinstance(answers, dict):
        return project_input

    company = project_input.setdefault("company", {})
    name = answers.get("companyName")
    if isinstance(name, str) and name.strip():
        company["name"] = name.strip()
    offer = answers.get("offer")
    if isinstance(offer, str) and offer.strip():
        # `tagline` har maxLength 140 i schemat; använd första meningen
        # som tagline och hela texten som story om story inte är
        # explicit ifylld i wizarden.
        first_sentence = offer.strip().split(". ")[0][:140]
        company["tagline"] = first_sentence
    about_text = answers.get("aboutText")
    if isinstance(about_text, str) and about_text.strip():
        company["story"] = about_text.strip()[:1200]

    # Kontakt — wizarden har individuella fält som mappar direkt mot
    # schemat (phone / email / addressLines / openingHours). Den lokala
    # `_raw`-variabeln existerar för att Pyright/basedpyright ska kunna
    # narrowa typen: isinstance-checken på ett upprepat `answers.get(...)`
    # på samma rad narrowar inte (Pyright kan inte garantera att andra
    # anropet ger samma värde), men checken på en lokal variabel gör det.
    _contact_raw = answers.get("contact")
    answer_contact: dict[str, Any] = (
        _contact_raw if isinstance(_contact_raw, dict) else {}
    )
    contact = project_input.setdefault("contact", {})
    phone = answer_contact.get("phone")
    if isinstance(phone, str) and phone.strip():
        contact["phone"] = phone.strip()
    email = answer_contact.get("email")
    if isinstance(email, str) and email.strip():
        contact["email"] = email.strip()
    opening_hours = answer_contact.get("openingHours")
    if isinstance(opening_hours, str) and opening_hours.strip():
        contact["openingHours"] = opening_hours.strip()
    addr = answer_contact.get("address")
    if isinstance(addr, str) and addr.strip():
        contact["addressLines"] = [addr.strip()]

    # Services — wizardens ServiceItem-shape mappar mot Project Inputs
    # services-array. Bevara LLM-genererade tjänster om wizarden lämnat
    # listan tom, annars övertar wizardens listan.
    service_items = answers.get("services")
    if isinstance(service_items, list) and service_items:
        mapped_services: list[dict[str, str]] = []
        for idx, item in enumerate(service_items):
            if not isinstance(item, dict):
                continue
            label = item.get("name")
            if not isinstance(label, str) or not label.strip():
                continue
            description_raw = item.get("description")
            summary = description_raw if isinstance(description_raw, str) else ""
            slug = _slugify_label(label) or f"service-{idx + 1}"
            mapped_services.append(
                {
                    "id": slug,
                    "label": label.strip(),
                    "summary": summary.strip() or _service_summary(label.strip(), project_input.get("language", "sv")),
                }
            )
        if mapped_services:
            project_input["services"] = mapped_services[:8]

    # MustHave / pages — speglas tillbaka som requestedCapabilities-hints.
    must_have = answers.get("mustHave")
    if isinstance(must_have, list) and must_have:
        extra_capabilities: list[str] = []
        page_to_capability = {
            "Kontaktformulär": "contact-form",
            "Bokning online": "booking",
            "Bildgalleri": "gallery",
            "Blogg / Nyheter": "blog",
            "Kundrecensioner": "testimonials",
            "FAQ": "faq",
            "Portfolio / Case": "portfolio",
            "Vårt team": "team",
            "Karta / Hitta hit": "map",
            "Nyhetsbrev": "newsletter",
            "Webshop / Produkter": "ecommerce",
            "Meny / Matsedel": "menu",
        }
        for page in must_have:
            cap = page_to_capability.get(str(page))
            if cap:
                extra_capabilities.append(cap)
        if extra_capabilities:
            current = project_input.get("requestedCapabilities") or []
            project_input["requestedCapabilities"] = _unique_strings(current, extra_capabilities)

    # Primary CTA → conversionGoals enum-hint.
    cta = answers.get("primaryCta")
    if isinstance(cta, str) and cta.strip():
        cta_map = {
            "Boka tid": "booking",
            "Kontakta oss": "contact",
            "Köp nu": "purchase",
            "Begär offert": "lead",
            "Registrera dig": "signup",
            "Ring oss": "call",
            "Ladda ner": "download",
        }
        goal = cta_map.get(cta.strip())
        if goal:
            current_goals = project_input.get("conversionGoals") or []
            project_input["conversionGoals"] = _unique_strings(current_goals, [goal])

    # Brand — tone array går in i project_input.tone.primary / secondary.
    _brand_raw = answers.get("brand")
    brand: dict[str, Any] = _brand_raw if isinstance(_brand_raw, dict) else {}
    tone_tags = brand.get("toneTags")
    if isinstance(tone_tags, list) and tone_tags:
        clean_tones = [t for t in tone_tags if isinstance(t, str) and t.strip()]
        if clean_tones:
            tone_block = project_input.setdefault("tone", {})
            tone_block["primary"] = clean_tones[0]
            tone_block["secondary"] = clean_tones[1:5]
    avoid_words = brand.get("wordsToAvoid")
    if isinstance(avoid_words, str) and avoid_words.strip():
        tone_block = project_input.setdefault("tone", {})
        # Komma/semikolon-separerad fri text → enkel splitt.
        tokens = [t.strip() for t in re.split(r"[;,\n]", avoid_words) if t.strip()]
        if tokens:
            tone_block["avoid"] = tokens[:10]

    # Brand-färger från wizardens brand-step.
    primary_color = brand.get("primaryColorHex")
    accent_color = brand.get("accentColorHex")
    if (
        isinstance(primary_color, str) and primary_color.strip()
    ) or (isinstance(accent_color, str) and accent_color.strip()):
        brand_block = project_input.setdefault("brand", {})
        if isinstance(primary_color, str) and primary_color.strip():
            brand_block["primaryColorHex"] = primary_color.strip()
        if isinstance(accent_color, str) and accent_color.strip():
            brand_block["accentColorHex"] = accent_color.strip()

    # Operatör-uppladdade assets (logo, hero, gallery). Lägg in i
    # project_input.brand och project_input.gallery — schemat
    # (`governance/schemas/project-input.schema.json` $defs/assetRef)
    # validerar att varje AssetRef har assetId/filename/mimeType/sizeBytes/role.
    _assets_raw = answers.get("assets")
    assets: dict[str, Any] = _assets_raw if isinstance(_assets_raw, dict) else {}

    def _sanitize_asset_ref(ref: dict, default_role: str) -> dict | None:
        """Bevara fält schemat godkänner; ignorera okända/null-fält så
        ``additionalProperties: false`` inte stoppar build:en.
        """
        if not isinstance(ref, dict):
            return None
        required = {"assetId", "filename", "mimeType", "sizeBytes"}
        if not required.issubset(ref.keys()):
            return None
        clean: dict[str, Any] = {
            "assetId": str(ref["assetId"]),
            "filename": str(ref["filename"]),
            "mimeType": str(ref["mimeType"]),
            "sizeBytes": int(ref["sizeBytes"]),
            "role": str(ref.get("role") or default_role),
        }
        if ref.get("width") is not None:
            clean["width"] = int(ref["width"])
        if ref.get("height") is not None:
            clean["height"] = int(ref["height"])
        alt = ref.get("alt")
        if isinstance(alt, str) and alt.strip():
            clean["alt"] = alt.strip()
        placement = ref.get("placement")
        if isinstance(placement, str) and placement.strip():
            clean["placement"] = placement.strip()
        subject = ref.get("visionSubject")
        if isinstance(subject, str) and subject.strip():
            clean["visionSubject"] = subject.strip()
        confidence = ref.get("visionConfidence")
        if isinstance(confidence, str) and confidence in {"low", "medium", "high"}:
            clean["visionConfidence"] = confidence
        return clean

    logo_ref = _sanitize_asset_ref(assets.get("logo") or {}, "logo")
    if logo_ref:
        brand_block = project_input.setdefault("brand", {})
        brand_block["logo"] = logo_ref

    hero_ref = _sanitize_asset_ref(assets.get("heroImage") or {}, "hero")
    if hero_ref:
        brand_block = project_input.setdefault("brand", {})
        brand_block["heroImage"] = hero_ref

    _gallery_raw = assets.get("gallery")
    raw_gallery: list[Any] = _gallery_raw if isinstance(_gallery_raw, list) else []
    gallery_refs = [
        _sanitize_asset_ref(item, "gallery") for item in raw_gallery if isinstance(item, dict)
    ]
    gallery_refs = [ref for ref in gallery_refs if ref is not None]
    if gallery_refs:
        project_input["gallery"] = gallery_refs

    # Scaffold hint från wizardens första valda kategori. Bara override
    # när planner-heuristiken pekar på fel scaffold (LLM saknar kontext).
    scaffold_hint = discovery.get("scaffoldHint")
    if isinstance(scaffold_hint, str) and scaffold_hint in {
        "local-service-business",
        "ecommerce-lite",
    }:
        # Bevara variantId om scaffold byts.
        if project_input.get("scaffoldId") != scaffold_hint:
            project_input["scaffoldId"] = scaffold_hint
            if scaffold_hint == "ecommerce-lite":
                project_input["variantId"] = "clean-store"
            else:
                project_input["variantId"] = "nordic-trust"

    # Location — om kontakt-adress innehåller postnummer, plocka ut city.
    if "addressLines" in contact:
        line = contact["addressLines"][0]
        m = re.search(r"\b\d{3}\s?\d{2}\s+([A-Za-zÅÄÖåäö\-]+)", line)
        if m:
            location = project_input.setdefault("location", {})
            location["city"] = m.group(1).strip()
            location.setdefault("country", "Sverige")
            location.setdefault("serviceAreas", [m.group(1).strip()])

    return project_input


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
    if schema_version != 1:
        raise SystemExit("--discovery payload måste ha schemaVersion=1.")
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


def generate(
    prompt: str,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    site_id: str | None = None,
    project_id: str | None = None,
    version: int = 1,
    mode: str = "init",
    base_project_input: dict[str, Any] | None = None,
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
    except Exception:  # noqa: BLE001
        # Mirror dev_generate.py's tolerance: a misconfigured llm-models
        # policy must not block the prompt-driven loop entirely.
        model = "gpt-5.4"

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

    final_site_id = site_id or slugify_site_id(prompt)
    if not _SITE_ID_PATTERN.match(final_site_id):
        raise SystemExit(
            f"Generated siteId {final_site_id!r} does not match the "
            "lower-case alphanumeric/dash pattern required by "
            "apps/viewser/lib/project-inputs.ts and build_site.py."
        )

    scaffold_id, variant_id = pick_scaffold(
        prompt, brief_artifact.get("businessTypeGuess")
    )
    candidate_project_input = site_brief_to_project_input(
        brief_artifact,
        site_id=final_site_id,
        scaffold_id=scaffold_id,
        variant_id=variant_id,
        original_prompt=prompt,
    )
    if base_project_input is not None:
        project_input = merge_followup_project_input(
            base_project_input,
            candidate_project_input,
            follow_up_prompt=prompt,
        )
    else:
        project_input = candidate_project_input

    # Discovery-overrides patchar in operatörens explicit ifyllda
    # wizard-svar. Körs efter LLM-extraktion så att wizardens
    # deterministiska fält vinner över LLM-gissningar för fält där
    # operatorn faktiskt skrev/klickade.
    if discovery is not None:
        project_input = _apply_discovery_overrides(project_input, discovery)

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
    if meta_overrides:
        meta.update(meta_overrides)

    project_input_path, meta_path = write_project_input(
        project_input, meta, output_dir=output_dir
    )
    return project_input, meta, project_input_path, meta_path


def generate_followup(
    prompt: str,
    *,
    site_id: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    """Generate a new Project Input version from an existing meta sidecar."""
    existing_meta = read_existing_meta(site_id, output_dir=output_dir)
    previous_project_input = read_existing_project_input(
        site_id, output_dir=output_dir
    )
    previous_version = existing_meta["version"]
    now = datetime.now(UTC).isoformat(timespec="seconds")
    return generate(
        prompt,
        output_dir=output_dir,
        site_id=site_id,
        project_id=existing_meta["projectId"],
        version=previous_version + 1,
        mode="followup",
        base_project_input=previous_project_input,
        meta_overrides={
            "originalPrompt": existing_meta.get("originalPrompt", prompt),
            "followUpPrompt": prompt,
            "previousVersion": previous_version,
            "createdAt": existing_meta.get("createdAt", now),
            "updatedAt": now,
        },
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
