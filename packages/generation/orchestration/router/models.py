"""Pydantic types for the deterministic message router (KÖR-6a).

These types back the structured decision the router returns for a single
user message. The router (working name "OpenClaw Router" per
docs/heavy-llm-flow/02) sits on top of init/follow-up and decides *what*
a message is and *how much* the system must do - without calling an LLM,
without touching the generated site, and without starting a build or
preview for pure questions.

The field names are camelCase on purpose: they mirror the output contract
in docs/heavy-llm-flow/kor-6a and stay byte-stable with
governance/schemas/router-decision.schema.json. tests/test_router_schema.py
locks the Pydantic models against that schema (top-level + nested $defs)
so the artefact-on-disk and the in-memory type can never drift.

Nothing here is a new canonical artefakt: the router does not persist a
decision file of its own. It returns the decision to the caller and may
only append an Engine Event to an *existing* run's trace.ndjson.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Closed enums (mirror the kor-6a output contract + 02 §2)
# ---------------------------------------------------------------------------

MessageKind = Literal[
    "answer_only",
    "site_review",
    "edit_instruction",
    "component_discovery",
    "reference_analysis",
    "bug_report",
    "multi_intent",
    "unclear",
]

EditKind = Literal[
    "component_add",
    "component_remove",
    "section_add",
    "visual_style",
    "copy_change",
    "layout_change",
    "route_add",
    "none",
]

BuildRequirement = Literal[
    "none",
    "plan_only",
    "artifact_patch_only",
    "targeted_rebuild",
    "full_rebuild",
]

ContextLevel = Literal[
    "none",
    "project_dna",
    "artifacts",
    "artifacts_plus_sections",
    "manifest",
    "selected_files",
    "preview_dom",
    "external_reference",
    "component_registry",
]

# Coarse placement within a section/route. Resolved deterministically from
# the message; the actual sectionId mapping is left to the context layer
# (kor-7a) so this module stays read-only and free of disk I/O.
Position = Literal["left", "right", "center", "top", "bottom"]

# Scope of a single subtask inside a multi_intent decision.
SubtaskScope = Literal["global", "route", "section", "component"]


# ---------------------------------------------------------------------------
# Nested shapes
# ---------------------------------------------------------------------------


class RouterTarget(BaseModel):
    """Where an edit applies.

    ``sectionOrdinal`` is the 1-based ordinal parsed from the message
    ("andra sektionen" -> 2). ``sectionId`` stays ``None`` unless a caller
    passes a route/section map in the context so the router can resolve the
    ordinal to a concrete id; this keeps classification deterministic and
    avoids reading disk in the hot path.
    """

    routeId: str | None = None
    sectionId: str | None = None
    sectionOrdinal: int | None = None
    position: Position | None = None


class RouterReference(BaseModel):
    """An external reference the user pointed at ("som på aftonbladet.se")."""

    url: str
    object: str | None = None


class RouterSubtask(BaseModel):
    """One deluppgift inside a multi_intent decision.

    Fields are intentionally permissive-but-typed so a single subtask can
    describe a style change, a component add, or a constraint without a
    union type. Unused fields stay ``None``/empty.
    """

    editKind: EditKind = "none"
    instruction: str = ""
    scope: SubtaskScope | None = None
    componentIntent: str | None = None
    target: RouterTarget | None = None
    constraint: str | None = None


class RouterDecision(BaseModel):
    """The structured result the router returns for one user message.

    ``buildRequirement`` answers "how much must the system do?" and
    ``shouldStartPreview`` is the single actuation flag the router owns:
    it is only ever ``True`` for a real rebuild and is forced ``False``
    when a live user session is active on the same site (builder
    coexistence, see 02 §8).
    """

    messageKind: MessageKind
    editKind: EditKind = "none"
    buildRequirement: BuildRequirement = "none"
    contextLevel: ContextLevel = "none"
    target: RouterTarget | None = None
    subtasks: list[RouterSubtask] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    reference: RouterReference | None = None
    componentIntent: str | None = None
    risk: str | None = None
    rationale: str = ""
    requiresClarification: bool = False
    shouldStartPreview: bool = False


class RouterContext(BaseModel):
    """Optional, caller-supplied context for one classification.

    Everything here is read-only signal the router *may* use; it never
    fetches it itself. ``hasActiveUserSession`` enforces builder
    coexistence (no preview started against a site the operator is live in).
    ``routeSections`` lets a caller (kor-7a) resolve ``sectionOrdinal`` to a
    real ``sectionId`` without the router touching disk.
    """

    siteId: str | None = None
    hasActiveUserSession: bool = False
    routeSections: dict[str, list[str]] = Field(default_factory=dict)
    defaultRouteId: str = "home"
