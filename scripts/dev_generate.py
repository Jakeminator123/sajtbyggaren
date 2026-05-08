"""Engine Run dev driver.

Runs an Engine Run from a prompt to artifacts under data/runs/<runId>/.

LLM status (as of Sprint 2B):
    - Phase 1 Understand: calls real `briefModel` via OpenAI when
      OPENAI_API_KEY is set, otherwise falls back to a deterministic
      mock and writes briefSource=mock-no-key into site-brief.json.
    - Phase 2 Plan: calls real `planningModel` via the shared
      `packages.generation.planning.produce_site_plan` helper when
      OPENAI_API_KEY is set. Falls back to deterministic mock with
      planSource=mock-no-key when the key is missing or
      planSource=mock-llm-error if the call raises. Same helper is
      used by scripts/build_site.py - that is what closes B19.
    - Phase 3 Build: deterministic placeholder files; codegenModel,
      Repair Pipeline and Quality Gate land in Sprint 3.

All artefakter (site-brief.json, site-plan.json, generation-package.json)
are validated against governance/schemas/ before they are written.

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
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RUNS_DIR = REPO_ROOT / "data" / "runs"

# Make packages/ importable when running this script directly.
sys.path.insert(0, str(REPO_ROOT))


def _resolve_brief_model() -> str:
    """Resolve briefModel via the canonical helper in packages.generation.brief.

    Wraps the strict resolver so the call sites in this script don't need to
    import the package directly. Strict by design: a misconfigured policy
    surfaces immediately instead of pinning an old default model.
    """
    from packages.generation.brief import resolve_brief_model

    return resolve_brief_model()


# ----- helpers ---------------------------------------------------------------


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def make_run_id() -> str:
    """Sortable, human-readable runId: 2026-05-07T07-12-34Z-<short>."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
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


# ----- detection helpers (delegated to packages/generation/brief) -----------


def detect_language(prompt: str) -> str:
    """Delegate to the canonical detector in packages/generation/brief.

    Kept as a thin wrapper so callers in this script don't need to import
    deeper. Single source of truth lives in packages.generation.brief.extract.
    """
    from packages.generation.brief import detect_language as _real_detect

    return _real_detect(prompt)


# ----- phase: understand (Site Brief) ----------------------------------------


def run_phase_understand(
    prompt: str,
    run_dir: Path,
    run_id: str,
    *,
    mode: str = "init",
    project_id: str | None = None,
) -> dict[str, Any]:
    emit(run_id, run_dir, "understand", "started", "started", f'Reading prompt ({len(prompt)} chars)')

    detected = detect_language(prompt)

    input_payload = {
        "runId": run_id,
        "mode": mode,
        "projectId": project_id,
        "rawPrompt": prompt,
        "detectedLanguage": detected,
        "createdAt": utcnow_iso(),
    }
    write_json(run_dir / "input.json", input_payload)
    emit(run_id, run_dir, "understand", "input.written", "done", "input.json written", "input.json")

    # Try real briefModel; falls back to mock inside extract_site_brief if no API key.
    from packages.generation.brief import has_openai_api_key

    has_key = has_openai_api_key()
    model_name = _resolve_brief_model()
    try:
        from packages.generation.brief import extract_site_brief, site_brief_to_artifact

        if has_key:
            emit(run_id, run_dir, "understand", "brief.calling-llm", "started", f"Calling briefModel ({model_name})")
        else:
            emit(run_id, run_dir, "understand", "brief.mock", "started", "No OPENAI_API_KEY - mock brief")

        result = extract_site_brief(prompt, model=model_name, language_hint=detected)
        site_brief = site_brief_to_artifact(result, run_id=run_id, model=model_name)
        if result.source == "mock-llm-error":
            emit(
                run_id,
                run_dir,
                "understand",
                "brief.degraded",
                "degraded",
                f"LLM call failed, used mock fallback: {result.error}",
            )
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[dev_generate.understand] {type(exc).__name__}: {exc}\n")
        sys.stderr.flush()
        emit(
            run_id,
            run_dir,
            "understand",
            "brief.fallback",
            "degraded",
            f"briefModel error, fallback to inline mock: {type(exc).__name__}: {exc}",
        )
        site_brief = {
            "runId": run_id,
            "language": detected,
            "rawPrompt": prompt,
            "businessTypeGuess": None,
            "pageCount": None,
            "tone": [],
            "targetAudience": [],
            "requestedCapabilities": [],
            "locationHint": None,
            "conversionGoals": [],
            "servicesMentioned": [],
            "contentDepth": None,
            "notesForPlanner": None,
            "sourceModelRole": "briefModel",
            "modelUsed": "mock",
            "briefSource": "mock-import-error",
            "briefError": f"{type(exc).__name__}: {exc}",
            "createdAt": utcnow_iso(),
        }

    from packages.generation.artifacts import validate_site_brief

    validate_site_brief(site_brief)
    write_json(run_dir / "site-brief.json", site_brief)
    source_label = site_brief.get("briefSource", "unknown")
    emit(
        run_id,
        run_dir,
        "understand",
        "brief.written",
        "done",
        f"site-brief.json written (source: {source_label})",
        "site-brief.json",
    )

    emit(run_id, run_dir, "understand", "done", "done", "Phase 1 complete")
    return site_brief


# ----- phase: plan (Site Plan + Generation Package) --------------------------


def run_phase_plan(run_dir: Path, run_id: str, site_brief: dict[str, Any]) -> dict[str, Any]:
    """Phase 2 Plan: delegate to the shared produce_site_plan helper.

    Both this script and scripts/build_site.py go through the SAME helper
    (packages.generation.planning.produce_site_plan). Local plan-construction
    code in this file used to mirror builder code and silently drifted -
    that drift is what docs/known-issues.md B19 tracked. Keep this function
    a thin wrapper: any new plan logic belongs in the helper, not here.
    """
    from packages.generation.brief import has_openai_api_key
    from packages.generation.planning import produce_site_plan

    if has_openai_api_key():
        emit(run_id, run_dir, "plan", "planning.calling-llm", "started", "Calling planningModel (real)")
    else:
        emit(run_id, run_dir, "plan", "planning.mock", "started", "No OPENAI_API_KEY - mock plan")

    result = produce_site_plan(
        site_brief,
        run_id=run_id,
        engine_mode="init",
        project_id=None,
    )

    if result.source == "mock-llm-error":
        emit(
            run_id,
            run_dir,
            "plan",
            "planning.degraded",
            "degraded",
            f"planningModel call failed, used mock fallback: {result.error}",
        )

    write_json(run_dir / "site-plan.json", result.site_plan)
    emit(
        run_id,
        run_dir,
        "plan",
        "site-plan.written",
        "done",
        f"site-plan.json written (planSource={result.source})",
        "site-plan.json",
    )

    write_json(run_dir / "generation-package.json", result.generation_package)
    emit(
        run_id,
        run_dir,
        "plan",
        "package.written",
        "done",
        "generation-package.json written",
        "generation-package.json",
    )

    emit(run_id, run_dir, "plan", "done", "done", "Phase 2 complete")
    return result.generation_package


# ----- phase: build (Generated Files + Repair + Quality) ---------------------


def run_phase_build(run_dir: Path, run_id: str, generation_package: dict[str, Any]) -> dict[str, Any]:
    """Mock fas 3 for the dev driver.

    Sprint 3A harmonises the artefact contract: ``quality-result.json``
    and ``repair-result.json`` use the same QualityResult/RepairResult
    shape that scripts/build_site.py produces via
    packages.generation.{quality_gate, repair}. Trace event names mirror
    builder events (``files.written``, ``codegen.manifest.emitted``,
    ``quality_result.written``, ``repair_result.written``,
    ``build.result.written``, ``phase.completed``) so a single Backoffice
    consumer can render both runner outputs without per-driver special
    casing.

    The dev driver still produces *placeholder* generated files (no real
    Next.js project tree) - that is what makes it a mock pipeline. The
    Quality Gate skipped statuses are honest about this: route-scan is
    skipped because the mock target has no app/ tree, typecheck because
    there is no node_modules, build-status because there is no npm run
    build.
    """
    emit(run_id, run_dir, "build", "phase.started", "started", "Codegen mock - writing placeholder files")

    files_dir = run_dir / "generated-files"
    files_dir.mkdir(parents=True, exist_ok=True)
    placeholder = (
        "// MOCK file generated by scripts/dev_generate.py\n"
        "// Real codegen via codegenModel will be wired in Sprint 3B.\n"
        f"// starter:  {generation_package.get('starterId')}\n"
        f"// scaffold: {generation_package.get('scaffoldId')}\n"
        f"// variant:  {generation_package.get('variantId')}\n"
    )
    (files_dir / "app.tsx").write_text(placeholder, encoding="utf-8")
    (files_dir / "README.md").write_text(
        "# Generated site (mock)\n\n"
        f"runId: {run_id}\n"
        "This is a placeholder produced by the mock chain.\n",
        encoding="utf-8",
    )
    emit(run_id, run_dir, "build", "files.written", "done", "Wrote 2 placeholder files", "generated-files/")

    # codegenModel v1 manifest (deterministic; same path as builder).
    from packages.generation.codegen import produce_codegen_artefakt

    codegen_result = produce_codegen_artefakt(
        generation_package,
        routes_written=[],
        dossier_components=[],
        starter_id=generation_package.get("starterId", "marketing-base"),
    )
    emit(
        run_id, run_dir, "build", "codegen.manifest.emitted", "done",
        f"codegenModel v1 manifest: {len(codegen_result.files)} files "
        f"(source={codegen_result.source}, mock pipeline)",
    )

    # Quality Gate runs against the placeholder target. Without an
    # app/ tree route-scan emits findings; without node_modules
    # typecheck is skipped; without an npm build build-status is
    # skipped. policy-compliance walks files_dir for forbidden .env*.
    from packages.generation.quality_gate import run_quality_gate
    from packages.generation.repair import run_repair_pipeline

    quality_result = run_quality_gate(
        target_dir=files_dir,
        required_routes=[],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    write_json(run_dir / "quality-result.json", quality_result.model_dump())
    emit(
        run_id, run_dir, "build", "quality_result.written", "done",
        f"Quality Gate status={quality_result.status} "
        f"({len(quality_result.checks)} checks, mock pipeline)",
        "quality-result.json",
    )

    repair_result = run_repair_pipeline(
        quality_result, target_dir=files_dir, do_repair=False
    )
    write_json(run_dir / "repair-result.json", repair_result.model_dump())
    emit(
        run_id, run_dir, "build", "repair_result.written", "done",
        f"Repair Pipeline status={repair_result.status} "
        f"(remainingErrors={len(repair_result.remainingErrors)})",
        "repair-result.json",
    )

    build_result = {
        "runId": run_id,
        "status": "mock-complete",
        "filesWritten": 2,
        "repairResultPath": "repair-result.json",
        "qualityResultPath": "quality-result.json",
        "codegen": {
            "source": codegen_result.source,
            "modelUsed": codegen_result.modelUsed,
            "fileCount": len(codegen_result.files),
            "rationale": codegen_result.rationale,
        },
        "createdAt": utcnow_iso(),
    }
    write_json(run_dir / "build-result.json", build_result)
    emit(
        run_id, run_dir, "build", "build.result.written", "done",
        "build-result.json written", "build-result.json",
    )

    emit(run_id, run_dir, "build", "phase.completed", "done", "Phase 3 complete (mock)")
    return build_result


# ----- driver ----------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an Engine Run end-to-end (Phase 1 may use real briefModel).")
    parser.add_argument("prompt", help="The user prompt to feed into the engine.")
    parser.add_argument(
        "--phase",
        choices=["brief", "plan", "build", "all"],
        default="all",
        help="Which phase to run. Default: all.",
    )
    parser.add_argument(
        "--mode",
        choices=["init", "followup"],
        default=os.environ.get("SAJTBYGGAREN_MODE", "init"),
        help="Engine Run mode. Default: init (or SAJTBYGGAREN_MODE env).",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Project ID for follow-up mode. Required when --mode=followup.",
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

    if args.mode == "followup" and not args.project_id:
        print("--mode=followup requires --project-id.", file=sys.stderr)
        return 2

    runs_dir = Path(args.data_runs_dir)
    run_id = args.run_id or make_run_id()
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    emit(
        run_id,
        run_dir,
        "engine",
        "run.started",
        "started",
        f"runId={run_id} phase={args.phase} mode={args.mode}",
    )

    site_brief: dict[str, Any] | None = None
    generation_package: dict[str, Any] | None = None

    if args.phase in ("brief", "all"):
        site_brief = run_phase_understand(
            args.prompt, run_dir, run_id, mode=args.mode, project_id=args.project_id
        )

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
