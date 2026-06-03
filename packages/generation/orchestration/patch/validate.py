"""Rail validation for the Artifact Patch Planner (KÖR-7b).

``validate_patch`` runs the **same rails as planning** over a single proposed
patch and returns ``None`` when the patch is allowed, or a human-readable
reason when a rail refuses it:

1. **artifact** - only ``generation-package.json`` is patchable (the blueprint
   lives there, 01 §1).
2. **field root** - must be a blueprint root the planner may patch
   (``contentBlocks`` / ``visualDirection``; never identity/refs).
3. **section** - a ``contentBlocks`` / ``visualDirection.sectionTreatments``
   address must resolve to a section that exists in the scaffold's
   ``sections.json`` (required or optional) for that route. Unknown route or
   section -> rejected (the planner never invents a section).
4. **accessoryComponent** - a ``contentBlocks.*.accessoryComponent`` value must
   name a component; a ``{"component": None}`` (or component-less) descriptor is
   a semantically empty component_add and is rejected (the planner invents no
   component name).
5. **capability/dossier** - when the patch value references a capability, that
   capability must exist in ``capability-map.v1.json`` *and* have an
   implementing dossier (an empty dossiers list is a gap, not a feature).

Every rail is read from a :class:`PatchRails` projection of the assembled
context (KÖR-7a) - the validator hardcodes nothing dynamic itself
(kor-7b: "Läs rälsen ur den assemblade contexten - hårdkoda inte").
``validate_patch`` is pure and side-effect free: no disk, no build, no write.
"""

from __future__ import annotations

import re
from typing import Any

from ..context.models import AssembledContext
from .models import (
    GENERATION_PACKAGE_ARTIFACT,
    ArtifactPatch,
    PatchRails,
)

__all__ = ["rails_from_context", "validate_patch"]

# The addressing contract from 01 §5 / the generation-package schema's
# propertyNames pattern: a section key is exactly ``<routeId>.<sectionId>`` and
# each id is ``[A-Za-z0-9_-]+``.
_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def rails_from_context(
    context: AssembledContext | None,
    *,
    registry: AssembledContext | None = None,
) -> PatchRails:
    """Project the rails a patch is validated against out of assembled context.

    ``context`` is expected to be an ``artifacts_plus_sections`` result (it
    carries ``sections`` + the derived ``routeSections``); ``registry`` is an
    optional ``component_registry`` result carrying the capability projection.
    Both are read read-only from the payload the assembler already produced -
    this function never reads disk and never re-assembles anything.
    """
    rails = PatchRails()

    payload: dict[str, Any] = context.payload if context is not None else {}
    sections = payload.get("sections")
    if isinstance(sections, dict):
        rails.sections = sections
    route_sections = payload.get("routeSections")
    if isinstance(route_sections, dict):
        # Keep only well-typed entries (list[str]) so a malformed payload can
        # never crash the validator.
        rails.routeSections = {
            route: [s for s in ids if isinstance(s, str)]
            for route, ids in route_sections.items()
            if isinstance(ids, list)
        }

    if registry is not None:
        rails.capabilitiesAvailable = True
        capabilities = registry.payload.get("capabilities")
        if isinstance(capabilities, list):
            for item in capabilities:
                if isinstance(item, dict) and isinstance(item.get("capability"), str):
                    rails.capabilities[item["capability"]] = item

    return rails


def _section_address(root: str, segments: list[str]) -> tuple[str, str] | None:
    """Return the ``(routeId, sectionId)`` a field addresses, or ``None``.

    - ``contentBlocks.<route>.<section>[.<leaf>...]`` -> (route, section)
    - ``visualDirection.sectionTreatments.<route>.<section>`` -> (route, section)
    - any other ``visualDirection.<prop>`` -> ``None`` (not section-addressed)
    """
    if root == "contentBlocks":
        if len(segments) >= 3:
            return segments[1], segments[2]
        return None
    if root == "visualDirection" and len(segments) >= 4 and segments[1] == "sectionTreatments":
        return segments[2], segments[3]
    return None


def validate_patch(patch: ArtifactPatch, rails: PatchRails) -> str | None:
    """Validate one proposed patch against the rails. ``None`` == allowed.

    Pure and deterministic. Returns the first failing rail's reason so a caller
    can drop the patch into ``PatchPlan.rejected`` with that reason.
    """
    # 1. artifact rail.
    if patch.artifact != GENERATION_PACKAGE_ARTIFACT:
        return (
            f"artifact {patch.artifact!r} is not patchable by the planner "
            f"(only {GENERATION_PACKAGE_ARTIFACT})"
        )

    # 2. op rail (defensive: PatchOp is a closed enum, but a hand-built patch
    # could still smuggle a bad op past static typing).
    if patch.op != "set":
        return f"unsupported op {patch.op!r} (only 'set')"

    # 3. field-root rail.
    segments = patch.field.split(".") if patch.field else []
    root = segments[0] if segments else ""
    if root not in rails.patchableRoots:
        return (
            f"field root {root!r} is not a patchable blueprint field "
            f"(allowed: {', '.join(rails.patchableRoots)})"
        )

    # contentBlocks must always be section-addressed (01 §5).
    if root == "contentBlocks" and len(segments) < 3:
        return (
            f"contentBlocks field {patch.field!r} must address "
            "'<routeId>.<sectionId>' (kor-1a addressing contract)"
        )
    # visualDirection top-level prop must be a known field.
    if root == "visualDirection":
        if len(segments) < 2 or segments[1] not in rails.visualDirectionFields:
            sub = segments[1] if len(segments) >= 2 else ""
            return (
                f"visualDirection field {sub!r} is not a known visualDirection "
                "property"
            )

    # 4. section rail (for section-addressed fields).
    address = _section_address(root, segments)
    if address is not None:
        route_id, section_id = address
        if not _ID_RE.match(route_id) or not _ID_RE.match(section_id):
            return (
                f"address {route_id!r}.{section_id!r} is malformed; each id must "
                "match '[A-Za-z0-9_-]+' (01 §5 addressing contract)"
            )
        if not rails.knows_route(route_id):
            return f"route {route_id!r} is not in the scaffold rails (sections.json)"
        allowed = rails.allowed_sections(route_id)
        if section_id not in allowed:
            return (
                f"section '{route_id}.{section_id}' is not in the scaffold "
                "sections.json rails (required/optional)"
            )

    # 5. accessoryComponent rail: a component_add patch must name a component.
    # A {"component": None} (or component-less) value is a valid-shaped but
    # empty component_add; reject it defensively so a hand-built patch cannot
    # slip a no-op accessoryComponent past the rails (mirrors the planner gate).
    if (
        root == "contentBlocks"
        and len(segments) >= 4
        and segments[3] == "accessoryComponent"
        and isinstance(patch.value, dict)
        and not patch.value.get("component")
    ):
        return (
            "accessoryComponent patch carries no named component "
            "(value.component saknas); inget att lägga till"
        )

    # 6. capability/dossier rail (only when the value references one).
    capability = _referenced_capability(patch.value)
    if capability is not None:
        if not rails.capabilitiesAvailable:
            return (
                f"capability {capability!r} is referenced but the component "
                "registry rail was not assembled (need a 'component_registry' "
                "context to verify the dossier)"
            )
        spec = rails.capabilities.get(capability)
        if spec is None:
            return f"capability {capability!r} is not in the capability-map rails"
        dossiers = spec.get("dossiers") if isinstance(spec, dict) else None
        if not dossiers:
            return (
                f"capability {capability!r} has no implementing dossier in the "
                "capability-map (gap, not a feature)"
            )

    return None


def _referenced_capability(value: Any) -> str | None:
    """The capability slug a patch value references, if any.

    A ``component_add`` value may carry ``{"capability": "<slug>"}`` when the
    component maps to a registered capability; an inline component (e.g. a
    clock) carries no capability key and so skips the dossier rail entirely.
    """
    if isinstance(value, dict):
        capability = value.get("capability")
        if isinstance(capability, str) and capability:
            return capability
    return None
