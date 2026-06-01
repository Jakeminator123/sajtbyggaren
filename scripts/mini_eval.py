#!/usr/bin/env python3
"""Run the local four-case mini-eval in an isolated output directory.

The runner is dev-tooling, not product runtime. It writes Project Inputs,
run artifacts, generated sites and reports under one timestamped eval
directory so it can run beside normal Cursor work without polluting
``data/runs/`` or ``data/prompt-inputs/``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_EVALS_DIR = REPO_ROOT / "data" / "evals" / "artifacts" / "mini"
# Legacy default kept so operators that still set
# ``SAJTBYGGAREN_EVALS_DIR=`` to the old external path keep getting that
# directory — only the unset default moved into the new canonical layout.
LEGACY_EVALS_DIR = REPO_ROOT.parent / "sajtbyggaren-output" / ".evals"

CSS_TOKEN_RE = re.compile(r"--(?P<name>[a-z-]+):\s*(?P<value>[^;]+);")
BLOCKED_RAW_PHRASES = (
    "Hemsida om",
    "hemsida om",
    "2 sidor",
    "3 sidor",
    "gröna färger",
    "gröna färg",
    "röda färger",
    "röd färg",
    "blå färger",
    "blå färg",
)


MINI_EVAL_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "electrician-malmo",
        "label": "Elektriker Malmö",
        "init_prompt": "Skapa en hemsida för en elektriker i Malmö",
        "followup_prompt": "gör tonen mer premium",
        "expected_effect": "tone och CSS-token ska kunna ändras",
        "expect_token_change": True,
        "adversarial": False,
    },
    {
        "id": "salon-goteborg",
        "label": "Frisör Göteborg",
        "init_prompt": "Skapa en hemsida för en frisörsalong i Göteborg",
        "followup_prompt": "gör den mer personlig",
        "expected_effect": "tone/copy ska ändras utan rå prompt-läckage",
        "expect_token_change": False,
        "adversarial": False,
    },
    {
        "id": "naprapat-stockholm",
        "label": "Naprapat Stockholm",
        "init_prompt": "Skapa en hemsida för en naprapatklinik i Stockholm",
        "followup_prompt": "gör den lugnare och mer förtroendeingivande",
        "expected_effect": "tone/copy ska kännas lugnare och mer förtroendeingivande",
        "expect_token_change": False,
        "adversarial": False,
    },
    {
        "id": "skoldpaddssoppa",
        "label": "Sköldpaddssoppa",
        "init_prompt": "Hemsida om sköldpaddssoppa, mat, 2 sidor, gröna färger",
        "followup_prompt": "gör tonen mer premium",
        "expected_effect": "warnings ska vara rimliga och rå prompt ska inte läcka",
        "expect_token_change": True,
        "adversarial": True,
    },
)


def _utc_stamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def resolve_evals_dir(value: str | None = None) -> Path:
    raw = value or os.environ.get("SAJTBYGGAREN_EVALS_DIR")
    return Path(raw).expanduser().resolve() if raw else DEFAULT_EVALS_DIR.resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _css_tokens(run_dir: Path) -> dict[str, str]:
    css = _read_text_if_exists(run_dir / "generated-files" / "app" / "globals.css")
    return {
        match.group("name"): match.group("value").strip()
        for match in CSS_TOKEN_RE.finditer(css)
    }


def _generated_text(run_dir: Path) -> str:
    generated_dir = run_dir / "generated-files" / "app"
    if not generated_dir.is_dir():
        return ""
    chunks: list[str] = []
    for path in sorted(generated_dir.rglob("*.tsx")):
        chunks.append(_read_text_if_exists(path))
    return "\n".join(chunks)


def _normalise_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _contains_text(haystack: str, needle: str) -> bool:
    return bool(needle.strip()) and _normalise_text(needle) in _normalise_text(haystack)


def _project_fields(project_input: dict[str, Any]) -> dict[str, Any]:
    company = project_input.get("company") if isinstance(project_input.get("company"), dict) else {}
    tone = project_input.get("tone") if isinstance(project_input.get("tone"), dict) else {}
    return {
        "story": company.get("story"),
        "tagline": company.get("tagline"),
        "tone": {
            "primary": tone.get("primary"),
            "secondary": tone.get("secondary", []),
            "avoid": tone.get("avoid", []),
        },
    }


def _compare_case(
    case: dict[str, Any],
    *,
    v1_project_input: dict[str, Any],
    v2_project_input: dict[str, Any],
    v1_meta: dict[str, Any],
    v2_meta: dict[str, Any],
    v1_run_dir: Path,
    v2_run_dir: Path,
) -> dict[str, Any]:
    v1_tokens = _css_tokens(v1_run_dir)
    v2_tokens = _css_tokens(v2_run_dir)
    v2_text = _generated_text(v2_run_dir)
    v2_site_plan = _read_json(v2_run_dir / "site-plan.json")
    v2_build_result = _read_json(v2_run_dir / "build-result.json")

    v1_fields = _project_fields(v1_project_input)
    v2_fields = _project_fields(v2_project_input)
    field_changes = {
        "story": v1_fields["story"] != v2_fields["story"],
        "tagline": v1_fields["tagline"] != v2_fields["tagline"],
        "tone": v1_fields["tone"] != v2_fields["tone"],
    }
    token_changes = {
        name: v1_tokens.get(name) != v2_tokens.get(name)
        for name in ("primary", "primary-foreground", "accent", "accent-foreground")
    }
    raw_leaks = [
        phrase
        for phrase in (
            case["init_prompt"],
            case["followup_prompt"],
            *BLOCKED_RAW_PHRASES,
        )
        if _contains_text(v2_text, phrase)
    ]
    warnings = {
        "pageCountWarning": v2_site_plan.get("pageCountWarning"),
        "intentGuardWarnings": v2_site_plan.get("intentGuardWarnings", []),
        "pageIntentWarnings": v2_site_plan.get("pageIntentWarnings", []),
        "placeholderContactFields": v2_build_result.get("placeholderContactFields", []),
    }
    followup_effect = any(field_changes.values()) or any(token_changes.values())
    passed = (
        v1_meta.get("projectId") == v2_meta.get("projectId")
        and v2_meta.get("version") == 2
        and followup_effect
        and not raw_leaks
        and (not case.get("expect_token_change") or token_changes["primary"])
    )

    return {
        "case": dict(case),
        "passed": passed,
        "followupEffect": followup_effect,
        "fieldChanges": field_changes,
        "tokenChanges": token_changes,
        "rawPromptLeaks": raw_leaks,
        "warnings": warnings,
        "v1": {
            "projectInput": _project_fields(v1_project_input),
            "cssTokens": {name: v1_tokens.get(name) for name in sorted(token_changes)},
            "runId": v1_run_dir.name,
        },
        "v2": {
            "projectInput": _project_fields(v2_project_input),
            "cssTokens": {name: v2_tokens.get(name) for name in sorted(token_changes)},
            "runId": v2_run_dir.name,
            "buildStatus": v2_build_result.get("status"),
        },
        "scorecardTemplate": {
            "tydlighet": None,
            "design": None,
            "CTA": None,
            "branschpassning": None,
            "copy": None,
            "followUpEffekt": None,
        },
    }


def run_case(
    case: dict[str, Any],
    *,
    work_dir: Path,
    run_build: bool,
) -> dict[str, Any]:
    from scripts.build_site import build
    from scripts.prompt_to_project_input import generate, generate_followup

    prompt_inputs_dir = work_dir / "prompt-inputs"
    runs_dir = work_dir / "runs"
    generated_dir = work_dir / "generated"
    for directory in (prompt_inputs_dir, runs_dir, generated_dir):
        directory.mkdir(parents=True, exist_ok=True)

    v1_project_input, v1_meta, v1_project_input_path, _v1_meta_path = generate(
        case["init_prompt"],
        output_dir=prompt_inputs_dir,
        site_id=case["id"],
    )
    _v1_target, v1_run_dir = build(
        v1_project_input_path,
        do_build=run_build,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        auto_prune=False,
    )
    v2_project_input, v2_meta, v2_project_input_path, _v2_meta_path = generate_followup(
        case["followup_prompt"],
        output_dir=prompt_inputs_dir,
        site_id=case["id"],
    )
    _v2_target, v2_run_dir = build(
        v2_project_input_path,
        do_build=run_build,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        auto_prune=False,
    )
    return _compare_case(
        case,
        v1_project_input=v1_project_input,
        v2_project_input=v2_project_input,
        v1_meta=v1_meta,
        v2_meta=v2_meta,
        v1_run_dir=v1_run_dir,
        v2_run_dir=v2_run_dir,
    )


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Mini-eval rapport",
        "",
        f"- Eval-id: `{report['evalId']}`",
        f"- Skapad: `{report['createdAt']}`",
        f"- Eval-dir: `{report['evalDir']}`",
        f"- Run build: `{report['runBuild']}`",
        f"- Summary: {report['summary']['passed']}/{report['summary']['total']} passerade",
        "",
        "## Cases",
        "",
    ]
    for result in report["results"]:
        case = result["case"]
        status = "PASS" if result["passed"] else "FAIL"
        lines.extend(
            [
                f"### {case['label']} — {status}",
                "",
                f"- Init: `{case['init_prompt']}`",
                f"- Follow-up: `{case['followup_prompt']}`",
                f"- Förväntad effekt: {case['expected_effect']}",
                f"- Field changes: `{result['fieldChanges']}`",
                f"- Token changes: `{result['tokenChanges']}`",
                f"- Raw prompt leaks: `{result['rawPromptLeaks']}`",
                f"- V1 run: `{result['v1']['runId']}`",
                f"- V2 run: `{result['v2']['runId']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Manuell scorecard",
            "",
            "Fyll 1-10 per case efter visuell/produktmässig granskning:",
            "",
            "- tydlighet",
            "- design",
            "- CTA",
            "- branschpassning",
            "- copy",
            "- follow-up-effekt",
            "",
        ]
    )
    return "\n".join(lines)


def run_mini_eval(
    *,
    cases: list[dict[str, Any]],
    evals_dir: Path,
    run_build: bool = False,
    eval_id: str | None = None,
) -> dict[str, Any]:
    eval_id = eval_id or f"{_utc_stamp()}-mini-eval"
    work_dir = evals_dir / eval_id
    work_dir.mkdir(parents=True, exist_ok=False)
    results = [
        run_case(case, work_dir=work_dir, run_build=run_build)
        for case in cases
    ]
    report = {
        "schemaVersion": 1,
        "evalId": eval_id,
        "createdAt": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "evalDir": str(work_dir),
        "runBuild": run_build,
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result["passed"]),
            "failed": sum(1 for result in results if not result["passed"]),
        },
        "results": results,
    }
    (work_dir / "mini-eval-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (work_dir / "mini-eval-report.md").write_text(
        _markdown_report(report),
        encoding="utf-8",
    )
    return report


def _select_cases(case_ids: list[str] | None) -> list[dict[str, Any]]:
    if not case_ids:
        return list(MINI_EVAL_CASES)
    known = {case["id"]: case for case in MINI_EVAL_CASES}
    missing = [case_id for case_id in case_ids if case_id not in known]
    if missing:
        raise SystemExit(
            "Okända case-id:n: "
            + ", ".join(missing)
            + ". Kända: "
            + ", ".join(sorted(known))
        )
    return [known[case_id] for case_id in case_ids]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evals-dir",
        default=None,
        help=(
            "Root for isolated eval output. Defaults to SAJTBYGGAREN_EVALS_DIR "
            f"or {DEFAULT_EVALS_DIR}."
        ),
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        help="Run one case id. Can be repeated. Default: all four baseline cases.",
    )
    parser.add_argument(
        "--eval-id",
        default=None,
        help="Override timestamped eval id (useful in tests or scripted reruns).",
    )
    parser.add_argument(
        "--run-build",
        action="store_true",
        help="Run npm install/build too. Default skips npm build for fast parallel evals.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the report JSON to stdout in addition to writing files.",
    )
    args = parser.parse_args()

    start = time.monotonic()
    report = run_mini_eval(
        cases=_select_cases(args.cases),
        evals_dir=resolve_evals_dir(args.evals_dir),
        run_build=args.run_build,
        eval_id=args.eval_id,
    )
    report["durationMs"] = int((time.monotonic() - start) * 1000)
    report_path = Path(report["evalDir"]) / "mini-eval-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Mini-eval klar: {report['summary']['passed']}/"
            f"{report['summary']['total']} passerade"
        )
        print(f"Rapport: {report_path}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
