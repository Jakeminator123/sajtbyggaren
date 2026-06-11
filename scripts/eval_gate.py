#!/usr/bin/env python3
"""Regression gate for the deterministic golden path eval.

The gate runs ``scripts/run_golden_path_eval.py`` in ``deterministic`` mode
(no LLM key, no ``npm`` build), distils the bit-stable scores, and compares
them to a committed baseline. It exits ``1`` when the new result is *worse*
than the baseline beyond a defined tolerance and exits ``0`` otherwise.

Key properties:

* **Honest without a key.** Deterministic mode pops ``OPENAI_API_KEY`` while
  generating, so the gate produces and validates real scores whether or not a
  key is present. It is never a silent no-op ("no key -> green").
* **Improvement never fails.** Scores above the baseline pass; the gate only
  reacts to regressions beyond tolerance.
* **Stable baseline.** The baseline holds only per-case ``totalScore``, the
  aggregate ``totalScore`` and ``embeddingsReadiness``. No timestamps, run ids
  or filesystem paths are stored, so the committed file stays byte-stable.

Regenerate the committed baseline with ``--update-baseline`` after an
intentional, reviewed quality change.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_BASELINE_PATH = REPO_ROOT / "tests" / "evals" / "golden-path-baseline.json"

# Tolerance is the source of truth for "what counts as a regression". The
# aggregate average may not drop by more than ``AGGREGATE_MAX_DROP`` and no
# single case may drop by more than ``CASE_MAX_DROP``. Both are absolute
# point deltas on the 0-10 scale. Chosen so a single trait flipping on one
# case (which moves a case total by ~0.4 at most given equal-weight traits)
# does not trip the gate, while a broad copy/render regression does.
AGGREGATE_MAX_DROP = 0.2
CASE_MAX_DROP = 0.5

# Float guard so a score that exactly equals the tolerance boundary is treated
# as "within tolerance" (passes) rather than tripping on representation noise.
_EPSILON = 1e-9

BASELINE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GateTolerance:
    """Allowed downward drift before the gate fails."""

    aggregate_max_drop: float = AGGREGATE_MAX_DROP
    case_max_drop: float = CASE_MAX_DROP


# Module-level singleton used as the default tolerance in signatures below.
# GateTolerance is frozen (immutable), so sharing one instance is safe and it
# keeps a bare ``GateTolerance()`` call out of argument defaults (ruff B008).
_DEFAULT_TOLERANCE = GateTolerance()


@dataclass
class GateResult:
    """Outcome of comparing a current eval to the committed baseline."""

    passed: bool
    regressions: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "regressions": self.regressions,
            "improvements": self.improvements,
            "notes": self.notes,
        }


def distill_scores(summary: dict[str, Any]) -> dict[str, Any]:
    """Extract the bit-stable score subset from a golden path summary.

    Returns per-case ``totalScore`` (keyed by ``caseId``, sorted), the
    aggregate ``totalScore`` and ``embeddingsReadiness``. Everything that
    varies between runs (timestamps, run ids, paths, elapsed times) is
    dropped on purpose so the result can be committed and diffed.
    """

    cases: dict[str, float] = {}
    for case in summary.get("cases", []):
        if not isinstance(case, dict):
            continue
        case_id = case.get("caseId")
        if not isinstance(case_id, str):
            continue
        cases[case_id] = round(float(case["totalScore"]), 2)
    return {
        "embeddingsReadiness": summary.get("embeddingsReadiness"),
        "totalScore": round(float(summary.get("totalScore", 0.0)), 2),
        "cases": dict(sorted(cases.items())),
    }


def build_baseline_document(
    distilled: dict[str, Any],
    *,
    tolerance: GateTolerance,
) -> dict[str, Any]:
    """Wrap distilled scores in a committed-baseline document with ``_meta``."""

    document: dict[str, Any] = {
        "_meta": {
            "schemaVersion": BASELINE_SCHEMA_VERSION,
            "description": (
                "Committed deterministic golden-path baseline. The eval-baseline "
                "gate (scripts/eval_gate.py) compares fresh deterministic scores "
                "to these values and fails CI on a regression beyond tolerance."
            ),
            "source": "scripts/run_golden_path_eval.py --mode deterministic",
            "regenerate": "python scripts/eval_gate.py --update-baseline",
            "fields": (
                "Per-case totalScore (0-10), aggregate totalScore and "
                "embeddingsReadiness only. No timestamps, run ids or paths."
            ),
            "tolerance": {
                "aggregateAverageMaxDrop": tolerance.aggregate_max_drop,
                "perCaseMaxDrop": tolerance.case_max_drop,
            },
        },
    }
    document.update(distilled)
    return document


def baseline_scores(baseline_document: dict[str, Any]) -> dict[str, Any]:
    """Return the score subset of a baseline document, ignoring ``_meta``."""

    return {
        "embeddingsReadiness": baseline_document.get("embeddingsReadiness"),
        "totalScore": round(float(baseline_document.get("totalScore", 0.0)), 2),
        "cases": {
            str(case_id): round(float(score), 2)
            for case_id, score in (baseline_document.get("cases") or {}).items()
        },
    }


def compare_to_baseline(
    current: dict[str, Any],
    baseline: dict[str, Any],
    *,
    tolerance: GateTolerance = _DEFAULT_TOLERANCE,
) -> GateResult:
    """Compare distilled ``current`` scores to ``baseline`` scores.

    A regression beyond tolerance (aggregate drop, per-case drop, a missing
    case, or an ``embeddingsReadiness`` drop from ``go``) fails the gate.
    Equal-to-baseline passes and any improvement passes.
    """

    regressions: list[str] = []
    improvements: list[str] = []
    notes: list[str] = []

    base_total = round(float(baseline["totalScore"]), 2)
    cur_total = round(float(current["totalScore"]), 2)
    aggregate_drop = round(base_total - cur_total, 4)
    if aggregate_drop > tolerance.aggregate_max_drop + _EPSILON:
        regressions.append(
            f"aggregate totalScore dropped {base_total} -> {cur_total} "
            f"(drop {aggregate_drop:.2f} > tolerance {tolerance.aggregate_max_drop})"
        )
    elif cur_total > base_total + _EPSILON:
        improvements.append(
            f"aggregate totalScore improved {base_total} -> {cur_total}"
        )

    base_cases: dict[str, float] = {
        str(case_id): round(float(score), 2)
        for case_id, score in (baseline.get("cases") or {}).items()
    }
    cur_cases: dict[str, float] = {
        str(case_id): round(float(score), 2)
        for case_id, score in (current.get("cases") or {}).items()
    }
    for case_id, base_score in sorted(base_cases.items()):
        if case_id not in cur_cases:
            regressions.append(f"case {case_id} is missing from the current eval")
            continue
        cur_score = cur_cases[case_id]
        case_drop = round(base_score - cur_score, 4)
        if case_drop > tolerance.case_max_drop + _EPSILON:
            regressions.append(
                f"case {case_id} dropped {base_score} -> {cur_score} "
                f"(drop {case_drop:.2f} > tolerance {tolerance.case_max_drop})"
            )
        elif cur_score > base_score + _EPSILON:
            improvements.append(
                f"case {case_id} improved {base_score} -> {cur_score}"
            )
    new_cases = sorted(set(cur_cases) - set(base_cases))
    if new_cases:
        notes.append("new cases not in baseline (ignored): " + ", ".join(new_cases))

    base_readiness = baseline.get("embeddingsReadiness")
    cur_readiness = current.get("embeddingsReadiness")
    if base_readiness == "go" and cur_readiness != "go":
        regressions.append(
            f"embeddingsReadiness regressed from go to {cur_readiness!r}"
        )
    elif base_readiness != "go" and cur_readiness == "go":
        improvements.append(
            f"embeddingsReadiness improved from {base_readiness!r} to go"
        )

    if not regressions:
        notes.append("no regression beyond tolerance vs committed baseline")
    return GateResult(
        passed=not regressions,
        regressions=regressions,
        improvements=improvements,
        notes=notes,
    )


def run_deterministic_eval(*, work_dir: Path | None = None) -> dict[str, Any]:
    """Run the golden path eval in deterministic mode and return the summary.

    The eval pops ``OPENAI_API_KEY`` internally, so this always produces real
    deterministic scores without an LLM call — never a no-op when a key is
    missing. Artifacts are written to an isolated work dir (a temp dir when
    ``work_dir`` is not given) so the repo's ``data/`` tree is never touched.
    """

    from scripts.run_golden_path_eval import run_golden_path_eval

    def _run(target: Path) -> dict[str, Any]:
        return run_golden_path_eval(
            mode="deterministic",
            evals_dir=target,
            eval_id="eval-gate",
        )

    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        return _run(work_dir)
    with tempfile.TemporaryDirectory(prefix="sajtbyggaren-eval-gate-") as tmp:
        return _run(Path(tmp))


def load_baseline(path: Path) -> dict[str, Any]:
    """Load and minimally validate a committed baseline document."""

    if not path.is_file():
        raise SystemExit(
            f"baseline saknas: {path}. Generera med "
            "`python scripts/eval_gate.py --update-baseline`."
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or "cases" not in document:
        raise SystemExit(f"baseline har fel form: {path}")
    return document


def write_baseline(path: Path, document: dict[str, Any]) -> None:
    """Write a baseline document as stable, newline-terminated JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def run_gate(
    *,
    baseline_path: Path = DEFAULT_BASELINE_PATH,
    tolerance: GateTolerance = _DEFAULT_TOLERANCE,
    work_dir: Path | None = None,
) -> tuple[GateResult, dict[str, Any]]:
    """Run the deterministic eval and compare it to the committed baseline."""

    baseline_document = load_baseline(baseline_path)
    summary = run_deterministic_eval(work_dir=work_dir)
    current = distill_scores(summary)
    result = compare_to_baseline(
        current,
        baseline_scores(baseline_document),
        tolerance=tolerance,
    )
    return result, current


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the eval-baseline regression gate."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        default=None,
        help=f"Path to the committed baseline. Default: {DEFAULT_BASELINE_PATH}.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Regenerate the committed baseline from a fresh deterministic eval.",
    )
    parser.add_argument(
        "--aggregate-tolerance",
        type=float,
        default=AGGREGATE_MAX_DROP,
        help=f"Max allowed aggregate average drop. Default: {AGGREGATE_MAX_DROP}.",
    )
    parser.add_argument(
        "--case-tolerance",
        type=float,
        default=CASE_MAX_DROP,
        help=f"Max allowed per-case drop. Default: {CASE_MAX_DROP}.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the gate result as JSON to stdout.",
    )
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline).resolve() if args.baseline else DEFAULT_BASELINE_PATH
    tolerance = GateTolerance(
        aggregate_max_drop=args.aggregate_tolerance,
        case_max_drop=args.case_tolerance,
    )

    if args.update_baseline:
        summary = run_deterministic_eval()
        distilled = distill_scores(summary)
        document = build_baseline_document(distilled, tolerance=tolerance)
        write_baseline(baseline_path, document)
        print(f"Baseline uppdaterad: {baseline_path}")
        print(json.dumps(distilled, ensure_ascii=False, indent=2))
        return 0

    result, current = run_gate(baseline_path=baseline_path, tolerance=tolerance)
    if args.json:
        print(json.dumps({"result": result.as_dict(), "current": current}, ensure_ascii=False, indent=2))
    else:
        print("Eval-baseline gate (deterministisk golden path)")
        print(f"  Baseline: {baseline_path}")
        print(
            "  Aktuellt: totalScore "
            f"{current['totalScore']}, embeddings={current['embeddingsReadiness']}"
        )
        for case_id, score in current["cases"].items():
            print(f"    {case_id}: {score}")
        for improvement in result.improvements:
            print(f"  + {improvement}")
        for regression in result.regressions:
            print(f"  ! {regression}")
        for note in result.notes:
            print(f"  - {note}")
        print(f"  Resultat: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
