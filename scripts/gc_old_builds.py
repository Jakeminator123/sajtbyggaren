"""Delayed garbage collection of old immutable builds (B157 level 4, Stage B).

Stage A (``packages/generation/build/immutable_builds.py`` + the builder)
made every build immutable: ``build_site.py`` writes into
``<generated>/<siteId>/builds/<buildId>/`` and publishes the active build via
an atomic ``<generated>/<siteId>/current.json`` pointer. That fixes the
WinError 5 file-lock class but, as the gap-spec notes under "Vad nivå 4 INTE
löser", it leaves old build directories on disk. This script is the delayed
GC that reclaims that space safely.

Retention policy (safety before space - keep a build if ANY holds):

1. it is the active build (``current.json:activeBuildId``) - never deleted;
2. it is younger than ``--max-age-hours`` (default 24h) by directory mtime -
   protects a just-replaced build that a running preview may still serve
   until it is restarted against the new pointer;
3. it is among the ``--keep-latest`` (default 5) most recent builds (mtime
   desc) for that siteId.

Everything else is a GC candidate.

Safety properties:

- Dry-run by default. Deletion only happens with explicit ``--apply``.
- Legacy flat-layout sites (no ``builds/`` directory) are never touched -
  flat-layout cleanup is future work, out of Stage B scope.
- A missing, unreadable or inconsistent ``current.json`` makes the whole
  siteId conservative: nothing is deleted and a warning is recorded. Better
  to leak disk than to delete a build a preview might still be serving.
- Deletes are robust: a build whose native ``.node`` binary is still locked
  by a live preview raises ``PermissionError``/``OSError`` (WinError 5 on
  Windows). That single build is skipped and recorded as ``delete-failed``;
  the GC never crashes and moves on to the next build. GC is idempotent, so a
  later run retries.

Usage::

    python scripts/gc_old_builds.py                      # dry-run, all sites
    python scripts/gc_old_builds.py --apply              # delete
    python scripts/gc_old_builds.py --site-id <id>       # one site only
    python scripts/gc_old_builds.py --keep-latest 3 --max-age-hours 12
    python scripts/gc_old_builds.py --apply --json       # machine-readable

Pointer/build-id logic is reused from
``packages/generation/build/immutable_builds.py`` (never duplicated here).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.build.immutable_builds import (  # noqa: E402
    _BUILD_ID_RE,
    BUILDS_DIRNAME,
    read_active_build_dir,
)

DEFAULT_GENERATED_DIR = REPO_ROOT.parent / "sajtbyggaren-output" / ".generated"
GENERATED_DIR_ENV_VAR = "SAJTBYGGAREN_GENERATED_DIR"

DEFAULT_KEEP_LATEST = 5
DEFAULT_MAX_AGE_HOURS = 24.0

# Per-build decision strings. Locked by tests so a refactor cannot silently
# rename them and break the operator's mental model of what --apply will do.
DECISION_KEEP_ACTIVE = "keep:active"
DECISION_KEEP_RECENT = "keep:within-max-age"
DECISION_KEEP_LATEST = "keep:within-keep-latest"
DECISION_WOULD_DELETE = "would-delete:retention"
DECISION_DELETED = "deleted"
DECISION_DELETE_FAILED = "delete-failed"

# Per-site skip reasons (the whole siteId is left untouched).
SKIP_NO_BUILDS_DIR = "skip-site:no-builds-dir"
SKIP_NO_VALID_POINTER = "skip-site:no-valid-current-json"


def resolve_generated_dir(override: str | Path | None = None) -> Path:
    """Resolve the ``.generated/`` root.

    Mirrors ``scripts/build_site.py:resolve_generated_dir`` and
    ``scripts/prune_generated_previews.py`` so GC targets exactly the tree the
    builder writes to: explicit override > ``SAJTBYGGAREN_GENERATED_DIR`` env >
    the default sibling ``../sajtbyggaren-output/.generated/``.
    """
    candidate: str | Path | None = override
    if candidate is None:
        env_value = os.environ.get(GENERATED_DIR_ENV_VAR)
        candidate = env_value if env_value else DEFAULT_GENERATED_DIR
    resolved = Path(candidate).expanduser()
    if not resolved.is_absolute():
        resolved = (REPO_ROOT / resolved).resolve()
    return resolved


@dataclass
class BuildDecision:
    """One immutable build directory and the retention decision made for it."""

    site_id: str
    build_id: str
    path: Path
    mtime: float
    decision: str
    error: str | None = None


@dataclass
class GcReport:
    """End-of-run summary so the CLI and tests can introspect the outcome."""

    generated_dir: Path
    apply: bool
    keep_latest: int
    max_age_hours: float
    decisions: list[BuildDecision] = field(default_factory=list)
    skipped_sites: list[tuple[str, str]] = field(default_factory=list)

    def _count(self, *decisions: str) -> int:
        return sum(1 for d in self.decisions if d.decision in decisions)

    @property
    def kept_count(self) -> int:
        return self._count(
            DECISION_KEEP_ACTIVE, DECISION_KEEP_RECENT, DECISION_KEEP_LATEST
        )

    @property
    def would_delete_count(self) -> int:
        return self._count(DECISION_WOULD_DELETE)

    @property
    def deleted_count(self) -> int:
        return self._count(DECISION_DELETED)

    @property
    def failed_count(self) -> int:
        return self._count(DECISION_DELETE_FAILED)

    def to_json_summary(self) -> dict:
        return {
            "generatedDir": str(self.generated_dir),
            "apply": self.apply,
            "keepLatest": self.keep_latest,
            "maxAgeHours": self.max_age_hours,
            "skippedSites": [
                {"siteId": site, "reason": reason}
                for site, reason in self.skipped_sites
            ],
            "builds": [
                {
                    "siteId": d.site_id,
                    "buildId": d.build_id,
                    "path": str(d.path),
                    "decision": d.decision,
                    "error": d.error,
                }
                for d in self.decisions
            ],
        }


def _decide(
    path: Path,
    mtime: float,
    *,
    active_id: str,
    now: float,
    age_cutoff_seconds: float,
    keep_latest_paths: set[Path],
) -> str:
    """Return the retention decision for one build (keep-reasons OR'd)."""
    if path.name == active_id:
        return DECISION_KEEP_ACTIVE
    if (now - mtime) < age_cutoff_seconds:
        return DECISION_KEEP_RECENT
    if path in keep_latest_paths:
        return DECISION_KEEP_LATEST
    return DECISION_WOULD_DELETE


def run_gc(
    generated_dir: Path,
    *,
    apply: bool = False,
    keep_latest: int = DEFAULT_KEEP_LATEST,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    site_id: str | None = None,
    now: float | None = None,
) -> GcReport:
    """Compute the GC plan and, when ``apply`` is true, perform the deletions.

    Returns a ``GcReport``. With ``apply=False`` (the default) no directory is
    removed and deletion candidates carry the ``would-delete:retention``
    decision. With ``apply=True`` each candidate is ``shutil.rmtree``'d; on
    success the decision becomes ``deleted``, and on ``OSError`` (a locked
    build) it becomes ``delete-failed`` with the error captured - the run
    continues regardless.
    """
    if keep_latest < 0:
        raise SystemExit("keep-latest must be non-negative")
    if max_age_hours < 0:
        raise SystemExit("max-age-hours must be non-negative")

    now = time.time() if now is None else now
    age_cutoff_seconds = max_age_hours * 3600.0
    report = GcReport(
        generated_dir=generated_dir,
        apply=apply,
        keep_latest=keep_latest,
        max_age_hours=max_age_hours,
    )
    if not generated_dir.is_dir():
        return report

    for site_dir in sorted(p for p in generated_dir.iterdir() if p.is_dir()):
        site = site_dir.name
        if site_id is not None and site != site_id:
            continue

        builds_dir = site_dir / BUILDS_DIRNAME
        if not builds_dir.is_dir():
            # Legacy flat layout (or a brand-new site without builds/). Never
            # touched in Stage B - flat-layout cleanup is future work.
            report.skipped_sites.append((site, SKIP_NO_BUILDS_DIR))
            continue

        active_dir = read_active_build_dir(site_dir)
        if active_dir is None:
            # Missing/corrupt/inconsistent current.json -> conservative: delete
            # nothing for this siteId. Better to leak disk than delete a build a
            # preview might still serve.
            report.skipped_sites.append((site, SKIP_NO_VALID_POINTER))
            continue
        active_id = active_dir.name

        builds: list[tuple[Path, float]] = []
        for entry in builds_dir.iterdir():
            if not entry.is_dir() or not _BUILD_ID_RE.match(entry.name):
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                # An unreadable build dir cannot be ranked or safely removed;
                # leave it for a later run rather than guess.
                continue
            builds.append((entry, mtime))

        builds.sort(key=lambda item: item[1], reverse=True)
        keep_latest_paths = {path for path, _ in builds[:keep_latest]}

        for path, mtime in builds:
            decision = _decide(
                path,
                mtime,
                active_id=active_id,
                now=now,
                age_cutoff_seconds=age_cutoff_seconds,
                keep_latest_paths=keep_latest_paths,
            )
            build_decision = BuildDecision(
                site_id=site,
                build_id=path.name,
                path=path,
                mtime=mtime,
                decision=decision,
            )
            if decision == DECISION_WOULD_DELETE and apply:
                try:
                    shutil.rmtree(path)
                    build_decision.decision = DECISION_DELETED
                except OSError as exc:
                    # Windows: a live preview holding a .node binary makes
                    # rmtree raise PermissionError [WinError 5]. Skip this one
                    # build, record it, and keep going. Never crash the GC.
                    build_decision.decision = DECISION_DELETE_FAILED
                    build_decision.error = f"{type(exc).__name__}: {exc}"
            report.decisions.append(build_decision)

    return report


def _print_report(report: GcReport) -> None:
    mode = "apply" if report.apply else "dry-run"
    print(f"gc_old_builds: {report.generated_dir}")
    print(
        f"  mode={mode} keep-latest={report.keep_latest} "
        f"max-age-hours={report.max_age_hours}"
    )

    if report.skipped_sites:
        print("Skipped sites (left untouched):")
        for site, reason in report.skipped_sites:
            print(f"  {site} - {reason}")

    if report.decisions:
        print("Builds:")
        for d in sorted(report.decisions, key=lambda x: (x.site_id, x.build_id)):
            suffix = f" (error: {d.error})" if d.error else ""
            print(f"  {d.decision:<24} {d.site_id}/{d.build_id}{suffix}")
    else:
        print("Builds: (none under any builds/ directory)")

    verb = "deleted" if report.apply else "would-delete"
    delete_n = report.deleted_count if report.apply else report.would_delete_count
    print(
        f"Summary: kept={report.kept_count} {verb}={delete_n} "
        f"delete-failed={report.failed_count} "
        f"skipped-sites={len(report.skipped_sites)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Garbage-collect old immutable builds under "
            "<generated>/<siteId>/builds/. Dry-run by default; pass --apply "
            "to delete. Never removes the active build, builds younger than "
            "--max-age-hours, or the --keep-latest most recent builds."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete GC candidates. Without this flag the script "
        "only prints the plan (dry-run).",
    )
    parser.add_argument(
        "--site-id",
        default=None,
        help="Only GC this siteId. Without it, every siteId is processed.",
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
        "--keep-latest",
        type=int,
        default=DEFAULT_KEEP_LATEST,
        help=f"Keep the N most recent builds per siteId (default {DEFAULT_KEEP_LATEST}).",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=DEFAULT_MAX_AGE_HOURS,
        help=(
            "Always keep builds younger than this many hours "
            f"(default {DEFAULT_MAX_AGE_HOURS})."
        ),
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit a JSON summary instead of the human-readable report.",
    )
    args = parser.parse_args(argv)

    generated_dir = resolve_generated_dir(args.generated_dir)
    report = run_gc(
        generated_dir,
        apply=args.apply,
        keep_latest=args.keep_latest,
        max_age_hours=args.max_age_hours,
        site_id=args.site_id,
    )

    if args.emit_json:
        print(json.dumps(report.to_json_summary(), indent=2))
    else:
        _print_report(report)

    # GC is best-effort: a locked build (delete-failed) is not a CLI failure.
    # Exit 0 unless argparse already rejected the arguments.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
