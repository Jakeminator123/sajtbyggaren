"""Read-only diagnostics for Viewser wizard answer propagation.

This module deliberately contains Backoffice-only metadata. Runtime code
does not import it, and generation decisions continue to live in Discovery
Resolver, Discovery Taxonomy, Capability Map, planning and the builder.

The diagnostic is **wizard-truth-driven**: it iterates the canonical wizard
UI option lists (``CTA_OPTIONS`` and ``MUST_HAVE_OPTIONS``) parsed at
runtime from
``apps/viewser/components/discovery-wizard/wizard-constants.ts`` and joins
each value against the backend chain

    wizard UI options
        -> Discovery Resolver (capability + conversion-goal mapping)
        -> planning wizard route definitions / unsupported reasons
        -> site-plan.routePlan / site-plan.pageIntentWarnings
        -> build_site renderer dispatch / scaffold default routes

UI values without a known destination must surface as
``no-known-destination`` so they are not silently hidden.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from packages.generation.discovery.resolve import (
    _RUNTIME_SCAFFOLD_HINTS,
    get_cta_to_conversion_goal_mapping,
    get_page_to_capability_mapping,
    normalize_capability_slug,
)
from packages.generation.planning.plan import (
    get_page_to_route_hint_mapping,
    get_wizard_route_definitions,
    get_wizard_route_scaffolds,
    get_wizard_route_unsupported_reasons,
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
PLAN_PATH = REPO_ROOT / "packages" / "generation" / "planning" / "plan.py"
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
PROJECT_INPUT_SCHEMA_PATH = (
    REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"
)
BUILD_SITE_PATH = REPO_ROOT / "scripts" / "build_site.py"

# Scaffolds that have a runtime + starter mapping today. The resolver owns
# the authoritative register in ``_RUNTIME_SCAFFOLD_HINTS``; this list is
# mirrored read-only from it so the diagnostic never drifts out of sync when
# new runtime scaffolds are activated.
_RUNTIME_SCAFFOLD_IDS: tuple[str, ...] = tuple(_RUNTIME_SCAFFOLD_HINTS.keys())

# Wizard ``mustHave`` labels whose intent matches a scaffold default
# route (``home`` / ``about`` / ``contact`` / ``products``) rather than a
# wizard-extra route. The diagnostic resolves the actual path against
# each scaffold's ``routes.json`` at read time, so any scaffold path
# rename surfaces immediately.
_MUST_HAVE_LABEL_TO_SCAFFOLD_ROUTE_ID: dict[str, str] = {
    "Startsida / Hero": "home",
    "Om oss / Om mig": "about",
    "Kontaktformulär": "contact",
    "Webshop / Produkter": "products",
}

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


# ---------------------------------------------------------------------------
# TypeScript wizard-constants.ts parser (drift detection)
# ---------------------------------------------------------------------------
#
# The Backoffice diagnostic must iterate the same UI option list the
# operator sees in the wizard. Reading the canonical TS source means a
# wizard option added in ``wizard-constants.ts`` shows up immediately,
# and a renamed option breaks the parser instead of leaving the
# diagnostic silently incomplete.

_STRING_LITERAL_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _parse_wizard_option_array(name: str) -> list[str]:
    """Extract a TypeScript ``as const`` string array from wizard-constants.ts.

    Returns the values in source order so the diagnostic surface matches
    the order an operator sees in the wizard UI. Raises ``RuntimeError``
    when the named export cannot be located - tests rely on this contract
    to detect drift between wizard-constants.ts and the Python
    diagnostic.
    """
    text = WIZARD_CONSTANTS_PATH.read_text(encoding="utf-8")
    block_re = re.compile(
        rf"export\s+const\s+{re.escape(name)}\s*=\s*\[(.*?)\]\s*as\s+const\s*;",
        re.DOTALL,
    )
    match = block_re.search(text)
    if match is None:
        raise RuntimeError(
            f"{name} block not found in {WIZARD_CONSTANTS_PATH.name}; "
            "wizard-constants.ts may have been renamed or restructured."
        )
    body = match.group(1)
    # Wizard option labels are plain Swedish UTF-8 text without backslash
    # escapes. We keep the parser strict: any backslash inside a literal
    # makes the parser bail rather than silently corrupting Swedish
    # characters (encoding via unicode_escape would damage å/ä/ö).
    values: list[str] = []
    for literal in _STRING_LITERAL_RE.finditer(body):
        raw = literal.group(1)
        if "\\" in raw:
            raise RuntimeError(
                f"{name} entry {raw!r} in {WIZARD_CONSTANTS_PATH.name} "
                "contains backslash escapes; extend the diagnostic parser "
                "before adding escapes to wizard option labels."
            )
        values.append(raw)
    if not values:
        raise RuntimeError(
            f"{name} block in {WIZARD_CONSTANTS_PATH.name} is empty; "
            "diagnostics would silently lose every wizard option."
        )
    return values


def parse_cta_options() -> list[str]:
    """Return the ordered list of ``CTA_OPTIONS`` from wizard-constants.ts."""
    return _parse_wizard_option_array("CTA_OPTIONS")


def parse_must_have_options() -> list[str]:
    """Return the ordered list of ``MUST_HAVE_OPTIONS`` from wizard-constants.ts."""
    return _parse_wizard_option_array("MUST_HAVE_OPTIONS")


# ---------------------------------------------------------------------------
# Capability classification (Capability Map + alias awareness)
# ---------------------------------------------------------------------------


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
    """Classify a capability without changing policies or runtime state.

    Applies the same alias normalisation the resolver uses
    (:func:`packages.generation.discovery.resolve.normalize_capability_slug`)
    so a wizard label that points to e.g. ``newsletter`` is classified
    against the canonical ``newsletter-subscribe`` entry.
    """
    resolved_map = capability_map if capability_map is not None else load_capability_map()
    canonical = normalize_capability_slug(capability_id)
    entry = resolved_map.get(canonical)
    if entry is None:
        return {
            "status": "unknown",
            "explanation": (
                f"Capability {canonical!r} saknas i capability-map.v1.json."
            ),
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


# ---------------------------------------------------------------------------
# Scaffold default routes (used to detect basroute / scaffold-default match)
# ---------------------------------------------------------------------------


def load_scaffold_default_routes() -> dict[str, list[dict[str, Any]]]:
    """Return ``{scaffold_id: [{id, path, ...}, ...]}`` for runtime scaffolds.

    Reads each runtime scaffold's ``routes.json`` directly so any
    scaffold path rename is picked up by the diagnostic without
    additional code changes. Missing files are silently skipped so a
    half-implemented scaffold cannot crash the Backoffice view.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for scaffold_id in _RUNTIME_SCAFFOLD_IDS:
        routes_path = SCAFFOLDS_DIR / scaffold_id / "routes.json"
        try:
            payload = json.loads(routes_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        routes = payload.get("defaultRoutes") or []
        if not isinstance(routes, list):
            continue
        clean: list[dict[str, Any]] = []
        for route in routes:
            if not isinstance(route, dict):
                continue
            route_id = route.get("id")
            path = route.get("path")
            if not isinstance(route_id, str) or not isinstance(path, str):
                continue
            clean.append({"id": route_id, "path": path})
        if clean:
            out[scaffold_id] = clean
    return out


# ---------------------------------------------------------------------------
# Taxonomy rows
# ---------------------------------------------------------------------------


def _classify_taxonomy_support_status(
    support_status: str,
) -> tuple[diagnostic_status, str]:
    """Map ``discovery-taxonomy`` ``supportStatus`` to diagnostic status.

    ``disabled`` is reported as ``gap`` with explicit "disabled in
    taxonomy" copy in the explanation so an operator can never read it
    as ``planned`` (the previous behaviour was to flip ``disabled`` to
    ``planned`` which made disabled categories indistinguishable from
    planned-but-coming ones).
    """
    if support_status == "active":
        return "active", "active"
    if support_status == "fallback":
        return "fallback", "fallback"
    if support_status == "planned":
        return "planned", "planned"
    if support_status == "disabled":
        return "gap", "disabled (taxonomi har stängt av kategorin)"
    return "unknown", "okänd supportStatus"


def _taxonomy_rows(
    capability_map: dict[str, dict[str, Any]],
    *,
    taxonomy_path: Path | None = None,
) -> list[dict[str, str]]:
    taxonomy = _read_json(taxonomy_path or DISCOVERY_TAXONOMY_PATH)
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
        status, status_label = _classify_taxonomy_support_status(support_status)
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
                propagation_level=(
                    "deterministic" if status == "active" else "downstream-gap"
                ),
                explanation=(
                    f"{category.get('labelSv', category_id)} har supportStatus="
                    f"{support_status} ({status_label}). Requested capabilities: "
                    f"{', '.join(capability_notes) if capability_notes else 'inga'}."
                ),
                source_path=_source_paths(DISCOVERY_TAXONOMY_PATH),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Must-have rows (wizard-truth driven)
# ---------------------------------------------------------------------------


def _classify_must_have(
    label: str,
    *,
    capability_map: dict[str, dict[str, Any]],
    page_to_capability: dict[str, str],
    page_to_route_hint: dict[str, str],
    wizard_route_definitions: dict[str, dict[str, str]],
    wizard_route_scaffolds: frozenset[str],
    wizard_unsupported_reasons: dict[str, str],
    scaffold_default_routes: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Pick the most specific destination/status for a wizard must-have label.

    Priority order (highest signal wins):

    1. Wizard route emission (``_WIZARD_ROUTE_DEFINITIONS``) - the wizard
       label maps to a deterministic route that ``write_pages`` renders
       for scaffolds in ``_WIZARD_ROUTE_SCAFFOLDS``.
    2. Scaffold default route (``_MUST_HAVE_LABEL_TO_SCAFFOLD_ROUTE_ID``
       matched against ``routes.json`` ``defaultRoutes``) - the label is
       just the wizard name for an existing scaffold basroute
       (home / about / contact / products).
    3. Unsupported reason (``_WIZARD_ROUTE_UNSUPPORTED_REASONS``) - planning
       emits a ``pageIntentWarnings`` entry with a specific reason; no
       route is rendered.
    4. Capability mapping (``_PAGE_TO_CAPABILITY``) only - the label
       feeds ``requestedCapabilities`` but no route is emitted in any
       runtime scaffold.
    5. No known destination - the wizard label has no mapping in any of
       the backend tables; surfaced as ``no-known-destination`` so the
       diagnostic does not hide it.
    """
    capability_slug = page_to_capability.get(label)
    capability_classification: dict[str, Any] | None = None
    if capability_slug:
        capability_classification = classify_capability(
            capability_slug, capability_map
        )

    capability_suffix = ""
    if capability_slug and capability_classification is not None:
        capability_suffix = (
            f" Capability-signalen: {capability_slug} "
            f"(status={capability_classification['status']})."
        )

    # 1. Wizard route emission
    if label in wizard_route_definitions:
        route_def = wizard_route_definitions[label]
        scaffolds_text = (
            ", ".join(sorted(wizard_route_scaffolds))
            if wizard_route_scaffolds
            else "(inga scaffolds opt-in)"
        )
        return {
            "destination": (
                f"site-plan.routePlan {route_def['path']} "
                f"(route emission via _WIZARD_ROUTE_DEFINITIONS; "
                f"opt-in scaffolds: {scaffolds_text})"
            ),
            "sourceChain": (
                "wizard-constants.ts MUST_HAVE_OPTIONS → "
                "planning _WIZARD_ROUTE_DEFINITIONS / _wizard_extra_routes → "
                "site-plan.routePlan → "
                "build_site _WIZARD_ROUTE_RENDERERS"
            ),
            "status": "active",
            "propagationLevel": "deterministic",
            "explanation": (
                f"{label} emitteras som deterministisk route "
                f"{route_def['path']!r} för {scaffolds_text}; "
                "scripts/build_site.py renderar via _WIZARD_ROUTE_RENDERERS. "
                "Övriga scaffolds håller warning-shape i pageIntentWarnings "
                "tills deras renderer-set granskats."
                + capability_suffix
            ),
            "sourcePath": _source_paths(
                WIZARD_CONSTANTS_PATH,
                PLAN_PATH,
                BUILD_SITE_PATH,
            ),
        }

    # 2. Scaffold default route
    scaffold_route_id = _MUST_HAVE_LABEL_TO_SCAFFOLD_ROUTE_ID.get(label)
    if scaffold_route_id:
        matches: list[tuple[str, str]] = []
        for scaffold_id, routes in scaffold_default_routes.items():
            for route in routes:
                if route.get("id") == scaffold_route_id:
                    matches.append((scaffold_id, route["path"]))
                    break
        if matches:
            paths_by_scaffold = ", ".join(
                f"{scaffold_id}:{path}" for scaffold_id, path in matches
            )
            matched_ids = {scaffold_id for scaffold_id, _ in matches}
            missing_scaffolds = sorted(
                scaffold_id
                for scaffold_id in _RUNTIME_SCAFFOLD_IDS
                if scaffold_id not in matched_ids
            )
            scope_note = (
                ""
                if not missing_scaffolds
                else (
                    " Saknas som default-route i: "
                    + ", ".join(missing_scaffolds)
                    + " (scaffold-specifik basroute)."
                )
            )
            return {
                "destination": (
                    f"scaffold default route {scaffold_route_id!r} "
                    f"({paths_by_scaffold})"
                ),
                "sourceChain": (
                    "wizard-constants.ts MUST_HAVE_OPTIONS → "
                    f"scaffolds/<scaffold>/routes.json defaultRoutes "
                    f"(id={scaffold_route_id}) → build_site write_pages"
                ),
                "status": "active",
                "propagationLevel": "deterministic",
                "explanation": (
                    f"{label} motsvarar scaffoldens basroute "
                    f"{scaffold_route_id!r}. Den emitteras alltid av "
                    "scaffold-defaults innan wizard-extras läggs till."
                    + scope_note
                    + capability_suffix
                ),
                "sourcePath": _source_paths(
                    WIZARD_CONSTANTS_PATH,
                    *[
                        SCAFFOLDS_DIR / sid / "routes.json"
                        for sid in _RUNTIME_SCAFFOLD_IDS
                    ],
                    BUILD_SITE_PATH,
                ),
            }

    # 3. Unsupported reason (warning-only)
    if label in wizard_unsupported_reasons:
        reason = wizard_unsupported_reasons[label]
        expected_path = page_to_route_hint.get(label, "")
        path_fragment = (
            f"expectedPath={expected_path}; " if expected_path else ""
        )
        return {
            "destination": (
                f"site-plan.pageIntentWarnings (warning-only, "
                f"{path_fragment}reason: {reason})"
            ),
            "sourceChain": (
                "wizard-constants.ts MUST_HAVE_OPTIONS → "
                "planning _WIZARD_ROUTE_UNSUPPORTED_REASONS → "
                "site-plan.pageIntentWarnings"
            ),
            "status": "gap",
            "propagationLevel": "downstream-gap",
            "explanation": (
                f"{label} är warning-only: deterministiska Buildern "
                "emitterar ingen route eftersom den kräver integration "
                "som saknas i v1. Reason: "
                f"{reason}"
                + capability_suffix
            ),
            "sourcePath": _source_paths(WIZARD_CONSTANTS_PATH, PLAN_PATH),
        }

    # 4. Capability mapping only (no route)
    if capability_slug and capability_classification is not None:
        cap_status = str(capability_classification["status"])
        diag_status: diagnostic_status = "no-known-destination"
        propagation: propagation_level = "diagnostic-only"
        if cap_status == "active":
            diag_status = "active"
            propagation = "project-input-only"
        elif cap_status == "gap":
            diag_status = "gap"
            propagation = "downstream-gap"
        elif cap_status == "unknown":
            diag_status = "unknown"
            propagation = "downstream-gap"
        return {
            "destination": (
                f"requestedCapabilities[{capability_slug}] "
                "(no deterministic route in any runtime scaffold)"
            ),
            "sourceChain": (
                "wizard-constants.ts MUST_HAVE_OPTIONS → "
                "Discovery Resolver _PAGE_TO_CAPABILITY → "
                "capability-map.v1.json"
            ),
            "status": diag_status,
            "propagationLevel": propagation,
            "explanation": (
                f"{label} blir bara capability-signal "
                f"({capability_slug}, capability-status={cap_status}); "
                "ingen deterministisk route emitteras varken som "
                "scaffold-default eller wizard-extra. "
                f"{capability_classification['explanation']}"
            ),
            "sourcePath": _source_paths(
                WIZARD_CONSTANTS_PATH,
                DISCOVERY_RESOLVER_PATH,
                CAPABILITY_MAP_PATH,
            ),
        }

    # 5. No known destination
    return {
        "destination": "(saknar känd destination)",
        "sourceChain": "wizard-constants.ts MUST_HAVE_OPTIONS → (gap)",
        "status": "no-known-destination",
        "propagationLevel": "diagnostic-only",
        "explanation": (
            f"Wizardens must-have-val {label!r} saknar mappning till "
            "_WIZARD_ROUTE_DEFINITIONS, scaffold-defaults, "
            "_WIZARD_ROUTE_UNSUPPORTED_REASONS och _PAGE_TO_CAPABILITY. "
            "Lägg till en mappning eller hantera medvetet."
        ),
        "sourcePath": _source_paths(WIZARD_CONSTANTS_PATH),
    }


def _must_have_rows(capability_map: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    page_to_capability = get_page_to_capability_mapping()
    page_to_route_hint = get_page_to_route_hint_mapping()
    wizard_route_definitions = get_wizard_route_definitions()
    wizard_route_scaffolds = get_wizard_route_scaffolds()
    wizard_unsupported_reasons = get_wizard_route_unsupported_reasons()
    scaffold_default_routes = load_scaffold_default_routes()

    child_rows: list[dict[str, str]] = []
    for label in parse_must_have_options():
        classification = _classify_must_have(
            label,
            capability_map=capability_map,
            page_to_capability=page_to_capability,
            page_to_route_hint=page_to_route_hint,
            wizard_route_definitions=wizard_route_definitions,
            wizard_route_scaffolds=wizard_route_scaffolds,
            wizard_unsupported_reasons=wizard_unsupported_reasons,
            scaffold_default_routes=scaffold_default_routes,
        )
        child_rows.append(
            _row(
                step="pages",
                answer_path=f"answers.mustHave[{label}]",
                destination=str(classification["destination"]),
                source_chain=str(classification["sourceChain"]),
                status=classification["status"],  # type: ignore[arg-type]
                propagation_level=classification["propagationLevel"],  # type: ignore[arg-type]
                explanation=str(classification["explanation"]),
                source_path=str(classification["sourcePath"]),
            )
        )

    parent_status, parent_propagation = _aggregate_status(child_rows)
    summary = _summarise_child_statuses(child_rows)
    parent_explanation = (
        "Must-have-sidor blir capability-/route-signaler. "
        f"{summary} "
        "Dossiers väljs inte direkt av wizardknappar utan går via "
        "Capability Map, Dossier Selection och planning."
    )

    parent_row = _row(
        step="pages",
        answer_path="answers.mustHave",
        destination=(
            "site-plan.routePlan + requestedCapabilities + "
            "site-plan.pageIntentWarnings (mixed, se barnrader)"
        ),
        source_chain=(
            "wizard-constants.ts MUST_HAVE_OPTIONS → "
            "Discovery Resolver _PAGE_TO_CAPABILITY → "
            "planning _WIZARD_ROUTE_DEFINITIONS / _WIZARD_ROUTE_UNSUPPORTED_REASONS → "
            "site-plan → build_site"
        ),
        status=parent_status,
        propagation_level=parent_propagation,
        explanation=parent_explanation,
        source_path=_source_paths(
            WIZARD_CONSTANTS_PATH,
            DISCOVERY_RESOLVER_PATH,
            PLAN_PATH,
            CAPABILITY_MAP_PATH,
            DOSSIER_SELECTION_PATH,
        ),
    )

    return [parent_row, *child_rows]


# ---------------------------------------------------------------------------
# CTA rows (wizard-truth driven)
# ---------------------------------------------------------------------------


def _classify_cta(
    label: str,
    *,
    cta_to_conversion_goal: dict[str, str],
) -> dict[str, Any]:
    goal = cta_to_conversion_goal.get(label)
    if goal is None:
        return {
            "destination": "(saknar conversion-goal-mappning)",
            "sourceChain": (
                "wizard-constants.ts CTA_OPTIONS → "
                "Discovery Resolver _CTA_TO_CONVERSION_GOAL (saknar mappning)"
            ),
            "status": "no-known-destination",
            "propagationLevel": "diagnostic-only",
            "explanation": (
                f"Wizard CTA-val {label!r} finns i CTA_OPTIONS men saknar "
                "deterministisk conversion-goal-mappning i Discovery "
                "Resolver. Lägg till en mappning i "
                "_CTA_TO_CONVERSION_GOAL eller hantera medvetet."
            ),
            "sourcePath": _source_paths(
                WIZARD_CONSTANTS_PATH, DISCOVERY_RESOLVER_PATH
            ),
        }
    return {
        "destination": f"conversionGoals[{goal}]",
        "sourceChain": (
            "wizard-constants.ts CTA_OPTIONS → "
            "Discovery Resolver _CTA_TO_CONVERSION_GOAL → "
            "Project Input conversionGoals"
        ),
        "status": "active",
        "propagationLevel": "deterministic",
        "explanation": (
            f"CTA-värdet {label!r} mappar deterministiskt till "
            f"conversionGoals[{goal}]."
        ),
        "sourcePath": _source_paths(WIZARD_CONSTANTS_PATH, DISCOVERY_RESOLVER_PATH),
    }


def _cta_rows() -> list[dict[str, str]]:
    cta_to_conversion_goal = get_cta_to_conversion_goal_mapping()
    child_rows: list[dict[str, str]] = []
    for label in parse_cta_options():
        classification = _classify_cta(
            label, cta_to_conversion_goal=cta_to_conversion_goal
        )
        child_rows.append(
            _row(
                step="pages",
                answer_path=f"answers.primaryCta[{label}]",
                destination=str(classification["destination"]),
                source_chain=str(classification["sourceChain"]),
                status=classification["status"],  # type: ignore[arg-type]
                propagation_level=classification["propagationLevel"],  # type: ignore[arg-type]
                explanation=str(classification["explanation"]),
                source_path=str(classification["sourcePath"]),
            )
        )

    parent_status, parent_propagation = _aggregate_status(child_rows)
    summary = _summarise_child_statuses(child_rows)
    parent_explanation = (
        "Kända CTA-chip översätts deterministiskt till conversionGoals. "
        f"{summary}"
    )

    parent_row = _row(
        step="pages",
        answer_path="answers.primaryCta",
        destination=(
            "conversionGoals (deterministisk för mappade CTA; saknad "
            "mappning gör att inga conversionGoals adderas)"
        ),
        source_chain=(
            "wizard-constants.ts CTA_OPTIONS → "
            "Discovery Resolver _CTA_TO_CONVERSION_GOAL → "
            "Project Input conversionGoals"
        ),
        status=parent_status,
        propagation_level=parent_propagation,
        explanation=parent_explanation,
        source_path=_source_paths(WIZARD_PAYLOAD_PATH, DISCOVERY_RESOLVER_PATH),
    )

    return [parent_row, *child_rows]


# ---------------------------------------------------------------------------
# Parent-row aggregation helpers
# ---------------------------------------------------------------------------


def _aggregate_status(
    child_rows: list[dict[str, str]],
) -> tuple[diagnostic_status, propagation_level]:
    """Pick the **worst-of** status + propagation across child rows.

    A parent row that says ``active`` + ``deterministic`` while one of
    its children is ``no-known-destination`` would falsely imply every
    child has a deterministic destination. Worst-of aggregation makes
    the parent row honest about partial coverage.
    """
    if not child_rows:
        return "active", "deterministic"
    worst_status: diagnostic_status = "active"
    worst_propagation: propagation_level = "deterministic"
    for row in child_rows:
        status = row["status"]
        if STATUS_ORDER.index(status) > STATUS_ORDER.index(worst_status):  # type: ignore[arg-type]
            worst_status = status  # type: ignore[assignment]
        propagation = row["propagationLevel"]
        if PROPAGATION_ORDER.index(propagation) > PROPAGATION_ORDER.index(
            worst_propagation
        ):  # type: ignore[arg-type]
            worst_propagation = propagation  # type: ignore[assignment]
    return worst_status, worst_propagation


def _summarise_child_statuses(child_rows: list[dict[str, str]]) -> str:
    """Render a compact Swedish summary of child row statuses for parent rows."""
    if not child_rows:
        return "Inga barnrader hittades."
    counts = Counter(row["status"] for row in child_rows)
    total = len(child_rows)
    fragments: list[str] = [f"{total} val totalt"]
    for status in STATUS_ORDER:
        if counts.get(status):
            fragments.append(f"{counts[status]} {status}")
    return ", ".join(fragments) + "."


# ---------------------------------------------------------------------------
# Direct Project Input rows, prompt-signal rows, asset rows, brand rows,
# diagnostic-only rows (unchanged from previous diagnostic shape).
# ---------------------------------------------------------------------------


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
            destination="tone.primary; tone.secondary → build_site.py CSS token override",
            source_chain="Discovery Resolver → Project Input tone → build_site.py",
            status="active",
            propagation_level="deterministic",
            explanation=(
                "Whitelistade tone.primary-signaler kan nu påverka CSS-tokens "
                "när explicit brand-hex saknas."
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
            destination="brand.primaryColorHex → build_site.py CSS --primary",
            source_chain="Discovery Resolver → Project Input brand → build_site.py",
            status="active",
            propagation_level="deterministic",
            explanation=(
                "Primärfärgen används som säker CSS-tokenoverride när värdet "
                "är giltig hex."
            ),
            source_path=source,
        ),
        _row(
            step="brand",
            answer_path="answers.brand.accentColorHex",
            destination="brand.accentColorHex → build_site.py CSS --accent",
            source_chain="Discovery Resolver → Project Input brand → build_site.py",
            status="active",
            propagation_level="deterministic",
            explanation=(
                "Accentfärgen används som säker CSS-tokenoverride när värdet "
                "är giltig hex."
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
