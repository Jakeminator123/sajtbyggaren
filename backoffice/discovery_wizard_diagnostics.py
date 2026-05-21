"""Read-only diagnostics for Viewser wizard answer propagation.

This module deliberately contains Backoffice-only metadata. Runtime code does
not import it, and generation decisions continue to live in Discovery Resolver,
Discovery Taxonomy, Capability Map, planning and the builder.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from packages.generation.discovery.resolve import (
    _CTA_TO_CONVERSION_GOAL,
    _PAGE_TO_CAPABILITY,
)

from .paths import POLICIES_DIR, REPO_ROOT

DISCOVERY_TAXONOMY_PATH = POLICIES_DIR / "discovery-taxonomy.v1.json"
CAPABILITY_MAP_PATH = POLICIES_DIR / "capability-map.v1.json"
DOSSIER_SELECTION_PATH = POLICIES_DIR / "dossier-selection.v1.json"
WIZARD_TYPES_PATH = (
    REPO_ROOT / "apps" / "viewser" / "components" / "discovery-wizard" / "wizard-types.ts"
)
WIZARD_PAYLOAD_PATH = (
    REPO_ROOT / "apps" / "viewser" / "components" / "discovery-wizard" / "wizard-payload.ts"
)
WIZARD_CONSTANTS_PATH = (
    REPO_ROOT
    / "apps"
    / "viewser"
    / "components"
    / "discovery-wizard"
    / "wizard-constants.ts"
)
DISCOVERY_RESOLVER_PATH = (
    REPO_ROOT / "packages" / "generation" / "discovery" / "resolve.py"
)
PROJECT_INPUT_SCHEMA_PATH = (
    REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"
)
BUILD_SITE_PATH = REPO_ROOT / "scripts" / "build_site.py"

diagnostic_status = Literal[
    "active",
    "fallback",
    "planned",
    "gap",
    "unknown",
    "no-known-destination",
]
propagation_level = Literal[
    "deterministic",
    "prompt-signal",
    "project-input-only",
    "downstream-gap",
    "diagnostic-only",
]

STEP_LABELS: dict[str, str] = {
    "company": "Ditt företag",
    "siteType": "Kategori",
    "content": "Innehåll",
    "story": "Om företaget",
    "pages": "Sidor och CTA",
    "assets": "Bilder och logotyp",
    "brand": "Ton och stil",
}

STATUS_ORDER: tuple[diagnostic_status, ...] = (
    "active",
    "fallback",
    "planned",
    "gap",
    "unknown",
    "no-known-destination",
)

PROPAGATION_ORDER: tuple[propagation_level, ...] = (
    "deterministic",
    "prompt-signal",
    "project-input-only",
    "downstream-gap",
    "diagnostic-only",
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _repo_relative(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _source_paths(*paths: Path) -> str:
    return "; ".join(_repo_relative(path) for path in paths)


def _row(
    *,
    step: str,
    answer_path: str,
    destination: str,
    source_chain: str,
    status: diagnostic_status,
    propagation_level: propagation_level,
    explanation: str,
    source_path: str,
) -> dict[str, str]:
    return {
        "step": step,
        "stepLabel": STEP_LABELS[step],
        "answerPath": answer_path,
        "destination": destination,
        "sourceChain": source_chain,
        "status": status,
        "propagationLevel": propagation_level,
        "explanation": explanation,
        "sourcePath": source_path,
    }


def load_capability_map(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return capability map entries keyed by capability id."""
    payload = _read_json(path or CAPABILITY_MAP_PATH)
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        return {}
    return {
        str(capability_id): entry
        for capability_id, entry in capabilities.items()
        if isinstance(entry, dict)
    }


def classify_capability(
    capability_id: str,
    capability_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Literal["active", "gap", "unknown"] | str]:
    """Classify a capability without changing policies or runtime state."""
    resolved_map = capability_map if capability_map is not None else load_capability_map()
    entry = resolved_map.get(capability_id)
    if entry is None:
        return {
            "status": "unknown",
            "explanation": "Capability saknas i capability-map.v1.json.",
        }
    if not (entry.get("dossiers") or []):
        return {
            "status": "gap",
            "explanation": str(
                entry.get("comment")
                or "Capability finns men saknar implementerad Dossier."
            ),
        }
    return {
        "status": "active",
        "explanation": "Capability har minst en implementerad Dossier.",
    }


def _taxonomy_rows(capability_map: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    taxonomy = _read_json(DISCOVERY_TAXONOMY_PATH)
    rows: list[dict[str, str]] = [
        _row(
            step="siteType",
            answer_path="answers.siteType",
            destination=(
                "Discovery Payload → Discovery Resolver → scaffoldId, "
                "variantId, expectedStarterId, requestedCapabilities"
            ),
            source_chain=(
                "wizard-payload.ts → Discovery Resolver → "
                "discovery-taxonomy.v1.json → planning"
            ),
            status="active",
            propagation_level="deterministic",
            explanation=(
                "Kategori-id är wizardens kontrakt. Wizarden får inte sätta "
                "starterId direkt; starter härleds via vald scaffold i planning."
            ),
            source_path=_source_paths(
                WIZARD_PAYLOAD_PATH,
                DISCOVERY_RESOLVER_PATH,
                DISCOVERY_TAXONOMY_PATH,
            ),
        )
    ]

    for category in taxonomy.get("categories", []):
        if not isinstance(category, dict):
            continue
        category_id = str(category.get("id") or "")
        if not category_id:
            continue
        support_status = str(category.get("supportStatus") or "unknown")
        status: diagnostic_status = (
            support_status
            if support_status in {"active", "fallback", "planned"}
            else "unknown"
        )
        if support_status == "disabled":
            status = "planned"
        selected_scaffold = (
            category.get("activeScaffoldId")
            if support_status == "active"
            else category.get("fallbackScaffoldId")
        )
        selected_scaffold = selected_scaffold or category.get("targetScaffoldId") or ""
        requested = [
            str(item)
            for item in category.get("requestedCapabilities", []) or []
            if isinstance(item, str)
        ]
        capability_notes = []
        for capability_id in requested:
            classified = classify_capability(capability_id, capability_map)
            capability_notes.append(f"{capability_id}:{classified['status']}")
        rows.append(
            _row(
                step="siteType",
                answer_path=f"answers.siteType[{category_id}]",
                destination=(
                    f"targetScaffoldId={category.get('targetScaffoldId', '')}; "
                    f"runtimeScaffold={selected_scaffold}; "
                    f"defaultVariantId={category.get('defaultVariantId', '')}; "
                    f"expectedStarterId={category.get('expectedStarterId', '')}"
                ),
                source_chain="Discovery Taxonomy → Discovery Resolver → planning",
                status=status,
                propagation_level="deterministic",
                explanation=(
                    f"{category.get('labelSv', category_id)} har supportStatus="
                    f"{support_status}. Requested capabilities: "
                    f"{', '.join(capability_notes) if capability_notes else 'inga'}."
                ),
                source_path=_source_paths(DISCOVERY_TAXONOMY_PATH),
            )
        )
    return rows


def _must_have_rows(capability_map: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        _row(
            step="pages",
            answer_path="answers.mustHave",
            destination="requestedCapabilities → Capability Map → Dossier Selection",
            source_chain=(
                "wizard-constants.ts → Discovery Resolver _PAGE_TO_CAPABILITY "
                "→ capability-map.v1.json → dossier-selection.v1.json"
            ),
            status="active",
            propagation_level="deterministic",
            explanation=(
                "Must-have-sidor blir capability-signaler. Dossiers väljs inte "
                "direkt av wizardknappar utan går vidare via Capability Map, "
                "Dossier Selection och planning."
            ),
            source_path=_source_paths(
                WIZARD_CONSTANTS_PATH,
                DISCOVERY_RESOLVER_PATH,
                CAPABILITY_MAP_PATH,
                DOSSIER_SELECTION_PATH,
            ),
        )
    ]
    for page_label, capability_id in sorted(_PAGE_TO_CAPABILITY.items()):
        classified = classify_capability(capability_id, capability_map)
        rows.append(
            _row(
                step="pages",
                answer_path=f"answers.mustHave[{page_label}]",
                destination=f"requestedCapabilities[{capability_id}]",
                source_chain=(
                    "Discovery Resolver _PAGE_TO_CAPABILITY → "
                    "capability-map.v1.json"
                ),
                status=classified["status"],
                propagation_level="deterministic",
                explanation=classified["explanation"],
                source_path=_source_paths(DISCOVERY_RESOLVER_PATH, CAPABILITY_MAP_PATH),
            )
        )
    return rows


def _cta_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        _row(
            step="pages",
            answer_path="answers.primaryCta",
            destination="conversionGoals",
            source_chain="wizard-payload.ts → Discovery Resolver _CTA_TO_CONVERSION_GOAL",
            status="active",
            propagation_level="deterministic",
            explanation="Kända CTA-chip översätts deterministiskt till conversionGoals.",
            source_path=_source_paths(WIZARD_PAYLOAD_PATH, DISCOVERY_RESOLVER_PATH),
        )
    ]
    for cta_label, goal in sorted(_CTA_TO_CONVERSION_GOAL.items()):
        rows.append(
            _row(
                step="pages",
                answer_path=f"answers.primaryCta[{cta_label}]",
                destination=f"conversionGoals[{goal}]",
                source_chain="Discovery Resolver _CTA_TO_CONVERSION_GOAL",
                status="active",
                propagation_level="deterministic",
                explanation="CTA-värdet har en känd conversion goal-mappning.",
                source_path=_source_paths(DISCOVERY_RESOLVER_PATH),
            )
        )
    return rows


def _direct_project_input_rows() -> list[dict[str, str]]:
    source = _source_paths(WIZARD_TYPES_PATH, DISCOVERY_RESOLVER_PATH)
    return [
        _row(
            step="company",
            answer_path="answers.companyName",
            destination="company.name",
            source_chain="WizardAnswers → Discovery Resolver → Project Input",
            status="active",
            propagation_level="deterministic",
            explanation="Företagsnamnet skriver deterministiskt Project Input company.name.",
            source_path=source,
        ),
        _row(
            step="company",
            answer_path="answers.offer",
            destination="company.tagline",
            source_chain="WizardAnswers → Discovery Resolver → Project Input",
            status="active",
            propagation_level="deterministic",
            explanation=(
                "Erbjudandet blir tagline när det inte ser ut som UI-direktiv. "
                "B137-skyddet låter brief/derived fallback vinna vid läckagerisk."
            ),
            source_path=source,
        ),
        _row(
            step="story",
            answer_path="answers.aboutText",
            destination="company.story",
            source_chain="WizardAnswers → Discovery Resolver → Project Input",
            status="active",
            propagation_level="deterministic",
            explanation="Om oss-texten skriver deterministiskt company.story.",
            source_path=source,
        ),
        _row(
            step="company",
            answer_path="answers.contact.phone",
            destination="contact.phone",
            source_chain="WizardAnswers → Discovery Resolver → Project Input",
            status="active",
            propagation_level="deterministic",
            explanation="Telefon skriver deterministiskt Project Input contact.phone.",
            source_path=source,
        ),
        _row(
            step="company",
            answer_path="answers.contact.email",
            destination="contact.email",
            source_chain="WizardAnswers → Discovery Resolver → Project Input",
            status="active",
            propagation_level="deterministic",
            explanation="E-post skriver deterministiskt Project Input contact.email.",
            source_path=source,
        ),
        _row(
            step="company",
            answer_path="answers.contact.address",
            destination="contact.addressLines; location.city",
            source_chain="WizardAnswers → Discovery Resolver → Project Input",
            status="active",
            propagation_level="deterministic",
            explanation=(
                "Adress skriver contact.addressLines. Svenskt postnummer kan "
                "även härleda location.city."
            ),
            source_path=source,
        ),
        _row(
            step="company",
            answer_path="answers.contact.openingHours",
            destination="contact.openingHours",
            source_chain="WizardAnswers → Discovery Resolver → Project Input",
            status="active",
            propagation_level="deterministic",
            explanation="Öppettider skriver deterministiskt contact.openingHours.",
            source_path=source,
        ),
        _row(
            step="content",
            answer_path="answers.services",
            destination="services",
            source_chain="WizardAnswers → Discovery Resolver → Project Input",
            status="active",
            propagation_level="deterministic",
            explanation="Tjänster ersätter briefens service-lista deterministiskt.",
            source_path=source,
        ),
    ]


def _prompt_signal_rows() -> list[dict[str, str]]:
    source = _source_paths(WIZARD_PAYLOAD_PATH)
    rows = [
        ("company", "answers.existingSite", "Site Brief prompt signal"),
        ("content", "answers.products", "Site Brief prompt signal"),
        ("content", "answers.menuItems", "Site Brief prompt signal"),
        ("content", "answers.projects", "Site Brief prompt signal"),
        ("content", "answers.team", "Site Brief prompt signal"),
        ("content", "answers.priceTier", "Site Brief prompt signal"),
        ("content", "answers.bookingUrl", "Site Brief prompt signal"),
        ("content", "answers.uniqueSellingPoints", "Site Brief prompt signal"),
        ("content", "answers.cuisineTags", "Site Brief prompt signal"),
        ("content", "answers.dietaryTags", "Site Brief prompt signal"),
        ("story", "answers.historyText", "Site Brief prompt signal"),
        ("story", "answers.visionText", "Site Brief prompt signal"),
        ("story", "answers.contactIntroText", "Site Brief prompt signal"),
        ("pages", "answers.targetAudience", "Site Brief prompt signal"),
        ("brand", "answers.brand.designStyle", "Site Brief prompt signal"),
    ]
    return [
        _row(
            step=step,
            answer_path=answer_path,
            destination=destination,
            source_chain="composeMasterPrompt → briefModel/Site Brief",
            status="active",
            propagation_level="prompt-signal",
            explanation=(
                "Fältet går in som LLM-/Site Brief-signal men saknar "
                "garanterad deterministisk renderer-destination i V1."
            ),
            source_path=source,
        )
        for step, answer_path, destination in rows
    ]


def _asset_rows() -> list[dict[str, str]]:
    source = _source_paths(
        WIZARD_TYPES_PATH,
        DISCOVERY_RESOLVER_PATH,
        PROJECT_INPUT_SCHEMA_PATH,
        BUILD_SITE_PATH,
    )
    return [
        _row(
            step="assets",
            answer_path="answers.assets.logo",
            destination="brand.logo → public/uploads → header/footer",
            source_chain="Discovery Resolver → Project Input brand.logo → build_site.py",
            status="active",
            propagation_level="deterministic",
            explanation="Logotypen kopieras till genererad sajt och renderas i layout.",
            source_path=source,
        ),
        _row(
            step="assets",
            answer_path="answers.assets.heroImage",
            destination="brand.heroImage → public/uploads → hero",
            source_chain="Discovery Resolver → Project Input brand.heroImage → build_site.py",
            status="active",
            propagation_level="deterministic",
            explanation="Hero-bilden kopieras till genererad sajt och renderas i hero.",
            source_path=source,
        ),
        _row(
            step="assets",
            answer_path="answers.assets.gallery",
            destination="gallery → public/uploads → about/gallery placement",
            source_chain="Discovery Resolver → Project Input gallery → build_site.py",
            status="active",
            propagation_level="deterministic",
            explanation="Galleribilder kopieras och kan renderas efter placement.",
            source_path=source,
        ),
    ]


def _brand_rows() -> list[dict[str, str]]:
    source = _source_paths(
        WIZARD_TYPES_PATH,
        DISCOVERY_RESOLVER_PATH,
        PROJECT_INPUT_SCHEMA_PATH,
        BUILD_SITE_PATH,
    )
    return [
        _row(
            step="brand",
            answer_path="answers.brand.toneTags",
            destination="tone.primary; tone.secondary",
            source_chain="Discovery Resolver → Project Input tone",
            status="active",
            propagation_level="downstream-gap",
            explanation=(
                "Tone når Project Input, men slutlig style/codegen-propagation "
                "är känd svaghet i B139/B141-spåret."
            ),
            source_path=source,
        ),
        _row(
            step="brand",
            answer_path="answers.brand.wordsToAvoid",
            destination="tone.avoid",
            source_chain="Discovery Resolver → Project Input tone",
            status="active",
            propagation_level="downstream-gap",
            explanation=(
                "Undvik-ord når Project Input, men färdig output-propagation "
                "är inte fullt styrkt."
            ),
            source_path=source,
        ),
        _row(
            step="brand",
            answer_path="answers.brand.primaryColorHex",
            destination="brand.primaryColorHex",
            source_chain="Discovery Resolver → Project Input brand",
            status="active",
            propagation_level="downstream-gap",
            explanation=(
                "Primärfärgen når Project Input, men CSS/output använder inte "
                "säkert värdet i dag (B140)."
            ),
            source_path=source,
        ),
        _row(
            step="brand",
            answer_path="answers.brand.accentColorHex",
            destination="brand.accentColorHex",
            source_chain="Discovery Resolver → Project Input brand",
            status="active",
            propagation_level="downstream-gap",
            explanation=(
                "Accentfärgen når Project Input, men CSS/output använder inte "
                "säkert värdet i dag (B140)."
            ),
            source_path=source,
        ),
    ]


def _diagnostic_only_rows() -> list[dict[str, str]]:
    return [
        _row(
            step="company",
            answer_path="answers.scrapedFields",
            destination="UI-feedback för auto-ifyllda fält",
            source_chain="Discovery wizard UI",
            status="no-known-destination",
            propagation_level="diagnostic-only",
            explanation=(
                "scrapedFields visar confidence-badges i UI:t och är inte en "
                "generation-signal."
            ),
            source_path=_source_paths(WIZARD_TYPES_PATH),
        )
    ]


def wizard_generation_rows() -> list[dict[str, str]]:
    """Return read-only rows for the Backoffice wizard propagation table."""
    capability_map = load_capability_map()
    rows: list[dict[str, str]] = []
    rows.extend(_taxonomy_rows(capability_map))
    rows.extend(_must_have_rows(capability_map))
    rows.extend(_cta_rows())
    rows.extend(_direct_project_input_rows())
    rows.extend(_prompt_signal_rows())
    rows.extend(_asset_rows())
    rows.extend(_brand_rows())
    rows.extend(_diagnostic_only_rows())
    return rows


def wizard_generation_summary(rows: list[dict[str, str]]) -> dict[str, int]:
    """Return compact counts used by Backoffice metrics."""
    status_counts = Counter(row["status"] for row in rows)
    propagation_counts = Counter(row["propagationLevel"] for row in rows)
    return {
        "total": len(rows),
        "active": status_counts["active"],
        "fallback_or_planned": status_counts["fallback"] + status_counts["planned"],
        "needs_attention": (
            status_counts["gap"]
            + status_counts["unknown"]
            + status_counts["no-known-destination"]
        ),
        "deterministic": propagation_counts["deterministic"],
        "prompt_signal": propagation_counts["prompt-signal"],
        "downstream_gap": propagation_counts["downstream-gap"],
    }
