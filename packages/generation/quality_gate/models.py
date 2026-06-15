"""Pydantic types for Quality Gate output.

Locked by ADR 0015 so Repair Pipeline can rely on a stable shape and so
build-result.json can serialise the QualityResult without drift.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .critic import CriticResult

CheckName = Literal[
    "typecheck",
    "route-scan",
    "internal-link-scan",
    "build-status",
    "policy-compliance",
    "contact-cta-presence",
    "placeholder-copy-scan",
]

CheckStatus = Literal["ok", "failed", "skipped"]

QualityStatus = Literal["ok", "degraded", "failed"]


class CheckResult(BaseModel):
    """One Quality Gate check.

    ``findings`` lists specific issues (missing routes, tsc errors,
    forbidden file paths) so Repair Pipeline can act on them. ``detail``
    is a short human-readable summary for operators reading
    quality-result.json.
    """

    name: CheckName
    status: CheckStatus
    detail: str = ""
    findings: list[str] = Field(default_factory=list)
    durationMs: int = 0
    severity: Literal["blocking", "warning"] = "blocking"


class QualityResult(BaseModel):
    """Aggregated Quality Gate output.

    ``status`` rules:
      - ``ok`` when every blocking check is ``ok`` or ``skipped``.
        Warning checks (severity=``warning``) may fail without lowering
        ``status``.
      - ``failed`` when typecheck or build-status is ``failed``
        (these are blocking).
      - ``degraded`` when route-scan, internal-link-scan or
        policy-compliance is ``failed`` but typecheck and build-status
        are ok or skipped.

    ``summary`` is a short string that build-result.json can surface
    without rendering the full check list. Failed blocking checks
    appear as ``failed=...``; failed warning checks appear as
    ``warning=...`` so the summary stays consistent with ``status``.

    ``critic`` is the optional deterministic Quality Critic lane (kor-4a):
    ``{score, issues, source="deterministic-v0"}``. It is a **warning lane**
    and NEVER feeds ``status`` aggregation. It stays ``None`` (serialised as
    ``null``) unless the caller passes the blueprint into ``run_quality_gate``;
    existing runs and the Repair Pipeline never set it.
    """

    status: QualityStatus
    checks: list[CheckResult]
    summary: str = ""
    critic: CriticResult | None = None
