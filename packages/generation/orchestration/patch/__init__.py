"""Artifact Patch Planner - dry-run (KÖR-7b).

Third sibling of the orchestration layer, after ``router/`` (KÖR-6a, decides
*what* a message is) and ``context/`` (KÖR-7a, fetches *lagom* much context).
This package turns a ``RouterDecision`` + an ``AssembledContext`` into a
transient ``PatchPlan``: proposed patches against named artefakt fields, each
validated against the same rails planning uses.

Hard guarantees of this slice (kor-7b "Definition of done"):
- **Dry-run.** Nothing here writes a file, creates a run, applies a patch,
  starts a build or a preview, or touches ``current.json``. It proposes and
  validates; apply/version is KÖR-7c, targeted rebuild is KÖR-7d.
- **Named fields only.** Proposals are derived from the decision's
  ``editKind``/``target`` for ``component_add`` / ``copy_change``; an unknown
  section/dossier/field lands in ``rejected`` with a reason. The planner never
  invents a section and never emits a free file patch.
- **Deterministic + mock-safe.** Pure functions, no LLM, no ``OPENAI_API_KEY``.

A ``PatchPlan`` is a transient object returned to the caller, never a new
canonical run-artefakt (builder-profil §3).

Public API:
    plan_patches(decision, context, *, registry=None) -> PatchPlan
    validate_patch(patch, rails) -> str | None        # None == allowed
    rails_from_context(context, *, registry=None) -> PatchRails
    PatchPlan, ArtifactPatch, RejectedPatch, PatchRails, PatchOp
"""

from .models import ArtifactPatch, PatchOp, PatchPlan, PatchRails, RejectedPatch
from .planner import plan_patches
from .validate import rails_from_context, validate_patch

__all__ = [
    "ArtifactPatch",
    "PatchOp",
    "PatchPlan",
    "PatchRails",
    "RejectedPatch",
    "plan_patches",
    "rails_from_context",
    "validate_patch",
]
