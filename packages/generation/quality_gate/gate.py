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
    run_placeholder_copy_scan_check,
    run_policy_compliance_check,
    run_route_scan_check,
    run_typecheck_check,
)
from .models import CheckResult, QualityResult, QualityStatus

_CHECKS_REGISTRY: tuple[tuple[str, Literal["blocking", "warning"]], ...] = (
    ("typecheck", "blocking"),
    ("route-scan", "blocking"),
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
    ``degraded`` when route-scan or policy-compliance failed but the
    blocking checks are ok/skipped.
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
        by_name.get("route-scan", None)
        and by_name["route-scan"].status == "failed"
    ) or (
        by_name.get("policy-compliance", None)
        and by_name["policy-compliance"].status == "failed"
    )
    if soft_failed:
        return "degraded"

    return "ok"


def _summary_from_checks(checks: list[CheckResult], status: QualityStatus) -> str:
    failed = [c.name for c in checks if c.status == "failed"]
    skipped = [c.name for c in checks if c.status == "skipped"]
    parts = [f"status={status}"]
    if failed:
        parts.append(f"failed={','.join(failed)}")
    if skipped:
        parts.append(f"skipped={','.join(skipped)}")
    if not failed and not skipped:
        parts.append("alla checks ok")
    return " ".join(parts)


def run_quality_gate(
    *,
    target_dir: Path,
    required_routes: list[str],
    npm_steps: list[dict[str, Any]],
    build_status: str,
    do_typecheck: bool = True,
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
    """
    checks = [
        _with_registry_severity(run_typecheck_check(target_dir, do_typecheck=do_typecheck)),
        _with_registry_severity(run_route_scan_check(target_dir, required_routes)),
        _with_registry_severity(
            run_build_status_check(build_status=build_status, npm_steps=npm_steps)
        ),
        _with_registry_severity(run_policy_compliance_check(target_dir)),
        _with_registry_severity(run_contact_cta_presence_check(target_dir)),
        _with_registry_severity(run_placeholder_copy_scan_check(target_dir)),
    ]
    status = _aggregate_status(checks)
    summary = _summary_from_checks(checks, status)
    return QualityResult(status=status, checks=checks, summary=summary)
