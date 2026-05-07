"""Engine Run dev driver (mock chain).

Runs an Engine Run from a prompt to artifacts under data/runs/<runId>/.
This first version is fully mocked: no LLM calls, no real codegen.
It exists to lock the artifact contract before runtime code is written.

Usage:
    python scripts/dev_generate.py "Skapa hemsida för elektriker i Malmö"
    python scripts/dev_generate.py "..." --phase brief
    python scripts/dev_generate.py "..." --phase plan
    python scripts/dev_generate.py "..." --phase build
    python scripts/dev_generate.py "..." --phase all      (default)

Phases:
    brief    -> writes input.json, site-brief.json
    plan     -> reads site-brief.json, writes site-plan.json, generation-package.json
    build    -> reads generation-package.json, writes generated-files/,
                repair-result.json, quality-result.json, build-result.json
    all      -> runs brief + plan + build sequentially

Every step appends an Engine Event to data/runs/<runId>/trace.ndjson.

Conventions:
    - Code comments and identifiers in English (governance/rules/code-in-english.md).
    - Operator-facing prints/logs may use either language; keep it concise.
    - No legacy term names from sajtmaskin (governance/rules/term-discipline.md).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RUNS_DIR = REPO_ROOT / "data" / "runs"


# ----- helpers ---------------------------------------------------------------


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_run_id() -> str:
    """Sortable, human-readable runId: 2026-05-07T07-12-34Z-<short>."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    short = uuid.uuid4().hex[:6]
    return f"{stamp}-{short}"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def append_event(run_dir: Path, event: dict[str, Any]) -> None:
    """Append an Engine Event to trace.ndjson."""
    trace_path = run_dir / "trace.ndjson"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False)
    with trace_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def emit(run_id: str, run_dir: Path, phase: str, event: str, status: str, message: str, payload_path: str | None = None) -> None:
    """Emit an Engine Event and echo a single line to stdout."""
    record = {
        "runId": run_id,
        "phase": phase,
        "event": event,
        "status": status,
        "message": message,
        "timestamp": utcnow_iso(),
        "payloadPath": payload_path,
    }
    append_event(run_dir, record)
    arrow = "ok" if status in ("done", "started") else status
    print(f"[{phase}.{event}] {arrow}: {message}")


# ----- detection helpers (minimal, deterministic) ----------------------------


SWEDISH_HINTS = {
    "skapa", "för", "hemsida", "sajt", "och", "att", "med", "på", "elektriker",
    "rörmokare", "tandläkare", "restaurang", "i", "av", "ett", "en",
}


def detect_language(prompt: str) -> str:
    tokens = {t.lower() for t in prompt.replace(",", " ").split() if t}
    if tokens & SWEDISH_HINTS:
        return "sv"
    return "en"


# ----- phase: understand (Site Brief) ----------------------------------------


def run_phase_understand(prompt: str, run_dir: Path, run_id: str) -> dict[str, Any]:
    emit(run_id, run_dir, "understand", "started", "started", f'Reading prompt ({len(prompt)} chars)')

    input_payload = {
        "runId": run_id,
        "rawPrompt": prompt,
        "operatorLanguage": "sv",
        "createdAt": utcnow_iso(),
    }
    write_json(run_dir / "input.json", input_payload)
    emit(run_id, run_dir, "understand", "input.written", "done", "input.json written", "input.json")

    site_brief = {
        "runId": run_id,
        "language": detect_language(prompt),
        "rawPrompt": prompt,
        "businessTypeGuess": None,
        "pageCount": None,
        "tone": [],
        "requestedCapabilities": [],
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "createdAt": utcnow_iso(),
        "_status": "mock - real briefModel call wired in Sprint 2",
    }
    write_json(run_dir / "site-brief.json", site_brief)
    emit(run_id, run_dir, "understand", "brief.written", "done", "site-brief.json written (mock)", "site-brief.json")

    emit(run_id, run_dir, "understand", "done", "done", "Phase 1 complete")
    return site_brief


# ----- phase: plan (Site Plan + Generation Package) --------------------------


def run_phase_plan(run_dir: Path, run_id: str, site_brief: dict[str, Any]) -> dict[str, Any]:
    emit(run_id, run_dir, "plan", "started", "started", "Selecting scaffold, variant, routes, dossiers (mock)")

    site_plan = {
        "runId": run_id,
        "selectedScaffold": "local-service-business",
        "selectedVariant": "premium-local",
        "routePlan": [
            {"id": "home", "path": "/", "purpose": "Position company, drive primary CTA."},
            {"id": "services", "path": "/tjanster", "purpose": "Show services."},
            {"id": "contact", "path": "/kontakt", "purpose": "Convert to call or quote."},
        ],
        "selectedDossiers": ["contact-form", "reviews"],
        "buildSpec": {
            "qualityTarget": 9.0,
            "verificationPolicy": "fast",
            "previewPolicy": "local",
        },
        "sourceModelRole": "planningModel",
        "modelUsed": "mock",
        "createdAt": utcnow_iso(),
        "_status": "mock - real Scaffold/Dossier Selectors wired in Sprint 2",
    }
    write_json(run_dir / "site-plan.json", site_plan)
    emit(run_id, run_dir, "plan", "site-plan.written", "done", "site-plan.json written (mock)", "site-plan.json")

    generation_package = {
        "runId": run_id,
        "structuredBrief": site_brief,
        "scaffold": site_plan["selectedScaffold"],
        "scaffoldVariant": site_plan["selectedVariant"],
        "routePlan": site_plan["routePlan"],
        "selectedDossiers": site_plan["selectedDossiers"],
        "buildSpec": site_plan["buildSpec"],
        "policyVersions": {
            "engineRun": "engine-run.v1",
            "llmModels": "llm-models.v1",
            "pageQualityTraits": "page-quality-traits.v1",
            "namingDictionary": "naming-dictionary.v1",
        },
        "createdAt": utcnow_iso(),
        "_status": "mock",
    }
    write_json(run_dir / "generation-package.json", generation_package)
    emit(run_id, run_dir, "plan", "package.written", "done", "generation-package.json written (mock)", "generation-package.json")

    emit(run_id, run_dir, "plan", "done", "done", "Phase 2 complete")
    return generation_package


# ----- phase: build (Generated Files + Repair + Quality) ---------------------


def run_phase_build(run_dir: Path, run_id: str, generation_package: dict[str, Any]) -> dict[str, Any]:
    emit(run_id, run_dir, "build", "started", "started", "Codegen mock - writing placeholder files")

    files_dir = run_dir / "generated-files"
    files_dir.mkdir(parents=True, exist_ok=True)
    placeholder = (
        "// MOCK file generated by scripts/dev_generate.py\n"
        "// Real codegen via codegenModel will be wired in Sprint 3.\n"
        f"// scaffold: {generation_package.get('scaffold')}\n"
        f"// variant:  {generation_package.get('scaffoldVariant')}\n"
    )
    (files_dir / "app.tsx").write_text(placeholder, encoding="utf-8")
    (files_dir / "README.md").write_text(
        "# Generated site (mock)\n\n"
        f"runId: {run_id}\n"
        "This is a placeholder produced by the mock chain.\n",
        encoding="utf-8",
    )
    emit(run_id, run_dir, "build", "files.written", "done", "Wrote 2 placeholder files", "generated-files/")

    repair_result = {
        "runId": run_id,
        "mechanicalFixesApplied": [],
        "llmFixCalled": False,
        "remainingErrors": 0,
        "status": "no-op (mock)",
        "modelUsed": None,
        "createdAt": utcnow_iso(),
    }
    write_json(run_dir / "repair-result.json", repair_result)
    emit(run_id, run_dir, "build", "repair.done", "done", "Repair Pipeline no-op (mock)", "repair-result.json")

    quality_result = {
        "runId": run_id,
        "checks": [
            {"id": "typecheck", "status": "skipped", "note": "mock: no real files yet"},
            {"id": "route-scan", "status": "skipped", "note": "mock"},
            {"id": "policy-compliance", "status": "skipped", "note": "mock"},
            {"id": "manual-score", "status": "skipped", "note": "operator scores manually for now"},
        ],
        "summary": "mock - no real checks executed",
        "passed": False,
        "createdAt": utcnow_iso(),
    }
    write_json(run_dir / "quality-result.json", quality_result)
    emit(run_id, run_dir, "build", "quality.done", "done", "Quality Gate skipped (mock)", "quality-result.json")

    build_result = {
        "runId": run_id,
        "status": "mock-complete",
        "filesWritten": 2,
        "repairResultPath": "repair-result.json",
        "qualityResultPath": "quality-result.json",
        "createdAt": utcnow_iso(),
    }
    write_json(run_dir / "build-result.json", build_result)
    emit(run_id, run_dir, "build", "result.written", "done", "build-result.json written", "build-result.json")

    emit(run_id, run_dir, "build", "done", "done", "Phase 3 complete")
    return build_result


# ----- driver ----------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a mock Engine Run end-to-end.")
    parser.add_argument("prompt", help="The user prompt to feed into the engine.")
    parser.add_argument(
        "--phase",
        choices=["brief", "plan", "build", "all"],
        default="all",
        help="Which phase to run. Default: all.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Reuse an existing runId (for re-running phase plan/build on the same run).",
    )
    parser.add_argument(
        "--data-runs-dir",
        default=str(DATA_RUNS_DIR),
        help="Override where runs are stored. Default: data/runs/",
    )
    args = parser.parse_args()

    runs_dir = Path(args.data_runs_dir)
    run_id = args.run_id or make_run_id()
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    emit(run_id, run_dir, "engine", "run.started", "started", f"runId={run_id} phase={args.phase}")

    site_brief: dict[str, Any] | None = None
    generation_package: dict[str, Any] | None = None

    if args.phase in ("brief", "all"):
        site_brief = run_phase_understand(args.prompt, run_dir, run_id)

    if args.phase in ("plan", "all"):
        if site_brief is None:
            brief_path = run_dir / "site-brief.json"
            if not brief_path.exists():
                print(
                    f"phase=plan requires site-brief.json in {run_dir}. "
                    "Run --phase brief first or use --phase all.",
                    file=sys.stderr,
                )
                return 2
            site_brief = read_json(brief_path)
        generation_package = run_phase_plan(run_dir, run_id, site_brief)

    if args.phase in ("build", "all"):
        if generation_package is None:
            pkg_path = run_dir / "generation-package.json"
            if not pkg_path.exists():
                print(
                    f"phase=build requires generation-package.json in {run_dir}. "
                    "Run --phase plan first or use --phase all.",
                    file=sys.stderr,
                )
                return 2
            generation_package = read_json(pkg_path)
        run_phase_build(run_dir, run_id, generation_package)

    emit(run_id, run_dir, "engine", "run.done", "done", f"runId={run_id}")
    print(f"\nRun complete: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
