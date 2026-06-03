"""Phase 2 Plan: turn a Site Brief into a Site Plan + Generation Package.

Public API:
    produce_site_plan(site_brief, *, run_id, pinned=None, ...) -> PlanResult
        Single source of truth for both ``scripts/build_site.py`` and
        ``scripts/dev_generate.py``. Closes ``docs/known-issues.md`` B19
        (the parallel-pipeline drift risk).

    PlanResult, PlanningChoice, RejectedCapability
        Pydantic types describing the plan output.

    load_scaffold_registry(), load_capability_map(), filter_capabilities()
        Loaders + capability filter exposed for tests and Backoffice.

    resolve_planning_model() -> str
        Returns the planningModel model string from llm-models.v1.json.
        Mirrors ``packages.generation.brief.resolve_brief_model``.

Mock fallback runs when ``OPENAI_API_KEY`` is missing or the LLM call
fails, identical to the briefModel pattern.
"""

from .blueprint import (
    SectionPlanEntry,
    build_generation_blueprint,
    derive_content_blocks,
    derive_faq,
    derive_quality_risks,
    derive_section_plan,
    derive_story,
    derive_visual_direction,
    merge_section_plans,
    resolve_section_plan,
    section_addresses,
)
from .models import (
    PLANNING_ROLE_ID,
    PlanningModelResolutionError,
    resolve_planning_model,
)
from .plan import (
    SCAFFOLD_TO_STARTER,
    PlanningChoice,
    PlanResult,
    RejectedCapability,
    dossier_is_enabled,
    filter_capabilities,
    load_capability_map,
    load_scaffold_enabled_map,
    load_scaffold_registry,
    load_starter_registry,
    merge_operator_selected_with_helper,
    produce_site_plan,
    starter_is_enabled,
)

__all__ = [
    "PLANNING_ROLE_ID",
    "PlanResult",
    "PlanningChoice",
    "PlanningModelResolutionError",
    "RejectedCapability",
    "SCAFFOLD_TO_STARTER",
    "SectionPlanEntry",
    "build_generation_blueprint",
    "derive_content_blocks",
    "derive_faq",
    "derive_quality_risks",
    "derive_section_plan",
    "derive_story",
    "derive_visual_direction",
    "dossier_is_enabled",
    "filter_capabilities",
    "load_capability_map",
    "load_scaffold_enabled_map",
    "load_scaffold_registry",
    "load_starter_registry",
    "merge_operator_selected_with_helper",
    "merge_section_plans",
    "produce_site_plan",
    "resolve_planning_model",
    "resolve_section_plan",
    "section_addresses",
    "starter_is_enabled",
]
