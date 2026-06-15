"""Quality Gate orchestrator.

Runs the four Sprint 3A checks against a generated site and aggregates
them into a QualityResult. Calling code (scripts/build_site.py) writes
the result to ``data/runs/<runId>/quality-result.json``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from .checks import (
    run_build_status_check,
    run_contact_cta_presence_check,
    run_internal_link_scan_check,
    run_placeholder_copy_scan_check,
    run_policy_compliance_check,
    run_route_scan_check,
    run_typecheck_check,
)
from .critic import append_critic_trace_event, run_deterministic_critic
from .models import CheckResult, QualityResult, QualityStatus
from .verifier import run_verifier_critic

# Severity-fältet säger "räknas mot status alls", inte "failure → failed".
# Avbildning från severity + check-namn till QualityResult.status sker i
# _aggregate_status() nedan, per ADR 0015 §3:
#   - typecheck / build-status                         (blocking, hardest) → status=failed
#   - route-scan / internal-link-scan / policy-compliance (blocking, soft) → status=degraded
#   - contact-cta-presence / placeholder-copy-scan     (warning)           → no status change
#
# `degraded` är ett avsiktligt mellan-tillstånd: pipelinen får exit 0 men
# overall_status="degraded" så operatören ser att något failade och Repair
# Pipeline `remainingErrors[]` blir källan för triage. Att lyfta soft-
# blocking till `failed` bryter både kontraktet i
# packages/generation/quality_gate/models.py:QualityResult.status och testet
# tests/test_quality_gate.py::test_run_quality_gate_returns_degraded_on_soft_failure.
_CHECKS_REGISTRY: tuple[tuple[str, Literal["blocking", "warning"]], ...] = (
    ("typecheck", "blocking"),
    ("route-scan", "blocking"),
    ("internal-link-scan", "blocking"),
    ("build-status", "blocking"),
    ("policy-compliance", "blocking"),
    ("contact-cta-presence", "warning"),
    ("placeholder-copy-scan", "warning"),
)
_CHECK_SEVERITY = dict(_CHECKS_REGISTRY)


def _with_registry_severity(check: CheckResult) -> CheckResult:
    return check.model_copy(
        update={"severity": _CHECK_SEVERITY.get(check.name, check.severity)}
    )


def _aggregate_status(checks: list[CheckResult]) -> QualityStatus:
    """Compute QualityResult.status from individual checks.

    ``failed`` when typecheck or build-status failed (these are blocking).
    ``degraded`` when route-scan, internal-link-scan or policy-compliance
    failed but the hardest blocking checks (typecheck/build-status) are
    ok/skipped.
    ``ok`` otherwise.
    """
    blocking_checks = [c for c in checks if c.severity == "blocking"]
    by_name = {check.name: check for check in blocking_checks}

    blocking_failed = (
        by_name.get("typecheck", None)
        and by_name["typecheck"].status == "failed"
    ) or (
        by_name.get("build-status", None)
        and by_name["build-status"].status == "failed"
    )
    if blocking_failed:
        return "failed"

    soft_failed = (
        (
            by_name.get("route-scan", None)
            and by_name["route-scan"].status == "failed"
        )
        or (
            by_name.get("internal-link-scan", None)
            and by_name["internal-link-scan"].status == "failed"
        )
        or (
            by_name.get("policy-compliance", None)
            and by_name["policy-compliance"].status == "failed"
        )
    )
    if soft_failed:
        return "degraded"

    return "ok"


def _summary_from_checks(checks: list[CheckResult], status: QualityStatus) -> str:
    """Build the operator-facing one-line summary.

    Splits failed checks by severity so the summary cannot contradict
    ``status``: blocking failures appear as ``failed=...`` (and drive
    ``status`` to ``degraded``/``failed``), warning failures appear as
    ``warning=...`` (do not lower ``status`` from ``ok``).
    """
    blocking_failed = [
        c.name for c in checks
        if c.status == "failed" and c.severity == "blocking"
    ]
    warning_failed = [
        c.name for c in checks
        if c.status == "failed" and c.severity == "warning"
    ]
    skipped = [c.name for c in checks if c.status == "skipped"]
    parts = [f"status={status}"]
    if blocking_failed:
        parts.append(f"failed={','.join(blocking_failed)}")
    if warning_failed:
        parts.append(f"warning={','.join(warning_failed)}")
    if skipped:
        parts.append(f"skipped={','.join(skipped)}")
    if not blocking_failed and not warning_failed and not skipped:
        parts.append("alla checks ok")
    return " ".join(parts)


def run_quality_gate(
    *,
    target_dir: Path,
    required_routes: list[str],
    npm_steps: list[dict[str, Any]],
    build_status: str,
    do_typecheck: bool = True,
    generation_package: dict[str, Any] | None = None,
    site_brief: dict[str, Any] | None = None,
    run_dir: Path | None = None,
    run_id: str | None = None,
    use_verifier_critic: bool = False,
) -> QualityResult:
    """Run all four Quality Gate checks and aggregate into a QualityResult.

    Parameters mirror what scripts/build_site.py already computes during
    fas 3 so the gate can run without re-doing build work.

    - ``target_dir``: the generated Next.js project directory.
    - ``required_routes``: routes that must exist with default export
      (subset of the scaffold's route plan, per
      ``required_routes(scaffold_routes)`` in the builder).
    - ``npm_steps``: list of {"name", "ok", "seconds"} dicts that the
      builder produced when running npm install / npm run build.
    - ``build_status``: ``ok`` / ``failed`` / ``skipped`` from the builder.
    - ``do_typecheck``: pass False to skip typecheck regardless of
      node_modules state (used by --skip-build paths and tests).

    kor-4a deterministic critic (warning lane, additive + opt-in):

    - ``generation_package``: when the blueprint is supplied the deterministic
      critic runs over it (plus the optional ``site_brief`` honesty/contact
      fields and the generated output) and the result is attached to
      ``QualityResult.critic``. ``site_brief`` alone does NOT trigger the critic
      — without a blueprint there are no ``contentBlocks`` to critique, so the
      gate would otherwise emit false findings (e.g. a spurious ``missing_cta``
      on empty content). With no blueprint (the Repair Pipeline / legacy
      callers) ``critic`` stays ``None`` and the gate behaves exactly as
      before. The critic NEVER affects ``status``.
    - ``run_dir`` / ``run_id``: when a run directory exists, the critic logs a
      non-blocking ``critic.evaluated`` event to ``<run_dir>/trace.ndjson``.

    kor-4b verifierModel critic (opt-in, still a warning lane):

    - ``use_verifier_critic``: when True (and a blueprint is supplied) the
      critic runs through ``run_verifier_critic`` instead of the deterministic
      lane - it merges read-only ``verifierModel`` taste findings on top of the
      deterministic ones (deduped per ``(type, target)``) and sets
      ``critic.source`` to ``verifierModel``. Without ``OPENAI_API_KEY`` (or on
      any LLM error) it falls back to exactly the deterministic findings with
      ``source = "mock-no-key"`` / ``mock-llm-error`` (identical findings to
      kor-4a, no regression). Default is False so existing callers keep the
      ``deterministic-v0`` behaviour unchanged. The verifier critic, like the
      deterministic one, NEVER affects ``status``.
    """
    checks = [
        _with_registry_severity(run_typecheck_check(target_dir, do_typecheck=do_typecheck)),
        _with_registry_severity(run_route_scan_check(target_dir, required_routes)),
        _with_registry_severity(run_internal_link_scan_check(target_dir)),
        _with_registry_severity(
            run_build_status_check(build_status=build_status, npm_steps=npm_steps)
        ),
        _with_registry_severity(run_policy_compliance_check(target_dir)),
        _with_registry_severity(run_contact_cta_presence_check(target_dir)),
        _with_registry_severity(run_placeholder_copy_scan_check(target_dir)),
    ]
    status = _aggregate_status(checks)
    summary = _summary_from_checks(checks, status)

    critic = None
    if generation_package is not None:
        if use_verifier_critic:
            critic = run_verifier_critic(
                generation_package=generation_package,
                site_brief=site_brief,
                target_dir=target_dir,
            )
        else:
            critic = run_deterministic_critic(
                generation_package=generation_package,
                site_brief=site_brief,
                target_dir=target_dir,
            )
        if run_dir is not None:
            append_critic_trace_event(run_dir, run_id or "unknown", critic)

    return QualityResult(status=status, checks=checks, summary=summary, critic=critic)
