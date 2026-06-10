"""Deterministic loop proof for the backoffice Playground.

Runs the canonical Golden Path slice IN-PROCESS and DETERMINISTICALLY (no
``OPENAI_API_KEY`` required, no ``npm``): ``generate`` -> ``build(do_build=
False)`` into an isolated work dir under ``data/evals/artifacts/playground/``.
This BUILDS a real site (Project Input -> Site Brief -> Site Plan ->
Generation Package -> Generated Files -> Quality Gate) — it is not a mocked
view.

It reuses the ``scripts/run_golden_path_eval.py`` pattern and helpers verbatim;
it does NOT invent a new engine. The ``build_site.build`` / ``generate``
entrypoints are called read-only (we never modify those modules).
"""

from __future__ import annotations

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .paths import EVALS_ARTIFACTS_DIR

# Default isolated work-tree root for playground runs (kept out of the
# canonical data/runs/ history). Mirrors the golden-path artifacts layout.
PLAYGROUND_ARTIFACTS_DIR = EVALS_ARTIFACTS_DIR / "playground"
PAGE_SNIPPET_MAX_CHARS = 2000
DEFAULT_KEEP_LAST = 5


def baseline_prompt_choices() -> list[tuple[str, str]]:
    """Return ``(case_id, prompt)`` for the four canonical golden-path prompts."""
    from scripts.run_golden_path_eval import BASELINE_CASES

    return [(case.case_id, case.prompt) for case in BASELINE_CASES]


def slugify(text: str, *, fallback: str = "fri-prompt") -> str:
    """Make a filesystem-safe, lowercase site id from free prompt text."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (cleaned[:40] or fallback).strip("-") or fallback


def _new_run_id(site_id: str) -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{stamp}-{site_id}"


def prune_playground_runs(
    artifacts_root: Path, keep_last: int = DEFAULT_KEEP_LAST
) -> list[str]:
    """Keep only the newest ``keep_last`` playground work dirs; remove the rest."""
    if keep_last <= 0 or not artifacts_root.is_dir():
        return []
    dirs = [p for p in artifacts_root.iterdir() if p.is_dir()]
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    removed: list[str] = []
    for stale in dirs[keep_last:]:
        removed.append(stale.name)
        shutil.rmtree(stale, ignore_errors=True)
    return removed


def _read_page_snippet(run_dir: Path) -> str:
    """Return a truncated app/page.tsx snippet from the generated snapshot."""
    page = run_dir / "generated-files" / "app" / "page.tsx"
    if not page.is_file():
        return ""
    text = page.read_text(encoding="utf-8")
    if len(text) > PAGE_SNIPPET_MAX_CHARS:
        return text[:PAGE_SNIPPET_MAX_CHARS] + "\n…(trunkerad)"
    return text


def run_loop_proof(
    prompt: str,
    *,
    site_id: str | None = None,
    artifacts_root: Path = PLAYGROUND_ARTIFACTS_DIR,
    keep_last: int = DEFAULT_KEEP_LAST,
) -> dict[str, Any]:
    """Generate + build one site deterministically and return a visual summary.

    Pure-ish (writes only into ``artifacts_root``); no subprocess, no LLM key,
    no npm. Raises nothing it can avoid — callers render the returned dict.
    """
    from scripts.build_site import build
    from scripts.prompt_to_project_input import generate
    from scripts.run_golden_path_eval import (
        deterministic_llm_env,
        list_generated_routes,
        read_json,
        route_paths,
    )

    site_id = site_id or slugify(prompt)
    run_id = _new_run_id(site_id)
    work_dir = artifacts_root / run_id
    prompt_inputs_dir = work_dir / "prompt-inputs"
    runs_dir = work_dir / "runs"
    generated_dir = work_dir / "generated"
    for directory in (prompt_inputs_dir, runs_dir, generated_dir):
        directory.mkdir(parents=True, exist_ok=True)

    with deterministic_llm_env(True):
        _project_input, _meta, project_input_path, _meta_path = generate(
            prompt,
            output_dir=prompt_inputs_dir,
            site_id=site_id,
        )
        _target, run_dir = build(
            project_input_path,
            do_build=False,
            runs_dir=runs_dir,
            generated_dir=generated_dir,
            auto_prune=False,
        )

    site_plan = read_json(run_dir / "site-plan.json")
    site_brief = read_json(run_dir / "site-brief.json")
    build_result = read_json(run_dir / "build-result.json")
    quality_result = read_json(run_dir / "quality-result.json")

    checks = quality_result.get("checks", [])
    quality_checks = [
        {
            "name": c.get("name", "—"),
            "status": c.get("status", "—"),
            "severity": c.get("severity", "blocking"),
            "detail": c.get("detail", ""),
        }
        for c in (checks if isinstance(checks, list) else [])
        if isinstance(c, dict)
    ]

    result = {
        "prompt": prompt,
        "siteId": site_id,
        "runId": run_dir.name,
        "runDir": str(run_dir),
        "scaffoldId": site_plan.get("scaffoldId"),
        "variantId": site_plan.get("variantId"),
        "starterId": site_plan.get("starterId"),
        "plannedRoutes": route_paths(site_plan),
        "generatedRoutes": list_generated_routes(run_dir),
        "briefSource": site_brief.get("briefSource"),
        "planSource": site_plan.get("planSource"),
        "buildStatus": build_result.get("status"),
        "qualityStatus": quality_result.get("status"),
        "qualityChecks": quality_checks,
        "pageSnippet": _read_page_snippet(run_dir),
    }
    result["prunedRuns"] = prune_playground_runs(artifacts_root, keep_last)
    return result
