"""Pure maintenance helpers for the Streamlit backoffice.

The UI layer in ``backoffice/views/maintenance.py`` renders the buttons and
warnings. This module keeps the filesystem planning/apply logic testable
without importing Streamlit.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from packages.generation.maintenance import (
    MAX_GENERATED_ENV_VAR,
    MAX_PROMPT_INPUTS_ENV_VAR,
    MAX_RUNS_ENV_VAR,
    prune_generated,
    prune_prompt_inputs,
    prune_runs,
)
from scripts.prune_generated_previews import resolve_generated_dir

from .paths import REPO_ROOT


@dataclass(frozen=True)
class CleanupItem:
    """One file or directory that a maintenance action can remove."""

    path: Path
    kind: str
    size_bytes: int
    warning: str | None = None


@dataclass
class CleanupPlan:
    """Dry-run view of a cleanup action."""

    label: str
    dry_run: bool
    items: list[CleanupItem] = field(default_factory=list)
    protected_paths: list[Path] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.items)


@dataclass
class CleanupResult:
    """Result from applying a cleanup plan."""

    deleted_paths: list[Path] = field(default_factory=list)
    freed_bytes: int = 0
    skipped_paths: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def deleted_count(self) -> int:
        return len(self.deleted_paths)


def positive_int_from_env(name: str, environ: dict[str, str] | None = None) -> int | None:
    """Parse the opt-in retention caps used by the generation maintenance module."""
    source = environ if environ is not None else os.environ
    raw = source.get(name)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def format_megabytes(size_bytes: int) -> str:
    """Return a compact megabyte string for operator-facing UI."""
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def path_size_bytes(path: Path) -> int:
    """Calculate file/directory size without following symlinks."""
    if not path.exists() or path.is_symlink():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        dirs[:] = [name for name in dirs if not (root_path / name).is_symlink()]
        for filename in files:
            child = root_path / filename
            if child.is_symlink():
                continue
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def assert_cleanup_path_allowed(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
    generated_dir: Path | None = None,
    allow_warning_targets: bool = False,
) -> None:
    """Fail closed before deleting anything from a maintenance cleanup."""
    resolved = path.resolve()
    if path.is_symlink():
        raise ValueError(f"Refusing to delete symlink: {resolved}")
    if resolved.name.startswith(".env") and resolved.name != ".env.example":
        raise ValueError(f"Refusing to delete dotenv file: {resolved}")

    denied_roots = [
        repo_root / "examples",
        repo_root / "data" / "starters",
        repo_root / "packages" / "preview-runtime",
    ]
    for denied in denied_roots:
        if _is_within(resolved, denied):
            raise ValueError(f"Refusing to delete off-limits path: {resolved}")

    warning_roots = [repo_root / "data" / "prompt-inputs", repo_root / "apps" / "viewser" / "node_modules"]
    if any(_is_within(resolved, root) for root in warning_roots):
        if allow_warning_targets:
            return
        raise ValueError(f"Warning target requires explicit confirmation: {resolved}")

    allowed_roots = [
        repo_root / "data" / "runs",
        repo_root / ".pytest_cache",
        repo_root / ".ruff_cache",
        repo_root / "sajtbyggaren.egg-info",
        repo_root / "apps" / "viewser" / ".next",
    ]
    if generated_dir is not None:
        allowed_roots.append(generated_dir)
    if resolved.parent == repo_root.resolve() and resolved.suffix == ".log":
        return
    if resolved.name == "__pycache__" and _is_within(resolved, repo_root):
        return
    if any(_is_within(resolved, root) for root in allowed_roots):
        return
    raise ValueError(f"Path is not part of a known cleanup target: {resolved}")


def _item(path: Path, kind: str, warning: str | None = None) -> CleanupItem:
    return CleanupItem(path=path, kind=kind, size_bytes=path_size_bytes(path), warning=warning)


def plan_safe_cleanup(
    *,
    repo_root: Path = REPO_ROOT,
    generated_dir: Path | None = None,
    environ: dict[str, str] | None = None,
    protected_run_ids: set[str] | None = None,
) -> CleanupPlan:
    """Plan safe cleanup targets without deleting anything."""
    plan = CleanupPlan(label="Cleanup - Säker rensning", dry_run=True)
    generated_root = generated_dir if generated_dir is not None else resolve_generated_dir()
    protected = protected_run_ids or set()

    max_runs = positive_int_from_env(MAX_RUNS_ENV_VAR, environ)
    if max_runs is not None:
        run_names = prune_runs(
            repo_root / "data" / "runs",
            max_runs,
            dry_run=True,
            protected_run_ids=protected,
        )
        for name in run_names:
            path = repo_root / "data" / "runs" / name
            if path.exists():
                plan.items.append(_item(path, "run"))

    max_generated = positive_int_from_env(MAX_GENERATED_ENV_VAR, environ)
    if max_generated is not None:
        site_ids = prune_generated(max_generated, dry_run=True, generated_dir=generated_root)
        for site_id in site_ids:
            path = generated_root / site_id
            if path.exists():
                plan.items.append(_item(path, "generated-preview"))

    for cache_path in [
        repo_root / ".pytest_cache",
        repo_root / ".ruff_cache",
        repo_root / "sajtbyggaren.egg-info",
        repo_root / "apps" / "viewser" / ".next",
    ]:
        if cache_path.exists():
            plan.items.append(_item(cache_path, "cache"))

    for pycache in repo_root.rglob("__pycache__"):
        if pycache.is_dir() and not pycache.is_symlink():
            plan.items.append(_item(pycache, "python-cache"))

    for log_file in repo_root.glob("*.log"):
        if log_file.is_file() and not log_file.is_symlink():
            plan.items.append(_item(log_file, "root-log"))

    return plan


def plan_warning_cleanup(
    *,
    repo_root: Path = REPO_ROOT,
    environ: dict[str, str] | None = None,
) -> CleanupPlan:
    """Plan warning cleanup targets without deleting anything."""
    plan = CleanupPlan(label="Cleanup - Med varning", dry_run=True)
    max_prompt_inputs = positive_int_from_env(MAX_PROMPT_INPUTS_ENV_VAR, environ)
    if max_prompt_inputs is not None:
        site_ids = prune_prompt_inputs(
            repo_root / "data" / "prompt-inputs",
            max_prompt_inputs,
            dry_run=True,
        )
        for site_id in site_ids:
            pointer = repo_root / "data" / "prompt-inputs" / f"{site_id}.project-input.json"
            if pointer.exists():
                plan.items.append(
                    _item(
                        pointer,
                        "prompt-input",
                        "Tar bort fortsätt-på-sajt-underlag för detta siteId.",
                    )
                )

    node_modules = repo_root / "apps" / "viewser" / "node_modules"
    if node_modules.exists():
        plan.items.append(
            _item(
                node_modules,
                "node-modules",
                "Kräver npm install i apps/viewser efteråt.",
            )
        )
    return plan


def apply_safe_cleanup(
    *,
    repo_root: Path = REPO_ROOT,
    generated_dir: Path | None = None,
    environ: dict[str, str] | None = None,
    protected_run_ids: set[str] | None = None,
) -> CleanupResult:
    """Apply safe cleanup and report deleted paths + freed bytes."""
    generated_root = generated_dir if generated_dir is not None else resolve_generated_dir()
    plan = plan_safe_cleanup(
        repo_root=repo_root,
        generated_dir=generated_root,
        environ=environ,
        protected_run_ids=protected_run_ids,
    )
    result = CleanupResult()

    max_runs = positive_int_from_env(MAX_RUNS_ENV_VAR, environ)
    removed_runs: set[str] = set()
    if max_runs is not None:
        removed_runs = set(
            prune_runs(
                repo_root / "data" / "runs",
                max_runs,
                dry_run=False,
                protected_run_ids=protected_run_ids or set(),
            )
        )

    max_generated = positive_int_from_env(MAX_GENERATED_ENV_VAR, environ)
    removed_generated: set[str] = set()
    if max_generated is not None:
        removed_generated = set(
            prune_generated(max_generated, dry_run=False, generated_dir=generated_root)
        )

    for item in plan.items:
        try:
            assert_cleanup_path_allowed(item.path, repo_root=repo_root, generated_dir=generated_root)
        except ValueError as exc:
            result.errors.append(str(exc))
            result.skipped_paths.append(item.path)
            continue

        already_handled = (
            item.kind == "run" and item.path.name in removed_runs
        ) or (
            item.kind == "generated-preview" and item.path.name in removed_generated
        )
        if already_handled:
            result.deleted_paths.append(item.path)
            result.freed_bytes += item.size_bytes
            continue
        if item.kind in {"run", "generated-preview"}:
            if item.path.exists():
                result.skipped_paths.append(item.path)
            else:
                result.deleted_paths.append(item.path)
                result.freed_bytes += item.size_bytes
            continue

        try:
            if item.path.is_dir():
                shutil.rmtree(item.path)
            else:
                item.path.unlink()
        except OSError as exc:
            result.errors.append(f"{item.path}: {exc}")
            result.skipped_paths.append(item.path)
            continue
        result.deleted_paths.append(item.path)
        result.freed_bytes += item.size_bytes

    return result


def apply_warning_cleanup(
    *,
    repo_root: Path = REPO_ROOT,
    environ: dict[str, str] | None = None,
    include_prompt_inputs: bool = False,
    include_node_modules: bool = False,
) -> CleanupResult:
    """Apply warning cleanup after the UI has collected explicit confirmation."""
    plan = plan_warning_cleanup(repo_root=repo_root, environ=environ)
    result = CleanupResult()
    max_prompt_inputs = positive_int_from_env(MAX_PROMPT_INPUTS_ENV_VAR, environ)
    removed_prompt_inputs: set[str] = set()
    if include_prompt_inputs and max_prompt_inputs is not None:
        removed_prompt_inputs = set(
            prune_prompt_inputs(
                repo_root / "data" / "prompt-inputs",
                max_prompt_inputs,
                dry_run=False,
            )
        )

    for item in plan.items:
        if item.kind == "prompt-input" and not include_prompt_inputs:
            result.skipped_paths.append(item.path)
            continue
        if item.kind == "node-modules" and not include_node_modules:
            result.skipped_paths.append(item.path)
            continue
        try:
            assert_cleanup_path_allowed(
                item.path,
                repo_root=repo_root,
                allow_warning_targets=True,
            )
        except ValueError as exc:
            result.errors.append(str(exc))
            result.skipped_paths.append(item.path)
            continue
        if item.kind == "prompt-input" and item.path.stem.removesuffix(".project-input") in removed_prompt_inputs:
            result.deleted_paths.append(item.path)
            result.freed_bytes += item.size_bytes
            continue
        if item.kind == "prompt-input":
            if item.path.exists():
                result.skipped_paths.append(item.path)
            else:
                result.deleted_paths.append(item.path)
                result.freed_bytes += item.size_bytes
            continue
        try:
            if item.path.is_dir():
                shutil.rmtree(item.path)
            else:
                item.path.unlink()
        except OSError as exc:
            result.errors.append(f"{item.path}: {exc}")
            result.skipped_paths.append(item.path)
            continue
        result.deleted_paths.append(item.path)
        result.freed_bytes += item.size_bytes
    return result
