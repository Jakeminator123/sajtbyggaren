"""Read-only Context Assembler for the orchestration layer (KÖR-7a).

Sibling to ``orchestration/router/`` (KÖR-6a). The router decides *which*
``contextLevel`` a message needs; this module fetches exactly that level -
*lagom* much context per question - with a hard character budget per level
and anti-bloat suppression of files the previous version already showed
(docs/heavy-llm-flow/02 §4).

Hard guarantees (kor-7a):
- Read-only: nothing here writes a file, creates a run, starts a build, or
  starts a preview/adapter. ``preview_dom`` only reads an already-captured
  snapshot.
- ``external_reference`` is behind a permission gate and performs no network
  I/O itself - the caller injects the fetch tool only when the gate allows.
- ``AssembledContext.charCount <= charBudget`` always holds.

Public API:
    assemble_context(level, *, ...) -> AssembledContext         # dispatch
    assemble_none / assemble_project_dna / assemble_artifacts /
    assemble_artifacts_plus_sections / assemble_component_registry /
    assemble_manifest / assemble_selected_files / assemble_preview_dom /
    assemble_external_reference                                  # per level
    AssembledContext, PriorContext, ReferencePermission,
    ManifestEntry, SelectedFile, ContextLevel
    ContextPaths, DEFAULT_BUDGETS
"""

from .assemble import (
    assemble_artifacts,
    assemble_artifacts_plus_sections,
    assemble_component_registry,
    assemble_context,
    assemble_external_reference,
    assemble_manifest,
    assemble_none,
    assemble_preview_dom,
    assemble_project_dna,
    assemble_selected_files,
)
from .budgets import DEFAULT_BUDGETS
from .models import (
    AssembledContext,
    ContextLevel,
    ManifestEntry,
    PriorContext,
    ReferencePermission,
    SelectedFile,
)
from .sources import ContextPaths

__all__ = [
    "DEFAULT_BUDGETS",
    "AssembledContext",
    "ContextLevel",
    "ContextPaths",
    "ManifestEntry",
    "PriorContext",
    "ReferencePermission",
    "SelectedFile",
    "assemble_artifacts",
    "assemble_artifacts_plus_sections",
    "assemble_component_registry",
    "assemble_context",
    "assemble_external_reference",
    "assemble_manifest",
    "assemble_none",
    "assemble_preview_dom",
    "assemble_project_dna",
    "assemble_selected_files",
]
