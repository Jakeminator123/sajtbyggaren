"""Generate a draft industry scaffold candidate from an SNI code.

Branschberedskap steg 2 (efter ADR 0045): för branscher vars hemsidor
behöver en EGEN sid-uppsättning (fotografens portfolio, webbutikens
produktsidor, restaurangens meny/bokning) räcker inte kategori-mappningen
— de behöver en egen scaffold. Det här skriptet tar en SNI 2025-kod,
slår upp branschprofilen (industry-profiles.v1.json) + närmaste
befintliga scaffold som referensexempel, och låter ``scaffoldModel``
(llm-models.v1 v10) skriva en komplett scaffold-spec: routes, sektioner
per route, primaryJobs, quality-contract-rader och selection-profile-
signaler. Spec:en renderas sedan deterministiskt till samma sex filer
som ``tooling/scaffold-generator`` producerar (scaffold.json,
routes.json, sections.json, quality-contract.json,
compatible-dossiers.json, selection-profile.json) plus en variant.

Säkerhetskontrakt (samma som variant-/dossier-generatorerna):

- Output skrivs ENBART under ``data/scaffold-candidates/<id>/`` —
  aldrig till ``packages/generation/orchestration/`` (guard).
- Kandidaten är inert by construction: den finns inte i
  scaffold-contract.v1-registret, så runtime kan aldrig välja den.
  Promotion till canonical scaffold kräver ADR + naming-dictionary
  per scaffold-contract.v1 ``revisionRules`` (spec.json skrivs med så
  att promotion = kopiera in i ``tooling/scaffold-generator/spec/``).
- Utan ``OPENAI_API_KEY`` (läses från repo-rotens ``.env`` via samma
  loader som byggaren) faller generatorn tillbaka till en deterministisk
  spec byggd ur branschprofilens recommendedPages/extraCapabilities.

Usage::

    python scripts/generate_scaffold_candidate.py --sni 74.201 \
        --scaffold-id photographer-portfolio
    python scripts/generate_scaffold_candidate.py --sni 47.752 --no-llm
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.brief.models import (  # noqa: E402
    OPENAI_API_KEY_ENV,
    has_openai_api_key,
)
from packages.generation.discovery import load_discovery_taxonomy  # noqa: E402
from packages.generation.discovery.resolve import _resolve_sni_signal  # noqa: E402
from packages.generation.discovery.taxonomy import TaxonomyCategory  # noqa: E402
from scripts.candidate_generation_metadata import (  # noqa: E402
    brief_fingerprint,
    created_at,
    guard_candidate_output_dir,
    repo_or_output_relative,
)

SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
ORCHESTRATION_DIR = REPO_ROOT / "packages" / "generation" / "orchestration"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "scaffold-candidates"
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"
TOOLING_GENERATOR_PATH = (
    REPO_ROOT / "tooling" / "scaffold-generator" / "generate.py"
)

SCAFFOLD_ROLE_ID = "scaffoldModel"
EXPECTED_PROVIDER = "openai"
SLUG_PATTERN_TEXT = r"^[a-z][a-z0-9-]*$"
SLUG_PATTERN = re.compile(SLUG_PATTERN_TEXT)
SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")
SLUG_DASHES = re.compile(r"-{2,}")
ROUTE_PATH_PATTERN = re.compile(r"^/(?:[a-z0-9-]+(?:/[a-z0-9-]+)*)?$")

# $schema-pekarna i tooling-byggarna är relativa packages/-trädet; en
# kandidat under data/scaffold-candidates/<id>/ ligger tre nivåer ner.
CANDIDATE_SCAFFOLD_SCHEMA = "../../../governance/schemas/scaffold.schema.json"
CANDIDATE_VARIANT_SCHEMA = "../../../../governance/schemas/variant.schema.json"


class ScaffoldCandidateError(RuntimeError):
    """Raised when a scaffold candidate cannot be generated or written."""


class ScaffoldModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json has no usable scaffoldModel role."""


# ---------------------------------------------------------------------------
# Structured output-modeller (OpenAI strict mode tillåter inte dict med
# fria nycklar, därför är sectionsPerRoute en lista med routeId-fält).
# ---------------------------------------------------------------------------


class SpecRouteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=SLUG_PATTERN_TEXT)
    path: str
    required: bool
    purpose: str


class SpecOptionalRouteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=SLUG_PATTERN_TEXT)
    path: str
    when: str


class SpecRouteSectionsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: str = Field(alias="routeId", pattern=SLUG_PATTERN_TEXT)
    required_sections: list[str] = Field(alias="requiredSections", min_length=1)
    optional_sections: list[str] = Field(alias="optionalSections")
    section_order_rules: list[str] = Field(alias="sectionOrderRules")


class ScaffoldSpecCandidateModel(BaseModel):
    """LLM-output: branschens scaffold-spec (utan variants/vikter)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(pattern=SLUG_PATTERN_TEXT)
    label: str
    description: str
    primary_jobs: list[str] = Field(alias="primaryJobs", min_length=3)
    supports_single_page: bool = Field(alias="supportsSinglePage")
    routes: list[SpecRouteModel] = Field(min_length=3)
    optional_routes: list[SpecOptionalRouteModel] = Field(alias="optionalRoutes")
    sections_per_route: list[SpecRouteSectionsModel] = Field(
        alias="sectionsPerRoute", min_length=3
    )
    must_pass: list[str] = Field(alias="mustPass", min_length=2)
    avoid: list[str] = Field(alias="avoid", min_length=1)
    recommended_dossiers: list[str] = Field(alias="recommendedDossiers")
    embedding_text: str = Field(alias="embeddingText")
    semantic_signals: list[str] = Field(alias="semanticSignals", min_length=3)
    negative_signals: list[str] = Field(alias="negativeSignals", min_length=1)
    llm_classification_hints: list[str] = Field(
        alias="llmClassificationHints", min_length=2
    )


# ---------------------------------------------------------------------------
# Kontext
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndustryScaffoldContext:
    """Allt branschunderlag som spec-genereringen utgår från."""

    sni_code: str
    category: TaxonomyCategory
    profile_payload: dict[str, Any] | None
    profile_id: str | None
    reference_scaffold_id: str
    reference_routes: dict[str, Any]
    reference_sections: dict[str, Any]
    reference_compatible_dossiers: dict[str, Any]
    reference_variant: dict[str, Any]
    known_dossier_ids: list[str]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScaffoldCandidateError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ScaffoldCandidateError(f"{path} must contain a JSON object")
    return payload


def _load_tooling_builders() -> Any:
    """Ladda tooling/scaffold-generator/generate.py som modul.

    Katalogen innehåller bindestreck och kan inte importeras som paket;
    importlib-laddning ger oss exakt samma build_*/validate-funktioner
    som canonical-generatorn använder — en enda källa för filshapen.
    """
    spec = importlib.util.spec_from_file_location(
        "sajtbyggaren_scaffold_tooling", TOOLING_GENERATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise ScaffoldCandidateError(
            f"Could not load tooling generator at {TOOLING_GENERATOR_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _known_soft_dossier_ids() -> list[str]:
    soft_dir = DOSSIERS_DIR / "soft"
    if not soft_dir.is_dir():
        return []
    return sorted(path.name for path in soft_dir.iterdir() if path.is_dir())


_FALLBACK_VARIANT_TOKENS: dict[str, Any] = {
    "color": {
        "background": "#f7f8f5",
        "foreground": "#18201b",
        "muted": "#68706a",
        "border": "#dde3dc",
        "primary": "#245c45",
        "primaryForeground": "#f7f8f5",
        "accent": "#b98f45",
        "accentForeground": "#18201b",
    },
    "typography": {
        "fontFamilyDisplay": "var(--font-geist-sans)",
        "fontFamilyBody": "var(--font-geist-sans)",
        "fontFamilyMono": "var(--font-geist-mono)",
        "scaleRatio": 1.22,
    },
    "radius": {"sm": "0.25rem", "md": "0.5rem", "lg": "0.75rem"},
    "spacing": {"section": "5.5rem", "container": "min(74rem, 92vw)"},
    "motion": {"level": "subtle"},
}


def _reference_variant(scaffold_dir: Path, default_variant_id: str) -> dict[str, Any]:
    """Plocka referens-scaffoldens default-varianttokens (eller fallback)."""
    variants_dir = scaffold_dir / "variants"
    candidates: list[Path] = []
    preferred = variants_dir / f"{default_variant_id}.json"
    if preferred.is_file():
        candidates.append(preferred)
    elif variants_dir.is_dir():
        candidates.extend(sorted(variants_dir.glob("*.json")))
    for path in candidates:
        try:
            variant = _read_json(path)
        except ScaffoldCandidateError:
            continue
        if isinstance(variant.get("tokens"), dict) and isinstance(
            variant.get("tone"), dict
        ):
            return variant
    return {
        "tokens": _FALLBACK_VARIANT_TOKENS,
        "tone": {"vibe": ["calm", "local", "credible", "polished"]},
    }


def load_industry_context(sni_code: str) -> IndustryScaffoldContext:
    """Slå upp bransch + referens-scaffold för en SNI-kod.

    Återanvänder exakt samma söm som Discovery Resolver
    (``_resolve_sni_signal``, ADR 0045): kategori via sni-discovery-map
    och profil ENDAST när profilens kategori matchar resolutionen.
    """
    normalized, category_id, profile = _resolve_sni_signal({"sniCode": sni_code})
    if normalized is None or category_id is None:
        raise ScaffoldCandidateError(
            f"SNI-koden {sni_code!r} resolvar inte till en känd kategori. "
            "Kontrollera koden mot data/taxonomies/sni/sni-2025.v1.json."
        )
    taxonomy = load_discovery_taxonomy()
    category = taxonomy.get(category_id)
    if category is None:
        raise ScaffoldCandidateError(
            f"Kategorin {category_id!r} saknas i discovery-taxonomy.v1.json."
        )

    # Referens-scaffold: kategorins runtime-scaffold om den finns på disk,
    # annars local-service-business (den canonical förebilden).
    reference_id = category.runtime_scaffold_id
    reference_dir = SCAFFOLDS_DIR / reference_id
    if not (reference_dir / "routes.json").is_file():
        reference_id = "local-service-business"
        reference_dir = SCAFFOLDS_DIR / reference_id

    profile_payload: dict[str, Any] | None = None
    profile_id: str | None = None
    if profile is not None:
        profile_id = profile.profileId
        profile_payload = {
            "profileId": profile.profileId,
            "sniCode": profile.sniCode,
            "labelSv": profile.labelSv,
            "wizardCategoryId": profile.wizardCategoryId,
            "copyAngle": profile.copyAngle,
            "toneHints": list(profile.toneHints),
            "trustSignals": list(profile.trustSignals),
            "primaryCta": profile.primaryCta,
            "extraCapabilities": list(profile.extraCapabilities),
            "recommendedPages": list(profile.recommendedPages),
            "imageryHints": list(profile.imageryHints),
        }

    return IndustryScaffoldContext(
        sni_code=normalized,
        category=category,
        profile_payload=profile_payload,
        profile_id=profile_id,
        reference_scaffold_id=reference_id,
        reference_routes=_read_json(reference_dir / "routes.json"),
        reference_sections=_read_json(reference_dir / "sections.json"),
        reference_compatible_dossiers=_read_json(
            reference_dir / "compatible-dossiers.json"
        ),
        reference_variant=_reference_variant(
            reference_dir, category.defaultVariantId
        ),
        known_dossier_ids=_known_soft_dossier_ids(),
    )


# ---------------------------------------------------------------------------
# Modellresolution + LLM-anrop
# ---------------------------------------------------------------------------


def resolve_scaffold_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for scaffoldModel."""
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise ScaffoldModelResolutionError(f"llm-models.v1.json missing at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScaffoldModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc
    for role in data.get("roles", []):
        if role.get("id") != SCAFFOLD_ROLE_ID:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise ScaffoldModelResolutionError(
                f"scaffoldModel provider must be {EXPECTED_PROVIDER!r}, got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ScaffoldModelResolutionError(
                "scaffoldModel role is missing a non-empty model value"
            )
        return model
    raise ScaffoldModelResolutionError(f"scaffoldModel role missing from {path.name}")


def build_scaffold_prompt_payload(
    *,
    context: IndustryScaffoldContext,
    brief: str,
    requested_scaffold_id: str,
) -> dict[str, Any]:
    """Den exakta strukturerade kontexten som skickas till scaffoldModel."""
    return {
        "operatorBrief": brief,
        "requestedScaffoldId": requested_scaffold_id,
        "industry": {
            "sniCode": context.sni_code,
            "wizardCategoryId": context.category.id,
            "categoryLabelSv": context.category.labelSv,
            "categoryRequestedCapabilities": list(
                context.category.requestedCapabilities
            ),
            "categoryRecommendedPages": list(context.category.recommendedPages),
            "industryProfile": context.profile_payload,
        },
        "referenceScaffold": {
            "id": context.reference_scaffold_id,
            "routes": context.reference_routes,
            "sections": context.reference_sections,
        },
        "allowedDossierIds": context.known_dossier_ids,
        "hardRules": [
            "Return exactly one scaffold spec object.",
            "Route ids, section ids and the scaffold id are kebab-case slugs.",
            "Route paths are Swedish, lowercase, start with '/', no trailing slash.",
            "Always include a home route with path '/' and a contact route.",
            "Every default route MUST have a sectionsPerRoute entry with the same routeId.",
            "Design the page set for THIS industry: e.g. a photographer needs a portfolio route, a webshop needs a products route, a restaurant needs menu + booking routes.",
            "recommendedDossiers may only contain ids from allowedDossierIds.",
            "All visitor-facing wording in purposes/rules is honest — no invented certifications or fake counts.",
        ],
    }


def _call_scaffold_model(
    *,
    context: IndustryScaffoldContext,
    brief: str,
    requested_scaffold_id: str,
    model: str,
) -> ScaffoldSpecCandidateModel:
    """Call OpenAI scaffoldModel with strict structured output."""
    from openai import OpenAI

    client = OpenAI()
    payload = build_scaffold_prompt_payload(
        context=context,
        brief=brief,
        requested_scaffold_id=requested_scaffold_id,
    )
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You design one industry-specific scaffold spec for "
                    "Sajtbyggaren (small-business website generator). A "
                    "scaffold defines the page set (routes) and the section "
                    "grammar per page for one industry. Use the reference "
                    "scaffold as the shape example but design the ROUTES and "
                    "SECTIONS for the given industry's actual needs. Follow "
                    "the hard rules exactly."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2),
            },
        ],
        text_format=ScaffoldSpecCandidateModel,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("scaffoldModel returned no structured output")
    return parsed


# ---------------------------------------------------------------------------
# Deterministisk fallback (ingen nyckel / LLM-fel)
# ---------------------------------------------------------------------------

# Branschprofilernas recommendedPages är svenska operatörsetiketter;
# tabellen mappar etikett-nyckelord → (routeId, path, purpose, sektioner).
_PAGE_KEYWORD_ROUTES: tuple[tuple[tuple[str, ...], tuple[str, str, str, list[str]]], ...] = (
    (
        ("meny", "matsedel"),
        ("menu", "/meny", "Visa hela menyn med priser utan friktion.", ["menu-overview", "contact-cta"]),
    ),
    (
        ("bokning", "boka"),
        ("booking", "/bokning", "Låt besökaren boka direkt online.", ["booking-form", "opening-hours"]),
    ),
    (
        ("portfolio", "case", "projekt", "arbeten", "galleri"),
        ("portfolio", "/portfolio", "Visa tidigare arbeten som huvudargument för att höra av sig.", ["portfolio-grid", "contact-cta"]),
    ),
    (
        ("produkter", "webbutik", "sortiment", "butik"),
        ("products", "/produkter", "Visa sortimentet med tydlig väg till köp.", ["product-grid", "contact-cta"]),
    ),
    (
        ("behandling",),
        ("treatments", "/behandlingar", "Lista behandlingarna med ärlig beskrivning och pris.", ["service-list", "contact-cta"]),
    ),
    (
        ("tjänster", "tjanster"),
        ("services", "/tjanster", "Beskriv tjänsterna konkret och koppla dem till en offertväg.", ["services-intro", "service-list", "contact-cta"]),
    ),
    (
        ("prislista", "priser"),
        ("pricing", "/priser", "Transparent prislista som sänker tröskeln att ta kontakt.", ["pricing-table", "contact-cta"]),
    ),
    (
        ("team", "personal"),
        ("team", "/team", "Presentera människorna bakom verksamheten.", ["team", "contact-cta"]),
    ),
    (
        ("referenser", "recension", "omdöme", "omdomen"),
        ("references", "/referenser", "Visa verkliga kundomdömen och referensjobb.", ["reviews", "contact-cta"]),
    ),
    (
        ("faq", "frågor", "fragor"),
        ("faq", "/faq", "Besvara de vanligaste frågorna innan de blir ett hinder.", ["faq", "contact-cta"]),
    ),
    (
        ("om oss", "om mig"),
        ("about", "/om-oss", "Berätta verksamhetens historia specifikt, inte generiskt.", ["about-story", "trust-proof"]),
    ),
)

_SKIP_PAGE_KEYWORDS = ("startsida", "hero", "kontakt", "karta", "hitta hit", "nyhetsbrev")


def _mock_routes_from_pages(page_labels: list[str]) -> list[tuple[str, str, str, list[str]]]:
    routes: list[tuple[str, str, str, list[str]]] = []
    seen_ids: set[str] = set()
    for label in page_labels:
        lowered = label.lower()
        if any(skip in lowered for skip in _SKIP_PAGE_KEYWORDS):
            continue
        for keywords, route in _PAGE_KEYWORD_ROUTES:
            if any(keyword in lowered for keyword in keywords):
                if route[0] not in seen_ids:
                    routes.append(route)
                    seen_ids.add(route[0])
                break
    return routes


def _mock_scaffold_spec(
    *,
    context: IndustryScaffoldContext,
    requested_scaffold_id: str,
) -> ScaffoldSpecCandidateModel:
    """Deterministisk spec ur branschprofil + taxonomi (utan LLM)."""
    profile = context.profile_payload or {}
    label_sv = profile.get("labelSv") or context.category.labelSv
    page_labels = list(profile.get("recommendedPages") or [])
    page_labels.extend(context.category.recommendedPages)

    industry_routes = _mock_routes_from_pages(page_labels)
    routes: list[SpecRouteModel] = [
        SpecRouteModel(
            id="home",
            path="/",
            required=True,
            purpose=(
                f"Visa direkt vad verksamheten ({label_sv}) erbjuder och "
                "vägen till nästa steg."
            ),
        )
    ]
    sections: list[SpecRouteSectionsModel] = [
        SpecRouteSectionsModel.model_validate(
            {
                "routeId": "home",
                "requiredSections": [
                    "hero",
                    "service-summary",
                    "trust-proof",
                    "contact-cta",
                ],
                "optionalSections": ["reviews", "faq"],
                "sectionOrderRules": [
                    "Hero must be first and state the business type and city.",
                    "Trust proof must appear before the final CTA.",
                ],
            }
        )
    ]
    for route_id, path, purpose, required_sections in industry_routes:
        routes.append(
            SpecRouteModel(id=route_id, path=path, required=True, purpose=purpose)
        )
        sections.append(
            SpecRouteSectionsModel.model_validate(
                {
                    "routeId": route_id,
                    "requiredSections": required_sections,
                    "optionalSections": [],
                    "sectionOrderRules": [],
                }
            )
        )
    routes.append(
        SpecRouteModel(
            id="contact",
            path="/kontakt",
            required=True,
            purpose="Telefon, e-post, adress och öppettider utan att besökaren behöver leta.",
        )
    )
    sections.append(
        SpecRouteSectionsModel.model_validate(
            {
                "routeId": "contact",
                "requiredSections": ["contact-info", "contact-cta"],
                "optionalSections": ["map"],
                "sectionOrderRules": ["Phone, email and address must all be present."],
            }
        )
    )

    trust = list(profile.get("trustSignals") or [])
    copy_angle = profile.get("copyAngle") or context.category.rationale
    dossier_recommended = [
        dossier
        for dossier in (context.reference_compatible_dossiers.get("recommended") or [])
        if dossier in context.known_dossier_ids
    ]

    return ScaffoldSpecCandidateModel.model_validate(
        {
            "id": requested_scaffold_id,
            "label": label_sv,
            "description": (
                f"Branschspecifik scaffold-kandidat för {label_sv} "
                f"(SNI {context.sni_code}). {copy_angle}"
            ),
            "primaryJobs": [
                "visa vad verksamheten erbjuder på ett branschtypiskt sätt",
                "göra det självklart att ta nästa steg "
                f"({profile.get('primaryCta') or 'Kontakta oss'})",
                "bygga förtroende med ärliga trust-signaler",
            ],
            "supportsSinglePage": False,
            "routes": [route.model_dump() for route in routes],
            "optionalRoutes": [],
            "sectionsPerRoute": [
                section.model_dump(by_alias=True) for section in sections
            ],
            "mustPass": [
                "Every page has a clear purpose.",
                "Primary CTA is visible above the fold on the homepage.",
                "All routes from routes.json are present.",
            ]
            + (
                [f"Trust signals are honest and verifiable: {', '.join(trust[:3])}."]
                if trust
                else []
            ),
            "avoid": [
                "Generic abstract language.",
                "Invented certifications, fake review counts or placeholder copy.",
            ],
            "recommendedDossiers": dossier_recommended,
            "embeddingText": (
                f"Scaffold för {label_sv} (SNI {context.sni_code}). {copy_angle} "
                "Besökarens mål: förstå utbudet, lita på verksamheten och ta "
                "kontakt eller genomföra nästa steg."
            ),
            "semanticSignals": _semantic_signals(label_sv, page_labels),
            "negativeSignals": ["saas-dashboard", "internal-tool"],
            "llmClassificationHints": [
                f"Choose this scaffold for businesses in: {label_sv}.",
                "Do not choose this scaffold when the prompt clearly describes "
                "another industry's page needs.",
            ],
        }
    )


def _semantic_signals(label_sv: str, page_labels: list[str]) -> list[str]:
    signals = [slugify_scaffold_id(label_sv)]
    for label in page_labels[:4]:
        slug = slugify_scaffold_id(label)
        if slug not in signals:
            signals.append(slug)
    while len(signals) < 3:
        signals.append(f"signal-{len(signals) + 1}")
    return signals


# ---------------------------------------------------------------------------
# Normalisering + rendering till de sex scaffold-filerna
# ---------------------------------------------------------------------------


def slugify_scaffold_id(text: str) -> str:
    """Return a valid scaffold id slug from free text."""
    normalised = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(char for char in normalised if not unicodedata.combining(char))
    cleaned = SLUG_CLEAN.sub("-", ascii_text.lower()).strip("-")
    cleaned = SLUG_DASHES.sub("-", cleaned)
    if not cleaned:
        cleaned = "industry-scaffold"
    if cleaned[0].isdigit():
        cleaned = f"scaffold-{cleaned}"
    return cleaned


def _normalise_spec(
    candidate: ScaffoldSpecCandidateModel,
    *,
    context: IndustryScaffoldContext,
    requested_scaffold_id: str,
) -> dict[str, Any]:
    """Validera/reparera LLM-spec:en och bygg tooling-spec-dicten.

    Ärlighetsgrindar: kandidat-id:t är operatörens (inte modellens),
    routes utan sektioner får en minimal grammatik i stället för att
    fälla körningen, och dossier-rekommendationer utanför den kända
    listan strippas tyst (modellen får inte hitta på Dossiers).
    """
    default_routes = []
    seen_route_ids: set[str] = set()
    seen_paths: set[str] = set()
    for route in candidate.routes:
        path = route.path.rstrip("/") or "/"
        if not ROUTE_PATH_PATTERN.match(path):
            raise ScaffoldCandidateError(
                f"Route {route.id!r} har ogiltig path {route.path!r}."
            )
        if route.id in seen_route_ids or path in seen_paths:
            continue
        seen_route_ids.add(route.id)
        seen_paths.add(path)
        default_routes.append(
            {
                "id": route.id,
                "path": path,
                "required": route.required,
                "purpose": route.purpose.strip(),
            }
        )
    if "home" not in seen_route_ids or "/" not in seen_paths:
        raise ScaffoldCandidateError("Spec saknar home-route med path '/'.")

    optional_routes = []
    for route in candidate.optional_routes:
        path = route.path.rstrip("/") or "/"
        if route.id in seen_route_ids or path in seen_paths:
            continue
        if not ROUTE_PATH_PATTERN.match(path):
            continue
        seen_route_ids.add(route.id)
        seen_paths.add(path)
        optional_routes.append(
            {"id": route.id, "path": path, "optional": True, "when": route.when}
        )

    sections_by_route = {
        section.route_id: section for section in candidate.sections_per_route
    }
    sections_per_route: dict[str, Any] = {}
    for route in default_routes:
        section = sections_by_route.get(route["id"])
        if section is None:
            sections_per_route[route["id"]] = {
                "requiredSections": ["hero", "contact-cta"],
                "optionalSections": [],
                "sectionOrderRules": [],
            }
            continue
        sections_per_route[route["id"]] = {
            "requiredSections": list(dict.fromkeys(section.required_sections)),
            "optionalSections": list(dict.fromkeys(section.optional_sections)),
            "sectionOrderRules": list(section.section_order_rules),
        }

    recommended_dossiers = [
        dossier
        for dossier in dict.fromkeys(candidate.recommended_dossiers)
        if dossier in context.known_dossier_ids
    ]
    disallowed = list(
        context.reference_compatible_dossiers.get("disallowedByDefault") or []
    )

    baseline_must_pass = [
        "All routes from routes.json are present.",
        "No lorem ipsum or sample placeholder copy.",
        "Generated code typechecks and the project builds.",
    ]
    must_pass = list(dict.fromkeys([*candidate.must_pass, *baseline_must_pass]))

    variant_tokens = context.reference_variant.get(
        "tokens", _FALLBACK_VARIANT_TOKENS
    )
    variant_tone = context.reference_variant.get(
        "tone", {"vibe": ["calm", "local", "credible", "polished"]}
    )

    return {
        "id": requested_scaffold_id,
        "label": candidate.label.strip(),
        "description": candidate.description.strip(),
        "scaffoldVersion": "0.1.0",
        "buildIntent": ["website"],
        "primaryJobs": [job.strip() for job in candidate.primary_jobs if job.strip()],
        "defaultPageCount": len(default_routes),
        "supportsSinglePage": candidate.supports_single_page,
        "supportsMultiPage": True,
        "supportsAppFeatures": False,
        "routes": [*default_routes, *optional_routes],
        "sectionsPerRoute": sections_per_route,
        "qualityContract": {
            "scorecardWeights": {
                "business_fit": 1.2,
                "trust_signals": 1.2,
                "conversion_clarity": 1.1,
                "content_specificity": 1.1,
                "visual_hierarchy": 1.0,
                "technical_correctness": 1.0,
            },
            "mustPass": must_pass,
            "avoid": list(dict.fromkeys(candidate.avoid)),
        },
        "compatibleDossiers": {
            "comment": (
                "Kandidat-rekommendationer härledda ur branschprofilen; "
                "verifiera mot riktiga Dossier-id före promotion."
            ),
            "required": [],
            "recommended": recommended_dossiers,
            "conditional": [],
            "disallowedByDefault": disallowed,
        },
        "selectionProfile": {
            "embeddingText": candidate.embedding_text.strip(),
            "semanticSignals": [
                slugify_scaffold_id(signal) for signal in candidate.semantic_signals
            ],
            "negativeSignals": [
                slugify_scaffold_id(signal) for signal in candidate.negative_signals
            ],
            "llmClassificationHints": list(candidate.llm_classification_hints),
            "minConfidence": 0.72,
            "requiresTieBreakWhenWithin": 0.08,
        },
        "variants": [
            {
                "id": "draft-default",
                "enabled": False,
                "label": "Draft Default",
                "description": (
                    "Startvariant kopierad från referens-scaffoldens default "
                    "så kandidaten kan förhandsgranskas; ersätts vid kurering."
                ),
                "tokens": variant_tokens,
                "tone": variant_tone,
            }
        ],
    }


@dataclass(frozen=True)
class ScaffoldGenerationResult:
    """Result metadata for one written candidate directory."""

    candidate_dir: Path
    spec_path: Path
    meta_path: Path
    spec: dict[str, Any]
    metadata: dict[str, Any]
    source: str
    model_used: str


def _guard_output_dir(output_dir: Path) -> None:
    guard_candidate_output_dir(
        output_dir,
        forbidden_roots=(ORCHESTRATION_DIR, SCAFFOLDS_DIR, DOSSIERS_DIR),
        error_cls=ScaffoldCandidateError,
        kind="Scaffold",
    )


def _write_candidate_files(
    spec: dict[str, Any],
    *,
    context: IndustryScaffoldContext,
    output_dir: Path,
    source: str,
    model_used: str,
    operator_brief: str,
    force: bool,
) -> ScaffoldGenerationResult:
    _guard_output_dir(output_dir)
    tooling = _load_tooling_builders()

    scaffold_doc = tooling.build_scaffold_json(spec)
    scaffold_doc["$schema"] = CANDIDATE_SCAFFOLD_SCHEMA
    routes_doc = tooling.build_routes_json(spec)
    sections_doc = tooling.build_sections_json(spec)
    quality_doc = tooling.build_quality_contract_json(spec)
    compatible_doc = tooling.build_compatible_dossiers_json(spec)
    selection_doc = tooling.build_selection_profile_json(spec)
    variant_docs = []
    for variant in spec["variants"]:
        variant_doc = tooling.build_variant_json(variant)
        variant_doc["$schema"] = CANDIDATE_VARIANT_SCHEMA
        variant_docs.append((variant["id"], variant_doc))

    errors: list[str] = []
    errors.extend(tooling.validate(scaffold_doc, "scaffold.schema.json", "scaffold.json"))
    errors.extend(tooling.validate(sections_doc, "sections.schema.json", "sections.json"))
    for variant_id, variant_doc in variant_docs:
        errors.extend(
            tooling.validate(
                variant_doc, "variant.schema.json", f"variants/{variant_id}.json"
            )
        )
    if errors:
        raise ScaffoldCandidateError(
            "Schema validation failed:\n" + "\n".join(errors)
        )

    candidate_dir = output_dir / spec["id"]
    if candidate_dir.exists() and not force:
        raise ScaffoldCandidateError(
            f"Candidate already exists: {candidate_dir}. Pass --force to overwrite."
        )
    (candidate_dir / "variants").mkdir(parents=True, exist_ok=True)

    def _dump(path: Path, doc: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    _dump(candidate_dir / "scaffold.json", scaffold_doc)
    _dump(candidate_dir / "routes.json", routes_doc)
    _dump(candidate_dir / "sections.json", sections_doc)
    _dump(candidate_dir / "quality-contract.json", quality_doc)
    _dump(candidate_dir / "compatible-dossiers.json", compatible_doc)
    _dump(candidate_dir / "selection-profile.json", selection_doc)
    for variant_id, variant_doc in variant_docs:
        _dump(candidate_dir / "variants" / f"{variant_id}.json", variant_doc)

    # Spec:en är promotion-artefakten: kopiera till
    # tooling/scaffold-generator/spec/ + kör generatorn = canonical filer.
    spec_path = candidate_dir / "spec.json"
    _dump(spec_path, spec)

    metadata = {
        "schemaVersion": 1,
        "candidateType": "scaffold",
        "candidateId": spec["id"],
        "sniCode": context.sni_code,
        "wizardCategoryId": context.category.id,
        "industryProfileId": context.profile_id,
        "referenceScaffoldId": context.reference_scaffold_id,
        "source": source,
        "modelUsed": model_used,
        "modelRole": SCAFFOLD_ROLE_ID,
        "generator": "scripts.generate_scaffold_candidate",
        "createdAt": created_at(),
        "outputPath": repo_or_output_relative(
            candidate_dir, repo_root=REPO_ROOT, output_dir=output_dir
        ),
        "operatorBriefHash": brief_fingerprint(operator_brief),
        "promotion": (
            "Kandidaten är inert (saknas i scaffold-contract.v1-registret). "
            "Promotion: ADR + naming-dictionary per scaffold-contract.v1 "
            "revisionRules, kopiera spec.json till "
            "tooling/scaffold-generator/spec/<id>.json och kör generatorn."
        ),
    }
    meta_path = candidate_dir / "meta.json"
    _dump(meta_path, metadata)

    return ScaffoldGenerationResult(
        candidate_dir=candidate_dir,
        spec_path=spec_path,
        meta_path=meta_path,
        spec=spec,
        metadata=metadata,
        source=source,
        model_used=model_used,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def generate_scaffold_candidate(
    *,
    sni_code: str,
    brief: str = "",
    scaffold_id: str | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    force: bool = False,
    use_llm: bool = True,
) -> ScaffoldGenerationResult:
    """Generate and write one industry scaffold candidate directory."""
    _guard_output_dir(output_dir)
    context = load_industry_context(sni_code)

    profile = context.profile_payload or {}
    base_label = profile.get("labelSv") or context.category.labelSv
    candidate_id = slugify_scaffold_id(scaffold_id or base_label)
    if not SLUG_PATTERN.match(candidate_id):
        raise ScaffoldCandidateError(f"Invalid scaffold id: {candidate_id!r}")
    if (SCAFFOLDS_DIR / candidate_id).exists():
        raise ScaffoldCandidateError(
            f"{candidate_id!r} finns redan som canonical scaffold; "
            "välj ett annat --scaffold-id."
        )

    operator_brief = brief.strip() or (
        f"Branschspecifik scaffold för {base_label} (SNI {sni_code}). "
        "Designa sid-uppsättningen efter branschens faktiska behov."
    )

    source = "mock-no-key" if use_llm else "deterministic-v1"
    model_used = "mock" if use_llm else "deterministic"
    if use_llm and has_openai_api_key():
        try:
            model_used = resolve_scaffold_model()
            candidate = _call_scaffold_model(
                context=context,
                brief=operator_brief,
                requested_scaffold_id=candidate_id,
                model=model_used,
            )
            source = "real"
        except Exception as exc:  # noqa: BLE001 - fallback är kontraktet
            print(
                f"scaffoldModel failed; using deterministic fallback: {exc}",
                file=sys.stderr,
            )
            candidate = _mock_scaffold_spec(
                context=context, requested_scaffold_id=candidate_id
            )
            source = "mock-llm-error"
    else:
        candidate = _mock_scaffold_spec(
            context=context, requested_scaffold_id=candidate_id
        )

    spec = _normalise_spec(
        candidate, context=context, requested_scaffold_id=candidate_id
    )
    return _write_candidate_files(
        spec,
        context=context,
        output_dir=output_dir,
        source=source,
        model_used=model_used,
        operator_brief=operator_brief,
        force=force,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an industry scaffold candidate under "
            "data/scaffold-candidates/ from an SNI 2025 code."
        )
    )
    parser.add_argument("--sni", required=True, help="SNI 2025-kod, t.ex. 74.201")
    parser.add_argument(
        "--brief",
        default="",
        help="Extra operatörsriktning utöver branschprofilen (valfri)",
    )
    parser.add_argument(
        "--scaffold-id",
        help="Kandidatens scaffold-id (kebab-case). Default: slug av branschetiketten.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for candidate output",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing candidate")
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic fallback")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Samma .env-källa som byggaren: repo-rotens .env, os.environ vinner.
    from scripts.build_site import load_repo_root_env

    load_repo_root_env()

    try:
        result = generate_scaffold_candidate(
            sni_code=args.sni,
            brief=args.brief,
            scaffold_id=args.scaffold_id,
            output_dir=args.output_dir,
            force=args.force,
            use_llm=not args.no_llm,
        )
    except (ScaffoldCandidateError, ScaffoldModelResolutionError) as exc:
        print(f"scaffold candidate generation failed: {exc}", file=sys.stderr)
        return 1

    key_state = "present" if has_openai_api_key() else "missing"
    print(f"{OPENAI_API_KEY_ENV}: {key_state}")
    print(f"candidateDir: {result.candidate_dir.resolve()}")
    print(f"source: {result.source}")
    print(f"modelUsed: {result.model_used}")
    routes = [route["path"] for route in result.spec["routes"]]
    print(f"routes: {', '.join(routes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
