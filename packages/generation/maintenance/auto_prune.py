"""Opt-in auto-prune triggered at the start of a new generation.

When the operator runs ``scripts/build_site.py`` or
``scripts/prompt_to_project_input.py`` (directly or via the Viewser
spawn), this module reads three env-vars and prunes the matching
directory tree down to the configured cap:

- ``SAJTBYGGAREN_MAX_RUNS`` -> ``data/runs/``
- ``SAJTBYGGAREN_MAX_GENERATED`` -> ``../sajtbyggaren-output/.generated/``
- ``SAJTBYGGAREN_MAX_PROMPT_INPUTS`` -> ``data/prompt-inputs/``

Opt-in semantics: each env-var is independent. If a var is unset, empty
or non-positive, the corresponding prune is a no-op. This way an
operator can enable run-pruning without forcing generated-preview
pruning at the same time, and CI/tests without env-vars get the safe
default of "do nothing".

Safety:

- Port guard: if ``localhost:3000`` (Viewser dev) OR any local-next
  preview port ``4100-4199`` (see ``apps/viewser/lib/local-preview-server.ts``)
  has a TCP listener, the entire auto-prune is skipped (an active
  preview must not have its ``.generated/<siteId>/`` directory pulled
  out from under it; B167 — the guard previously only checked 3000, so
  a preview on 41xx with Viewser closed was unprotected). Same
  defence-in-depth as ``scripts/prune_generated_previews.py``.
- ``data/prompt-inputs/`` deletes the oldest current-pointer files
  (``<siteId>.project-input.json``) and removes their sidecar
  ``<siteId>.meta.json`` plus the matching versioned snapshots
  (``<siteId>.vN.project-input.json`` and ``<siteId>.vN.meta.json``)
  in one shot, so we don't leave orphan version snapshots behind.
- ``data/runs/`` keeps the N newest run directories by mtime; older
  runs are removed. Old runs have no current-pointer claim - Viewser's
  ``listRuns()`` already only reads the most recent set after B72.
- ``.generated/`` delegates to ``scripts/prune_generated_previews.py``
  via the same ``prune(...)`` entry point that the CLI uses; current-
  pointer protection from ``data/prompt-inputs/`` carries through.

Never touches: ``examples/``, ``data/starters/``, ``.env*``,
``packages/``, ``apps/``, ``governance/``. Only the three data dirs
listed above are in scope.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_INPUTS_DIR = REPO_ROOT / "data" / "prompt-inputs"
RUNS_DIR = REPO_ROOT / "data" / "runs"

MAX_RUNS_ENV_VAR = "SAJTBYGGAREN_MAX_RUNS"
MAX_GENERATED_ENV_VAR = "SAJTBYGGAREN_MAX_GENERATED"
MAX_PROMPT_INPUTS_ENV_VAR = "SAJTBYGGAREN_MAX_PROMPT_INPUTS"

# Mirror the patterns from scripts/prune_generated_previews.py so the
# definition of "current pointer" stays in sync across the two prune
# entry points.
_SITE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_VERSIONED_PROJECT_INPUT_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.v[1-9][0-9]*\.project-input\.json$"
)
_VERSIONED_META_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.v[1-9][0-9]*\.meta\.json$"
)
_CURRENT_POINTER_RE = re.compile(
    r"^([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)\.project-input\.json$"
)


@dataclass
class AutoPruneReport:
    """End-of-call summary so callers and tests can inspect outcome."""

    dry_run: bool
    skipped_due_to_dev_server: bool = False
    runs_removed: list[str] = field(default_factory=list)
    prompt_inputs_removed: list[str] = field(default_factory=list)
    generated_removed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_removed(self) -> int:
        return (
            len(self.runs_removed)
            + len(self.prompt_inputs_removed)
            + len(self.generated_removed)
        )


def _read_max(env_var: str) -> int | None:
    """Return the configured cap, or ``None`` if the var is opt-out.

    Treats unset, empty, non-numeric, zero and negative values all as
    "do not prune this resource". This is the strict opt-in path that
    keeps CI/tests safe by default.
    """
    raw = os.environ.get(env_var)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


# Local-next preview port range. Mirrors PORT_BASE/PORT_RANGE in
# apps/viewser/lib/local-preview-server.ts — keep in sync (B167).
PREVIEW_PORT_BASE = 4100
PREVIEW_PORT_RANGE = 100


def _is_port_in_use(port: int = 3000, host: str = "127.0.0.1") -> bool:
    """Return ``True`` when something is already listening on ``port``.

    Mirrors ``scripts/prune_generated_previews.py:is_port_in_use``.
    A successful TCP connect means a server is up; that is the
    unambiguous signal we use to refuse pruning while a live dev-
    preview is running.
    """
    import socket

    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


def _any_preview_port_in_use() -> bool:
    """True när Viewser (3000) ELLER någon local-next-preview (4100-4199) kör.

    B167: guarden kollade bara 3000 — en `next start`-preview på 41xx
    (spawnad av local-preview-server.ts) med Viewser avstängd skyddades
    inte mot prune av sin egen build-katalog.
    """
    if _is_port_in_use(3000):
        return True
    return any(
        _is_port_in_use(port)
        for port in range(PREVIEW_PORT_BASE, PREVIEW_PORT_BASE + PREVIEW_PORT_RANGE)
    )


def prune_runs(
    runs_dir: Path,
    max_runs: int,
    *,
    dry_run: bool = False,
    protected_run_ids: set[str] | None = None,
) -> list[str]:
    """Prune ``data/runs/`` down to ``max_runs`` newest directories.

    Newest is defined by directory mtime. Returns the list of removed
    run-id directory names. With ``dry_run=True`` the list still reports
    what would be removed but nothing is deleted.
    """
    if max_runs <= 0:
        return []
    if not runs_dir.is_dir():
        return []
    protected = protected_run_ids or set()
    entries: list[tuple[float, Path]] = []
    for child in runs_dir.iterdir():
        if not child.is_dir():
            continue
        if child.name in protected:
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        entries.append((mtime, child))
    if len(entries) <= max_runs:
        return []
    entries.sort(key=lambda item: item[0], reverse=True)
    to_remove = [path for _, path in entries[max_runs:]]
    removed: list[str] = []
    for path in to_remove:
        removed.append(path.name)
        if dry_run:
            continue
        try:
            shutil.rmtree(path)
        except OSError as exc:
            print(
                f"auto-prune: failed to remove run {path.name}: {exc}",
                file=sys.stderr,
            )
    return removed


def prune_prompt_inputs(
    prompt_inputs_dir: Path,
    max_inputs: int,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Prune ``data/prompt-inputs/`` current pointers down to ``max_inputs``.

    Counts only ``<siteId>.project-input.json`` pointer files. For each
    pointer that is removed, the sidecar ``<siteId>.meta.json`` and all
    versioned snapshots ``<siteId>.vN.project-input.json`` plus their
    ``<siteId>.vN.meta.json`` siblings are removed in the same pass so
    no orphan snapshots are left behind. Returns the list of removed
    siteIds.
    """
    if max_inputs <= 0:
        return []
    if not prompt_inputs_dir.is_dir():
        return []
    pointers: list[tuple[float, str, Path]] = []
    for child in prompt_inputs_dir.iterdir():
        if not child.is_file():
            continue
        match = _CURRENT_POINTER_RE.match(child.name)
        if not match:
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        pointers.append((mtime, match.group(1), child))
    if len(pointers) <= max_inputs:
        return []
    pointers.sort(key=lambda item: item[0], reverse=True)
    to_remove = pointers[max_inputs:]
    removed_site_ids: list[str] = []
    for _, site_id, pointer_path in to_remove:
        removed_site_ids.append(site_id)
        related = _associated_paths(prompt_inputs_dir, site_id, pointer_path)
        for path in related:
            if dry_run:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                print(
                    f"auto-prune: failed to remove {path.name}: {exc}",
                    file=sys.stderr,
                )
    return removed_site_ids


def _associated_paths(
    prompt_inputs_dir: Path, site_id: str, pointer_path: Path
) -> list[Path]:
    """Return pointer + sidecar + all versioned snapshots for ``site_id``."""
    associated: list[Path] = [pointer_path]
    sidecar = prompt_inputs_dir / f"{site_id}.meta.json"
    if sidecar.is_file():
        associated.append(sidecar)
    prefix_pi = f"{site_id}.v"
    prefix_meta = f"{site_id}.v"
    for child in prompt_inputs_dir.iterdir():
        if not child.is_file():
            continue
        name = child.name
        if name.startswith(prefix_pi) and _VERSIONED_PROJECT_INPUT_RE.match(name):
            associated.append(child)
        elif name.startswith(prefix_meta) and _VERSIONED_META_RE.match(name):
            associated.append(child)
    return associated


def prune_generated(
    max_generated: int,
    *,
    dry_run: bool = False,
    generated_dir: Path | None = None,
    skip_live_check: bool = False,
) -> list[str]:
    """Prune ``.generated/`` previews down to ``max_generated`` newest.

    Delegates to ``scripts/prune_generated_previews.prune(...)`` so the
    current-pointer protection from ``data/prompt-inputs/`` and the
    port-3000 guard stay consistent with the standalone CLI. Returns
    the list of removed ``<siteId>`` directory names.
    """
    if max_generated <= 0:
        return []
    scripts_dir = REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from prune_generated_previews import (  # type: ignore[import-not-found]
            DECISION_DELETE_APPLIED,
            DECISION_DELETE_PER_SITE,
            DECISION_DELETE_TOTAL,
            prune,
            resolve_generated_dir,
        )
    except ImportError as exc:
        print(
            f"auto-prune: cannot import prune_generated_previews: {exc}",
            file=sys.stderr,
        )
        return []

    target_dir = resolve_generated_dir(generated_dir)
    report = prune(
        generated_dir=target_dir,
        keep_per_site=max_generated,
        keep_total=max_generated,
        apply=not dry_run,
        skip_live_check=skip_live_check,
    )
    delete_decisions = {
        DECISION_DELETE_PER_SITE,
        DECISION_DELETE_TOTAL,
        DECISION_DELETE_APPLIED,
    }
    return [entry.site_id for entry in report.entries if entry.decision in delete_decisions]


def auto_prune_all(
    *,
    dry_run: bool = False,
    skip_port_guard: bool = False,
    runs_dir: Path | None = None,
    prompt_inputs_dir: Path | None = None,
    generated_dir: Path | None = None,
    verbose: bool = True,
) -> AutoPruneReport:
    """Read env-vars and prune each enabled resource.

    Returns an ``AutoPruneReport`` summarising the operation. Logs a
    single human-readable summary line to stderr when ``verbose=True``
    so the operator sees what happened without having to inspect the
    return value.
    """
    report = AutoPruneReport(dry_run=dry_run)
    max_runs = _read_max(MAX_RUNS_ENV_VAR)
    max_generated = _read_max(MAX_GENERATED_ENV_VAR)
    max_prompt_inputs = _read_max(MAX_PROMPT_INPUTS_ENV_VAR)

    if max_runs is None and max_generated is None and max_prompt_inputs is None:
        return report

    if not skip_port_guard and _any_preview_port_in_use():
        report.skipped_due_to_dev_server = True
        if verbose:
            print(
                "auto-prune: skipped (port 3000 or a preview port 4100-4199 "
                "in use; live dev-preview detected)",
                file=sys.stderr,
            )
        return report

    runs_target = runs_dir if runs_dir is not None else RUNS_DIR
    if max_runs is not None:
        report.runs_removed = prune_runs(runs_target, max_runs, dry_run=dry_run)

    prompt_inputs_target = (
        prompt_inputs_dir if prompt_inputs_dir is not None else PROMPT_INPUTS_DIR
    )
    if max_prompt_inputs is not None:
        report.prompt_inputs_removed = prune_prompt_inputs(
            prompt_inputs_target, max_prompt_inputs, dry_run=dry_run
        )

    if max_generated is not None:
        report.generated_removed = prune_generated(
            max_generated, dry_run=dry_run, generated_dir=generated_dir
        )

    if verbose and report.total_removed:
        mode = "would-remove" if dry_run else "removed"
        print(
            "auto-prune: "
            f"{mode} {len(report.runs_removed)} runs, "
            f"{len(report.generated_removed)} generated, "
            f"{len(report.prompt_inputs_removed)} prompt-inputs",
            file=sys.stderr,
        )

    return report
