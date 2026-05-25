#!/usr/bin/env python3
"""Probe which scaffolds the planner actually picks for representative prompts.

The point of this script is operational honesty: the
``primaryScaffoldRegistry`` in
``governance/policies/scaffold-contract.v1.json`` advertises 14 scaffolds,
but only those with a ``scaffold.json`` on disk under
``packages/generation/orchestration/scaffolds/<id>/`` survive
``load_scaffold_registry`` and reach the planner. This probe runs
``scripts/dev_generate.py "<prompt>" --phase plan`` for one prompt per
scaffold in the registry and records exactly what came back so the
operator can answer:

* scaffold exists in registry?
* scaffold has a directory on disk?
* scaffold has a starter mapping in ``SCAFFOLD_TO_STARTER``?
* did the planner actually pick it for the matched prompt?
* what was the variant + starter chosen?
* what dossiers were selected / capabilities rejected?

This is purely observational dev tooling. It does not modify the
planner, scaffolds, starters or the policy.
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

SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DEFAULT_RUNS_DIR = REPO_ROOT / "data" / "runs"
DEFAULT_EVALS_DIR = REPO_ROOT / "data" / "evals"


PROBE_CASES: tuple[dict[str, str], ...] = (
    {
        "promptId": "local-service-business",
        "expectedScaffold": "local-service-business",
        "prompt": "Skapa en hemsida för en elektriker i Malmö med trygg lokal SEO och tydlig kontaktbokning",
    },
    {
        "promptId": "professional-services",
        "expectedScaffold": "professional-services",
        "prompt": "Skapa en hemsida för en advokatbyrå i Stockholm med kompetensområden och kontaktformulär",
    },
    {
        "promptId": "restaurant-hospitality",
        "expectedScaffold": "restaurant-hospitality",
        "prompt": "Skapa en restauranghemsida med meny, bordsbokning och öppettider",
    },
    {
        "promptId": "clinic-healthcare",
        "expectedScaffold": "clinic-healthcare",
        "prompt": "Skapa en hemsida för en tandvårdsklinik med team, behandlingar och onlinebokning",
    },
    {
        "promptId": "real-estate",
        "expectedScaffold": "real-estate",
        "prompt": "Skapa en hemsida för en mäklarbyrå i Göteborg med objektslistor och premiumkänsla",
    },
    {
        "promptId": "agency-studio",
        "expectedScaffold": "agency-studio",
        "prompt": "Skapa en hemsida för en designbyrå med case-portfolio och tjänsteerbjudande",
    },
    {
        "promptId": "consultant-expert",
        "expectedScaffold": "consultant-expert",
        "prompt": "Skapa en hemsida för en oberoende ledarskapsrådgivare med boka samtal och referenser",
    },
    {
        "promptId": "saas-product",
        "expectedScaffold": "saas-product",
        "prompt": "Skapa en SaaS-produkthemsida för ett bokföringsverktyg med pricing, features och login",
    },
    {
        "promptId": "ecommerce-lite",
        "expectedScaffold": "ecommerce-lite",
        "prompt": "Skapa en webbshop för handgjorda keramikvaser med produktkatalog och kassa",
    },
    {
        "promptId": "course-education",
        "expectedScaffold": "course-education",
        "prompt": "Skapa en hemsida för en online-kurs i webbutveckling med läroplan och anmälan",
    },
    {
        "promptId": "nonprofit-community",
        "expectedScaffold": "nonprofit-community",
        "prompt": "Skapa en hemsida för en ideell förening som hjälper hemlösa i Uppsala, med donationsknapp",
    },
    {
        "promptId": "portfolio-creator",
        "expectedScaffold": "portfolio-creator",
        "prompt": "Skapa en portfolio för en frilansande fotograf med bildgallerier och kontaktformulär",
    },
    {
        "promptId": "event-campaign",
        "expectedScaffold": "event-campaign",
        "prompt": "Skapa en hemsida för en techkonferens i Malmö med program, talare och biljettköp",
    },
    {
        "promptId": "app-landing",
        "expectedScaffold": "app-landing",
        "prompt": "Skapa en landningssida för en ny mobilapp för meditation med App Store och Google Play-knappar",
    },
)


_RUN_ID_RE = re.compile(r"runId[:=]\s*(?P<run_id>[A-Za-z0-9._-]+)")


def utc_iso() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def make_probe_run_id() -> str:
    now = datetime.now(tz=UTC)
    stamp = now.strftime("%Y%m%dT%H%M%S")
    millis = f"{now.microsecond // 1000:03d}"
    short = uuid.uuid4().hex[:8]
    return f"scaffold-probe-{stamp}.{millis}Z-{short}"


def _load_scaffold_to_starter() -> dict[str, str]:
    """Return the canonical scaffold->starter mapping.

    Reading directly from ``packages.generation.planning.plan`` keeps the
    probe honest: if the mapping changes, this surfaces it without us
    duplicating the table.
    """

    # Imported lazily through __import__ so module-level import order
    # stays small and ruff's import-block sorter is not triggered by a
    # single late ``from`` line inside the function body.
    plan_module = __import__(
        "packages.generation.planning.plan", fromlist=["SCAFFOLD_TO_STARTER"]
    )
    return dict(plan_module.SCAFFOLD_TO_STARTER)


def _scaffold_dir_status(scaffold_id: str) -> dict[str, bool]:
    scaffold_dir = SCAFFOLDS_DIR / scaffold_id
    return {
        "directoryExists": scaffold_dir.is_dir(),
        "scaffoldJsonExists": (scaffold_dir / "scaffold.json").is_file(),
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _extract_run_id(output: str) -> str | None:
    match = _RUN_ID_RE.search(output)
    if not match:
        return None
    return match.group("run_id").strip().strip(".,") or None


def _extract_selected_dossiers(plan: dict[str, Any] | None) -> list[str]:
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


def _extract_rejected_capabilities(plan: dict[str, Any] | None) -> list[dict[str, str]]:
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


def _classify_runtime_readiness(
    expected_scaffold: str,
    selected_scaffold: str | None,
    starter_to_scaffold: dict[str, str],
    scaffold_dir_status: dict[str, bool],
) -> str:
    """Return a short note about runtime readiness for the matched scaffold.

    The classification is deliberately coarse — full build verification
    lives in ``run_eval_suite.py full``. This is only meant to flag the
    obvious states a non-technical operator wants to see in the matrix.
    """

    if not scaffold_dir_status["directoryExists"]:
        return "registry-placeholder (no directory on disk)"
    if not scaffold_dir_status["scaffoldJsonExists"]:
        return "directory exists but no scaffold.json — planner skips"
    has_starter = expected_scaffold in starter_to_scaffold
    if not has_starter:
        return "scaffold loadable but no starter mapping in SCAFFOLD_TO_STARTER"
    if selected_scaffold == expected_scaffold:
        return "planner picked the intended scaffold"
    if selected_scaffold:
        return f"planner picked {selected_scaffold!r} instead"
    return "site-plan never written"


def run_probe_case(
    case: dict[str, str],
    *,
    runs_dir: Path,
    starter_to_scaffold: dict[str, str],
    verbose: bool = True,
) -> dict[str, Any]:
    expected = case["expectedScaffold"]
    prompt = case["prompt"]
    dir_status = _scaffold_dir_status(expected)
    result: dict[str, Any] = {
        "promptId": case["promptId"],
        "prompt": prompt,
        "expectedScaffold": expected,
        "expectedHasDirectory": dir_status["directoryExists"],
        "expectedHasScaffoldJson": dir_status["scaffoldJsonExists"],
        "expectedHasStarterMapping": expected in starter_to_scaffold,
        "expectedStarterIfMapped": starter_to_scaffold.get(expected),
        "runId": None,
        "briefSource": None,
        "planSource": None,
        "scaffoldId": None,
        "variantId": None,
        "starterId": None,
        "selectedDossiers": [],
        "rejectedCapabilities": [],
        "selectedMatchesExpected": False,
        "error": None,
        "elapsedSeconds": 0.0,
        "comment": "",
    }

    # ``--phase all`` runs brief -> plan -> mock build inline. We could
    # call ``--phase brief`` then ``--phase plan`` separately with the
    # same ``--run-id``, but the mock build is cheap and gives us a
    # well-formed ``data/runs/<runId>`` we can inspect without juggling
    # subprocess pairs. dev_generate's Phase 3 is intentionally a
    # placeholder mock — no npm install runs from here.
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "dev_generate.py"),
        prompt,
        "--phase",
        "all",
        "--data-runs-dir",
        str(runs_dir),
    ]
    started = time.monotonic()
    if verbose:
        print(f"  -> {case['promptId']} ...", flush=True)
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        result["error"] = f"dev_generate failed to start: {exc}"
        result["elapsedSeconds"] = round(time.monotonic() - started, 2)
        result["comment"] = _classify_runtime_readiness(
            expected, None, starter_to_scaffold, dir_status
        )
        return result

    result["elapsedSeconds"] = round(time.monotonic() - started, 2)
    combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
    result["runId"] = _extract_run_id(combined)

    if completed.returncode != 0:
        tail = combined.strip().splitlines()[-10:]
        result["error"] = (
            f"dev_generate exit={completed.returncode}; tail: " + " | ".join(tail)
        )

    if result["runId"]:
        run_dir = runs_dir / result["runId"]
        brief = _read_json(run_dir / "site-brief.json") or {}
        plan = _read_json(run_dir / "site-plan.json") or {}
        result["briefSource"] = brief.get("briefSource")
        result["planSource"] = plan.get("planSource")
        result["scaffoldId"] = plan.get("scaffoldId")
        result["variantId"] = plan.get("variantId")
        result["starterId"] = plan.get("starterId")
        result["selectedDossiers"] = _extract_selected_dossiers(plan)
        result["rejectedCapabilities"] = _extract_rejected_capabilities(plan)
        result["selectedMatchesExpected"] = result["scaffoldId"] == expected

    result["comment"] = _classify_runtime_readiness(
        expected,
        result["scaffoldId"],
        starter_to_scaffold,
        dir_status,
    )

    if verbose:
        picked = result["scaffoldId"] or "—"
        match = "✓" if result["selectedMatchesExpected"] else "≠"
        print(
            f"     picked={picked} {match} expected={expected} elapsed={result['elapsedSeconds']}s",
            flush=True,
        )

    return result


def run_probe(
    *,
    evals_dir: Path = DEFAULT_EVALS_DIR,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    verbose: bool = True,
) -> dict[str, Any]:
    starter_to_scaffold = _load_scaffold_to_starter()
    probe_id = make_probe_run_id()
    summary: dict[str, Any] = {
        "probeId": probe_id,
        "createdAt": utc_iso(),
        "openaiKeyPresent": _has_openai_key(),
        "totalCases": len(PROBE_CASES),
        "starterMappings": starter_to_scaffold,
        "cases": [],
    }
    if verbose:
        print(f"scaffold-probe start (probeId={probe_id})", flush=True)

    for case in PROBE_CASES:
        record = run_probe_case(
            case,
            runs_dir=runs_dir,
            starter_to_scaffold=starter_to_scaffold,
            verbose=verbose,
        )
        summary["cases"].append(record)

    out_dir = evals_dir / "scaffold-probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{probe_id}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(out_path)

    if verbose:
        matches = sum(1 for c in summary["cases"] if c.get("selectedMatchesExpected"))
        print(
            f"scaffold-probe done: {matches}/{summary['totalCases']} prompts picked expected scaffold",
            flush=True,
        )
        print(f"  summary: {out_path.relative_to(REPO_ROOT)}", flush=True)
        print(f"probeId={probe_id}", flush=True)

    return summary


def write_markdown_report(summary: dict[str, Any], path: Path) -> Path:
    lines: list[str] = []
    lines.append(f"# Scaffold selection probe — {summary['probeId']}\n")
    lines.append(f"- createdAt: `{summary['createdAt']}`")
    lines.append(f"- OPENAI_API_KEY present: {summary['openaiKeyPresent']}")
    matches = sum(1 for c in summary["cases"] if c.get("selectedMatchesExpected"))
    lines.append(f"- Picked expected scaffold: {matches} / {summary['totalCases']}\n")
    lines.append(
        "| Scaffold | Listed in registry | Directory on disk | Picked by planner | Variant | Starter | Comment |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for case in summary["cases"]:
        lines.append(
            "| `{expected}` | yes | {dir} | {picked} | `{variant}` | `{starter}` | {comment} |".format(
                expected=case["expectedScaffold"],
                dir="yes" if case["expectedHasScaffoldJson"] else "no",
                picked=(
                    f"`{case['scaffoldId']}`"
                    + (" ✓" if case["selectedMatchesExpected"] else " ≠")
                    if case["scaffoldId"]
                    else "—"
                ),
                variant=case["variantId"] or "—",
                starter=case["starterId"] or "—",
                comment=case["comment"],
            )
        )
    lines.append("")
    failures = [c for c in summary["cases"] if c.get("error")]
    if failures:
        lines.append("## Errors\n")
        for case in failures:
            lines.append(f"- `{case['promptId']}`: {case['error']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _has_openai_key() -> bool:
    import os

    raw = os.environ.get("OPENAI_API_KEY")
    return bool(raw and raw.strip())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Probe which scaffolds the planner picks for a fixed set of "
            "representative prompts (one per primaryScaffoldRegistry entry)."
        ),
    )
    parser.add_argument(
        "--runs-dir",
        default=None,
        help="Override data/runs/ root for the probe runs.",
    )
    parser.add_argument(
        "--evals-dir",
        default=None,
        help="Override data/evals/ root where the probe summary is written.",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Optional markdown report path. Default: data/evals/scaffold-probe/<probeId>.md",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the final probeId.",
    )
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir).resolve() if args.runs_dir else DEFAULT_RUNS_DIR
    evals_dir = Path(args.evals_dir).resolve() if args.evals_dir else DEFAULT_EVALS_DIR

    summary = run_probe(evals_dir=evals_dir, runs_dir=runs_dir, verbose=not args.quiet)

    report_path: Path
    if args.report:
        report_path = Path(args.report).resolve()
    else:
        report_path = evals_dir / "scaffold-probe" / f"{summary['probeId']}.md"
    write_markdown_report(summary, report_path)

    if not args.quiet:
        try:
            rel = report_path.relative_to(REPO_ROOT)
            print(f"  report:  {rel}", flush=True)
        except ValueError:
            print(f"  report:  {report_path}", flush=True)
    if args.quiet:
        print(f"probeId={summary['probeId']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
