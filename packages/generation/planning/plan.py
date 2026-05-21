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
# ``marketing-base`` covers the local-service-business chrome and is the
# only starter wired into ``_REAL_CODEGEN_STARTERS`` in
# packages/generation/codegen/codegen.py (see ADR 0017). ``commerce-base``
# was vendored in PR #16 (ADR 0018, vendor-only checkpoint) and the
# runtime mapping ``ecommerce-lite -> commerce-base`` was activated in
# B20 step 2 per ADR 0019; ecommerce-lite runs through the
# deterministic-v1 codegen path until real-codegen scope is widened in
# a follow-up sprint with its own ADR extension on top of 0017.
SCAFFOLD_TO_STARTER: dict[str, str] = {
    "local-service-business": "marketing-base",
    "ecommerce-lite": "commerce-base",
}

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

    Narrow on purpose: the LLM only chooses scaffold/variant + which
    Dossiers from the candidate set to include. starterId, routePlan and
    buildSpec are derived deterministically from the chosen scaffold
    after the call so the LLM cannot invent values that drift from the
    on-disk scaffold registry.
    """

    scaffoldId: str = Field(description="Must be a registered scaffold with content on disk.")
    variantId: str = Field(description="Must be a variant of the chosen scaffold.")
    selectedDossiers: list[str] = Field(default_factory=list)
    rejectedCapabilities: list[RejectedCapability] = Field(default_factory=list)
    rationale: str = Field(default="")


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
    otherwise the default ``local-service-business``. Falls back to the
    first registered scaffold if neither preferred scaffold has content.
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

    by_id = {s["id"]: s for s in registry}
    return by_id.get(chosen_id, registry[0])


_DEFAULT_VARIANT_BY_SCAFFOLD: dict[str, str] = {
    "local-service-business": "nordic-trust",
    "ecommerce-lite": "clean-store",
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
    "    and explain in rationale."
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
        scaffold_lines.append(
            f"- id: {entry['id']}\n"
            f"  label: {entry['label']}\n"
            f"  description: {entry.get('description', '')}\n"
            f"  variants: {variant_ids}\n"
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

    return (
        "Site Brief (JSON):\n"
        f"{json.dumps(site_brief, ensure_ascii=False, indent=2)}\n\n"
        "Scaffold Registry (only on-disk scaffolds are listed):\n"
        + "\n".join(scaffold_lines)
        + "\n\nCapability Map (capability-map.v1):\n"
        + "\n".join(cap_lines)
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


def _pages_not_in_routes(
    wizard_must_have: list[str],
    routes: list[dict[str, Any]],
) -> list[str]:
    """Return route-bearing wizard pages missing from the scaffold routes."""
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
    """Render non-blocking warnings for wizard page intent route gaps."""
    if not wizard_must_have:
        return []
    return [
        {
            "page": page,
            "expectedPath": _PAGE_TO_ROUTE_HINT[page],
            "reason": (
                "Wizard must-have page is not emitted by the selected "
                "scaffold route plan."
            ),
        }
        for page in _pages_not_in_routes(wizard_must_have, routes)
    ]


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
    page_count_value = site_brief.get("pageCount")
    trimmed_route_plan, page_count_warning = _trim_route_plan(
        raw_route_plan, page_count_value
    )
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
            trimmed_route_plan,
        ),
        route_plan=trimmed_route_plan,
        page_count_warning=page_count_warning,
        intent_guard_warnings=intent_guard_warnings,
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
