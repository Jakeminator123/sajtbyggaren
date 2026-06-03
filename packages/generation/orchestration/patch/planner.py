"""Artifact Patch Planner - dry-run (KÖR-7b).

``plan_patches`` consumes a deterministic router decision (KÖR-6a) and an
assembled context (KÖR-7a) and returns a transient :class:`PatchPlan`: proposed
patches against **named** artefakt fields, each validated against the same
rails planning uses. It is a strict dry-run:

- It **applies nothing** - no write, no build, no preview, no ``current.json``.
  Apply/version is KÖR-7c; targeted rebuild is KÖR-7d.
- It proposes patches **only** for named fields derived from the decision
  (``editKind`` ``component_add`` / ``copy_change`` with a ``target``). It never
  invents a section and never emits a free file patch.
- It is deterministic and mock-safe: pure functions over the decision + context,
  no LLM, no ``OPENAI_API_KEY`` needed.

The section a target addresses is resolved from the assembled context's
``routeSections`` (ordinal -> sectionId, "andra sektionen" -> 2 -> the route's
2nd section), and every proposal is run through ``validate_patch`` so an unknown
section/dossier/field lands in ``rejected`` with a reason instead of being
emitted.
"""

from __future__ import annotations

from ..context.models import AssembledContext
from ..router.models import EditKind, RouterDecision, RouterTarget
from .models import (
    GENERATION_PACKAGE_ARTIFACT,
    ArtifactPatch,
    PatchPlan,
    PatchRails,
    RejectedPatch,
)
from .validate import rails_from_context, validate_patch

__all__ = ["plan_patches"]

# Edit kinds the planner can turn into a named-field patch. Other edit kinds
# (visual_style, layout_change, component_remove, route_add, none) are out of
# scope for the dry-run patch planner and produce no proposal (with a note).
_PATCHABLE_EDITS: tuple[EditKind, ...] = ("component_add", "copy_change")

# The named leaf field each patchable edit writes inside a section's
# contentBlock. ``accessoryComponent`` is the convention from 02 §6 / kor-7b for
# attaching a component to a section; ``headline`` is the section's primary copy
# field (01 §4 hero example). Deterministic, named, never free-form.
_LEAF_BY_EDIT: dict[EditKind, str] = {
    "component_add": "accessoryComponent",
    "copy_change": "headline",
}

# componentIntent (router slug) -> capability slug (capability-map.v1.json key).
# Only intents that correspond to a registered capability are mapped; intents
# without a capability (e.g. clock_widget, button, image) are treated as inline
# components and carry no capability, so they skip the dossier rail (02 §3:
# "om inte, föreslå soft dossier eller inline-komponent"). This is a documented
# lookup, not a runtime rail - whether the capability is *implemented* is read
# from the assembled capability-map rail at validation time.
_INTENT_CAPABILITY: dict[str, str] = {
    "contact_form": "contact-form",
    "form": "contact-form",
    "map_embed": "location",
    "image_gallery": "gallery",
    "pricing_table": "pricing",
    "faq_accordion": "faq-section",
    "opening_hours": "hours",
    "reviews_display": "reviews",
    "menu": "menu",
    "video": "hero-video",
    "newsletter_signup": "newsletter-subscribe",
}

_DEFAULT_ROUTE_ID = "home"


def plan_patches(
    decision: RouterDecision,
    context: AssembledContext | None,
    *,
    registry: AssembledContext | None = None,
) -> PatchPlan:
    """Propose + validate patches for a router decision. Applies nothing.

    ``context`` should be an ``artifacts_plus_sections`` assembled context
    (it carries the section rails); ``registry`` is an optional
    ``component_registry`` context used only to validate any capability a
    ``component_add`` references. Returns a transient :class:`PatchPlan`.
    """
    rails = rails_from_context(context, registry=registry)
    plan = PatchPlan()

    if not rails.routeSections and not rails.sections:
        plan.notes.append(
            "No section rails in the assembled context; expected an "
            "'artifacts_plus_sections' context. Section-addressed patches "
            "cannot be validated and will be rejected."
        )

    edits = _collect_edits(decision)
    if not edits:
        plan.notes.append(
            f"Router decision (messageKind={decision.messageKind}, "
            f"editKind={decision.editKind}) carries no patchable edit "
            f"({' / '.join(_PATCHABLE_EDITS)} with a target); nothing proposed."
        )
        plan.valid = True
        return plan

    for edit_kind, target, component_intent in edits:
        _plan_one(plan, rails, edit_kind, target, component_intent)

    plan.valid = not plan.rejected
    return plan


def _collect_edits(
    decision: RouterDecision,
) -> list[tuple[EditKind, RouterTarget, str | None]]:
    """Gather (editKind, target, componentIntent) tuples worth proposing.

    Handles the single top-level edit and any multi_intent subtasks, keeping
    only patchable edit kinds that carry a target (a patch needs a place to go).
    """
    edits: list[tuple[EditKind, RouterTarget, str | None]] = []
    if decision.editKind in _PATCHABLE_EDITS and decision.target is not None:
        edits.append((decision.editKind, decision.target, decision.componentIntent))
    for subtask in decision.subtasks:
        if subtask.editKind in _PATCHABLE_EDITS and subtask.target is not None:
            edits.append((subtask.editKind, subtask.target, subtask.componentIntent))
    return edits


def _plan_one(
    plan: PatchPlan,
    rails: PatchRails,
    edit_kind: EditKind,
    target: RouterTarget,
    component_intent: str | None,
) -> None:
    """Resolve the target section, build the named patch, validate, file it."""
    route_id = target.routeId or _DEFAULT_ROUTE_ID
    section_id, resolve_error = _resolve_section(rails, route_id, target)

    leaf = _LEAF_BY_EDIT[edit_kind]
    field = f"contentBlocks.{route_id}.{section_id}.{leaf}"
    value = _build_value(edit_kind, component_intent, target)

    if resolve_error is not None:
        plan.rejected.append(
            RejectedPatch(
                artifact=GENERATION_PACKAGE_ARTIFACT,
                field=field,
                value=value,
                reason=resolve_error,
            )
        )
        return

    patch = ArtifactPatch(
        artifact=GENERATION_PACKAGE_ARTIFACT,
        field=field,
        op="set",
        value=value,
    )
    reason = validate_patch(patch, rails)
    if reason is None:
        plan.patches.append(patch)
        if edit_kind == "copy_change":
            plan.notes.append(
                f"copy_change target {field!r}: value deferred - the new copy is "
                "produced by the copy model (kor-1c) at apply time, never invented "
                "by the planner (honesty rule)."
            )
    else:
        plan.rejected.append(
            RejectedPatch(
                artifact=patch.artifact,
                field=patch.field,
                op=patch.op,
                value=patch.value,
                reason=reason,
            )
        )


def _resolve_section(
    rails: PatchRails,
    route_id: str,
    target: RouterTarget,
) -> tuple[str, str | None]:
    """Resolve the concrete ``sectionId`` a target addresses.

    Returns ``(sectionId, errorReason)``. An explicit ``sectionId`` is trusted
    as-is and re-checked by ``validate_patch`` against the rails; an ordinal is
    resolved via the assembled ``routeSections`` (1-based; ``-1`` == last, the
    router's "sista" mapping). When an ordinal cannot resolve, the returned
    ``sectionId`` is a readable token for the rejected entry and the error
    explains why.
    """
    if target.sectionId:
        return target.sectionId, None

    ordinal = target.sectionOrdinal
    if ordinal is None:
        return (
            "<unresolved>",
            f"target for route {route_id!r} has neither sectionId nor "
            "sectionOrdinal; nothing to address",
        )

    sections = rails.allowed_sections(route_id)
    if not sections:
        return (
            f"<ordinal-{ordinal}>",
            f"route {route_id!r} has no sections in the rails; cannot resolve "
            f"sectionOrdinal={ordinal}",
        )

    if ordinal == -1:
        return sections[-1], None
    if 1 <= ordinal <= len(sections):
        return sections[ordinal - 1], None

    return (
        f"<ordinal-{ordinal}>",
        f"sectionOrdinal={ordinal} is out of range for route {route_id!r} "
        f"({len(sections)} sections); cannot resolve to a section",
    )


def _build_value(
    edit_kind: EditKind,
    component_intent: str | None,
    target: RouterTarget,
) -> object:
    """Build the patch value for an edit.

    - ``component_add``: a small descriptor. ``component`` is the intent slug
      hyphenated (clock_widget -> clock-widget); ``variant`` is ``None`` (the
      router gives none, and the planner invents nothing). When the intent maps
      to a registered capability, the capability slug is attached so the dossier
      rail can verify it; an inline component (no mapping) carries none.
    - ``copy_change``: ``None`` - the new copy is produced downstream (kor-1c).
    """
    if edit_kind == "copy_change":
        return None

    component = component_intent.replace("_", "-") if component_intent else None
    value: dict[str, object] = {"component": component, "variant": None}
    if target.position is not None:
        value["position"] = target.position
    capability = _INTENT_CAPABILITY.get(component_intent) if component_intent else None
    if capability is not None:
        value["capability"] = capability
    return value
