"""Phase 3 codegenModel: produce a structured manifest of generated files.

Public API:
    produce_codegen_artefakt(generation_package, *, ...) -> CodegenResult
        Single source of truth for what fas 3 generates. Sprint 3A v1
        was deterministic. Sprint 3B-next (ADR 0017) adds a minimal
        real LLM call that enriches the manifest with rationale and
        riskNotes when ``OPENAI_API_KEY`` is set and ``starter_id`` is
        ``marketing-base``; the file list itself stays deterministic
        in all paths so a hallucinating LLM cannot inject arbitrary
        files.

    CodegenFile, CodegenResult, CodegenLLMResponse, CodegenUsage
        Pydantic types describing each generated file (path, source,
        role), the aggregated codegen output (files, source, modelUsed,
        rationale, riskNotes, usage, error), the narrow LLM response
        schema, and a token-usage record. Contracts locked by
        ADR 0015 + 0017.

    resolve_codegen_model
        Returns the OpenAI model id registered for ``codegenModel`` in
        ``governance/policies/llm-models.v1.json``. Mirrors
        ``resolve_brief_model`` and ``resolve_planning_model``.

    CodegenModelResolutionError
        Raised when the policy file is missing or misconfigured.

The manifest is fed to ``packages/generation/quality_gate`` (for
inspection) and ``packages/generation/repair`` (for context). It is
NOT written as a canonical artefakt; ``engine-run.v1.json:artifacts``
lists exactly eight artefacts and codegen metadata fits inside
``build-result.json``.
"""

from .codegen import produce_codegen_artefakt
from .models import (
    CodegenFile,
    CodegenLLMResponse,
    CodegenModelResolutionError,
    CodegenResult,
    CodegenUsage,
    resolve_codegen_model,
)

__all__ = [
    "CodegenFile",
    "CodegenLLMResponse",
    "CodegenModelResolutionError",
    "CodegenResult",
    "CodegenUsage",
    "produce_codegen_artefakt",
    "resolve_codegen_model",
]
