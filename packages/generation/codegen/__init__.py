"""Phase 3 codegenModel v1: produce a structured manifest of generated files.

Public API:
    produce_codegen_artefakt(generation_package, *, ...) -> CodegenResult
        Single source of truth for what fas 3 generates. Sprint 3A v1 is
        deterministic - it adapts the file list that scripts/build_site.py
        already writes. Later sprints replace the body with a real
        codegenModel LLM call that emits the manifest before files are
        written, and the builder becomes a thin writer of the manifest.

    CodegenFile, CodegenResult
        Pydantic types describing each generated file (path, source, role)
        and the aggregated codegen output (files, source, modelUsed,
        rationale, error). Locked by ADR 0015.

The manifest is fed to packages/generation/quality_gate (for inspection)
and packages/generation/repair (for context). It is NOT written as a
canonical artefakt; engine-run.v1.json:artifacts lists exactly eight
artefacts and codegen metadata fits inside build-result.json.
"""

from .codegen import produce_codegen_artefakt
from .models import CodegenFile, CodegenResult

__all__ = [
    "CodegenFile",
    "CodegenResult",
    "produce_codegen_artefakt",
]
