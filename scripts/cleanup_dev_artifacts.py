#!/usr/bin/env python3
"""Clean local development artifacts with dry-run as the default.

The script focuses on operator-local output: mini-eval directories,
generated previews and Python caches. It never deletes anything unless
``--apply`` is passed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = REPO_ROOT.parent / "sajtbyggaren-output"
# Default mini-eval cleanup root mirrors ``scripts/mini_eval.py``:
# operator-local runs now land under ``data/evals/artifacts/mini/`` (post
# evals-folder-plan). ``LEGACY_OUTPUT_EVALS_DIR`` is kept so allowlist
# checks accept the previous default when an operator still has a
# ``SAJTBYGGAREN_EVALS_DIR=``-override pointing there.
DEFAULT_EVALS_DIR = REPO_ROOT / "data" / "evals" / "artifacts" / "mini"
LEGACY_OUTPUT_EVALS_DIR = OUTPUT_ROOT / ".evals"
DEFAULT_GENERATED_DIR = OUTPUT_ROOT / ".generated"
RUNS_DIR = REPO_ROOT / "data" / "runs"
PROMPT_INPUTS_DIR = REPO_ROOT / "data" / "prompt-inputs"

EVALS_DIR_ENV = "SAJTBYGGAREN_EVALS_DIR"
GENERATED_DIR_ENV = "SAJTBYGGAREN_GENERATED_DIR"
MAX_RUNS_ENV = "SAJTBYGGAREN_MAX_RUNS"
MAX_GENERATED_ENV = "SAJTBYGGAREN_MAX_GENERATED"
MAX_PROMPT_INPUTS_ENV = "SAJTBYGGAREN_MAX_PROMPT_INPUTS"
MINI_EVAL_KEEP_ENV = "SAJTBYGGAREN_MINI_EVAL_KEEP"

EVAL_DIR_SUFFIX = "-mini-eval"
PYTHON_CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache"}
SKIP_WALK_DIR_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    ".next",
    ".turbo",
    "sajtbyggaren-output",
}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def resolve_evals_dir(value: str | None = None) -> Path:
    raw = value or os.environ.get(EVALS_DIR_ENV)
    return Path(raw).expanduser().resolve() if raw else DEFAULT_EVALS_DIR.resolve()


def resolve_generated_dir(value: str | None = None) -> Path:
    raw = value or os.environ.get(GENERATED_DIR_ENV)
    return Path(raw).expanduser().resolve() if raw else DEFAULT_GENERATED_DIR.resolve()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _assert_cleanup_root_allowed(
    root: Path,
    *,
    allow_outside_root: bool = False,
) -> None:
    if _is_relative_to(root, REPO_ROOT) or _is_relative_to(root, OUTPUT_ROOT):
        return
    if allow_outside_root:
        return
    raise SystemExit(
        f"Refusing cleanup outside repo/output roots: {root}. "
        "Pass --allow-outside-root if this is intentional."
    )


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        root_path = Path(root)
        for filename in files:
            try:
                total += (root_path / filename).stat().st_size
            except OSError:
                continue
    return total


def _iso_from_timestamp(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value).isoformat(timespec="seconds")


def _safe_rmtree(path: Path) -> None:
    shutil.rmtree(path)


def _directory_entries(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            stat = child.stat()
        except OSError:
            continue
        entries.append(
            {
                "name": child.name,
                "path": child,
                "mtime": stat.st_mtime,
                "sizeBytes": _dir_size_bytes(child),
            }
        )
    return sorted(entries, key=lambda item: item["mtime"], reverse=True)


def _summary_for_entries(root: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    oldest = min((entry["mtime"] for entry in entries), default=None)
    newest = max((entry["mtime"] for entry in entries), default=None)
    return {
        "root": str(root),
        "count": len(entries),
        "totalSizeBytes": sum(int(entry["sizeBytes"]) for entry in entries),
        "oldest": _iso_from_timestamp(oldest),
        "newest": _iso_from_timestamp(newest),
    }


def cleanup_evals(
    *,
    evals_dir: Path,
    keep: int,
    apply: bool = False,
    allow_outside_root: bool = False,
) -> dict[str, Any]:
    _assert_cleanup_root_allowed(evals_dir, allow_outside_root=allow_outside_root)
    entries = [
        entry
        for entry in _directory_entries(evals_dir)
        if entry["name"].endswith(EVAL_DIR_SUFFIX)
    ]
    entries.sort(key=lambda entry: entry["name"], reverse=True)
    kept = entries[:keep]
    delete_candidates = entries[keep:]
    deleted: list[dict[str, Any]] = []
    if apply:
        for entry in delete_candidates:
            _safe_rmtree(entry["path"])
            deleted.append(entry)
    return {
        "kind": "evals",
        "dryRun": not apply,
        "keep": keep,
        "summary": _summary_for_entries(evals_dir, entries),
        "kept": [_serialise_entry(entry) for entry in kept],
        "wouldDelete": [_serialise_entry(entry) for entry in delete_candidates],
        "deleted": [_serialise_entry(entry) for entry in deleted],
    }


def cleanup_generated(
    *,
    generated_dir: Path,
    keep: int,
    apply: bool = False,
    allow_outside_root: bool = False,
) -> dict[str, Any]:
    _assert_cleanup_root_allowed(generated_dir, allow_outside_root=allow_outside_root)
    entries = _directory_entries(generated_dir)
    kept = entries[:keep]
    delete_candidates = entries[keep:]
    deleted: list[dict[str, Any]] = []
    if apply:
        for entry in delete_candidates:
            _safe_rmtree(entry["path"])
            deleted.append(entry)
    return {
        "kind": "generated",
        "dryRun": not apply,
        "keep": keep,
        "summary": _summary_for_entries(generated_dir, entries),
        "kept": [_serialise_entry(entry) for entry in kept],
        "wouldDelete": [_serialise_entry(entry) for entry in delete_candidates],
        "deleted": [_serialise_entry(entry) for entry in deleted],
    }


def _serialise_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": entry["name"],
        "path": str(entry["path"]),
        "lastModified": _iso_from_timestamp(entry["mtime"]),
        "sizeBytes": entry["sizeBytes"],
    }


def collect_python_caches(roots: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for current, dirs, _files in os.walk(root):
            current_path = Path(current)
            dirs[:] = [name for name in dirs if name not in SKIP_WALK_DIR_NAMES]
            for dirname in list(dirs):
                if dirname not in PYTHON_CACHE_DIR_NAMES:
                    continue
                cache_path = current_path / dirname
                try:
                    stat = cache_path.stat()
                except OSError:
                    continue
                entries.append(
                    {
                        "name": dirname,
                        "path": cache_path,
                        "mtime": stat.st_mtime,
                        "sizeBytes": _dir_size_bytes(cache_path),
                    }
                )
    return sorted(entries, key=lambda item: str(item["path"]))


def cleanup_python_cache(
    *,
    roots: list[Path],
    apply: bool = False,
    allow_outside_root: bool = False,
) -> dict[str, Any]:
    for root in roots:
        _assert_cleanup_root_allowed(root, allow_outside_root=allow_outside_root)
    entries = collect_python_caches(roots)
    deleted: list[dict[str, Any]] = []
    if apply:
        for entry in entries:
            _safe_rmtree(entry["path"])
            deleted.append(entry)
    synthetic_root = Path(";".join(str(root) for root in roots))
    return {
        "kind": "python-cache",
        "dryRun": not apply,
        "summary": _summary_for_entries(synthetic_root, entries),
        "wouldDelete": [_serialise_entry(entry) for entry in entries],
        "deleted": [_serialise_entry(entry) for entry in deleted],
    }


def build_summary(
    *,
    evals_dir: Path,
    generated_dir: Path,
) -> dict[str, Any]:
    return {
        "evals": _summary_for_entries(evals_dir, _directory_entries(evals_dir)),
        "runs": _summary_for_entries(RUNS_DIR, _directory_entries(RUNS_DIR)),
        "promptInputs": {
            "root": str(PROMPT_INPUTS_DIR),
            "count": len(list(PROMPT_INPUTS_DIR.glob("*.json"))) if PROMPT_INPUTS_DIR.is_dir() else 0,
        },
        "generated": _summary_for_entries(generated_dir, _directory_entries(generated_dir)),
        "pythonCache": _summary_for_entries(REPO_ROOT, collect_python_caches([REPO_ROOT])),
    }


def _render_section(report: dict[str, Any]) -> str:
    lines = [
        f"{report['kind']}:",
        f"  dry-run: {report.get('dryRun')}",
    ]
    summary = report.get("summary") or {}
    lines.extend(
        [
            f"  root: {summary.get('root')}",
            f"  count: {summary.get('count')}",
            f"  total size bytes: {summary.get('totalSizeBytes')}",
            f"  oldest: {summary.get('oldest')}",
            f"  newest: {summary.get('newest')}",
        ]
    )
    if "kept" in report:
        lines.append(f"  kept: {len(report['kept'])}")
    lines.append(f"  would delete: {len(report.get('wouldDelete', []))}")
    lines.append(f"  deleted: {len(report.get('deleted', []))}")
    for entry in report.get("wouldDelete", [])[:20]:
        lines.append(f"    - {entry['name']} :: {entry['path']}")
    return "\n".join(lines)


def _render_summary(summary: dict[str, Any]) -> str:
    lines = ["Sammanfattning:"]
    for key, data in summary.items():
        fragments = [f"{key}: root={data.get('root')}", f"count={data.get('count')}"]
        if "totalSizeBytes" in data:
            fragments.append(f"size={data.get('totalSizeBytes')}")
        if data.get("oldest"):
            fragments.append(f"oldest={data.get('oldest')}")
        if data.get("newest"):
            fragments.append(f"newest={data.get('newest')}")
        lines.append("  " + ", ".join(fragments))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true", help="Print counts/sizes only.")
    parser.add_argument("--evals", action="store_true", help="Clean mini-eval directories.")
    parser.add_argument("--generated", action="store_true", help="Clean generated preview directories.")
    parser.add_argument("--python-cache", action="store_true", help="Clean __pycache__ and .pytest_cache.")
    parser.add_argument("--all", action="store_true", help="Run eval, generated and python-cache cleanup plans.")
    parser.add_argument("--keep", type=int, default=None, help="Keep N newest directories for evals/generated.")
    parser.add_argument("--evals-dir", default=None, help=f"Override {EVALS_DIR_ENV}.")
    parser.add_argument("--generated-dir", default=None, help=f"Override {GENERATED_DIR_ENV}.")
    parser.add_argument("--apply", action="store_true", help="Actually delete. Default is dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="Explicit dry-run; default behaviour.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Allow cleanup roots outside repo or ../sajtbyggaren-output.",
    )
    args = parser.parse_args(argv)

    evals_dir = resolve_evals_dir(args.evals_dir)
    generated_dir = resolve_generated_dir(args.generated_dir)
    apply = bool(args.apply and not args.dry_run)
    reports: list[dict[str, Any]] = []
    summary = build_summary(evals_dir=evals_dir, generated_dir=generated_dir)
    run_all = args.all

    if args.evals or run_all:
        keep = args.keep if args.keep is not None else _env_int(MINI_EVAL_KEEP_ENV, 10)
        reports.append(
            cleanup_evals(
                evals_dir=evals_dir,
                keep=keep,
                apply=apply,
                allow_outside_root=args.allow_outside_root,
            )
        )
    if args.generated or run_all:
        keep = args.keep if args.keep is not None else _env_int(MAX_GENERATED_ENV, 5)
        reports.append(
            cleanup_generated(
                generated_dir=generated_dir,
                keep=keep,
                apply=apply,
                allow_outside_root=args.allow_outside_root,
            )
        )
    if args.python_cache or run_all:
        reports.append(
            cleanup_python_cache(
                roots=[REPO_ROOT],
                apply=apply,
                allow_outside_root=args.allow_outside_root,
            )
        )

    payload = {
        "dryRun": not apply,
        "env": {
            EVALS_DIR_ENV: os.environ.get(EVALS_DIR_ENV),
            GENERATED_DIR_ENV: os.environ.get(GENERATED_DIR_ENV),
            MAX_RUNS_ENV: os.environ.get(MAX_RUNS_ENV),
            MAX_GENERATED_ENV: os.environ.get(MAX_GENERATED_ENV),
            MAX_PROMPT_INPUTS_ENV: os.environ.get(MAX_PROMPT_INPUTS_ENV),
            MINI_EVAL_KEEP_ENV: os.environ.get(MINI_EVAL_KEEP_ENV),
        },
        "summary": summary,
        "reports": reports,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(_render_summary(summary))
    for report in reports:
        print()
        print(_render_section(report))
    if not reports and not args.summary:
        print()
        print("Inga cleanup-mål valda. Använd --summary, --evals, --generated, --python-cache eller --all.")
    if not apply:
        print()
        print("Dry-run: ingen radering gjordes. Lägg till --apply för att radera.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
