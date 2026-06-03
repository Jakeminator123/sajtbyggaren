"""Artifact patch apply + next version (KÖR-7c).

Fourth sibling of the orchestration layer, after ``router/`` (KÖR-6a, decides
*what* a message is), ``context/`` (KÖR-7a, fetches *lagom* much context) and
``patch/`` (KÖR-7b, proposes + validates a transient ``PatchPlan``). This
package applies a **validated** ``PatchPlan`` by creating the **next** Project
Input version - never an in-place edit of history, never a build.

Hard guarantees of this slice (kor-7c "Definition of done"):
- **Immutable.** Only the next ``<siteId>.v<N+1>`` snapshot is written; no prior
  ``vN`` snapshot and no ``data/runs/<älder runId>/`` artefakt is touched.
- **Identity preserved, scaffold/variant frozen** - via the existing follow-up
  merge in ``scripts/prompt_to_project_input.py`` (reuse, not duplicate).
- **No build, no ``current.json``-swap** (that is KÖR-7d). Apply only advances
  the prompt-inputs version pointer.
- **Rejected/invalid never applies.** A plan that failed kor-7b's rails raises
  ``PatchApplyError``; a valid plan whose patch has no existing Project Input
  field writes nothing and reports the gap (it never invents a new contract).
- **Mock-safe + deterministic.** No LLM, no ``OPENAI_API_KEY``.

An ``ApplyResult`` is a transient object returned to the caller, never a new
canonical run-artefakt (builder-profil §3).

Public API:
    apply_patch_plan(plan, *, site_id, ...) -> ApplyResult
    classify_patch(patch) -> (capability, None) | (None, reason)
    log_patch_apply_to_existing_run(run_dir, result, *, run_id=None) -> bool
    ApplyResult, AppliedCapability, UnmappedPatch, PatchApplyError
"""

from .apply import apply_patch_plan
from .mapping import classify_patch
from .models import (
    AppliedCapability,
    ApplyResult,
    PatchApplyError,
    UnmappedPatch,
)
from .trace import log_patch_apply_to_existing_run

__all__ = [
    "AppliedCapability",
    "ApplyResult",
    "PatchApplyError",
    "UnmappedPatch",
    "apply_patch_plan",
    "classify_patch",
    "log_patch_apply_to_existing_run",
]
