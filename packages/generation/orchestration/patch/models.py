"""Transient Pydantic types for the Artifact Patch Planner (KÖR-7b).

The planner turns a deterministic router decision (KÖR-6a) plus an assembled
context (KÖR-7a) into *proposed* patches against named artefakt fields and
validates them against the same rails planning uses. It is a **dry-run**: it
proposes and validates, it never applies, writes, builds or previews
(apply/version is KÖR-7c, rebuild is KÖR-7d).

Nothing here is a new canonical artefakt. A ``PatchPlan`` is a **transient**
object the planner returns to its caller, exactly like the router returns a
``RouterDecision`` and the assembler returns an ``AssembledContext`` - it is
never persisted as a ``patch-plan.json`` (builder-profil §3, the ordregel:
forbid canonicalisation, not the word "patch plan").

Field names are camelCase on purpose so a serialised ``PatchPlan`` reads the
same as the structured-output example in docs/heavy-llm-flow/02 §6 and the
output shape in kor-7b. The core shape per the card is::

    {"patches": [{"artifact": ..., "field": ..., "op": "set", "value": ...}],
     "valid": bool,
     "rejected": [{..., "reason": ...}]}

``notes`` is an additive transient diagnostic (like ``AssembledContext.notes``
and ``RouterDecision.rationale``); it carries no canonical contract.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = [
    "ArtifactPatch",
    "PatchOp",
    "PatchPlan",
    "PatchRails",
    "RejectedPatch",
]

# Only "set" is part of the patch contract (kor-7b output example + 02 §6).
# A closed enum keeps the apply step (kor-7c) from ever seeing an op it does
# not understand.
PatchOp = Literal["set"]

# The single artefakt the planner is allowed to patch. The blueprint lives in
# the Generation Package ("the only payload that enters codegen", 01 §1), so
# that is where copy/component patches land.
GENERATION_PACKAGE_ARTIFACT = "generation-package.json"

# Top-level Generation Package fields the planner may address. These are the
# *blueprint* fields (01 §4-5 + governance/schemas/generation-package.schema.json):
# identity/refs (runId, scaffoldId, ...) are never patched by the planner. This
# is a stable contract constant, not a runtime rail - the dynamic rails
# (which sections / capabilities exist) are read live from the assembled
# context, never hardcoded (see ``PatchRails`` / ``rails_from_context``).
PATCHABLE_ROOTS: tuple[str, ...] = ("contentBlocks", "visualDirection")

# Known sub-properties of ``visualDirection`` (mirrors the schema's
# ``visualDirection.properties``). Used only when ``validate_patch`` is called
# directly with a visualDirection patch; the planner itself emits contentBlocks
# patches.
VISUAL_DIRECTION_FIELDS: tuple[str, ...] = (
    "mood",
    "density",
    "heroStyle",
    "colorIntent",
    "sectionTreatments",
    "imageBriefs",
    "layoutSignals",
)


class ArtifactPatch(BaseModel):
    """One proposed change to a named artefakt field.

    ``field`` is the address contract from 01 §5: ``<root>.<routeId>.<sectionId>``
    plus a leaf (e.g. ``contentBlocks.home.service-summary.accessoryComponent``).
    ``value`` is intentionally open: for ``component_add`` it is a small
    descriptor (``{"component": ..., "variant": ..., "capability"?: ...}``); for
    ``copy_change`` it is ``None`` because the new copy is produced downstream by
    the copy model (kor-1c), never invented by the router/planner (honesty rule).
    """

    artifact: str
    field: str
    op: PatchOp = "set"
    value: Any = None


class RejectedPatch(BaseModel):
    """A proposed patch that failed a rail, echoed with the reason it was rejected.

    Echoing the full proposed patch (not just the reason) keeps the dry-run
    auditable: a caller/trace can see exactly what was proposed and why the
    rails refused it, without re-deriving it.
    """

    artifact: str
    field: str
    op: PatchOp = "set"
    value: Any = None
    reason: str


class PatchPlan(BaseModel):
    """The transient result the planner returns for one router decision.

    ``valid`` is ``True`` only when no proposal was rejected. An empty plan
    (no patchable edit in the decision) is trivially valid with an explanatory
    note. The plan is never written to disk - it is returned to the caller, like
    the router's decision and the assembler's context.
    """

    patches: list[ArtifactPatch] = Field(default_factory=list)
    valid: bool = True
    rejected: list[RejectedPatch] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PatchRails(BaseModel):
    """The rails a patch is validated against, projected from assembled context.

    Everything dynamic here is *read* from an ``AssembledContext`` (KÖR-7a), not
    hardcoded (kor-7b: "Läs rälsen ur den assemblade contexten"):

    - ``sections``/``routeSections`` come from an ``artifacts_plus_sections``
      context (scaffold ``sections.json`` + the derived ordinal->sectionId map).
    - ``capabilities`` come from a ``component_registry`` context
      (``capability-map.v1.json`` projection); ``capabilitiesAvailable`` records
      whether such a context was supplied, so the validator can tell
      "capability not in map" from "capability rail not assembled".

    ``patchableRoots`` is the only contract constant (the blueprint roots, see
    ``PATCHABLE_ROOTS``); it is carried on the rails so ``validate_patch`` reads
    it from the rails object and hardcodes nothing itself.
    """

    sections: dict[str, Any] = Field(default_factory=dict)
    routeSections: dict[str, list[str]] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    capabilitiesAvailable: bool = False
    patchableRoots: list[str] = Field(default_factory=lambda: list(PATCHABLE_ROOTS))
    visualDirectionFields: list[str] = Field(
        default_factory=lambda: list(VISUAL_DIRECTION_FIELDS)
    )

    def allowed_sections(self, route_id: str) -> list[str]:
        """Ordered ``sectionId``s allowed on ``route_id`` (required + optional).

        Prefers the assembler's derived ``routeSections`` projection; falls back
        to deriving it from the raw ``sections.json`` map when a tight context
        budget dropped the projection but kept the sections.
        """
        if route_id in self.routeSections:
            return self.routeSections[route_id]
        spec = self.sections.get(route_id)
        if isinstance(spec, dict):
            required = spec.get("requiredSections", [])
            optional = spec.get("optionalSections", [])
            if isinstance(required, list) and isinstance(optional, list):
                return [*required, *optional]
        return []

    def knows_route(self, route_id: str) -> bool:
        return route_id in self.routeSections or route_id in self.sections
