"""Phase 3 Quality Gate: run typecheck, route-scan, build-status and
policy-compliance checks against the generated site.

Public API:
    run_quality_gate(*, target_dir, required_routes, npm_steps,
                     build_status, do_typecheck=True) -> QualityResult
        Aggregates four checks into a single QualityResult. Locked by
        ADR 0015. Sprint 3A v1 reads results that scripts/build_site.py
        already computed (build_status, npm_steps) and runs typecheck +
        route-scan + policy-compliance directly.

    QualityResult, CheckResult
        Pydantic types for the gate output. Status aggregates to
        ``ok`` (all checks ok or skipped), ``degraded`` (something
        failed but typecheck and build were ok), or ``failed``
        (typecheck or build failed).

The Quality Gate does NOT mutate files - that is Repair Pipeline's
job. It also does NOT call repair logic itself; the orchestrator
chains them. Locked by repo-boundaries.v1.json:packages/generation/
quality_gate.
"""

from .critic import (
    CriticIssue,
    CriticResult,
    append_critic_trace_event,
    run_deterministic_critic,
)
from .gate import run_quality_gate
from .models import CheckResult, CheckStatus, QualityResult, QualityStatus

__all__ = [
    "CheckResult",
    "CheckStatus",
    "CriticIssue",
    "CriticResult",
    "QualityResult",
    "QualityStatus",
    "append_critic_trace_event",
    "run_deterministic_critic",
    "run_quality_gate",
]
