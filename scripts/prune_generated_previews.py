"""Prune dev-preview directories under ../sajtbyggaren-output/.generated/.

The Builder MVP writes every dev-preview build into
``$SAJTBYGGAREN_GENERATED_DIR`` (default ``../sajtbyggaren-output/.generated/``,
see ``scripts/build_site.py:resolve_generated_dir``). The directory grows
over time: each fresh prompt creates a new ``<siteId>/`` subdirectory with
``node_modules/``, ``.next/`` and the full Next.js project. Without
periodic cleanup the operator runs out of disk space and IDE indexers
slow down.

This script implements queue-item 1 from ``docs/current-focus.md`` and
the Scout-RO spec from 2026-05-15:

- **Dry-run by default.** No deletion happens unless ``--apply`` is
  passed. The default also honours
  ``SAJTBYGGAREN_PREVIEW_RETENTION_DRY_RUN=true`` so an operator can
  still get a preview by running ``--apply`` together with the env
  var set to ``false`` (or unset).
- **Current-pointer protection.** Any siteId referenced by a current
  pointer in ``data/prompt-inputs/<siteId>.project-input.json`` (the
  pointer file, never the immutable ``<siteId>.vN.project-input.json``
  snapshots) or by ``data/runs/*/build-result.json`` is never pruned,
  regardless of retention caps.
- **Retention caps.** ``--keep-per-site`` (default 3) keeps the N most
  recent previews per ``siteId`` group; ``--keep-total`` (default 10)
  caps the total survivors after per-site filtering. Today the layout
  is one preview per siteId, so ``--keep-per-site`` is effectively a
  no-op until a future architecture introduces versioned subdirs.
- **Live-target guard.** Refuses to operate when a process appears to
  be using the target tree: a TCP listener on port 3000 (Next.js dev
  default) blocks the run unconditionally; per-process cwd checks run
  when ``psutil`` is importable and warn-only otherwise.
- **Off-limits.** Never touches ``data/runs/``, ``data/prompt-inputs/``
  or any ``.env*`` file. Operates strictly under the resolved
  ``.generated/`` root.

Usage::

    python scripts/prune_generated_previews.py            # dry-run
    python scripts/prune_generated_previews.py --apply    # delete
    python scripts/prune_generated_previews.py --keep-per-site 2 --keep-total 5
    python scripts/prune_generated_previews.py --generated-dir /tmp/.generated

The dry-run output prints one row per preview directory with siteId,
absolute path, last-write timestamp and decision so the operator can
audit what would be deleted before passing ``--apply``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GENERATED_DIR = REPO_ROOT.parent / "sajtbyggaren-output" / ".generated"
PROMPT_INPUTS_DIR = REPO_ROOT / "data" / "prompt-inputs"
RUNS_DIR = REPO_ROOT / "data" / "runs"

DEFAULT_KEEP_PER_SITE = 3
DEFAULT_KEEP_TOTAL = 10
NEXT_DEV_PORT = 3000

DRY_RUN_ENV_VAR = "SAJTBYGGAREN_PREVIEW_RETENTION_DRY_RUN"
GENERATED_DIR_ENV_VAR = "SAJTBYGGAREN_GENERATED_DIR"

# Mirrors apps/viewser/lib/project-inputs.ts:VERSIONED_PROJECT_INPUT_PATTERN
# so that immutable ``.vN.project-input.json`` snapshots are filtered out
# of the current-pointer set. Only the pointer file
# ``<siteId>.project-input.json`` (without ``.vN.``) acts as a current
# selection target in Viewser.
_VERSIONED_PROJECT_INPUT_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.v[1-9][0-9]*\.project-input\.json$"
)
_PROJECT_INPUT_FILE_RE = re.compile(
    r"^([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)\.project-input\.json$"
)
_SITE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


# Decision strings emitted in dry-run output. Locked by tests so a
# refactor cannot silently rename them and break the operator's mental
# model of what the script will do under ``--apply``.
DECISION_SKIP_CURRENT = "skip:current-pointer"
DECISION_KEEP_WITHIN = "keep:within-retention"
DECISION_DELETE_PER_SITE = "would-delete:per-site-cap"
DECISION_DELETE_TOTAL = "would-delete:total-cap"
DECISION_DELETE_APPLIED = "deleted"


@dataclass
class PreviewEntry:
    """One toplevel directory under ``.generated/`` and its decision."""

    site_id: str
    path: Path
    last_write: float
    decision: str = ""
    apply_error: str | None = None

    @property
    def last_write_iso(self) -> str:
        return datetime.fromtimestamp(self.last_write).isoformat(timespec="seconds")


@dataclass
class PruneReport:
    """End-of-run summary so callers (CLI + tests) can introspect."""

    generated_dir: Path
    dry_run: bool
    keep_per_site: int
    keep_total: int
    protected_site_ids: set[str]
    entries: list[PreviewEntry] = field(default_factory=list)
    skipped_live_reasons: list[str] = field(default_factory=list)

    def to_json_summary(self) -> dict:
        return {
            "generatedDir": str(self.generated_dir),
            "dryRun": self.dry_run,
            "keepPerSite": self.keep_per_site,
            "keepTotal": self.keep_total,
            "protectedSiteIds": sorted(self.protected_site_ids),
            "entries": [
                {
                    "siteId": entry.site_id,
                    "path": str(entry.path),
                    "lastWrite": entry.last_write_iso,
                    "decision": entry.decision,
                    "applyError": entry.apply_error,
                }
                for entry in self.entries
            ],
        }


def _env_flag(value: str | None, *, default: bool) -> bool:
    """Parse a boolean env-var. Empty/unset -> ``default``."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_generated_dir(override: str | Path | None = None) -> Path:
    """Resolve where dev-preview builds live.

    Mirrors ``scripts/build_site.py:resolve_generated_dir`` so the prune
    target follows the same env/default chain that the builder writes
    to: explicit override > ``SAJTBYGGAREN_GENERATED_DIR`` env > the
    default sibling ``../sajtbyggaren-output/.generated/``.
    """
    candidate: str | Path | None = override
    if candidate is None:
        env_value = os.environ.get(GENERATED_DIR_ENV_VAR)
        if env_value:
            candidate = env_value
        else:
            candidate = DEFAULT_GENERATED_DIR

    resolved = Path(candidate).expanduser()
    if not resolved.is_absolute():
        resolved = (REPO_ROOT / resolved).resolve()
    return resolved


def collect_protected_site_ids(
    *,
    prompt_inputs_dir: Path = PROMPT_INPUTS_DIR,
    runs_dir: Path = RUNS_DIR,
) -> set[str]:
    """Collect siteIds that are referenced by a current pointer.

    Two sources contribute:

    1. ``data/prompt-inputs/<siteId>.project-input.json`` pointer files
       (the immutable ``<siteId>.vN.project-input.json`` snapshots are
       filtered out via ``_VERSIONED_PROJECT_INPUT_RE`` so a stale
       version snapshot cannot keep an orphan preview alive forever).
    2. ``data/runs/<runId>/build-result.json`` ``siteId`` fields - any
       run that reached the build phase recorded the siteId there, so a
       still-referenced preview is protected even if the operator has
       since renamed the prompt-input file.
    """
    protected: set[str] = set()
    if prompt_inputs_dir.is_dir():
        for entry in prompt_inputs_dir.iterdir():
            if not entry.is_file():
                continue
            if _VERSIONED_PROJECT_INPUT_RE.match(entry.name):
                continue
            match = _PROJECT_INPUT_FILE_RE.match(entry.name)
            if match:
                protected.add(match.group(1))

    if runs_dir.is_dir():
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            build_result = run_dir / "build-result.json"
            if not build_result.is_file():
                continue
            try:
                payload = json.loads(build_result.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                # A corrupt or half-written build-result must not
                # silently un-protect siteIds; skip the file but keep
                # whatever else we already collected.
                continue
            site_id = payload.get("siteId")
            if isinstance(site_id, str) and _SITE_ID_RE.match(site_id):
                protected.add(site_id)

    return protected


def is_port_in_use(port: int = NEXT_DEV_PORT, *, host: str = "127.0.0.1") -> bool:
    """Return True when something is already listening on ``port``.

    Uses a 200ms TCP connect attempt instead of binding. Bind-based
    detection is ambiguous on Windows when the port is in TIME_WAIT;
    a successful connect is unambiguous: someone accepted the
    handshake, therefore a server is up.
    """
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


def detect_processes_using_dir(target: Path) -> list[str]:
    """Return human-readable descriptions of processes whose cwd is under ``target``.

    Best-effort: ``psutil`` is not in ``requirements.txt`` so this
    helper imports it lazily and silently skips the check when it is
    missing. The port-3000 guard remains as the unconditional safety
    net; this helper is the additional defence in depth requested by
    the Scout RO-spec for a future cleanup-tooling deployment.
    """
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        return []

    target_resolved = target.resolve()
    matches: list[str] = []
    for proc in psutil.process_iter(["pid", "name", "cwd"]):
        try:
            cwd_raw = proc.info.get("cwd")
            if not cwd_raw:
                continue
            cwd = Path(cwd_raw).resolve()
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        try:
            cwd.relative_to(target_resolved)
        except ValueError:
            continue
        matches.append(
            f"pid={proc.info.get('pid')} name={proc.info.get('name')} cwd={cwd}"
        )
    return matches


def _site_id_from_dir_name(name: str) -> str | None:
    """Best-effort siteId extraction from a ``.generated/<dir>`` name.

    The Builder MVP writes one directory per siteId so the directory
    name matches ``_SITE_ID_RE`` exactly. Names that do not match are
    treated as unknown siteIds (still groupable, but never matched
    against the protected set).
    """
    if _SITE_ID_RE.match(name):
        return name
    return None


def _enumerate_previews(generated_dir: Path) -> list[PreviewEntry]:
    """List toplevel directories under ``generated_dir`` as preview entries."""
    if not generated_dir.is_dir():
        return []
    entries: list[PreviewEntry] = []
    for child in generated_dir.iterdir():
        if not child.is_dir():
            continue
        site_id = _site_id_from_dir_name(child.name) or child.name
        try:
            last_write = child.stat().st_mtime
        except OSError:
            continue
        entries.append(
            PreviewEntry(site_id=site_id, path=child, last_write=last_write)
        )
    return entries


def _decide_retention(
    entries: list[PreviewEntry],
    *,
    protected: set[str],
    keep_per_site: int,
    keep_total: int,
) -> None:
    """Populate ``entry.decision`` on every entry in ``entries`` in-place.

    Algorithm:

    1. Skip any entry whose ``site_id`` is in ``protected``.
    2. For each remaining ``site_id`` group, keep the ``keep_per_site``
       newest entries; mark the rest ``would-delete:per-site-cap``.
    3. Across the surviving (non-protected, kept-per-site) entries
       globally, keep the ``keep_total`` newest; mark the overflow
       ``would-delete:total-cap``.

    This lets the operator tune the two caps independently. With the
    current 1-per-siteId layout step 2 is mostly a no-op and step 3
    does the real work; the script remains correct if a future layout
    versions previews per siteId.
    """
    grouped: dict[str, list[PreviewEntry]] = defaultdict(list)
    for entry in entries:
        if entry.site_id in protected:
            entry.decision = DECISION_SKIP_CURRENT
            continue
        grouped[entry.site_id].append(entry)

    survivors: list[PreviewEntry] = []
    for site_entries in grouped.values():
        site_entries.sort(key=lambda e: e.last_write, reverse=True)
        for index, entry in enumerate(site_entries):
            if index < keep_per_site:
                entry.decision = DECISION_KEEP_WITHIN
                survivors.append(entry)
            else:
                entry.decision = DECISION_DELETE_PER_SITE

    survivors.sort(key=lambda e: e.last_write, reverse=True)
    for index, entry in enumerate(survivors):
        if index >= keep_total:
            entry.decision = DECISION_DELETE_TOTAL


def _delete_entry(entry: PreviewEntry) -> None:
    """Recursively remove a preview directory.

    Captures any OS error on the entry itself so a single failed
    rmtree does not stop the rest of the prune; the operator sees the
    error message in the final report.
    """
    try:
        shutil.rmtree(entry.path)
    except OSError as exc:  # noqa: BLE001
        entry.apply_error = f"{type(exc).__name__}: {exc}"
        return
    entry.decision = DECISION_DELETE_APPLIED


def _is_deletion_decision(decision: str) -> bool:
    return decision in {DECISION_DELETE_PER_SITE, DECISION_DELETE_TOTAL}


def prune(
    *,
    generated_dir: Path,
    keep_per_site: int = DEFAULT_KEEP_PER_SITE,
    keep_total: int = DEFAULT_KEEP_TOTAL,
    apply: bool = False,
    prompt_inputs_dir: Path = PROMPT_INPUTS_DIR,
    runs_dir: Path = RUNS_DIR,
    skip_live_check: bool = False,
) -> PruneReport:
    """Compute the prune plan, optionally apply it, and return a report.

    ``apply=False`` (the default) performs no deletion and leaves the
    decisions in the ``would-delete:*`` form. ``apply=True`` walks the
    decided plan and removes each ``would-delete:*`` directory; on
    success the decision is rewritten to ``deleted``.

    The live-target guard runs first when ``apply=True``; under the
    dry-run default it would only block introspection and is therefore
    skipped so the operator can always preview which directories are
    targeted. ``skip_live_check`` lets tests bypass the guard while
    still exercising the apply path.
    """
    if keep_per_site < 0 or keep_total < 0:
        raise SystemExit("keep-per-site and keep-total must be non-negative")

    report = PruneReport(
        generated_dir=generated_dir,
        dry_run=not apply,
        keep_per_site=keep_per_site,
        keep_total=keep_total,
        protected_site_ids=collect_protected_site_ids(
            prompt_inputs_dir=prompt_inputs_dir,
            runs_dir=runs_dir,
        ),
    )

    if apply and not skip_live_check:
        if is_port_in_use(NEXT_DEV_PORT):
            report.skipped_live_reasons.append(
                f"port {NEXT_DEV_PORT} is in use - refusing to prune while a "
                "preview/dev server is running"
            )
        cwd_matches = detect_processes_using_dir(generated_dir)
        if cwd_matches:
            report.skipped_live_reasons.append(
                "process cwd under target directory: " + "; ".join(cwd_matches)
            )
        if report.skipped_live_reasons:
            raise SystemExit(
                "Live target detected; aborting before any deletion. Reasons:\n  - "
                + "\n  - ".join(report.skipped_live_reasons)
            )

    entries = _enumerate_previews(generated_dir)
    entries.sort(key=lambda e: (e.site_id, -e.last_write))
    report.entries = entries

    _decide_retention(
        entries,
        protected=report.protected_site_ids,
        keep_per_site=keep_per_site,
        keep_total=keep_total,
    )

    if apply:
        for entry in entries:
            if _is_deletion_decision(entry.decision):
                _delete_entry(entry)

    return report


def _format_report_table(report: PruneReport) -> str:
    """Render the per-entry table that the CLI emits."""
    if not report.entries:
        return "(no preview directories found)"
    rows = [
        ("siteId", "decision", "lastWrite", "path"),
    ]
    for entry in report.entries:
        rows.append(
            (
                entry.site_id,
                entry.decision + (
                    f" (apply-error: {entry.apply_error})" if entry.apply_error else ""
                ),
                entry.last_write_iso,
                str(entry.path),
            )
        )
    widths = [max(len(row[col]) for row in rows) for col in range(len(rows[0]))]
    formatted = []
    for row in rows:
        formatted.append(
            "  ".join(cell.ljust(widths[col]) for col, cell in enumerate(row))
        )
    return "\n".join(formatted)


def _summarise_decisions(report: PruneReport) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for entry in report.entries:
        counts[entry.decision] += 1
    return dict(counts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prune dev-preview directories under "
            "../sajtbyggaren-output/.generated/. Dry-run by default."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Actually delete the would-delete entries. Without this flag "
            "the script only prints the plan."
        ),
    )
    parser.add_argument(
        "--keep-per-site",
        type=int,
        default=DEFAULT_KEEP_PER_SITE,
        help=(
            "Keep the N most recent previews per siteId group "
            f"(default {DEFAULT_KEEP_PER_SITE})."
        ),
    )
    parser.add_argument(
        "--keep-total",
        type=int,
        default=DEFAULT_KEEP_TOTAL,
        help=(
            "Cap total survivors after per-site filtering "
            f"(default {DEFAULT_KEEP_TOTAL})."
        ),
    )
    parser.add_argument(
        "--generated-dir",
        default=None,
        help=(
            "Override the .generated/ root. Defaults to "
            f"${GENERATED_DIR_ENV_VAR} env var or "
            "../sajtbyggaren-output/.generated/."
        ),
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit a JSON summary instead of the human-readable table.",
    )
    args = parser.parse_args(argv)

    generated_dir = resolve_generated_dir(args.generated_dir)

    # The dry-run env flag is an opt-in safety belt: an operator who
    # exports ``SAJTBYGGAREN_PREVIEW_RETENTION_DRY_RUN=true`` in their
    # shell gets a global "no-deletion" override that neutralises any
    # ``--apply`` on the command line. The env defaults to ``False``
    # (unset = inactive) so the natural CLI invocation
    # ``python scripts/prune_generated_previews.py --apply`` actually
    # deletes; the previous default=True made --apply a no-op without
    # the operator first exporting the env var to ``false``, which
    # contradicted the script's own help text.
    dry_run_env = _env_flag(os.environ.get(DRY_RUN_ENV_VAR), default=False)
    apply = args.apply and not dry_run_env

    report = prune(
        generated_dir=generated_dir,
        keep_per_site=args.keep_per_site,
        keep_total=args.keep_total,
        apply=apply,
    )

    if args.emit_json:
        print(json.dumps(report.to_json_summary(), indent=2))
        return 0

    print(f"prune_generated_previews: {generated_dir}")
    print(
        f"  dry-run={report.dry_run} keep-per-site={report.keep_per_site} "
        f"keep-total={report.keep_total}"
    )
    print(
        f"  protected site ids ({len(report.protected_site_ids)}): "
        + (", ".join(sorted(report.protected_site_ids)) or "(none)")
    )
    if args.apply and dry_run_env:
        print(
            f"  NOTE: --apply was passed but {DRY_RUN_ENV_VAR}=true forces "
            "dry-run. Unset or set to 'false' to enable deletion."
        )
    print()
    print(_format_report_table(report))
    print()
    print("Decision counts:")
    for decision, count in sorted(_summarise_decisions(report).items()):
        print(f"  {decision:<32} {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
