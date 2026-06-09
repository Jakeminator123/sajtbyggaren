"""Transient result types for the Artifact Patch apply step (KÖR-7c).

The apply step turns a **validated** :class:`~packages.generation.orchestration.patch.PatchPlan`
(from KÖR-7b) into the **next** Project Input version. It applies nothing in
place: a follow-up is a *new version of the same site*, never an overwrite of
history (kor-7c "Immutabilitetsregel"). These types describe the outcome of one
apply attempt; like the router's ``RouterDecision`` and the planner's
``PatchPlan`` they are **transient** objects returned to the caller, never a new
canonical run-artefakt (builder-profil §3, the ordregel).

The field names are camelCase so a serialised ``ApplyResult`` reads the same as
the rest of the orchestration layer's structured outputs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = [
    "AppliedCapability",
    "ApplyResult",
    "PatchApplyError",
    "UnmappedPatch",
]


class PatchApplyError(Exception):
    """Raised when a plan must never be applied at all.

    A ``rejected``/invalid plan (kor-7b put a rail-breaking patch in
    ``rejected`` and set ``valid=False``) is refused here: apply never writes a
    version for a plan that did not pass the rails (kor-7c DoD: "En rejected/
    ogiltig patch appliceras aldrig"). This is a hard stop, distinct from the
    soft "valid plan, but a patch has no Project Input home" case which is
    reported as :class:`UnmappedPatch` on a non-applied :class:`ApplyResult`.
    """


class AppliedCapability(BaseModel):
    """One validated patch mapped onto an existing Project Input field.

    The KÖR-7b ``PatchPlan`` addresses ``generation-package.json`` blueprint
    fields; KÖR-7c stores the validated change as a *version-delta on the
    Project Input* via the existing directive mechanism (builder-profil §3:
    reuse the field, do not mint a new canonical artefakt). The only kor-7b
    patch shape that has an existing Project Input home is a ``component_add``
    that references a registered capability: it is recorded as a
    ``requestedCapabilities`` entry, exactly the field the discovery wizard
    already feeds and ``produce_site_plan`` / the build already consume.
    """

    patchField: str
    capability: str
    projectInputField: Literal["requestedCapabilities"] = "requestedCapabilities"


class UnmappedPatch(BaseModel):
    """A validated patch with no existing Project Input field to land in.

    These are patch shapes the kor-7b planner can emit but that today have no
    Project Input home: an inline ``component_add`` (a component with no
    registered capability, e.g. a clock) or a ``copy_change`` against a section
    headline (whose new copy is produced downstream by the copy model, kor-1c).
    Giving them a home would require a **new** directive field plus a build-side
    consumer - a new runtime contract that needs an operator decision + ADR
    (builder-profil §4). Apply therefore never invents one: it reports the
    unmapped patches and writes **no** version, leaving the call all-or-nothing.
    """

    patchField: str
    op: str
    value: Any = None
    reason: str


class ApplyResult(BaseModel):
    """The transient outcome of one apply attempt.

    ``applied`` is ``True`` only when every patch in a valid plan mapped onto an
    existing Project Input field and the next version snapshot was written.
    When any patch is unmapped (or the plan was empty) ``applied`` is ``False``,
    nothing is written, and ``unmapped`` names what needs an operator decision.
    """

    applied: bool
    siteId: str
    projectId: str | None = None
    previousVersion: int | None = None
    version: int | None = None
    projectInputPath: str | None = None
    metaPath: str | None = None
    appliedCapabilities: list[AppliedCapability] = Field(default_factory=list)
    unmapped: list[UnmappedPatch] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # Logical route ids a section_add surfaced as a NEW visible dedicated page
    # (e.g. ``["faq"]``) by recording the wizard label on the next version's
    # meta sidecar. Empty for component_add, restyle, and mount-only section
    # adds. The targeted-render layer uses it to attribute the affected route to
    # the surfaced page instead of the home default.
    sectionRoutesSurfaced: list[str] = Field(default_factory=list)
