"""Run the standard pre-merge guard chain.

One command replaces the five-step chain that ro-review-agents and
operators were running manually before every merge. Works on Windows and
on the Linux Cloud Agent VMs because it shells out to the same Python
that runs the script.

Exits non-zero on the first failing step. Prints a final summary table
either way so the operator can see which step blocked the run.

Usage:

    python scripts/review_check.py            # run the full chain
    python scripts/review_check.py --quick    # skip the slow pytest step

The non-quick run mirrors the chain documented in
`docs/agent-handbook.md` under "Reviewer-checklist" item 4 and the
"Standard loop" step 5.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Step:
    name: str
    args: list[str]
    quick_ok: bool  # whether this step runs in --quick mode


STEPS: list[Step] = [
    Step(
        name="governance_validate",
        args=[sys.executable, "scripts/governance_validate.py"],
        quick_ok=True,
    ),
    Step(
        name="rules_sync_check",
        args=[sys.executable, "scripts/rules_sync.py", "--check"],
        quick_ok=True,
    ),
    Step(
        name="term_coverage_strict",
        args=[sys.executable, "scripts/check_term_coverage.py", "--strict"],
        quick_ok=True,
    ),
    Step(
        name="ruff_check",
        args=[sys.executable, "-m", "ruff", "check", "."],
        quick_ok=True,
    ),
    Step(
        name="pytest",
        args=[sys.executable, "-m", "pytest", "tests/", "-q"],
        quick_ok=False,
    ),
]


def run_step(step: Step) -> tuple[int, float]:
    start = time.perf_counter()
    result = subprocess.run(step.args, cwd=REPO_ROOT)
    return result.returncode, time.perf_counter() - start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="skip pytest (use only for fast iteration, not for merge gates)",
    )
    args = parser.parse_args()

    results: list[tuple[str, int, float]] = []
    first_failure: str | None = None

    for step in STEPS:
        if args.quick and not step.quick_ok:
            results.append((step.name, -1, 0.0))
            continue

        print(f"\n=== {step.name} ===", flush=True)
        code, elapsed = run_step(step)
        results.append((step.name, code, elapsed))
        if code != 0 and first_failure is None:
            first_failure = step.name
            # Stop at first failure so the operator can fix and retry,
            # instead of swimming through unrelated errors below.
            break

    print("\n" + "=" * 60)
    print("review_check summary")
    print("=" * 60)
    for name, code, elapsed in results:
        if code == -1:
            status = "SKIPPED (--quick)"
        elif code == 0:
            status = f"OK    ({elapsed:5.1f}s)"
        else:
            status = f"FAIL  (exit {code})"
        print(f"  {name:<24} {status}")

    if first_failure is not None:
        print(f"\nFirst failure: {first_failure}")
        return 1

    if args.quick:
        print("\nQuick run completed. Run without --quick before merge.")
    else:
        print("\nAll guard steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
