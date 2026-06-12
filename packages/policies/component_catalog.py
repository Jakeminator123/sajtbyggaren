"""Component Catalog reads + scaffold->starter mapping (ADR 0040 lager 3).

This module is the single, in-bounds home for two things the BUILD layer needs
to consume the Component Catalog at render time without importing the planning
package (repo-boundaries: ``packages/generation/build`` may import
``packages/policies`` but NOT ``packages/generation/planning``):

1. ``SCAFFOLD_STARTER_MAP`` - the canonical scaffold -> Starter mapping. It used
   to live in ``packages/generation/planning/plan.py``; it was moved here
   (surgically, mapping only) so both planning (``plan.py`` re-exports it as
   ``SCAFFOLD_TO_STARTER``) and build read ONE source of truth.

2. Catalog reads: ``capability_components`` (capability-map ``components`` key,
   ADR 0040 lager 2) and ``starter_component_names`` (a Starter's generated
   ``component-manifest.json``, lager 1), plus
   ``faq_accordion_component_available`` - the deterministic, per-build gate the
   ``/faq`` renderer uses to decide whether to emit the accordion component
   import. Per-build precision (resolve THIS build's Starter, not the union of
   all Starters) is the honesty requirement: emitting an accordion import for a
   Starter that does not vendor the component would be a broken build.

No LLM, no I/O beyond reading the governance policy + the Starter manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPABILITY_MAP_PATH = REPO_ROOT / "governance" / "policies" / "capability-map.v1.json"
STARTERS_DIR = REPO_ROOT / "data" / "starters"
COMPONENT_MANIFEST_FILENAME = "component-manifest.json"

__all__ = [
    "SCAFFOLD_STARTER_MAP",
    "capability_components",
    "faq_accordion_component_available",
    "starter_component_names",
    "starter_for_scaffold",
]


# Canonical scaffold -> Starter mapping (moved verbatim from plan.py).
#
# ``marketing-base`` covers the local-service-business chrome and is the
# only starter wired into ``_REAL_CODEGEN_STARTERS`` in
# packages/generation/codegen/codegen.py (see ADR 0017). ``commerce-base``
# was vendored in PR #16 (ADR 0018, vendor-only checkpoint) and the
# runtime mapping ``ecommerce-lite -> commerce-base`` was activated in
# B20 step 2 per ADR 0019; ecommerce-lite runs through the
# deterministic-v1 codegen path until real-codegen scope is widened in
# a follow-up sprint with its own ADR extension on top of 0017.
SCAFFOLD_STARTER_MAP: dict[str, str] = {
    "local-service-business": "marketing-base",
    "ecommerce-lite": "commerce-base",
    # clinic-healthcare reuses ``marketing-base`` (Next.js + Tailwind) per
    # Path B step 12 — every route renders via the section dispatcher,
    # not by extending the starter. Added 2026-05-25 alongside the
    # ``_DISPATCHED_SCAFFOLDS`` entry in scripts/build_site.py.
    "clinic-healthcare": "marketing-base",
    # professional-services is the second Path B native scaffold (step 13,
    # 2026-05-25). It also runs on ``marketing-base`` because the four
    # default routes (home / expertise / about / contact) are pure
    # informational pages — no checkout, no booking surface — and the
    # scaffold-distinct character lives entirely in the section
    # composition (expertise-areas / practice-grid / partners-grid).
    "professional-services": "marketing-base",
    # agency-studio is the third Path B native scaffold (step 14,
    # 2026-05-25). Same starter for the same reason — informational
    # routes (home / work / about / contact); the work-led
    # composition (selected-work-preview / selected-work-grid /
    # manifesto-block / process-steps / client-roster) carries the
    # creative-studio voice.
    "agency-studio": "marketing-base",
    # Restaurant-hospitality is enabled in scaffold-contract.v1.json and
    # therefore appears in load_scaffold_registry(); without a starter
    # mapping here, produce_site_plan() raises in _resolve_starter_id when
    # the planner (real LLM or a pinned scaffoldId) picks it.
    #
    # As of Issue #90 the route renderers for ``menu`` and ``booking``
    # are wired in scripts/build_site.py:write_pages (Path A — per-route
    # if/elif), so a full restaurant build now produces a complete
    # Next.js project. Path B (section-driven generic dispatcher from
    # docs/scaffold-runtime-extension-needed.md) is still the longer-
    # term direction; Path A keeps the surface area small until more
    # scaffolds land on disk.
    #
    # ``marketing-base`` is the documented mapping in
    # data/starters/README.md line 34 and matches the long-running test
    # tests/test_starter_scaffold_mapping.py.
    "restaurant-hospitality": "marketing-base",
}


def starter_for_scaffold(scaffold_id: str | None) -> str | None:
    """Return the Starter id mapped to ``scaffold_id``, or None."""
    if not isinstance(scaffold_id, str) or not scaffold_id:
        return None
    return SCAFFOLD_STARTER_MAP.get(scaffold_id)


def _load_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def capability_components(
    capability_slug: str, *, capability_map_path: Path | None = None
) -> list[str]:
    """Return capability-map ``components`` for ``capability_slug`` (ADR 0040).

    Defensive: returns ``[]`` for an unknown capability or a capability without
    a ``components`` list. Never raises on a malformed/missing policy file.
    """
    data = _load_json(capability_map_path or CAPABILITY_MAP_PATH)
    capabilities = data.get("capabilities")
    entry = capabilities.get(capability_slug) if isinstance(capabilities, dict) else None
    components = entry.get("components") if isinstance(entry, dict) else None
    if not isinstance(components, list):
        return []
    return [c for c in components if isinstance(c, str) and c]


def starter_component_names(
    starter_id: str | None, *, starters_dir: Path | None = None
) -> set[str]:
    """Return the component names listed in a Starter's component-manifest.

    Reads ``data/starters/<starterId>/component-manifest.json`` (the generated
    lager-1 inventory). Returns an empty set for an unknown/missing Starter or a
    manifest without components. Never raises.
    """
    if not isinstance(starter_id, str) or not starter_id:
        return set()
    base = starters_dir or STARTERS_DIR
    manifest = _load_json(base / starter_id / COMPONENT_MANIFEST_FILENAME)
    components = manifest.get("components")
    if not isinstance(components, list):
        return set()
    return {
        component["name"]
        for component in components
        if isinstance(component, dict) and isinstance(component.get("name"), str)
    }


def faq_accordion_component_available(
    *,
    scaffold_id: str | None,
    starter_id: str | None = None,
    capability_map_path: Path | None = None,
    starters_dir: Path | None = None,
) -> bool:
    """Per-build gate: may the ``/faq`` route emit the accordion component?

    True iff BOTH (ADR 0040 lager 3):

    - capability-map ``faq-section.components`` lists ``accordion`` (lager 2), AND
    - the build's resolved Starter vendors an ``accordion`` component in its
      ``component-manifest.json`` (lager 1).

    The Starter is resolved per-build: ``starter_id`` when the Project Input pins
    it, else ``starter_for_scaffold(scaffold_id)``. When neither resolves a
    Starter, the gate is False (honest native fallback) - never a union over all
    Starters, because emitting the import for a Starter that does not carry the
    component would be a broken build. Deterministic, offline, never raises.
    """
    resolved_starter = starter_id or starter_for_scaffold(scaffold_id)
    if not resolved_starter:
        return False
    if "accordion" not in capability_components(
        "faq-section", capability_map_path=capability_map_path
    ):
        return False
    return "accordion" in starter_component_names(
        resolved_starter, starters_dir=starters_dir
    )
