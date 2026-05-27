#!/usr/bin/env python3
"""Run a canonical eval suite over the committed example dossiers.

Two modes:

* ``quick`` — runs the ``QUICK_CASES`` fixtures with ``--skip-build`` for
  a fast regression smoke check (no npm).
* ``full`` — runs the ``FULL_CASES`` fixtures without ``--skip-build`` so
  ``npm install`` + ``npm run build`` are exercised against each scaffold
  that has a real on-disk implementation. Case counts are reported in
  the CLI ``--help`` text dynamically via ``format_case_list()`` so they
  stay in sync if new fixtures land. Backoffice button labels read the
  same helpers (``get_quick_case_ids`` / ``get_full_case_ids``).

For each case the runner reads the canonical artefakter under
``data/runs/<runId>/`` and writes a summary to
``data/evals/summaries/suite/<evalRunId>.json`` containing the nine trace
fields that operators inspect to see whether the chain is alive:
``briefSource``, ``planSource``, ``scaffoldId``, ``variantId``,
``starterId``, ``selectedDossiers``, ``rejectedCapabilities``,
``qualityStatus`` and ``buildStatus``.

This is **smoke/regression signal, not a 1-10 quality score**. Manual
``1-10`` scorecards live separately under
``data/evals/summaries/manual-scorecards/<evalRunId>.json`` (format
documented in ``docs/evals.md``).

The runner is dev-tooling and does not modify ``build_site.py`` or any
``packages/generation/`` code. It is safe to invoke from the backoffice
Streamlit view (``backoffice/views/evals.py``) or directly from a shell.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_EVALS_DIR = REPO_ROOT / "data" / "evals"
# Sub-roots inside ``data/evals/`` (post evals-folder-plan). The CLI
# argument ``--evals-dir`` still overrides the top-level evals root so
# tests can point everything at ``tmp_path`` without knowing the new
# layout; ``run_suite`` derives the suite-specific summary/artifact
# directories from whatever evals root it ends up with.
SUITE_SUMMARIES_SUBDIR = ("summaries", "suite")
SUITE_ARTIFACTS_SUBDIR = ("artifacts", "suite")
RUNS_DIR = REPO_ROOT / "data" / "runs"
EXAMPLES_DIR = REPO_ROOT / "examples"

QUICK_CASES: tuple[str, ...] = (
    "atelje-bird",
    "painter-palma",
    "foto-ram",
    "arcade-hall",
    # restaurant-hospitality regression fixture, Issue #90. Pinned to the
    # warm-bistro variant + marketing-base starter; covers the menu and
    # booking renderers added in scripts/build_site.py write_pages.
    "cafe-bistro",
    # clinic-healthcare regression fixture, Path B step 12 (2026-05-25).
    # Pinned to the clinic-calm variant + marketing-base starter; covers
    # the new ``treatment-list`` / ``treatment-summary`` / ``credentials``
    # section renderers and the ``_DISPATCHED_SCAFFOLDS`` write_pages arm
    # so the section-driven dispatcher can be smoke-checked daily.
    "clinic-tandvard",
    # professional-services regression fixture, Path B step 13 (2026-05-25).
    # Pinned to the legal-classic variant + marketing-base starter; covers
    # the new ``expertise-areas`` / ``practice-grid`` / ``industries-served``
    # / ``partners-grid`` section renderers and the second
    # ``_DISPATCHED_SCAFFOLDS`` arm so PS regressions are caught daily.
    "advokatbyra-novum",
    # agency-studio regression fixture, Path B step 14 (2026-05-25).
    # Pinned to the studio-monochrome variant + marketing-base starter;
    # covers the new ``selected-work-preview`` / ``selected-work-grid``
    # / ``capabilities-row`` / ``manifesto-block`` / ``process-steps`` /
    # ``client-roster`` section renderers and the third
    # ``_DISPATCHED_SCAFFOLDS`` arm.
    "studio-bjork",
)

FULL_CASES: tuple[str, ...] = (
    "painter-palma",
    "atelje-bird",
    # restaurant-hospitality (warm-bistro variant, marketing-base starter).
    # Added in eval-hardening so the full suite covers all three on-disk
    # scaffolds (local-service-business via painter-palma, ecommerce-lite
    # via atelje-bird, restaurant-hospitality via cafe-bistro) and not
    # just the first two. Without this entry the menu+booking renderers
    # added in Issue #90 (PR #93) are only verified via targeted full
    # builds, never via the canonical full-suite regression signal.
    "cafe-bistro",
    # clinic-healthcare (clinic-calm variant, marketing-base starter).
    # Added 2026-05-25 alongside Path B step 12 so the full suite also
    # covers all four on-disk scaffolds. Without this entry the new
    # ``_DISPATCHED_SCAFFOLDS`` dispatch arm is only verified via the
    # quick suite and targeted full builds.
    "clinic-tandvard",
    # professional-services (legal-classic variant, marketing-base starter).
    # Added 2026-05-25 alongside Path B step 13 so the full suite covers
    # all five on-disk scaffolds and exercises both
    # ``_DISPATCHED_SCAFFOLDS`` arms (clinic + professional-services).
    "advokatbyra-novum",
    # agency-studio (studio-monochrome variant, marketing-base starter).
    # Added 2026-05-25 alongside Path B step 14 so the full suite covers
    # all six on-disk scaffolds and exercises every ``_DISPATCHED_SCAFFOLDS``
    # arm (clinic + professional-services + agency-studio).
    "studio-bjork",
)

# `scripts/build_site.py` prints `runId: <id>` on stdout. Other tools in
# the repo (dev_generate.py + playground.py) use `runId=<id>`; accept both
# so this runner stays robust if the print format is ever harmonised.
_RUN_ID_RE = re.compile(r"runId[:=]\s*(?P<run_id>[A-Za-z0-9._-]+)")


def get_quick_case_ids() -> tuple[str, ...]:
    """Return the canonical quick-suite case IDs.

    This small accessor keeps CLI help text and Backoffice labels tied to
    the same source of truth without importing or running any suite work.
    """

    return QUICK_CASES


def get_full_case_ids() -> tuple[str, ...]:
    """Return the canonical full-suite case IDs."""

    return FULL_CASES


def format_case_list(case_ids: tuple[str, ...], *, separator: str = ", ") -> str:
    """Format case IDs for human-facing CLI/UI text."""

    return separator.join(case_ids)


def utc_now_iso() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def make_eval_run_id() -> str:
    now = datetime.now(tz=UTC)
    stamp = now.strftime("%Y%m%dT%H%M%S")
    millis = f"{now.microsecond // 1000:03d}"
    short = uuid.uuid4().hex[:8]
    return f"eval-{stamp}.{millis}Z-{short}"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def extract_selected_dossiers(plan: dict[str, Any] | None) -> list[str]:
    """Return required Dossier IDs from a Site Plan.

    ``selectedDossiers`` is ``oneOf`` in
    ``governance/schemas/site-plan.schema.json``: a flat list of strings
    (legacy/array form) or an object split into ``required`` /
    ``recommended`` / ``conditional`` / ``rejected``. We surface the
    required set for both shapes; recommended/conditional buckets are
    intentionally not collapsed into the smoke summary to keep the field
    aligned with what build_site.py treats as authoritative.
    """

    if not plan:
        return []
    sd = plan.get("selectedDossiers")
    if isinstance(sd, list):
        return [str(item) for item in sd if isinstance(item, str)]
    if isinstance(sd, dict):
        required = sd.get("required", [])
        if isinstance(required, list):
            return [str(item) for item in required if isinstance(item, str)]
    return []


def extract_rejected_capabilities(plan: dict[str, Any] | None) -> list[dict[str, str]]:
    """Return rejected capability entries from a Site Plan.

    The schema places rejected entries under ``selectedDossiers.rejected``
    when the object form is used; the array form has no slot for them, so
    we report an empty list in that case. Each entry is
    ``{"id": ..., "reason": ...}``.
    """

    if not plan:
        return []
    sd = plan.get("selectedDossiers")
    if isinstance(sd, dict):
        rejected = sd.get("rejected", [])
        if isinstance(rejected, list):
            cleaned: list[dict[str, str]] = []
            for entry in rejected:
                if not isinstance(entry, dict):
                    continue
                rid = entry.get("id")
                reason = entry.get("reason", "")
                if isinstance(rid, str):
                    cleaned.append({"id": rid, "reason": str(reason)})
            return cleaned
    return []


def parse_case_artifacts(run_dir: Path) -> dict[str, Any]:
    """Read the nine trace fields from a finished run directory.

    Missing artefakter or fields are reported as ``None`` rather than
    raising — the summary is allowed to be partial when a case errors
    out mid-build.
    """

    brief = _read_json(run_dir / "site-brief.json") or {}
    plan = _read_json(run_dir / "site-plan.json") or {}
    quality = _read_json(run_dir / "quality-result.json") or {}
    build = _read_json(run_dir / "build-result.json") or {}
    repair = _read_json(run_dir / "repair-result.json") or {}

    return {
        "briefSource": brief.get("briefSource"),
        "planSource": plan.get("planSource"),
        "scaffoldId": plan.get("scaffoldId"),
        "variantId": plan.get("variantId"),
        "starterId": plan.get("starterId"),
        "selectedDossiers": extract_selected_dossiers(plan),
        "rejectedCapabilities": extract_rejected_capabilities(plan),
        "qualityStatus": quality.get("status"),
        "qualityChecks": [
            {"name": c.get("name"), "status": c.get("status")}
            for c in quality.get("checks", [])
            if isinstance(c, dict)
        ],
        "repairStatus": repair.get("status"),
        "buildStatus": build.get("status"),
    }


def _extract_run_id(output: str) -> str | None:
    match = _RUN_ID_RE.search(output)
    if not match:
        return None
    return match.group("run_id").strip().strip(".,") or None


def run_one_case(
    site_id: str,
    *,
    skip_build: bool,
    runs_dir: Path,
    examples_dir: Path,
    generated_dir: Path | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Invoke ``scripts/build_site.py`` for one dossier and parse artefakter.

    Returns a case dict that the caller appends to the suite summary.
    Subprocess failures are captured as ``error`` strings; the runner
    never re-raises so the rest of the suite can still finish.

    ``generated_dir`` is passed through to ``build_site.py --generated-dir``.
    Full builds receive a per-case directory so each run validates a clean
    ``npm install`` instead of reusing a cached ``node_modules`` from an
    earlier suite invocation (Codex P2 review on PR #87).
    """

    dossier_path = examples_dir / f"{site_id}.project-input.json"
    try:
        dossier_display = str(dossier_path.relative_to(REPO_ROOT))
    except ValueError:
        dossier_display = str(dossier_path)
    case: dict[str, Any] = {
        "siteId": site_id,
        "dossierPath": dossier_display,
        "skipBuild": skip_build,
        "generatedDir": str(generated_dir) if generated_dir is not None else None,
        "runId": None,
        "briefSource": None,
        "planSource": None,
        "scaffoldId": None,
        "variantId": None,
        "starterId": None,
        "selectedDossiers": [],
        "rejectedCapabilities": [],
        "qualityStatus": None,
        "qualityChecks": [],
        "repairStatus": None,
        "buildStatus": None,
        "error": None,
        "elapsedSeconds": 0.0,
    }

    if not dossier_path.exists():
        case["error"] = f"dossier not found: {dossier_path}"
        return case

    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "build_site.py"),
        "--dossier",
        str(dossier_path),
        "--runs-dir",
        str(runs_dir),
    ]
    if skip_build:
        cmd.append("--skip-build")
    if generated_dir is not None:
        cmd.extend(["--generated-dir", str(generated_dir)])

    started = time.monotonic()
    if verbose:
        mode_label = "skip-build" if skip_build else "full"
        print(f"  -> {site_id} ({mode_label}) ...", flush=True)
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        case["error"] = f"subprocess failed to start: {exc}"
        case["elapsedSeconds"] = round(time.monotonic() - started, 2)
        return case

    case["elapsedSeconds"] = round(time.monotonic() - started, 2)
    combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
    case["runId"] = _extract_run_id(combined)

    if completed.returncode != 0:
        tail = combined.strip().splitlines()[-12:]
        case["error"] = (
            f"build_site.py exit={completed.returncode}; tail: " + " | ".join(tail)
        )
    if not case["runId"]:
        if not case["error"]:
            case["error"] = "could not parse runId from build_site.py output"
        return case

    run_dir = runs_dir / case["runId"]
    if not run_dir.exists():
        if not case["error"]:
            case["error"] = f"run dir not found: {run_dir}"
        return case

    case.update(parse_case_artifacts(run_dir))
    if verbose:
        status_bits = [
            f"quality={case['qualityStatus'] or '-'}",
            f"build={case['buildStatus'] or '-'}",
            f"elapsed={case['elapsedSeconds']}s",
        ]
        print(f"     {' '.join(status_bits)}", flush=True)
    return case


def run_suite(
    mode: str,
    *,
    evals_dir: Path = DEFAULT_EVALS_DIR,
    runs_dir: Path = RUNS_DIR,
    examples_dir: Path = EXAMPLES_DIR,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run all cases for ``mode`` (``quick`` or ``full``) and write summary."""

    if mode == "quick":
        site_ids = QUICK_CASES
        skip_build = True
    elif mode == "full":
        site_ids = FULL_CASES
        skip_build = False
    else:
        raise ValueError(f"unknown mode: {mode!r} (expected 'quick' or 'full')")

    eval_run_id = make_eval_run_id()
    summary: dict[str, Any] = {
        "evalRunId": eval_run_id,
        "mode": mode,
        "createdAt": utc_now_iso(),
        "openaiKeyPresent": _has_openai_key(),
        "cases": [],
    }

    if verbose:
        print(f"eval-suite {mode} start (evalRunId={eval_run_id})", flush=True)

    # Full builds get a per-case generated directory so each case runs
    # a clean ``npm install`` instead of reusing the default
    # ``../sajtbyggaren-output/.generated/<siteId>`` target (which would
    # let ``copy_starter`` preserve a stale ``node_modules`` and make
    # the suite blind to dependency regressions). Skip-build keeps the
    # default target — there is no npm step to isolate.
    generated_root = evals_dir.joinpath(*SUITE_ARTIFACTS_SUBDIR) / eval_run_id

    for site_id in site_ids:
        case_generated_dir = None if skip_build else generated_root / site_id
        case = run_one_case(
            site_id,
            skip_build=skip_build,
            runs_dir=runs_dir,
            examples_dir=examples_dir,
            generated_dir=case_generated_dir,
            verbose=verbose,
        )
        summary["cases"].append(case)

    out_dir = evals_dir.joinpath(*SUITE_SUMMARIES_SUBDIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{eval_run_id}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(out_path)

    if verbose:
        passed = sum(1 for c in summary["cases"] if not c.get("error"))
        total = len(summary["cases"])
        print(
            f"eval-suite {mode} done: {passed}/{total} ok -> {out_path.relative_to(REPO_ROOT)}",
            flush=True,
        )
        print(f"evalRunId={eval_run_id}", flush=True)

    return summary


def compute_exit_code(summary: dict[str, Any]) -> int:
    """Return 0 when every case is clean, 1 when any case has an error.

    The exit code is how the backoffice subprocess and any future CI
    integration tell "kedjan lever" from "kedjan failade". Returning 0
    on a partial failure would render a green ``klar`` state in the
    UI even when one or more dossiers blew up, defeating the
    smoke/regression signal these runs exist to provide (Codex P1
    review on PR #87).
    """

    cases = summary.get("cases", [])
    for case in cases:
        if case.get("error"):
            return 1
    return 0


def _has_openai_key() -> bool:
    """Mirror packages.generation.brief.has_openai_api_key without importing it.

    The helper exists at module-load time inside packages/generation/brief
    but importing it here would force the dev-tool to drag the package
    onto sys.path. A whitespace-only check matches the package's own
    contract documented in AGENTS.md.
    """

    import os

    raw = os.environ.get("OPENAI_API_KEY")
    return bool(raw and raw.strip())


def main() -> int:
    quick_cases = get_quick_case_ids()
    full_cases = get_full_case_ids()
    parser = argparse.ArgumentParser(
        description=(
            "Run a canonical eval suite over examples/*.project-input.json "
            "and write a smoke summary to data/evals/summaries/suite/."
        ),
    )
    parser.add_argument(
        "mode",
        choices=("quick", "full"),
        help=(
            f"quick: {len(quick_cases)} examples "
            f"({format_case_list(quick_cases)}) with --skip-build. "
            f"full: {len(full_cases)} examples "
            f"({format_case_list(full_cases)}) without --skip-build "
            "(real npm install + npm run build)."
        ),
    )
    parser.add_argument(
        "--evals-dir",
        default=None,
        help="Override data/evals/ root (used by tests).",
    )
    parser.add_argument(
        "--runs-dir",
        default=None,
        help="Override data/runs/ root (used by tests).",
    )
    parser.add_argument(
        "--examples-dir",
        default=None,
        help="Override examples/ root (used by tests).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the final evalRunId line on stdout.",
    )
    args = parser.parse_args()

    evals_dir = Path(args.evals_dir).resolve() if args.evals_dir else DEFAULT_EVALS_DIR
    runs_dir = Path(args.runs_dir).resolve() if args.runs_dir else RUNS_DIR
    examples_dir = (
        Path(args.examples_dir).resolve() if args.examples_dir else EXAMPLES_DIR
    )

    summary = run_suite(
        args.mode,
        evals_dir=evals_dir,
        runs_dir=runs_dir,
        examples_dir=examples_dir,
        verbose=not args.quiet,
    )
    if args.quiet:
        print(f"evalRunId={summary['evalRunId']}")
    return compute_exit_code(summary)


if __name__ == "__main__":
    raise SystemExit(main())
