"""planningModel: produce a Site Plan + Generation Package from a Site Brief.

Single source of truth for Phase 2 Plan. Both ``scripts/build_site.py`` and
``scripts/dev_generate.py`` call into this module so they cannot drift
apart on plan shape or selection logic. Closes ``docs/known-issues.md``
B19, which tracked the parallel-pipeline drift risk.

Calls planningModel via OpenAI structured output when ``OPENAI_API_KEY``
is available. Otherwise returns a deterministic mock plan that still
validates against ``site-plan.schema.json`` and
``generation-package.schema.json``. Project Inputs that pre-pin
``scaffoldId``/``variantId`` skip the LLM altogether and use ``planSource
= 'pinned'``: the operator's explicit choice is authoritative.

Capability filtering follows ``capability-map.v1.json``'s "empty
capability list = gap" principle: a capability with an empty
``dossiers`` list is recorded as ``rejected`` on the Site Plan rather
than silently included in ``selectedDossiers``.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from packages.generation.brief.models import has_openai_api_key
from packages.generation.orchestration.section_treatments import (
    load_section_treatments_catalogue,
)
from packages.policies.component_catalog import SCAFFOLD_STARTER_MAP
from packages.policies.llm_model_params import resolve_role_params, responses_kwargs

from .blueprint import (
    SectionPlanEntry,
    build_generation_blueprint,
    derive_section_plan,
    merge_section_plans,
    resolve_section_plan,
    section_addresses,
)
from .models import resolve_planning_model

logger = logging.getLogger("sajtbyggaren.planning")

REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
STARTERS_DIR = REPO_ROOT / "data" / "starters"
DEFAULT_CAPABILITY_MAP_PATH = (
    REPO_ROOT / "governance" / "policies" / "capability-map.v1.json"
)
DEFAULT_SCAFFOLD_CONTRACT_PATH = (
    REPO_ROOT / "governance" / "policies" / "scaffold-contract.v1.json"
)
DEFAULT_STARTER_REGISTRY_PATH = (
    REPO_ROOT / "governance" / "policies" / "starter-registry.v1.json"
)

DEFAULT_SCAFFOLD_ID = "local-service-business"

# Hardcoded scaffold -> starter mapping for Sprint 2B.
#
# The mapping itself was moved (surgically, ADR 0040 lager 3) to
# ``packages/policies/component_catalog.py`` so the BUILD layer can resolve a
# build's Starter for the Component Catalog gate WITHOUT importing this planning
# module (repo-boundaries: build may import packages/policies, not planning).
# It is re-exported here as ``SCAFFOLD_TO_STARTER`` so every existing
# planning-side reference (planning/__init__.py, backoffice, tests) is
# unchanged - this stays the runtime mapping and the single source of truth.
SCAFFOLD_TO_STARTER: dict[str, str] = SCAFFOLD_STARTER_MAP

# Phase 3 (ADR 0032, originally landed as ADR 0031 on origin/main pre-port;
# renumbered during the B146 port to avoid colliding with jakob-be:s
# ADR 0031 — Steward auto-bump): catalogue of registered section design
# treatments per section-id. Used by the planning prompt so planningModel
# can reason about visual structure when it picks a scaffold/variant.
#
# kor-3a (2026-06-03): this catalogue is no longer a hand-maintained
# Python mirror. It is loaded from the SAME declarative source the build
# dispatcher reads — ``scaffolds/<id>/section-treatments.json`` via the
# shared loader in ``orchestration/section_treatments`` (moved out of
# ``build`` in the Pushvakt P1 boundary fix, 2026-06-03)
# — so the planning prompt and the runtime variant→treatment table
# (``_SECTION_TREATMENTS_BY_VARIANT``) cannot drift apart. The catalogue
# stays an LLM-prompt aid; the JSON files + schema enums are the
# canonical sources. tests/test_section_treatments_prompts.py still
# guards catalogue↔schema↔runtime agreement, and
# tests/test_section_treatments_json_parity.py proves the JSON encodes
# the exact pre-migration values.
_SECTION_TREATMENTS_CATALOGUE: dict[str, list[str]] = (
    load_section_treatments_catalogue()
)


# Heuristic keywords used by the deterministic mock planner to pick
# ecommerce-lite over the default scaffold. Real planningModel does its
# own classification; these signals only fire on the no-key fallback.
_COMMERCE_SIGNALS = (
    "shop",
    "butik",
    "ecommerce",
    "e-commerce",
    "e-handel",
    "webshop",
    "produkt",
    "store",
)


# Heuristic keywords used by the deterministic mock planner to pick
# clinic-healthcare over the default scaffold. Real planningModel does its
# own classification with selection-profile.json embeddingText /
# semanticSignals; these signals only fire on the no-key fallback.
#
# Sharp medical terms only — bare "klinik"/"clinic" is too broad
# (beauty-klinik, hair-klinik, wellness-klinik are explicit negative
# signals in the scaffold's selection-profile.json and belong to
# local-service-business). The list here mirrors the regulated-clinician
# subset of selection-profile.json's semanticSignals while staying
# conservative against false positives on wellness, salon and ecommerce
# briefs (the other three baseline cases in scripts/run_golden_path_eval.py).
#
# B137-precedent: Lane 3 Embeddings audit
# (docs/reports/embedding-readiness-2026-05-25.md) identified this gap as
# the single embeddings-gate blocker — naprapat-stockholm scored 5.83
# (under PASS_CASE_THRESHOLD=6.5) only because the mock fallback routed
# it to local-service-business. Embeddings will eventually replace the
# whole heuristic; until then this list stays the deterministic floor.
#
# Mirrors ``_CLINIC_TOKENS`` in scripts/prompt_to_project_input.py — both
# the prompt-time pinning (pick_scaffold) and the mock plan fallback
# (_pick_scaffold_from_brief) need the same coverage so a clinic prompt
# routes consistently regardless of which path produced the Project Input.
_CLINIC_SIGNALS = (
    "naprapat",
    "naprapath",
    "naprapatklinik",
    "kiropraktor",
    "chiropractor",
    "chiropractic",
    "tandläkar",
    "tandlakar",
    "tandvård",
    "tandvard",
    "dentist",
    "dental",
    "psykolog",
    "psychologist",
    "psykoterapi",
    "psychotherapy",
    "fysioterapi",
    "fysioterapeut",
    "physiotherapy",
    "physiotherapist",
    "sjukgymnast",
    "ortoped",
    "orthopedic",
    "orthopaedic",
    "audionom",
    "podiatrist",
    "optometrist",
    "specialistklinik",
    "veterinärklinik",
    "veterinarklinik",
)


# ---------------------------------------------------------------------------
# Pydantic types
# ---------------------------------------------------------------------------


class RejectedCapability(BaseModel):
    """A requestedCapability planningModel could not honour.

    Either the slug is not in capability-map.v1.json (unknown) or the
    capability has no implemented Dossier yet (gap). The reason string
    is what the operator sees in Backoffice.
    """

    id: str
    reason: str


class PlanningChoice(BaseModel):
    """Structured plan output from planningModel.

    Narrow on purpose: the LLM chooses scaffold/variant + which Dossiers from
    the candidate set to include, and MAY propose ``sectionPlan`` (section-level
    intent). starterId, routePlan and buildSpec are derived deterministically
    from the chosen scaffold after the call so the LLM cannot invent values that
    drift from the on-disk scaffold registry. ``sectionPlan`` entries are
    validated against the scaffold's sections.json (kor-1c); an entry that
    addresses a section the scaffold does not declare is rejected, never
    written. contentBlocks / visualDirection / qualityRisks are derived
    deterministically from the (LLM-or-mock) Site Brief blueprint, not emitted
    here, so the contract is identical with or without an API key.
    """

    scaffoldId: str = Field(description="Must be a registered scaffold with content on disk.")
    variantId: str = Field(description="Must be a variant of the chosen scaffold.")
    selectedDossiers: list[str] = Field(default_factory=list)
    rejectedCapabilities: list[RejectedCapability] = Field(default_factory=list)
    rationale: str = Field(default="")
    sectionPlan: list[SectionPlanEntry] = Field(
        default_factory=list,
        description=(
            "Section-level intent, one entry per '<routeId>.<sectionId>' address. "
            "Each section MUST be one the chosen scaffold declares in sections.json; "
            "unknown sections are rejected. Leave empty if unsure - a deterministic "
            "baseline is always produced."
        ),
    )


class PlanResult(BaseModel):
    """Wrapper that both scripts receive from ``produce_site_plan``.

    Contains the final, schema-validated artefakt dicts plus a truth
    field (``source``) about which code path produced them. Mirrors
    ``BriefResult`` from packages.generation.brief.
    """

    site_plan: dict[str, Any]
    generation_package: dict[str, Any]
    source: str  # "real" | "mock-no-key" | "mock-llm-error" | "pinned"
    error: str | None = None
    attemptedModel: str | None = None


# ---------------------------------------------------------------------------
# Scaffold registry + capability map loaders
# ---------------------------------------------------------------------------


def load_scaffold_registry(
    scaffolds_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Read all scaffolds with content from disk.

    Returns a list of dicts with keys ``id``, ``label``, ``description``,
    ``scaffold`` (raw scaffold.json), ``routes``, ``sections``,
    ``selectionProfile``, ``compatibleDossiers`` and ``variants`` (list
    of variant dicts). Scaffolds that exist as registry placeholders but
    have no ``scaffold.json`` on disk are skipped: planningModel must
    only choose between scaffolds that can actually be built.
    """
    base = scaffolds_dir if scaffolds_dir is not None else SCAFFOLDS_DIR
    registry: list[dict[str, Any]] = []
    if not base.exists():
        return registry
    enabled_by_id = load_scaffold_enabled_map()
    from packages.generation.artifacts import validate_scaffold, validate_sections

    for scaffold_dir in sorted(base.iterdir()):
        if not scaffold_dir.is_dir():
            continue
        scaffold_json = scaffold_dir / "scaffold.json"
        if not scaffold_json.exists():
            continue
        scaffold = _read_json(scaffold_json)
        validate_scaffold(scaffold)
        if enabled_by_id.get(scaffold["id"], True) is False:
            continue
        routes = _read_json_or_default(scaffold_dir / "routes.json", {"defaultRoutes": []})
        sections = _read_json_or_default(scaffold_dir / "sections.json", {})
        if sections:
            validate_sections(sections)
        selection = _read_json_or_default(scaffold_dir / "selection-profile.json", {})
        compatible = _read_json_or_default(
            scaffold_dir / "compatible-dossiers.json",
            {"required": [], "recommended": [], "conditional": []},
        )

        variants_dir = scaffold_dir / "variants"
        variants: list[dict[str, Any]] = []
        if variants_dir.exists():
            for variant_path in sorted(variants_dir.glob("*.json")):
                variants.append(_read_json(variant_path))

        registry.append(
            {
                "id": scaffold["id"],
                "label": scaffold.get("label", scaffold["id"]),
                "description": scaffold.get("description", ""),
                "scaffold": scaffold,
                "routes": routes,
                "sections": sections,
                "selectionProfile": selection,
                "compatibleDossiers": compatible,
                "variants": variants,
            }
        )
    return registry


def _is_enabled(entry: dict[str, Any]) -> bool:
    """Treat missing ``enabled`` as true for backward compatibility."""
    return entry.get("enabled", True) is not False


def load_scaffold_enabled_map(path: Path | None = None) -> dict[str, bool]:
    """Read scaffold enabled-state from scaffold-contract.v1.json."""
    actual = path or DEFAULT_SCAFFOLD_CONTRACT_PATH
    if not actual.exists():
        return {}
    payload = _read_json(actual)
    return {
        entry["id"]: _is_enabled(entry)
        for entry in payload.get("primaryScaffoldRegistry", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def load_starter_registry(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Read starter-registry.v1.json keyed by starter id."""
    actual = path or DEFAULT_STARTER_REGISTRY_PATH
    if not actual.exists():
        return {}
    payload = _read_json(actual)
    return {
        entry["id"]: entry
        for entry in payload.get("starters", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def starter_is_enabled(starter_id: str, registry_path: Path | None = None) -> bool:
    """Return whether a Starter may be used by generation."""
    registry = load_starter_registry(registry_path)
    entry = registry.get(starter_id)
    if entry is None:
        return True
    return _is_enabled(entry)


def _dossier_manifest_path(dossier_id: str, dossiers_dir: Path = DOSSIERS_DIR) -> Path | None:
    for dossier_class in ("soft", "hard"):
        candidate = dossiers_dir / dossier_class / dossier_id / "manifest.json"
        if candidate.exists():
            return candidate
    return None


def dossier_is_enabled(dossier_id: str, dossiers_dir: Path = DOSSIERS_DIR) -> bool:
    """Return whether a Dossier may be selected or mounted."""
    manifest_path = _dossier_manifest_path(dossier_id, dossiers_dir)
    if manifest_path is None:
        return True
    manifest = _read_json(manifest_path)
    return _is_enabled(manifest)


def load_capability_map(path: Path | None = None) -> dict[str, Any]:
    """Read ``governance/policies/capability-map.v1.json``."""
    actual = path or DEFAULT_CAPABILITY_MAP_PATH
    return _read_json(actual)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_or_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return _read_json(path)


# ---------------------------------------------------------------------------
# Capability filtering (the "empty list = gap" rule from capability-map.v1)
# ---------------------------------------------------------------------------


def filter_capabilities(
    requested: list[str],
    capability_map: dict[str, Any],
) -> tuple[list[str], list[RejectedCapability]]:
    """Apply capability-map.v1.principles "empty list = gap, not feature".

    Returns ``(selected_dossier_ids, rejected_capabilities)``. A
    capability whose entry has an empty ``dossiers`` list is recorded as
    rejected with the entry's ``comment`` as the reason. A capability
    not in the map at all is rejected with a generic "unknown" reason.
    """
    selected: list[str] = []
    rejected: list[RejectedCapability] = []
    capabilities = capability_map.get("capabilities", {})
    seen: set[str] = set()
    for cap in requested:
        if cap in seen:
            continue
        seen.add(cap)
        entry = capabilities.get(cap)
        if entry is None:
            rejected.append(
                RejectedCapability(
                    id=cap,
                    reason="Capability not registered in capability-map.v1.json.",
                )
            )
            continue
        dossiers = entry.get("dossiers") or []
        if not dossiers:
            reason = entry.get("comment") or "No Dossier implemented yet for this capability."
            rejected.append(RejectedCapability(id=cap, reason=reason))
            continue
        default = entry.get("default") or dossiers[0]
        if default not in dossiers:
            raise RuntimeError(
                f"Capability {cap!r} has default={default!r} that is not listed in dossiers={dossiers} "
                "in capability-map.v1.json."
            )
        if not dossier_is_enabled(default):
            rejected.append(
                RejectedCapability(
                    id=cap,
                    reason=f"Default Dossier {default!r} is disabled in its manifest.",
                )
            )
            continue
        if default not in selected:
            selected.append(default)
    return selected, rejected


# ---------------------------------------------------------------------------
# Mock planner (deterministic)
# ---------------------------------------------------------------------------


def _pick_scaffold_from_brief(
    site_brief: dict[str, Any],
    registry: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deterministic scaffold selector used in mock fallback paths.

    Picks ``ecommerce-lite`` when commerce signals appear in the brief,
    ``clinic-healthcare`` when sharp medical signals appear (and no
    commerce override fires first), otherwise the default
    ``local-service-business``. Falls back to the first registered
    scaffold if neither preferred scaffold has content.

    Order matters: commerce wins over clinic so a "tandvårdsbutik som
    säljer munhygienprodukter" routes to ecommerce-lite, not
    clinic-healthcare. Real ``planningModel`` (with embeddings retrieval
    eventually) handles the nuance; this fallback only fires in the
    no-key path.
    """
    if not registry:
        raise RuntimeError(
            "Scaffold registry is empty - cannot plan a site without any scaffold "
            "containing scaffold.json on disk."
        )

    business = (site_brief.get("businessTypeGuess") or "").lower()
    services = " ".join(site_brief.get("servicesMentioned") or []).lower()
    raw = (site_brief.get("rawPrompt") or "").lower()
    haystack = f"{business} {services} {raw}"

    chosen_id = DEFAULT_SCAFFOLD_ID
    if any(signal in haystack for signal in _COMMERCE_SIGNALS):
        if any(s["id"] == "ecommerce-lite" for s in registry):
            chosen_id = "ecommerce-lite"
    elif any(signal in haystack for signal in _CLINIC_SIGNALS):
        if any(s["id"] == "clinic-healthcare" for s in registry):
            chosen_id = "clinic-healthcare"

    by_id = {s["id"]: s for s in registry}
    return by_id.get(chosen_id, registry[0])


_DEFAULT_VARIANT_BY_SCAFFOLD: dict[str, str] = {
    "local-service-business": "nordic-trust",
    "ecommerce-lite": "clean-store",
    # ``warm-bistro`` is the safest restaurant default — warm, neighbourhood,
    # works for bistros, brasseries and traditional restaurants without
    # overcommitting to fine-dining (nordic-fine-dining), café-only daytime
    # (casual-cafe) or bar-only after-dark (midnight-bar) signals. Picked by
    # _pick_variant() when the planner has no stronger vibe signal.
    "restaurant-hospitality": "warm-bistro",
    # ``clinic-calm`` is the safest clinic default — bright, soft-blue,
    # works for general dental, primary care, optometry, paediatric.
    # warm-care suits chiropractor / naprapath / holistic; modern-precision
    # suits specialist / fertility / aesthetic medicine.
    "clinic-healthcare": "clinic-calm",
    # ``legal-classic`` is the safest professional-services default —
    # restrained, institutional, works for advokatbyråer, audit firms
    # and traditional advisory practices without overcommitting to the
    # minimalist consulting language (consulting-modern) or the warm
    # accounting language (accounting-trust).
    "professional-services": "legal-classic",
    # ``studio-monochrome`` is the safest agency-studio default —
    # high-contrast, modular, works for design studios and brand
    # studios without committing to the editorial-warm voice or
    # the high-energy bold-electric direction.
    "agency-studio": "studio-monochrome",
}


def _pick_variant(scaffold: dict[str, Any]) -> str:
    variants = [variant for variant in scaffold.get("variants") or [] if _is_enabled(variant)]
    if not variants:
        raise RuntimeError(
            f"Scaffold {scaffold['id']!r} has no enabled variants under variants/. "
            "A scaffold must declare at least one variant for planningModel to pick from."
        )
    scaffold_id = scaffold.get("id")
    preferred_id = (
        _DEFAULT_VARIANT_BY_SCAFFOLD.get(scaffold_id)
        if isinstance(scaffold_id, str)
        else None
    )
    if preferred_id and any(variant.get("id") == preferred_id for variant in variants):
        return preferred_id
    return variants[0]["id"]


def _mock_plan_choice(
    site_brief: dict[str, Any],
    registry: list[dict[str, Any]],
    capability_map: dict[str, Any],
    *,
    rationale_prefix: str = "Mock plan",
) -> tuple[PlanningChoice, dict[str, Any]]:
    """Deterministic mock planner used when no LLM is called.

    Returns the structured choice plus the full scaffold dict so callers
    don't have to look it up again.
    """
    scaffold = _pick_scaffold_from_brief(site_brief, registry)
    variant_id = _pick_variant(scaffold)
    requested = list(site_brief.get("requestedCapabilities") or [])
    selected, rejected = filter_capabilities(requested, capability_map)
    rationale = (
        f"{rationale_prefix}: chose scaffold {scaffold['id']!r} via "
        "deterministic heuristic (commerce signals -> ecommerce-lite, "
        "clinic/healthcare signals -> clinic-healthcare, "
        "otherwise local-service-business)."
    )
    return (
        PlanningChoice(
            scaffoldId=scaffold["id"],
            variantId=variant_id,
            selectedDossiers=selected,
            rejectedCapabilities=rejected,
            rationale=rationale,
        ),
        scaffold,
    )


# ---------------------------------------------------------------------------
# Real planner (planningModel via OpenAI structured output)
# ---------------------------------------------------------------------------


_PLANNING_SYSTEM_INSTRUCTIONS = (
    "You are the planningModel for Sajtbyggaren. You receive a Site Brief and "
    "a Scaffold Registry. Your job is to choose ONE scaffoldId from the registry "
    "and ONE variantId from that scaffold's variants. You also pick which Dossiers "
    "from the candidate set should be selected for this run. Constraints: "
    "(1) scaffoldId MUST be one of the IDs in the registry. "
    "(2) variantId MUST be one of the variant IDs declared for the chosen scaffold. "
    "(3) selectedDossiers MUST only contain Dossier IDs that the capability map "
    "    actually backs with an implementation; never invent IDs. "
    "(4) For any requestedCapability that has no implemented Dossier, return it "
    "    in rejectedCapabilities with a short reason - the operator will decide "
    "    whether to drop the capability or wait for the Dossier to be imported. "
    "(5) Be conservative: if the brief is ambiguous, pick the safest scaffold "
    "    and explain in rationale. "
    # ADR 0032 — section design treatments (Phase 3) awareness
    "(6) directives.sectionTreatments on the Project Input is operator-authoritative. "
    "    If the brief or context indicates the operator has pinned per-section "
    "    treatments, treat them as a fixed visual contract: do not propose a "
    "    scaffold/variant whose registered treatments would conflict with the "
    "    pinned ids, and do not include sectionTreatments in your output - the "
    "    PlanningChoice schema does not carry that field on purpose. The "
    "    Section Design Treatments Catalogue listed in the user message tells "
    "    you which treatments exist per section. Do not invent treatment ids. "
    # kor-1c — section-level intent (sectionPlan)
    "(7) You MAY return sectionPlan: a list of section-level intent entries, one "
    "    per section you want to steer. Each entry's 'section' MUST be a "
    "    '<routeId>.<sectionId>' address from the chosen scaffold's section list "
    "    (shown per scaffold in the user message); never invent a section. Use "
    "    goal/copyIntent/ctaRole to express INTENT (what the section should "
    "    achieve and the angle), not finished customer copy. Entries addressing "
    "    a section the scaffold does not declare are rejected. Leave sectionPlan "
    "    empty if you have nothing specific to add; a deterministic baseline is "
    "    always produced from the Site Brief. "
    # kor-1c-copy — how the rendered copy is composed (honesty)
    "(8) The Generation Package's contentBlocks (hero, the company story, the "
    "    branschnära FAQ and the per-service offer summaries) are composed "
    "    DETERMINISTICALLY from the Site Brief - its positioning "
    "    (oneLiner/differentiator/localAngle), contentStrategy and "
    "    servicesMentioned - so the contract is identical with or without an "
    "    API key. You do not author that copy here; instead make your "
    "    sectionPlan copyIntent for the hero / offer / story / faq sections "
    "    honest and specific so it steers that composition. Never propose copy "
    "    intent that asserts a certification, review, price, contact channel or "
    "    any fact the Site Brief does not state - anything unknown stays a "
    "    qualityRisk, never customer copy, and the raw prompt is never copy."
)


def _build_planning_prompt(
    site_brief: dict[str, Any],
    registry: list[dict[str, Any]],
    capability_map: dict[str, Any],
) -> str:
    """Compose the user message handed to planningModel.

    Includes only what the planner needs: brief signals, the scaffold
    registry summary (id + label + selection-profile blurbs), and the
    capability map (so the model can see which capabilities have a real
    Dossier vs which are gaps).
    """
    scaffold_lines: list[str] = []
    for entry in registry:
        profile = entry.get("selectionProfile") or {}
        variant_ids = [v["id"] for v in entry.get("variants") or []]
        # kor-1c: list the valid '<routeId>.<sectionId>' addresses so the LLM
        # can only steer sections the scaffold actually declares.
        section_addr = sorted(section_addresses(entry))
        scaffold_lines.append(
            f"- id: {entry['id']}\n"
            f"  label: {entry['label']}\n"
            f"  description: {entry.get('description', '')}\n"
            f"  variants: {variant_ids}\n"
            f"  sections: {section_addr}\n"
            f"  embeddingText: {profile.get('embeddingText', '')}\n"
            f"  semanticSignals: {profile.get('semanticSignals', [])}\n"
            f"  negativeSignals: {profile.get('negativeSignals', [])}"
        )

    cap_lines: list[str] = []
    for slug, entry in (capability_map.get("capabilities") or {}).items():
        dossiers = entry.get("dossiers") or []
        status = "implemented" if dossiers else "gap (no Dossier yet)"
        cap_lines.append(
            f"- {slug}: {status}; dossiers={dossiers}; comment={entry.get('comment', '')}"
        )

    # Phase 3 (ADR 0032): tell the LLM which section design treatments
    # exist per section so it can reason about visual structure when
    # picking a scaffold/variant. The LLM does not produce this field —
    # PlanningChoice has no sectionTreatments slot — but it must avoid
    # routing a brief that pinned a specific treatment to a variant
    # whose registered default would silently override it.
    treatment_lines = [
        f"- {section_id}: {sorted(treatment_ids)}"
        for section_id, treatment_ids in sorted(_SECTION_TREATMENTS_CATALOGUE.items())
    ]

    return (
        "Site Brief (JSON):\n"
        f"{json.dumps(site_brief, ensure_ascii=False, indent=2)}\n\n"
        "Scaffold Registry (only on-disk scaffolds are listed):\n"
        + "\n".join(scaffold_lines)
        + "\n\nCapability Map (capability-map.v1):\n"
        + "\n".join(cap_lines)
        + "\n\nSection Design Treatments Catalogue (ADR 0032 — read-only):\n"
        + "\n".join(treatment_lines)
        + "\n\nReminder: directives.sectionTreatments on the Project Input is "
        "operator-pin only. Treatments above are the registered ids per "
        "section; never invent new ones."
    )


def _real_plan_choice(
    site_brief: dict[str, Any],
    registry: list[dict[str, Any]],
    capability_map: dict[str, Any],
    *,
    model: str,
) -> tuple[PlanningChoice, dict[str, Any]]:
    """Call planningModel via OpenAI structured output. Requires OPENAI_API_KEY.

    Validates the LLM's choice against the registry: scaffoldId must
    exist on disk and variantId must be declared for that scaffold. A
    drifted choice raises so the caller can fall back to mock instead of
    writing a Site Plan that points at non-existent files.
    """
    from openai import OpenAI

    client = OpenAI()
    user_message = _build_planning_prompt(site_brief, registry, capability_map)

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": _PLANNING_SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_message},
        ],
        text_format=PlanningChoice,
        **responses_kwargs(resolve_role_params("planningModel")),
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("planningModel returned no structured output")

    by_id = {entry["id"]: entry for entry in registry}
    scaffold = by_id.get(parsed.scaffoldId)
    if scaffold is None:
        raise RuntimeError(
            f"planningModel picked scaffoldId={parsed.scaffoldId!r} but it is "
            "not in the on-disk scaffold registry."
        )
    variant_ids = {v["id"] for v in scaffold.get("variants") or []}
    if parsed.variantId not in variant_ids:
        raise RuntimeError(
            f"planningModel picked variantId={parsed.variantId!r} but scaffold "
            f"{scaffold['id']!r} only declares variants {sorted(variant_ids)}."
        )

    # Re-apply the capability filter on top of the LLM's selection so a
    # hallucinated Dossier ID can never reach selectedDossiers.
    requested = list(site_brief.get("requestedCapabilities") or [])
    safe_selected, derived_rejected = filter_capabilities(requested, capability_map)
    safe_selected_set = set(safe_selected)
    final_selected = [d for d in parsed.selectedDossiers if d in safe_selected_set]
    # Anything the LLM dropped that we computed as safe is fine; anything
    # the LLM added that is not in safe_selected is silently filtered.

    final_rejected = list(parsed.rejectedCapabilities)
    rejected_ids = {r.id for r in final_rejected}
    for derived in derived_rejected:
        if derived.id not in rejected_ids:
            final_rejected.append(derived)

    parsed.selectedDossiers = final_selected
    parsed.rejectedCapabilities = final_rejected
    return parsed, scaffold


# ---------------------------------------------------------------------------
# Site Plan + Generation Package assembly
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _route_plan_from_scaffold(scaffold: dict[str, Any]) -> list[dict[str, str]]:
    routes = scaffold.get("routes") or {}
    defaults = routes.get("defaultRoutes") or []
    return [
        {"id": r["id"], "path": r["path"], "purpose": r["purpose"]}
        for r in defaults
    ]


_MINIMUM_RUNNABLE_ROUTE_COUNT = 2
_PAGE_COUNT_VALID_RANGE = range(1, 11)  # 1-10 inclusive


def _trim_route_plan(
    route_plan: list[dict[str, str]],
    page_count: int | None,
) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    """Trim route_plan to honour ``brief.pageCount`` (B138).

    Rules:
      * ``page_count`` outside 1-10 (None, int below 1, int above 10) →
        no trim, no warning. Defensive against briefModel halucinations.
      * ``page_count`` >= scaffold defaults → no trim, no warning.
      * ``home`` + ``contact`` routes are never dropped (identified by id;
        falls back to first/last route if those ids are missing).
      * Minimum runnable set is 2 (home + contact). ``page_count`` < 2 is
        clamped to 2 with ``reason="below-minimum-keeping-default"``.
      * Middle slots are filled in scaffold default order.

    Returns ``(possibly_trimmed_route_plan, optional_warning_dict)``.
    """
    if not isinstance(page_count, int):
        return route_plan, None
    if isinstance(page_count, bool):
        # bool is a subclass of int; reject defensively.
        return route_plan, None
    if page_count not in _PAGE_COUNT_VALID_RANGE:
        return route_plan, None

    default_count = len(route_plan)
    if default_count == 0:
        return route_plan, None
    if page_count >= default_count:
        return route_plan, None

    home_idx = next(
        (i for i, r in enumerate(route_plan) if r.get("id") == "home"),
        None,
    )
    contact_idx = next(
        (i for i, r in enumerate(route_plan) if r.get("id") == "contact"),
        None,
    )
    # Defensive fallback: if scaffold lacks canonical home/contact IDs,
    # treat first/last route as the anchor pair so trim still produces a
    # sensible 2-route minimum.
    if home_idx is None:
        home_idx = 0
    if contact_idx is None or contact_idx == home_idx:
        contact_idx = default_count - 1 if default_count > 1 else None

    effective_count = max(page_count, _MINIMUM_RUNNABLE_ROUTE_COUNT)
    keep_idx: list[int] = [home_idx]
    if contact_idx is not None and contact_idx != home_idx:
        seats_for_middle = effective_count - 2
        middle_candidates = [
            i
            for i in range(default_count)
            if i != home_idx and i != contact_idx
        ]
        if seats_for_middle > 0:
            keep_idx.extend(middle_candidates[:seats_for_middle])
        keep_idx.append(contact_idx)
    else:
        # Single-route scaffold (rare). Nothing to trim further.
        return route_plan, None

    keep_idx_sorted = sorted(set(keep_idx))
    trimmed = [route_plan[i] for i in keep_idx_sorted]

    reason = (
        "below-minimum-keeping-default"
        if page_count < _MINIMUM_RUNNABLE_ROUTE_COUNT
        else "trimmed-to-brief-page-count"
    )
    warning: dict[str, Any] = {
        "requestedPageCount": page_count,
        "scaffoldDefaultCount": default_count,
        "emittedRouteCount": len(trimmed),
        "reason": reason,
    }
    return trimmed, warning


_PAGE_TO_ROUTE_HINT: dict[str, str] = {
    "Om oss / Om mig": "/om-oss",
    "Bokning online": "/bokning",
    "Priser och paket": "/priser",
    "Bildgalleri": "/galleri",
    "Karta / Hitta hit": "/karta",
    "Blogg / Nyheter": "/blogg",
    "FAQ": "/faq",
    "Vårt team": "/team",
    "Portfolio / Case": "/portfolio",
    "Nyhetsbrev": "/nyhetsbrev",
}


# Wizard pages that the deterministic Builder can emit as real routes
# without introducing new integration layers (no booking, payments,
# auth, newsletter). Each entry maps a wizard mustHave label to a route
# definition that ``write_pages`` knows how to render. Restricted to a
# small set of scaffolds today (only ``local-service-business``) so the
# expansion lands incrementally; ecommerce-lite and future scaffolds
# need their own renderer review before opting in.
_WIZARD_ROUTE_DEFINITIONS: dict[str, dict[str, str]] = {
    "FAQ": {
        "id": "faq",
        "path": "/faq",
        "purpose": (
            "Answer recurring customer questions in a single readable "
            "page so visitors do not need to call to clarify basics."
        ),
    },
    "Bildgalleri": {
        "id": "gallery",
        "path": "/galleri",
        "purpose": (
            "Showcase project photos uploaded by the operator so "
            "visitors can see real work before contacting."
        ),
    },
    "Karta / Hitta hit": {
        "id": "map",
        "path": "/karta",
        "purpose": (
            "Show address, service area and a static map link so "
            "local visitors can find or navigate to the business."
        ),
    },
    "Vårt team": {
        "id": "team",
        "path": "/team",
        "purpose": (
            "Introduce the team members and their roles to build "
            "trust before the visitor takes the contact step."
        ),
    },
    "Priser och paket": {
        "id": "pricing",
        "path": "/priser",
        "purpose": (
            "List packages, price ranges or hourly rates so visitors "
            "know what to expect before requesting a quote."
        ),
    },
    "Portfolio / Case": {
        "id": "portfolio",
        "path": "/portfolio",
        "purpose": (
            "Showcase completed work as named cases so visitors can "
            "judge quality and relevance to their own need."
        ),
    },
}


# Scaffolds whose renderer set in ``scripts/build_site.py`` can mount
# the wizard-driven extras above. New scaffolds opt in explicitly when
# the corresponding render_* helpers exist.
_WIZARD_ROUTE_SCAFFOLDS: frozenset[str] = frozenset({"local-service-business"})


# Wizard pages that intentionally stay warning-only because emitting
# a route would require a real integration layer that the deterministic
# Builder does not have today. Each entry carries the reason text shown
# in ``pageIntentWarnings``; the path hint in ``_PAGE_TO_ROUTE_HINT`` is
# what an operator would expect a future integration to land at.
_WIZARD_ROUTE_UNSUPPORTED_REASONS: dict[str, str] = {
    "Bokning online": (
        "Wizard must-have page Bokning online requires a real "
        "booking integration; deterministic Builder emits no fake "
        "booking surface in v1."
    ),
    "Blogg / Nyheter": (
        "Wizard must-have page Blogg / Nyheter requires editorial "
        "tooling (CMS or markdown ingest); not in deterministic "
        "Builder v1."
    ),
    "Nyhetsbrev": (
        "Wizard must-have page Nyhetsbrev requires a newsletter "
        "integration (signup + provider); not in deterministic "
        "Builder v1."
    ),
}


# ---------------------------------------------------------------------------
# Read-only public accessors for Backoffice diagnostics
# ---------------------------------------------------------------------------
#
# Backoffice diagnostics need to verify that every wizard ``mustHave``
# option in ``apps/viewser/components/discovery-wizard/wizard-constants.ts``
# has a known destination (wizard-extra route, scaffold default, warning
# reason, or capability mapping). These helpers expose immutable copies of
# the private mapping tables so the diagnostic does not import private
# underscore-prefixed names. Runtime planning code keeps using the
# private constants directly.


def get_wizard_route_definitions() -> dict[str, dict[str, str]]:
    """Read-only copy of wizard ``mustHave`` -> route definition mapping.

    These are the wizard must-have labels that ``_wizard_extra_routes``
    can emit as real routes (``id``/``path``/``purpose``) for scaffolds
    listed in :func:`get_wizard_route_scaffolds`.
    """
    return {page: dict(definition) for page, definition in _WIZARD_ROUTE_DEFINITIONS.items()}


def get_wizard_route_scaffolds() -> frozenset[str]:
    """Read-only set of scaffold ids that opt in to wizard route emission.

    Other scaffolds keep warning-shape via ``pageIntentWarnings`` for the
    same wizard labels until their renderer set is reviewed.
    """
    return _WIZARD_ROUTE_SCAFFOLDS


def get_wizard_route_unsupported_reasons() -> dict[str, str]:
    """Read-only copy of wizard ``mustHave`` -> ``pageIntentWarnings`` reason map.

    These wizard labels intentionally stay warning-only because emitting
    a route would require a real integration layer (booking, CMS,
    newsletter) the deterministic Builder does not have in v1.
    """
    return dict(_WIZARD_ROUTE_UNSUPPORTED_REASONS)


def get_page_to_route_hint_mapping() -> dict[str, str]:
    """Read-only copy of wizard ``mustHave`` -> expected route path hint.

    Used by ``_page_intent_warnings`` to decide which scaffold-default
    paths a wizard label is competing against, and by Backoffice
    diagnostics to surface route hints next to the warning reason.
    """
    return dict(_PAGE_TO_ROUTE_HINT)


def _insert_wizard_extras_before_contact(
    scaffold_routes: list[dict[str, str]],
    wizard_extras: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Compose the final routePlan with wizard extras sitting before
    the contact route.

    Keeping ``/kontakt`` (or whatever path the scaffold maps the
    contact id to) at the end of the routePlan matches both visitor
    intuition and the nav layout produced by
    ``scripts.build_site._nav_items_from_scaffold``. When no contact
    route is present the extras are appended at the tail so the
    function never silently drops them.
    """
    if not wizard_extras:
        return list(scaffold_routes)
    contact_idx = next(
        (i for i, route in enumerate(scaffold_routes) if route.get("id") == "contact"),
        None,
    )
    if contact_idx is None:
        return list(scaffold_routes) + list(wizard_extras)
    return (
        list(scaffold_routes[:contact_idx])
        + list(wizard_extras)
        + list(scaffold_routes[contact_idx:])
    )


def _wizard_extra_routes(
    scaffold_id: str | None,
    wizard_must_have: list[str] | None,
    scaffold_default_paths: set[str],
) -> list[dict[str, str]]:
    """Return wizard-driven route entries to append to the routePlan.

    The deterministic Builder only emits these for scaffolds in
    ``_WIZARD_ROUTE_SCAFFOLDS``. Routes whose path already exists in
    the scaffold defaults are skipped silently so trimming
    ``brief.pageCount`` cannot accidentally collide with a wizard
    extra. Order follows the operator's mustHave order so the route
    list reflects the wizard intent rather than a hash-sorted set.
    """
    if not wizard_must_have or scaffold_id not in _WIZARD_ROUTE_SCAFFOLDS:
        return []
    seen_paths: set[str] = set()
    extras: list[dict[str, str]] = []
    for page in wizard_must_have:
        route_def = _WIZARD_ROUTE_DEFINITIONS.get(page)
        if route_def is None:
            continue
        path = route_def["path"]
        if path in scaffold_default_paths or path in seen_paths:
            continue
        extras.append(dict(route_def))
        seen_paths.add(path)
    return extras


def _pages_not_in_routes(
    wizard_must_have: list[str],
    routes: list[dict[str, Any]],
) -> list[str]:
    """Return route-bearing wizard pages missing from the route plan.

    A page is "missing" when the wizard mustHave entry maps to a path
    in ``_PAGE_TO_ROUTE_HINT`` that does not appear in the supplied
    ``routes`` (scaffold defaults + wizard extras combined). Wizard
    extras that ``_wizard_extra_routes`` emitted as real routes are
    therefore filtered out here automatically.
    """
    route_paths = {
        route.get("path")
        for route in routes
        if isinstance(route, dict) and isinstance(route.get("path"), str)
    }
    missing: list[str] = []
    seen: set[str] = set()
    for page in wizard_must_have:
        route_hint = _PAGE_TO_ROUTE_HINT.get(page)
        if route_hint is None or route_hint in route_paths or page in seen:
            continue
        missing.append(page)
        seen.add(page)
    return missing


def _page_intent_warnings(
    wizard_must_have: list[str] | None,
    routes: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Render non-blocking warnings for wizard page intent route gaps.

    Pages that ``_wizard_extra_routes`` emitted as real routes are
    filtered out via ``_pages_not_in_routes``. Pages in
    ``_WIZARD_ROUTE_UNSUPPORTED_REASONS`` keep their specific reason
    string so the operator can tell "no integration yet" apart from
    "scaffold simply does not have this surface".
    """
    if not wizard_must_have:
        return []
    default_reason = (
        "Wizard must-have page is not emitted by the selected "
        "scaffold route plan."
    )
    warnings: list[dict[str, str]] = []
    for page in _pages_not_in_routes(wizard_must_have, routes):
        warnings.append(
            {
                "page": page,
                "expectedPath": _PAGE_TO_ROUTE_HINT[page],
                "reason": _WIZARD_ROUTE_UNSUPPORTED_REASONS.get(
                    page, default_reason
                ),
            }
        )
    return warnings


def _selected_dossiers_payload(
    choice: PlanningChoice,
) -> list[str] | dict[str, Any]:
    """Render selectedDossiers as the array form when there is nothing to
    explain, otherwise as the object form so rationale + rejected[] survive.

    The site-plan schema accepts both via oneOf. The object form is used
    whenever planningModel produced a rationale or rejected anything,
    because that signal is operator-relevant - dropping it would silently
    erase the gap report.
    """
    if not choice.rationale and not choice.rejectedCapabilities:
        return list(choice.selectedDossiers)
    return {
        "required": [],
        "recommended": list(choice.selectedDossiers),
        "conditional": [],
        "rationale": choice.rationale,
        "rejected": [r.model_dump() for r in choice.rejectedCapabilities],
    }


def _resolve_starter_id(scaffold_id: str) -> str:
    starter = SCAFFOLD_TO_STARTER.get(scaffold_id)
    if starter is None:
        raise RuntimeError(
            f"No starter mapping registered for scaffoldId={scaffold_id!r}. "
            "Add it to SCAFFOLD_TO_STARTER in packages/generation/planning/plan.py "
            "or register the matching starter under data/starters/."
        )
    if not starter_is_enabled(starter):
        raise RuntimeError(
            f"Starter {starter!r} for scaffoldId={scaffold_id!r} is disabled "
            "in starter-registry.v1.json."
        )
    return starter


def merge_operator_selected_with_helper(
    operator: dict[str, Any] | list[str] | None,
    helper_payload: list[str] | dict[str, Any],
) -> list[str] | dict[str, Any]:
    """Merge Project Input selectedDossiers with helper output.

    Strategy:
      - operator=None -> helper is authoritative.
      - operator=list -> keep operator list as selected IDs, but if helper has
        rejected/rationale, convert to object form so gap reporting survives.
      - operator=dict -> operator owns required/recommended/conditional/rationale
        while helper-reported rejected[] is appended (deduped by id).

    This preserves operator intent without silently discarding capability gaps
    detected by ``filter_capabilities``.
    """
    if operator is None:
        return helper_payload

    helper_obj = helper_payload if isinstance(helper_payload, dict) else {}
    helper_rejected = helper_obj.get("rejected", []) if isinstance(helper_obj, dict) else []
    helper_rationale = helper_obj.get("rationale") if isinstance(helper_obj, dict) else None

    if isinstance(operator, list):
        if not helper_rejected and not helper_rationale:
            return list(operator)
        return {
            "required": [],
            "recommended": list(operator),
            "conditional": [],
            "rationale": helper_rationale or "Merged operator-selected dossiers with helper gap report.",
            "rejected": list(helper_rejected),
        }

    if not isinstance(operator, dict):
        return helper_payload

    merged: dict[str, Any] = dict(operator)
    merged["required"] = list(operator.get("required", [])) if isinstance(operator.get("required"), list) else []
    merged["recommended"] = list(operator.get("recommended", [])) if isinstance(operator.get("recommended"), list) else []
    merged["conditional"] = list(operator.get("conditional", [])) if isinstance(operator.get("conditional"), list) else []

    rejected_by_id: dict[str, dict[str, Any]] = {}
    for item in operator.get("rejected", []) if isinstance(operator.get("rejected"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            rejected_by_id[item["id"]] = item
    for item in helper_rejected:
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] not in rejected_by_id:
            rejected_by_id[item["id"]] = item
    if rejected_by_id:
        merged["rejected"] = list(rejected_by_id.values())

    if not merged.get("rationale"):
        merged["rationale"] = helper_rationale or "Merged operator-selected dossiers with helper gap report."
    return merged


def _assemble_site_plan(
    *,
    run_id: str,
    choice: PlanningChoice,
    scaffold: dict[str, Any],
    starter_id: str,
    plan_source: str,
    plan_error: str | None,
    model_used: str,
    verification_policy: str,
    preview_runtime: str,
    created_at: str,
    page_intent_warnings: list[dict[str, str]],
    route_plan: list[dict[str, str]] | None = None,
    page_count_warning: dict[str, Any] | None = None,
    intent_guard_warnings: list[dict[str, str]] | None = None,
    section_plan: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if route_plan is None:
        route_plan = _route_plan_from_scaffold(scaffold)
    site_plan: dict[str, Any] = {
        "runId": run_id,
        "scaffoldId": choice.scaffoldId,
        "variantId": choice.variantId,
        "starterId": starter_id,
        "routePlan": route_plan,
        "pageIntentWarnings": page_intent_warnings,
        "selectedDossiers": _selected_dossiers_payload(choice),
        "buildSpec": {
            "qualityTarget": 9.0,
            "verificationPolicy": verification_policy,
            "previewRuntime": preview_runtime,
        },
        "sourceModelRole": "planningModel",
        "modelUsed": model_used,
        "planSource": plan_source,
        "planError": plan_error,
        "createdAt": created_at,
    }
    if page_count_warning is not None:
        site_plan["pageCountWarning"] = page_count_warning
    if intent_guard_warnings:
        # Empty list intentionally omitted from the schema-required keys so
        # legacy consumers do not need to treat "no warnings" as a new field.
        site_plan["intentGuardWarnings"] = list(intent_guard_warnings)
    if section_plan:
        # kor-1c blueprint: section-level intent keyed by '<routeId>.<sectionId>'.
        # Optional + additive; omitted entirely when empty so legacy runs are
        # byte-identical until the blueprint actually carries content.
        site_plan["sectionPlan"] = section_plan
    scaffold_version = (scaffold.get("scaffold") or {}).get("version")
    if isinstance(scaffold_version, str) and scaffold_version:
        site_plan["scaffoldVersion"] = scaffold_version
    return site_plan


def _assemble_generation_package(
    *,
    run_id: str,
    choice: PlanningChoice,
    starter_id: str,
    site_brief: dict[str, Any],
    engine_mode: str,
    project_id: str | None,
    created_at: str,
    scaffold: dict[str, Any] | None = None,
    route_plan: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    package: dict[str, Any] = {
        "runId": run_id,
        "policyVersions": {
            "engineRun": "engine-run.v1",
            "namingDictionary": "naming-dictionary.v1",
            "scaffoldContract": "scaffold-contract.v1",
            "capabilityMap": "capability-map.v1",
            "llmModels": "llm-models.v1",
        },
        "siteBriefRef": "site-brief.json",
        "sitePlanRef": "site-plan.json",
        "scaffoldId": choice.scaffoldId,
        "variantId": choice.variantId,
        "starterId": starter_id,
        "language": site_brief["language"],
        "engineMode": engine_mode,
        "createdAt": created_at,
    }
    if project_id is not None:
        package["projectId"] = project_id
    elif engine_mode == "followup":
        raise RuntimeError(
            "engine_mode='followup' requires a projectId; got None."
        )
    # kor-1c blueprint: the actual work order the renderer consumes in kor-2.
    # contentBlocks / visualDirection / qualityRisks are derived deterministically
    # from the (LLM-or-mock) Site Brief blueprint + the scaffold's sections.json,
    # so the contract is identical with or without an API key. Each is additive
    # and only emitted when it has content.
    if scaffold is not None:
        blueprint = build_generation_blueprint(
            site_brief,
            scaffold,
            route_plan or _route_plan_from_scaffold(scaffold),
            section_treatments_catalogue=_SECTION_TREATMENTS_CATALOGUE,
        )
        package.update(blueprint)
    return package


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def produce_site_plan(
    site_brief: dict[str, Any],
    *,
    run_id: str,
    pinned: dict[str, str] | None = None,
    wizard_must_have: list[str] | None = None,
    capability_map: dict[str, Any] | None = None,
    scaffold_registry: list[dict[str, Any]] | None = None,
    model: str | None = None,
    engine_mode: str = "init",
    project_id: str | None = None,
    verification_policy: str | None = None,
    preview_runtime: str = "local",
    intent_guard_warnings: list[dict[str, str]] | None = None,
) -> PlanResult:
    """Phase 2 Plan entry point. Single source of truth for both scripts.

    Selection logic:

    * ``pinned`` (Project Input pre-selected scaffold/variant): the
      operator's choice is authoritative. planningModel is NOT called.
      Capability filtering still runs so contact-form / payments etc.
      are honestly recorded as gaps when no Dossier exists.
      ``planSource = 'pinned'``.
    * ``OPENAI_API_KEY`` set: call planningModel via structured output
      (``PlanningChoice``). Validate the LLM's scaffoldId/variantId
      against the on-disk registry. ``planSource = 'real'`` on success
      or ``'mock-llm-error'`` on any exception.
    * No ``OPENAI_API_KEY``: deterministic mock that picks
      ecommerce-lite when commerce signals appear in the brief,
      otherwise the default local-service-business.
      ``planSource = 'mock-no-key'``.

    The returned ``PlanResult`` contains schema-validated dicts ready
    for both scripts to write to ``data/runs/<runId>/site-plan.json``
    and ``generation-package.json``.
    """
    from packages.generation.artifacts import (
        validate_generation_package,
        validate_site_plan,
    )

    registry = (
        scaffold_registry
        if scaffold_registry is not None
        else load_scaffold_registry()
    )
    cap_map = capability_map if capability_map is not None else load_capability_map()

    plan_error: str | None = None
    attempted_model: str | None = None

    if pinned is not None:
        choice, scaffold = _resolve_pinned_choice(pinned, registry, site_brief, cap_map)
        plan_source = "pinned"
        model_used = "mock"
    elif not has_openai_api_key():
        choice, scaffold = _mock_plan_choice(
            site_brief,
            registry,
            cap_map,
            rationale_prefix="Mock plan (no OPENAI_API_KEY)",
        )
        plan_source = "mock-no-key"
        model_used = "mock"
    else:
        attempted_model = model or resolve_planning_model()
        try:
            choice, scaffold = _real_plan_choice(
                site_brief,
                registry,
                cap_map,
                model=attempted_model,
            )
            plan_source = "real"
            model_used = attempted_model
        except Exception as exc:  # noqa: BLE001
            plan_error = f"{type(exc).__name__}: {exc}"
            sys.stderr.write(
                f"[planningModel] error: {plan_error} - falling back to mock plan\n"
            )
            sys.stderr.flush()
            logger.warning("planningModel failed: %s", plan_error)
            choice, scaffold = _mock_plan_choice(
                site_brief,
                registry,
                cap_map,
                rationale_prefix=f"Mock plan after planningModel error ({plan_error})",
            )
            plan_source = "mock-llm-error"
            model_used = "mock"

    starter_id = _resolve_starter_id(choice.scaffoldId)

    if pinned is not None:
        # Builder honors Project Input's starter pin too if present.
        starter_id = pinned.get("starterId", starter_id)

    if verification_policy is None:
        # Builder runs npm install + npm run build, so it needs the strict
        # gate. dev_generate.py is mock-only: 'fast' is the honest label.
        verification_policy = "build-must-pass" if pinned is not None else "fast"

    created_at = _utc_now_iso()
    raw_route_plan = _route_plan_from_scaffold(scaffold)
    # B138: respect brief.pageCount when emitting routes. Trim runs for
    # both pinned and helper-chosen scaffolds; warning surfaces in the
    # site-plan so operator/Backoffice can see why the count diverged.
    # The trim only touches scaffold defaults; wizard-driven extras
    # below are operator-explicit choices and stay outside the trim so
    # a low brief.pageCount cannot silently delete a must-have page.
    page_count_value = site_brief.get("pageCount")
    trimmed_route_plan, page_count_warning = _trim_route_plan(
        raw_route_plan, page_count_value
    )
    scaffold_default_paths = {
        route["path"]
        for route in trimmed_route_plan
        if isinstance(route, dict) and isinstance(route.get("path"), str)
    }
    wizard_extra_routes = _wizard_extra_routes(
        choice.scaffoldId,
        wizard_must_have,
        scaffold_default_paths,
    )
    full_route_plan = _insert_wizard_extras_before_contact(
        trimmed_route_plan, wizard_extra_routes
    )

    # kor-1c blueprint: derive section-level intent from the (LLM-or-mock) Site
    # Brief blueprint, then overlay any sectionPlan planningModel proposed. The
    # resolver rejects addresses the chosen scaffold's sections.json does not
    # declare - the same rail used for dossiers. The deterministic baseline
    # guarantees a usable sectionPlan in every path (mock, pinned, real).
    section_plan = derive_section_plan(site_brief, scaffold, full_route_plan)
    resolved_section_plan, rejected_sections = resolve_section_plan(
        choice.sectionPlan, scaffold
    )
    if rejected_sections:
        logger.warning(
            "planningModel proposed sectionPlan addresses not in %r sections.json: %s",
            choice.scaffoldId,
            rejected_sections,
        )
    section_plan = merge_section_plans(section_plan, resolved_section_plan)

    site_plan = _assemble_site_plan(
        run_id=run_id,
        choice=choice,
        scaffold=scaffold,
        starter_id=starter_id,
        plan_source=plan_source,
        plan_error=plan_error,
        model_used=model_used,
        verification_policy=verification_policy,
        preview_runtime=preview_runtime,
        created_at=created_at,
        page_intent_warnings=_page_intent_warnings(
            wizard_must_have,
            full_route_plan,
        ),
        route_plan=full_route_plan,
        page_count_warning=page_count_warning,
        intent_guard_warnings=intent_guard_warnings,
        section_plan=section_plan,
    )
    validate_site_plan(site_plan)

    generation_package = _assemble_generation_package(
        run_id=run_id,
        choice=choice,
        starter_id=starter_id,
        site_brief=site_brief,
        engine_mode=engine_mode,
        project_id=project_id,
        created_at=created_at,
        scaffold=scaffold,
        route_plan=full_route_plan,
    )
    validate_generation_package(generation_package)

    return PlanResult(
        site_plan=site_plan,
        generation_package=generation_package,
        source=plan_source,
        error=plan_error,
        attemptedModel=attempted_model,
    )


def _resolve_pinned_choice(
    pinned: dict[str, str],
    registry: list[dict[str, Any]],
    site_brief: dict[str, Any],
    capability_map: dict[str, Any],
) -> tuple[PlanningChoice, dict[str, Any]]:
    """Honor a Project Input's scaffoldId/variantId pin while still running
    the capability filter so gaps are recorded honestly.

    Validates that the pinned scaffold actually exists on disk and that
    the pinned variant is one of its declared variants - otherwise a
    typo in a Project Input would silently produce a Site Plan that
    points at non-existent files.
    """
    scaffold_id = pinned["scaffoldId"]
    variant_id = pinned["variantId"]
    by_id = {entry["id"]: entry for entry in registry}
    scaffold = by_id.get(scaffold_id)
    if scaffold is None:
        if load_scaffold_enabled_map().get(scaffold_id) is False:
            raise RuntimeError(
                f"Project Input pins scaffoldId={scaffold_id!r} but that Scaffold "
                "is disabled in scaffold-contract.v1.json."
            )
        raise RuntimeError(
            f"Project Input pins scaffoldId={scaffold_id!r} but no scaffold "
            f"with that id has scaffold.json on disk under {SCAFFOLDS_DIR}."
        )
    variant_ids = {v["id"] for v in scaffold.get("variants") or []}
    if variant_id not in variant_ids:
        raise RuntimeError(
            f"Project Input pins variantId={variant_id!r} but scaffold "
            f"{scaffold_id!r} only declares variants {sorted(variant_ids)}."
        )
    pinned_starter = pinned.get("starterId")
    if pinned_starter is not None:
        if not isinstance(pinned_starter, str) or not pinned_starter.strip():
            raise RuntimeError(
                f"Project Input pins starterId={pinned_starter!r} but starterId must be a non-empty string."
            )
        starter_path = STARTERS_DIR / pinned_starter
        if not starter_path.exists():
            raise RuntimeError(
                f"Project Input pins starterId={pinned_starter!r} but no starter exists at {starter_path}."
            )
        expected_starter = _resolve_starter_id(scaffold_id)
        if pinned_starter != expected_starter:
            raise RuntimeError(
                f"Project Input pins starterId={pinned_starter!r} for scaffoldId={scaffold_id!r}, "
                f"but Sprint 2B mapping expects {expected_starter!r}. "
                "Update SCAFFOLD_TO_STARTER first if this remapping is intentional."
            )

    requested = list(site_brief.get("requestedCapabilities") or [])
    selected, rejected = filter_capabilities(requested, capability_map)
    rationale = (
        f"Pinned by Project Input: scaffold={scaffold_id!r} variant={variant_id!r}. "
        "Capabilities filtered through capability-map.v1; rejected entries are "
        "real gaps awaiting Dossier import."
    )
    return (
        PlanningChoice(
            scaffoldId=scaffold_id,
            variantId=variant_id,
            selectedDossiers=selected,
            rejectedCapabilities=rejected,
            rationale=rationale,
        ),
        scaffold,
    )
