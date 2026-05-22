"""Canonical Discovery Resolver för B121.

Konsumerar:

- raw prompt (operatörens ursprungstext)
- :class:`DiscoveryPayload` från Viewser (validerat mot
  ``governance/schemas/discovery-payload.schema.json``)
- kandidat Project Input från ``site_brief_to_project_input``
- optional scrape-derived fields (samma shape som Project Input-fragment;
  scrape-pipelinen är inte uppkopplad i PR A, men resolvern accepterar fältet
  så future scrape-källor kan plugga in utan en API-breaking change)
- Discovery Taxonomy från ``governance/policies/discovery-taxonomy.v1.json``

Producerar:

- resolverat Project Input dict (fortsatt kompatibelt med
  ``project-input.schema.json``)
- :class:`DiscoveryDecision` med ``fieldSources``, ``fallbackWarnings`` och
  selectionSource som Backoffice/Doctor kan visa.

Refaktorregeln från Scout-planen är att ``_apply_discovery_overrides`` i
``scripts/prompt_to_project_input.py`` ska bli en tunn wrapper runt
``resolve_discovery``. :func:`apply_discovery_overrides` är den helpern;
den returnerar bara Project Input för bakåtkompatibilitet med
``tests/test_operator_uploads.py`` och övriga callers som inte bryr sig om
``DiscoveryDecision``.

Field-source-regel (vinstordning per fält):

1. ``wizard`` — operatorn klickade/skrev explicit i overlayen.
2. ``scrape`` — wizardfältet är tomt men URL-skrapning fyllde det.
3. ``brief`` — wizard/scrape är tomma men briefModel/site_brief_to_project_input
   redan hade ett värde.
4. ``taxonomy`` — gäller scaffold/variant/expected starter/capabilities som
   härleds från ``discovery-taxonomy.v1.json``.
5. ``default`` — placeholder från ``site_brief_to_project_input`` (sista utvägen).
6. ``operator`` / ``pinned`` — reserverade för framtida Backoffice-pin /
   Project Input ``starterId``-pin (används inte av resolvern idag).
7. ``derived`` — resolvern härledde fältet ur andra signaler när varken
   wizard, scrape eller brief gav ett brukbart värde (B137: tagline-
   fallback när wizardens offer var UI-direktiv och brief saknade tagline).
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import (
    DiscoveryDecision,
    FallbackWarning,
    FieldSourceLiteral,
    SelectionSource,
)
from .taxonomy import (
    DEFAULT_TAXONOMY_PATH,
    DiscoveryTaxonomy,
    TaxonomyCategory,
    load_discovery_taxonomy,
)

DEFAULT_CAPABILITY_MAP_PATH = (
    Path(__file__).resolve().parents[3]
    / "governance"
    / "policies"
    / "capability-map.v1.json"
)
"""Canonical location för ``capability-map.v1.json``.

Resolvern läser policyn runtime (R3 #2 på PR #34: tidigare hårdkodning
av ``_KNOWN_CAPABILITY_SLUGS`` gjorde governance till en sekundär källa
och kunde inte triggas av ``capability-gap``-warnings).
"""

# ---------------------------------------------------------------------------
# Static mappings (behållna 1:1 från scripts/prompt_to_project_input.py)
# ---------------------------------------------------------------------------

# Wizardens "Sidor att bygga" → capability-slugs. Vissa slugs (t.ex.
# ``booking``, ``team``, ``gallery``) finns ännu inte i
# ``capability-map.v1.json``; resolvern lägger då en ``capability-unknown``
# fallbackWarning så Backoffice ser gap:et utan att vi tappar information.
_PAGE_TO_CAPABILITY: dict[str, str] = {
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

# Aliaserna mappar mot resolverns lokala canonical
# (_PAGE_TO_CAPABILITY-output) tills capability-map.v1.json fått en
# aliases-array i en framtida governance-sprint.
_CAPABILITY_ALIASES: dict[str, str] = {
    "online-booking": "booking",
    "webshop": "ecommerce",
    "online-shop": "ecommerce",
    "newsletter": "newsletter-subscribe",
    "contact": "contact-form",
}


def _normalize_capability_slug(slug: str) -> str:
    """Returnera canonical capability-slug för lokalt kända alias."""
    cleaned = slug.strip()
    return _CAPABILITY_ALIASES.get(cleaned.lower(), cleaned)


# Wizardens primära CTA → ``conversionGoals``-slug. Identisk med tidigare
# ``_apply_discovery_overrides``-mapping så befintliga produktbygg behåller
# samma conversion-spår.
_CTA_TO_CONVERSION_GOAL: dict[str, str] = {
    "Boka tid": "booking",
    "Kontakta oss": "contact",
    "Köp nu": "purchase",
    "Begär offert": "lead",
    "Registrera dig": "signup",
    "Ring oss": "call",
    "Ladda ner": "download",
}

def _load_capability_map(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Läs ``capability-map.v1.json`` och returnera capabilities-dict.

    Resultatet är en map ``slug -> {dossiers: [...], default?: str, comment?: str}``.
    Resolvern använder den för att skilja på tre fall:

    1. ``known`` — slug finns och har minst en dossier; ingen warning.
    2. ``gap`` — slug finns men ``dossiers`` är tom; lägg
       ``capability-gap`` warning så Backoffice ser att en planerad Dossier
       saknas. Detta är fallet idag för ``contact-form``, ``payments`` m.fl.
       som ``planning.filter_capabilities`` annars rapporterar via Site Plan
       ``rejectedCapabilities``.
    3. ``unknown`` — slug saknas i map; lägg ``capability-unknown`` warning.

    R3 #2 på PR #34: tidigare hårdkodade frozenset gjorde att resolvern
    aldrig kunde trigga ``capability-gap``, så ``operatorReviewRequired``
    blev felaktigt ``False`` för ecommerce med payments etc.
    """
    actual = path if path is not None else DEFAULT_CAPABILITY_MAP_PATH
    try:
        payload = json.loads(actual.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for slug, entry in capabilities.items():
        if isinstance(slug, str) and isinstance(entry, dict):
            out[slug] = entry
    return out


def _classify_capability(
    slug: str, capability_map: dict[str, dict[str, Any]]
) -> tuple[str, str | None]:
    """Returnerar ``("known"|"gap"|"unknown", reason_or_None)``."""
    entry = capability_map.get(slug)
    if entry is None:
        return ("unknown", None)
    dossiers = entry.get("dossiers") or []
    if not dossiers:
        comment = entry.get("comment")
        reason = comment if isinstance(comment, str) and comment else (
            "Capability finns i capability-map.v1.json men har ingen "
            "implementerad Dossier ännu."
        )
        return ("gap", reason)
    return ("known", None)

# Scaffold/variant-defaults för payloads utan kategori (catch-all "other"
# vägen). Speglar ``_SCAFFOLD_LOCAL_SERVICE`` i
# ``scripts/prompt_to_project_input.py`` så befintliga tester av
# ``pick_scaffold`` och ``site_brief_to_project_input`` behåller samma
# fallback-beteende.
_DEFAULT_SCAFFOLD_ID = "local-service-business"
_DEFAULT_VARIANT_ID = "nordic-trust"
_DEFAULT_STARTER_ID = "marketing-base"

# Postnummer-extraktion från svensk adress (samma regex som tidigare).
_SWEDISH_POSTCODE_RE = re.compile(r"\b\d{3}\s?\d{2}\s+([A-Za-zÅÄÖåäö\-]+)")


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def resolve_discovery(
    *,
    raw_prompt: str,
    payload: dict[str, Any] | None,
    project_input_candidate: dict[str, Any],
    scrape: dict[str, Any] | None = None,
    placeholder_fields: Iterable[str] | None = None,
    taxonomy: DiscoveryTaxonomy | None = None,
    taxonomy_path: Path | None = None,
    capability_map: dict[str, dict[str, Any]] | None = None,
    capability_map_path: Path | None = None,
) -> tuple[dict[str, Any], DiscoveryDecision]:
    """Main entry point — resolverat Project Input + ``DiscoveryDecision``.

    Bevarar Project Input-schemat. Operator-uppladdade assets, services och
    kontaktfält flyttas in från payload exakt som tidigare; nytt är att
    scaffold/variant/expected starter härleds från
    ``discovery-taxonomy.v1.json`` och att varje viktig field-mutation
    lagras som en ``fieldSource`` så Backoffice kan visa varför fältet vann.

    ``scrape`` är reserverat för framtida URL-skrapnings-pipeline (PR B+
    levererar den). Idag förväntar resolvern att ``scrape`` är ``None``
    eller ``dict`` med Project Input-fragment-shape; ``scrape`` vinner
    bara där wizard saknar explicit värde.

    ``capability_map`` injekteras från ``capability-map.v1.json`` runtime
    och används för att klassificera ``requestedCapabilities`` som
    ``known`` / ``gap`` / ``unknown``. Tester och Backoffice-dry-run kan
    skicka in egen map för deterministiska scenarion.

    ``placeholder_fields`` lists contact-block keys that
    ``site_brief_to_project_input`` filled with deterministic default
    values. Those values are still valid Project Input data, but their
    field-source is ``default`` rather than ``brief``.
    """
    _ = raw_prompt  # bevaras för future heuristics, inte använt i v1
    project_input: dict[str, Any] = copy.deepcopy(project_input_candidate)
    placeholder_contact_fields = {
        field.strip()
        for field in (placeholder_fields or [])
        if isinstance(field, str) and field.strip()
    }
    decision_taxonomy = taxonomy or load_discovery_taxonomy(taxonomy_path)
    resolved_capability_map = (
        capability_map
        if capability_map is not None
        else _load_capability_map(capability_map_path)
    )

    # ------------------------------------------------------------------
    # Steg 1 — extrahera ``answers`` och ``categoryIds``
    # ------------------------------------------------------------------
    answers: dict[str, Any] = {}
    if isinstance(payload, dict):
        raw_answers = payload.get("answers")
        if isinstance(raw_answers, dict):
            answers = raw_answers

    category_ids = _collect_category_ids(answers)
    field_sources: dict[str, FieldSourceLiteral] = {}
    warnings: list[FallbackWarning] = []

    # ------------------------------------------------------------------
    # Steg 2 — matcha kategorier mot taxonomi
    # ------------------------------------------------------------------
    matched_categories: list[TaxonomyCategory] = []
    for cid in category_ids:
        category = decision_taxonomy.get(cid)
        if category is None:
            warnings.append(
                FallbackWarning(
                    code="category-unknown",
                    message=(
                        f"Wizard-kategori {cid!r} saknas i "
                        "discovery-taxonomy.v1.json; resolvern kan inte avgöra "
                        "scaffold/variant utan ny mapping."
                    ),
                    categoryId=cid,
                )
            )
            continue
        matched_categories.append(category)
        if category.supportStatus == "planned":
            warnings.append(
                FallbackWarning(
                    code="category-planned",
                    message=(
                        f"Kategori {category.id!r} pekar mot målscaffold "
                        f"{category.targetScaffoldId!r} som ännu inte är "
                        "runtime-mappad; bygger med fallback."
                    ),
                    categoryId=category.id,
                    scaffoldId=category.targetScaffoldId,
                )
            )
        elif category.supportStatus == "fallback":
            warnings.append(
                FallbackWarning(
                    code="category-fallback",
                    message=(
                        f"Kategori {category.id!r} körs som fallback mot "
                        f"{category.runtime_scaffold_id!r}; promotera när målscaffold är klar."
                    ),
                    categoryId=category.id,
                    scaffoldId=category.runtime_scaffold_id,
                )
            )
        elif category.supportStatus == "disabled":
            warnings.append(
                FallbackWarning(
                    code="category-disabled",
                    message=(
                        f"Kategori {category.id!r} är disabled i discovery-taxonomy. "
                        "Resolvern faller tillbaka till default-scaffold; operatorn bör granska."
                    ),
                    categoryId=category.id,
                )
            )

    # R2 P1 + R3 #1: primary_category måste väljas med samma branch-
    # prioritet som ``pick_branch``, annars kan multi-select ge
    # ``contentBranch=ecommerce`` men scaffold=``local-service-business``.
    # R2 P2 (round 3): disabled-kategori får inte pinna icke-byggbar
    # scaffold via runtime_scaffold_id. Vi behandlar disabled som "ingen
    # primärkategori" — warning category-disabled är redan tillagd i
    # föregående loop, men resolvern faller tillbaka till scaffoldHint
    # eller candidate Project Input istället för att använda
    # taxonomy-scaffolden.
    primary_category = decision_taxonomy.pick_primary_category(matched_categories)
    primary_disabled = (
        primary_category is not None and primary_category.supportStatus == "disabled"
    )
    if primary_disabled:
        primary_category = None

    # ------------------------------------------------------------------
    # Steg 3 — välj scaffold/variant/starter via taxonomy
    # ------------------------------------------------------------------
    selection_source: SelectionSource
    scaffold_hint_used = False
    if primary_category is not None:
        selected_scaffold_id = primary_category.runtime_scaffold_id
        target_scaffold_id = primary_category.targetScaffoldId
        fallback_scaffold_id = (
            primary_category.fallbackScaffoldId
            if primary_category.fallbackScaffoldId
            and primary_category.fallbackScaffoldId != selected_scaffold_id
            else None
        )
        selected_variant_id = primary_category.defaultVariantId
        expected_starter_id = primary_category.expectedStarterId
        content_branch = decision_taxonomy.pick_branch(category_ids)
        # Project Input ska få den buildbara scaffolden / varianten även om
        # target pekar längre fram. produce_site_plan validerar mot
        # SCAFFOLD_TO_STARTER så detta är säkert.
        project_input["scaffoldId"] = selected_scaffold_id
        project_input["variantId"] = selected_variant_id
        field_sources["scaffoldId"] = "taxonomy"
        field_sources["variantId"] = "taxonomy"
        selection_source = (
            "fallback"
            if primary_category.supportStatus in {"planned", "fallback"}
            else "taxonomy"
        )
        if expected_starter_id is None:
            warnings.append(
                FallbackWarning(
                    code="starter-mapping-missing",
                    message=(
                        f"Scaffold {selected_scaffold_id!r} saknar "
                        "expectedStarterId i discovery-taxonomy."
                    ),
                    categoryId=primary_category.id,
                    scaffoldId=selected_scaffold_id,
                )
            )
    else:
        # R3 #4: bakåtkompatibilitet med legacy payloads som saknar
        # ``siteType`` men har ``scaffoldHint``. Pre-B121 accepterade
        # ``_apply_discovery_overrides`` ``scaffoldHint`` som primär
        # signal när den pekade mot en buildbar scaffold; resolvern
        # behöver hålla det kontraktet så CLI-/test-payloads inte
        # tappar scaffold-val. Hinten respekteras bara för de två
        # scaffolds som faktiskt har runtime + variant + starter:
        # local-service-business och ecommerce-lite.
        hint = _scaffold_hint_from_payload(payload)
        if hint is not None:
            # R2 P2 (round 3): selectionSource måste matcha fieldSources
            # — wizardens hint pinnar fältet och fieldSources["scaffoldId"]
            # blir "wizard", så top-level selectionSource ska också vara
            # "wizard". Tidigare blev det "default" vilket var osant.
            scaffold_hint_used = True
            selected_scaffold_id, selected_variant_id, expected_starter_id = hint
            target_scaffold_id = selected_scaffold_id
            fallback_scaffold_id = None
            project_input["scaffoldId"] = selected_scaffold_id
            project_input["variantId"] = selected_variant_id
            field_sources["scaffoldId"] = "wizard"
            field_sources["variantId"] = "wizard"
            selection_source = "wizard"
            content_branch = (
                payload.get("contentBranch", "business")
                if isinstance(payload, dict)
                and isinstance(payload.get("contentBranch"), str)
                else "business"
            )
        else:
            # Tom siteType och ingen användbar scaffoldHint — bevara
            # existing scaffold/variant från project_input_candidate
            # (``pick_scaffold``-resultatet från
            # scripts/prompt_to_project_input). Resolvern rör inte fälten
            # så test_operator_uploads' empty-pi-fall behåller sin shape.
            selected_scaffold_id = project_input.get("scaffoldId", _DEFAULT_SCAFFOLD_ID)
            target_scaffold_id = selected_scaffold_id
            fallback_scaffold_id = None
            selected_variant_id = project_input.get("variantId", _DEFAULT_VARIANT_ID)
            expected_starter_id = _starter_for_scaffold(selected_scaffold_id)
            selection_source = "default"
            content_branch = (
                payload.get("contentBranch", "business")
                if isinstance(payload, dict)
                and isinstance(payload.get("contentBranch"), str)
                else "business"
            )

    # ------------------------------------------------------------------
    # Steg 4 — patcha Project Input-fält med wizard > scrape > brief
    # ------------------------------------------------------------------
    _apply_company_fields(project_input, answers, field_sources)
    _apply_contact_fields(
        project_input,
        answers,
        scrape,
        field_sources,
        placeholder_fields=placeholder_contact_fields,
    )
    _apply_services_field(project_input, answers, field_sources)
    _apply_brand_and_assets(project_input, answers, field_sources)
    _apply_tone_field(project_input, answers, field_sources)
    _apply_location_from_address(project_input)

    # ------------------------------------------------------------------
    # Steg 5 — capabilities (mustHave + CTA + taxonomy) → conversion goals
    # ------------------------------------------------------------------
    capability_result = _resolve_capabilities(
        project_input=project_input,
        answers=answers,
        primary_category=primary_category,
        field_sources=field_sources,
        capability_map=resolved_capability_map,
    )
    warnings.extend(capability_result["warnings"])

    _apply_cta_field(project_input, answers, field_sources)

    # ------------------------------------------------------------------
    # Steg 6 — bygg ``DiscoveryDecision``
    # ------------------------------------------------------------------
    candidate_dossiers: list[str] = []
    if primary_category is not None:
        candidate_dossiers = list(primary_category.candidateDossiers)

    # ``scaffold_hint_used`` är True när scaffoldHint-fallback användes
    # utan en matchande kategori; resolvern behöver inte automatisk
    # operator review i det fallet (det är samma kontrakt som pre-B121).
    #
    # R1 #1 + huvudreviewer #4 på PR #34 (round 3): ``capability-gap``
    # bör flaggas i ``fallbackWarnings`` men ska INTE trigga
    # operatorReviewRequired. Gap betyder att taxonomin/wizarden begär
    # en känd capability vars Dossier ännu inte är implementerad
    # (``contact-form``, ``payments`` m.fl. idag) — det är samma signal
    # för alla runs och kräver ingen per-run-review. ``capability-unknown``
    # (slug som inte ens finns i capability-map) däremot triggar review
    # eftersom resolvern inte vet vad operatorn vill ha.
    #
    # R1 (round 4): ``category-disabled`` ska trigga review oavsett om
    # den disablade kategorin blev primary eller bara en sekundär entry
    # i multi-select. Tidigare räckte ``primary_disabled`` som villkor,
    # men ``["salon", "broken-disabled"]`` gav då review=False eftersom
    # salon (active) vann tie-break och primary_disabled blev False —
    # trots att ``category-disabled``-warning loggats. Att läsa direkt
    # från warnings gör att alla disabled-kategorier triggar review och
    # gör den separata ``primary_disabled``-grenen redundant.
    operator_review_required = bool(
        (
            primary_category is None
            and not scaffold_hint_used
            and len(category_ids) > 0
        )
        or (
            primary_category is not None
            and primary_category.supportStatus == "planned"
        )
        or any(
            warning.code
            in {"category-unknown", "category-disabled", "capability-unknown"}
            for warning in warnings
        )
        or _has_placeholder_contact_source(field_sources)
    )

    rationale = _build_rationale(
        primary_category,
        selected_scaffold_id,
        target_scaffold_id,
        warnings,
    )

    decision = DiscoveryDecision(
        categoryIds=category_ids,
        contentBranch=content_branch,
        selectedScaffoldId=selected_scaffold_id,
        targetScaffoldId=target_scaffold_id,
        fallbackScaffoldId=fallback_scaffold_id,
        selectedVariantId=selected_variant_id,
        expectedStarterId=expected_starter_id,
        requestedCapabilities=list(project_input.get("requestedCapabilities") or []),
        candidateDossiers=candidate_dossiers,
        fallbackWarnings=warnings,
        fieldSources=field_sources,
        selectionSource=selection_source,
        operatorReviewRequired=operator_review_required,
        rationale=rationale,
    )
    return project_input, decision


def apply_discovery_overrides(
    project_input: dict[str, Any],
    discovery: dict[str, Any] | None,
) -> dict[str, Any]:
    """Tunn wrapper — bevarad för bakåtkompatibilitet.

    ``scripts/prompt_to_project_input._apply_discovery_overrides`` är en
    direktdelegation till denna helper; den returnerar bara Project Input
    så testet ``test_apply_discovery_overrides_maps_assets_to_brand_and_gallery``
    fortsätter passera utan att läsa decision-objektet.
    """
    if not isinstance(discovery, dict):
        return project_input
    project_input_dict = project_input if isinstance(project_input, dict) else {}
    resolved, _decision = resolve_discovery(
        raw_prompt=str(discovery.get("rawPrompt") or ""),
        payload=discovery,
        project_input_candidate=project_input_dict,
    )
    return resolved


# ---------------------------------------------------------------------------
# Field-mappers (private)
# ---------------------------------------------------------------------------


def _collect_category_ids(answers: dict[str, Any]) -> list[str]:
    raw = answers.get("siteType")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _starter_for_scaffold(scaffold_id: str) -> str | None:
    """Resolverns lokala spegling av ``planning.SCAFFOLD_TO_STARTER``.

    Bara de två runtime-aktiva paren listas; importera planningmodulen är
    overkill för att slippa en cyklisk dependency mellan
    ``packages.generation.discovery`` och ``packages.generation.planning``.
    Om mappingen utvidgas i ``plan.py`` bör listan här hållas i synk
    (capturas av ``tests/test_starter_scaffold_mapping.py`` och
    ``tests/test_discovery_resolver.py``).
    """
    return _RUNTIME_SCAFFOLD_HINTS.get(scaffold_id, (None, None, None))[2]


# Buildbara scaffolds som ``scaffoldHint`` får peka mot. Spegling av
# de två par som planning.SCAFFOLD_TO_STARTER faktiskt mappar idag —
# pre-B121 _apply_discovery_overrides accepterade samma whitelist.
_RUNTIME_SCAFFOLD_HINTS: dict[str, tuple[str, str, str]] = {
    "local-service-business": (
        "local-service-business",
        "nordic-trust",
        "marketing-base",
    ),
    "ecommerce-lite": ("ecommerce-lite", "clean-store", "commerce-base"),
}


def _scaffold_hint_from_payload(
    payload: dict[str, Any] | None,
) -> tuple[str, str, str] | None:
    """R3 #4: tolka ``payload.scaffoldHint`` när ``siteType`` saknas.

    Returnerar ``(scaffoldId, variantId, expectedStarterId)`` för
    runtime-aktiva scaffold-hints, annars ``None``. Hinten respekteras
    bara för scaffolds som faktiskt har starter-mapping; en hint som
    pekar mot en planned scaffold (t.ex. ``restaurant-hospitality``) tas
    inte som hård signal eftersom det skulle krocka med taxonomins
    ``planned`` -> ``fallbackScaffoldId``-regel.
    """
    if not isinstance(payload, dict):
        return None
    hint = payload.get("scaffoldHint")
    if not isinstance(hint, str):
        return None
    return _RUNTIME_SCAFFOLD_HINTS.get(hint.strip())


# ---------------------------------------------------------------------------
# B137 - wizard-overlay tagline-sanering
# ---------------------------------------------------------------------------
#
# Wizardens "Beskriv din verksamhet"-fält (``answers.offer``) skickas både
# till briefModel som rådata OCH till discovery-payloaden. När operatören
# skriver UI-direktiv där ("Hemsida om X, 2 sidor, gröna färger") hamnade
# texten tidigare rakt som ``company.tagline`` och läckte ut som publik
# hero-tagline. Helpern ``_offer_looks_like_ui_directive`` detekterar de
# vanligaste läckage-mönstren så att brief-taglinen (eller en derived
# fallback) får företräde i ``_apply_company_fields``.

_OFFER_PAGE_COUNT_RE = re.compile(r"\b\d+\s+sidor?\b", re.IGNORECASE)
_OFFER_COLOR_DIRECTIVE_RE = re.compile(
    r"\b(röd|grön|blå|gul|svart|vit|grå)a?\s+(färger|färg|tema)\b",
    re.IGNORECASE,
)
_OFFER_INSTRUCTION_PREFIXES: tuple[str, ...] = (
    "hemsida om",
    "bygg ",
    "skapa ",
    "gör en",
    "vill ha",
    "behöver",
)
# Tröskel sänkt från < 12 till < 8 tecken per operatör-OK 2026-05-21:
# korta riktiga verksamhetsbeskrivningar ("Bagar bröd" = 10 tkn) ska
# inte felklassas som UI-direktiv. Endast uppenbar spam-input fångas.
_OFFER_MIN_LENGTH = 8
_OFFER_MAX_LENGTH = 120


def _strip_offer_markup(offer: str) -> str:
    """Strippa markdown- och listprefix från offer innan prefix-match."""
    text = offer.strip()
    text = re.sub(r"^[\s*#>\-•·]+", "", text)
    text = re.sub(r"^\d+[.)]\s+", "", text)
    return text.lstrip()


def _offer_looks_like_ui_directive(offer: str) -> bool:
    """True när wizardens offer-fält är operatörs-direktiv, inte verksamhet.

    Returnerar True när texten ser ut att vara en instruktion till
    sajtbyggaren (sidantal, färgval, "bygg en ..."-prefix etc.) snarare
    än en faktisk verksamhetsbeskrivning. Används i
    ``_apply_company_fields`` så ``company.tagline`` inte läcker UI-text.

    OBS: ensamt färgord utan ``färger``/``färg``/``tema``-suffix passerar
    fortfarande detektorn (acceptabel risk för v1 — Scout-uppföljning
    eskalerar om det syns i ett verkligt case).
    """
    text = offer.strip()
    if not text:
        return False
    if len(text) < _OFFER_MIN_LENGTH or len(text) > _OFFER_MAX_LENGTH:
        return True
    if _OFFER_PAGE_COUNT_RE.search(text):
        return True
    if _OFFER_COLOR_DIRECTIVE_RE.search(text):
        return True
    stripped = _strip_offer_markup(text).lower()
    for prefix in _OFFER_INSTRUCTION_PREFIXES:
        if stripped.startswith(prefix):
            return True
    return False


def _derived_fallback_tagline(
    company: dict[str, Any], language: str
) -> str:
    """Tagline-fallback när offer är UI-direktiv OCH brief tagline saknas.

    Sällsynt edge case (briefModel producerar normalt alltid en tagline),
    men resolvern måste leverera en schema-valid sträng (minLength=1,
    maxLength=140). Helpern är medvetet minimal — för rikare derivation
    se ``scripts/prompt_to_project_input._derive_tagline`` (lyft till
    paketmodul vid behov i framtida sprint).
    """
    business_type = (company.get("businessType") or "").strip().lower()
    business_label = business_type.replace("-", " ").replace("_", " ").strip()
    if language == "en":
        if business_label:
            return f"Clear help with {business_label}"[:140]
        return "Welcome"
    if business_label:
        return f"Tydlig hjälp inom {business_label}"[:140]
    return "Välkommen"


def _apply_company_fields(
    project_input: dict[str, Any],
    answers: dict[str, Any],
    field_sources: dict[str, FieldSourceLiteral],
) -> None:
    company = project_input.setdefault("company", {})
    name = answers.get("companyName")
    if isinstance(name, str) and name.strip():
        company["name"] = name.strip()
        field_sources["company.name"] = "wizard"
    elif company.get("name"):
        field_sources["company.name"] = "brief"

    offer = answers.get("offer")
    if isinstance(offer, str) and offer.strip():
        if _offer_looks_like_ui_directive(offer):
            # B137: behåll brief-tagline framför UI-direktiv. När brief
            # saknar tagline producerar vi en kort derived fallback så
            # schemat fortfarande accepterar Project Input.
            if company.get("tagline"):
                field_sources["company.tagline"] = "brief"
            else:
                language = (
                    project_input.get("language", "sv") or "sv"
                ).strip().lower()
                company["tagline"] = _derived_fallback_tagline(company, language)
                field_sources["company.tagline"] = "derived"
        else:
            first_sentence = offer.strip().split(". ")[0][:140]
            company["tagline"] = first_sentence
            field_sources["company.tagline"] = "wizard"
    elif company.get("tagline"):
        field_sources["company.tagline"] = "brief"

    about = answers.get("aboutText")
    if isinstance(about, str) and about.strip():
        company["story"] = about.strip()[:1200]
        field_sources["company.story"] = "wizard"
    elif company.get("story"):
        field_sources["company.story"] = "brief"


def _apply_contact_fields(
    project_input: dict[str, Any],
    answers: dict[str, Any],
    scrape: dict[str, Any] | None,
    field_sources: dict[str, FieldSourceLiteral],
    *,
    placeholder_fields: set[str] | None = None,
) -> None:
    placeholder_contact_fields = placeholder_fields or set()

    def existing_source(field: str) -> FieldSourceLiteral:
        return "default" if field in placeholder_contact_fields else "brief"

    contact_raw = answers.get("contact")
    answer_contact: dict[str, Any] = (
        contact_raw if isinstance(contact_raw, dict) else {}
    )
    scrape_contact: dict[str, Any] = {}
    if isinstance(scrape, dict):
        raw_scrape_contact = scrape.get("contact")
        if isinstance(raw_scrape_contact, dict):
            scrape_contact = raw_scrape_contact

    contact = project_input.setdefault("contact", {})

    phone = answer_contact.get("phone")
    if isinstance(phone, str) and phone.strip():
        contact["phone"] = phone.strip()
        field_sources["contact.phone"] = "wizard"
    else:
        scrape_phone = scrape_contact.get("phone")
        if isinstance(scrape_phone, str) and scrape_phone.strip():
            contact["phone"] = scrape_phone.strip()
            field_sources["contact.phone"] = "scrape"
        elif contact.get("phone"):
            field_sources["contact.phone"] = existing_source("phone")

    email = answer_contact.get("email")
    if isinstance(email, str) and email.strip():
        contact["email"] = email.strip()
        field_sources["contact.email"] = "wizard"
    else:
        scrape_email = scrape_contact.get("email")
        if isinstance(scrape_email, str) and scrape_email.strip():
            contact["email"] = scrape_email.strip()
            field_sources["contact.email"] = "scrape"
        elif contact.get("email"):
            field_sources["contact.email"] = existing_source("email")

    opening_hours = answer_contact.get("openingHours")
    if isinstance(opening_hours, str) and opening_hours.strip():
        contact["openingHours"] = opening_hours.strip()
        field_sources["contact.openingHours"] = "wizard"
    elif contact.get("openingHours"):
        field_sources["contact.openingHours"] = existing_source("openingHours")

    addr = answer_contact.get("address")
    if isinstance(addr, str) and addr.strip():
        contact["addressLines"] = [addr.strip()]
        field_sources["contact.addressLines"] = "wizard"
    else:
        scrape_addr = scrape_contact.get("address")
        if isinstance(scrape_addr, str) and scrape_addr.strip():
            contact["addressLines"] = [scrape_addr.strip()]
            field_sources["contact.addressLines"] = "scrape"
        elif contact.get("addressLines"):
            field_sources["contact.addressLines"] = existing_source("addressLines")


def _has_placeholder_contact_source(
    field_sources: dict[str, FieldSourceLiteral],
) -> bool:
    return any(
        field_sources.get(path) == "default"
        for path in (
            "contact.phone",
            "contact.email",
            "contact.addressLines",
            "contact.openingHours",
        )
    )


def _apply_services_field(
    project_input: dict[str, Any],
    answers: dict[str, Any],
    field_sources: dict[str, FieldSourceLiteral],
) -> None:
    items = answers.get("services")
    if not isinstance(items, list) or not items:
        if project_input.get("services"):
            field_sources["services"] = "brief"
        return
    mapped: list[dict[str, str]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        label = item.get("name")
        if not isinstance(label, str) or not label.strip():
            continue
        description_raw = item.get("description")
        summary = (
            description_raw.strip()
            if isinstance(description_raw, str) and description_raw.strip()
            else f"Tydlig hjälp med {label.strip().lower()} och enkel väg vidare."
        )
        slug = _slugify(label) or f"service-{idx + 1}"
        mapped.append({"id": slug, "label": label.strip(), "summary": summary})
    if mapped:
        project_input["services"] = mapped[:8]
        field_sources["services"] = "wizard"


def _apply_brand_and_assets(
    project_input: dict[str, Any],
    answers: dict[str, Any],
    field_sources: dict[str, FieldSourceLiteral],
) -> None:
    brand_raw = answers.get("brand")
    wizard_brand: dict[str, Any] = brand_raw if isinstance(brand_raw, dict) else {}
    primary = wizard_brand.get("primaryColorHex")
    accent = wizard_brand.get("accentColorHex")
    if (isinstance(primary, str) and primary.strip()) or (
        isinstance(accent, str) and accent.strip()
    ):
        brand_block = project_input.setdefault("brand", {})
        if isinstance(primary, str) and primary.strip():
            brand_block["primaryColorHex"] = primary.strip()
            field_sources["brand.primaryColorHex"] = "wizard"
        if isinstance(accent, str) and accent.strip():
            brand_block["accentColorHex"] = accent.strip()
            field_sources["brand.accentColorHex"] = "wizard"

    assets_raw = answers.get("assets")
    assets: dict[str, Any] = assets_raw if isinstance(assets_raw, dict) else {}

    logo_ref = _sanitize_asset_ref(assets.get("logo") or {}, "logo")
    if logo_ref:
        brand_block = project_input.setdefault("brand", {})
        brand_block["logo"] = logo_ref
        field_sources["brand.logo"] = "wizard"

    hero_ref = _sanitize_asset_ref(assets.get("heroImage") or {}, "hero")
    if hero_ref:
        brand_block = project_input.setdefault("brand", {})
        brand_block["heroImage"] = hero_ref
        field_sources["brand.heroImage"] = "wizard"

    gallery_raw = assets.get("gallery")
    raw_gallery: list[Any] = gallery_raw if isinstance(gallery_raw, list) else []
    gallery_refs: list[dict[str, Any]] = []
    for item in raw_gallery:
        if not isinstance(item, dict):
            continue
        ref = _sanitize_asset_ref(item, "gallery")
        if ref is not None:
            gallery_refs.append(ref)
    if gallery_refs:
        project_input["gallery"] = gallery_refs
        field_sources["gallery"] = "wizard"


def _apply_tone_field(
    project_input: dict[str, Any],
    answers: dict[str, Any],
    field_sources: dict[str, FieldSourceLiteral],
) -> None:
    brand_raw = answers.get("brand")
    brand: dict[str, Any] = brand_raw if isinstance(brand_raw, dict) else {}
    tone_tags = brand.get("toneTags")
    if isinstance(tone_tags, list) and tone_tags:
        clean = [t for t in tone_tags if isinstance(t, str) and t.strip()]
        if clean:
            tone_block = project_input.setdefault("tone", {})
            tone_block["primary"] = clean[0]
            tone_block["secondary"] = clean[1:5]
            field_sources["tone.primary"] = "wizard"

    avoid = brand.get("wordsToAvoid")
    if isinstance(avoid, str) and avoid.strip():
        tokens = [t.strip() for t in re.split(r"[;,\n]", avoid) if t.strip()]
        if tokens:
            tone_block = project_input.setdefault("tone", {})
            tone_block["avoid"] = tokens[:10]
            field_sources["tone.avoid"] = "wizard"


def _apply_location_from_address(project_input: dict[str, Any]) -> None:
    contact = project_input.get("contact") or {}
    address_lines = contact.get("addressLines") if isinstance(contact, dict) else None
    if not isinstance(address_lines, list) or not address_lines:
        return
    line = address_lines[0]
    if not isinstance(line, str):
        return
    match = _SWEDISH_POSTCODE_RE.search(line)
    if not match:
        return
    city = match.group(1).strip()
    if not city:
        return
    location = project_input.setdefault("location", {})
    location["city"] = city
    location.setdefault("country", "Sverige")
    location.setdefault("serviceAreas", [city])


def _resolve_capabilities(
    *,
    project_input: dict[str, Any],
    answers: dict[str, Any],
    primary_category: TaxonomyCategory | None,
    field_sources: dict[str, FieldSourceLiteral],
    capability_map: dict[str, dict[str, Any]],
) -> dict[str, list[FallbackWarning]]:
    """Bygg ``requestedCapabilities`` med fieldSources och warnings.

    Klassificerar varje slug via ``_classify_capability`` mot
    ``capability-map.v1.json``:

    - ``known`` → ingen warning.
    - ``gap`` → ``capability-gap`` (slug registrerad men ingen Dossier).
    - ``unknown`` → ``capability-unknown`` (slug saknas i map).

    Båda gap- och unknown-fynd höjer ``operatorReviewRequired`` i
    ``resolve_discovery`` (R2 P1 + R3 #2 på PR #34).
    """
    existing = list(project_input.get("requestedCapabilities") or [])
    wizard_caps: list[str] = []
    must_have = answers.get("mustHave")
    if isinstance(must_have, list):
        for page in must_have:
            cap = _PAGE_TO_CAPABILITY.get(str(page))
            if cap:
                wizard_caps.append(cap)

    taxonomy_caps: list[str] = []
    if primary_category is not None:
        taxonomy_caps = list(primary_category.requestedCapabilities)

    combined: list[str] = []
    seen: set[str] = set()
    sources_per_slug: dict[str, FieldSourceLiteral] = {}
    for slug in wizard_caps:
        canonical = _normalize_capability_slug(slug)
        if canonical and canonical not in seen:
            combined.append(canonical)
            seen.add(canonical)
            sources_per_slug[canonical] = "wizard"
    for slug in taxonomy_caps:
        canonical = _normalize_capability_slug(slug)
        if canonical and canonical not in seen:
            combined.append(canonical)
            seen.add(canonical)
            sources_per_slug[canonical] = "taxonomy"
    for slug in existing:
        if not isinstance(slug, str):
            continue
        canonical = _normalize_capability_slug(slug)
        if not canonical or canonical in seen:
            continue
        combined.append(canonical)
        seen.add(canonical)
        sources_per_slug[canonical] = "brief"

    warnings: list[FallbackWarning] = []
    for slug in combined:
        classification, reason = _classify_capability(slug, capability_map)
        if classification == "known":
            continue
        if classification == "gap":
            warnings.append(
                FallbackWarning(
                    code="capability-gap",
                    message=(
                        reason
                        or (
                            f"Capability {slug!r} finns i capability-map.v1.json "
                            "men saknar implementerad Dossier."
                        )
                    ),
                    capabilityId=slug,
                )
            )
            continue
        warnings.append(
            FallbackWarning(
                code="capability-unknown",
                message=(
                    f"Capability {slug!r} finns inte i capability-map.v1.json; "
                    "planning rapporterar den som unknown och Backoffice kan "
                    "föreslå Dossier-import."
                ),
                capabilityId=slug,
            )
        )
    project_input["requestedCapabilities"] = combined
    if combined:
        # Toppen-källa per fält registreras på ``requestedCapabilities``;
        # per-slug-källor lever bara i resolvern (kan exponeras via
        # Backoffice när vi behöver granulär provenance).
        priority = ("wizard", "taxonomy", "brief")
        for candidate in priority:
            if candidate in sources_per_slug.values():
                field_sources["requestedCapabilities"] = candidate  # type: ignore[assignment]
                break
    elif existing:
        field_sources["requestedCapabilities"] = "brief"
    return {"warnings": warnings}


def _apply_cta_field(
    project_input: dict[str, Any],
    answers: dict[str, Any],
    field_sources: dict[str, FieldSourceLiteral],
) -> None:
    cta = answers.get("primaryCta")
    if not isinstance(cta, str) or not cta.strip():
        if project_input.get("conversionGoals"):
            field_sources["conversionGoals"] = "brief"
        return
    goal = _CTA_TO_CONVERSION_GOAL.get(cta.strip())
    if goal is None:
        return
    current_goals = list(project_input.get("conversionGoals") or [])
    if goal in current_goals:
        # CTA-värdet finns redan; bevara existerande list-shape men markera
        # att wizarden satt den (vinst-regeln säger wizard slår brief).
        field_sources["conversionGoals"] = "wizard"
        return
    current_goals.append(goal)
    project_input["conversionGoals"] = current_goals
    field_sources["conversionGoals"] = "wizard"


def _build_rationale(
    category: TaxonomyCategory | None,
    selected_scaffold_id: str,
    target_scaffold_id: str,
    warnings: list[FallbackWarning],
) -> str:
    if category is None:
        if warnings:
            return (
                "Discovery payload saknade matchande kategori; resolvern "
                "behåller scaffold/variant från briefModel-heuristiken."
            )
        return ""
    parts: list[str] = [
        f"Kategori {category.id!r} -> scaffold {selected_scaffold_id!r}."
    ]
    if selected_scaffold_id != target_scaffold_id:
        parts.append(f"Target scaffold {target_scaffold_id!r} kör som planned/fallback.")
    if category.expectedStarterId:
        parts.append(f"Förväntad starter {category.expectedStarterId!r}.")
    return " ".join(parts)


def _sanitize_asset_ref(
    ref: dict[str, Any], default_role: str
) -> dict[str, Any] | None:
    """Bevara fält schemat godkänner; ignorera okända/null-fält.

    Identisk shape som tidigare ``_sanitize_asset_ref`` i
    ``scripts/prompt_to_project_input.py`` så
    ``test_apply_discovery_overrides_maps_assets_to_brand_and_gallery``
    fortsätter passera efter refaktorn.
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


def _slugify(text: str) -> str:
    """ASCII-folded kebab-case-slug (mirror av ``_slugify_label``).

    Resolvern duplikerar slugify-helpern istället för att importera den
    från ``scripts.prompt_to_project_input`` för att undvika att
    ``packages/generation/`` importerar från ``scripts/`` (repo-boundaries
    förbjuder den vägen). När resolvern blir canonical kan
    ``scripts/prompt_to_project_input._slugify_label`` flyttas hit istället.
    """
    import unicodedata

    normalised = unicodedata.normalize("NFKD", text or "")
    folded = "".join(ch for ch in normalised if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9-]+", "-", folded.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug


# ---------------------------------------------------------------------------
# Read-only public accessors for Backoffice diagnostics
# ---------------------------------------------------------------------------
#
# Backoffice diagnostics need to read the wizard label -> capability and
# wizard label -> conversion goal mappings to verify that every wizard UI
# value has a known destination. Importing the private underscore-prefixed
# constants from another package couples Backoffice to implementation
# details. These helpers expose immutable copies so a consumer can iterate
# without mutating resolver state.


def get_page_to_capability_mapping() -> dict[str, str]:
    """Read-only copy of the wizard ``mustHave`` -> capability slug map.

    Used by ``backoffice/discovery_wizard_diagnostics.py`` to know which
    wizard must-have labels feed ``requestedCapabilities`` deterministically.
    Returns a new dict so callers cannot mutate resolver internals.
    """
    return dict(_PAGE_TO_CAPABILITY)


def get_cta_to_conversion_goal_mapping() -> dict[str, str]:
    """Read-only copy of the wizard ``primaryCta`` -> conversion-goal map.

    Used by ``backoffice/discovery_wizard_diagnostics.py`` to surface
    wizard CTA values that lack a deterministic conversion-goal mapping
    so they are not silently hidden.
    """
    return dict(_CTA_TO_CONVERSION_GOAL)


def normalize_capability_slug(slug: str) -> str:
    """Public wrapper for the resolver's capability alias normalisation.

    The resolver folds known aliases (``newsletter``, ``online-booking``,
    etc.) into canonical capability slugs before classifying them against
    ``capability-map.v1.json``. Backoffice diagnostics rely on the same
    folding so the classification matches what the resolver actually does.
    """
    return _normalize_capability_slug(slug)


__all__ = [
    "apply_discovery_overrides",
    "resolve_discovery",
    "get_page_to_capability_mapping",
    "get_cta_to_conversion_goal_mapping",
    "normalize_capability_slug",
    # Re-export för bakåtkompat när konsumenter vill ha taxonomy-loadern
    "load_discovery_taxonomy",
    "DEFAULT_TAXONOMY_PATH",
]
