"""Mechanical fix: ensure-default-export.

Registry entry: ``governance/policies/fix-registry.v1.json``,
``mechanicalFixes`` array, ``id="ensure-default-export"``,
``stage="post-codegen"``, ``priority=20``, ``idempotent=true``,
``onFailure="abort-pipeline"``.

What it does
------------
Quality Gate ``route-scan`` produces findings of two shapes:

1. ``"<route> -> <relpath> (saknas)"`` -- the page file does not exist.
   This fix does NOT handle that case; creating a page from scratch
   would be a "magic" fix that invents structure not driven by the
   plan. The registry's ``route-recovery`` LLM fix is what eventually
   creates missing pages (Sprint 5+).

2. ``"<route> -> <relpath> (saknar export default)"`` -- the page file
   exists but has no ``export default`` statement. This fix appends
   ``export default <Symbol>;\\n`` to the file when it can find an
   unambiguous exportable symbol (a top-level ``function Page``,
   ``const Page = ...``, etc.) that matches the file's expected
   component name. If no such symbol can be found, the fix returns a
   ``RepairFix(success=False, ...)`` entry without mutating the file --
   the registry's ``onFailure="abort-pipeline"`` is interpreted as
   "this fix cannot proceed; the orchestrator will surface the failure
   and stop trying further fixes on this file".

Determinism guarantees
----------------------
- Idempotent: running the fix on a file that already has
  ``export default`` is a no-op (route-scan would not have flagged
  the file).
- Safe: the fix never rewrites or deletes existing content. It only
  appends a single line at the end of the file.
- Bounded: the fix only acts on findings explicitly tagged with the
  ``(saknar export default)`` marker that ``packages/generation/
  quality_gate/checks.py:run_route_scan_check`` emits. Other findings
  are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from packages.generation.quality_gate import QualityResult

from ..models import RepairFix

# Marker that route-scan emits when a page exists but has no export
# default. Must match scripts.build_site / quality_gate.checks output
# verbatim. Tests in tests/test_repair_fixes.py lock the marker.
_ROUTE_NO_EXPORT_MARKER = "(saknar export default)"

# Parse "<route> -> <relpath> (saknar export default)". The relpath
# segment can contain forward slashes (POSIX on data/runs snapshots)
# but never spaces in our scaffolds. Captured group 1 is the relative
# path; we resolve it against target_dir before opening.
_FINDING_RE = re.compile(
    r"->\s+(?P<relpath>\S+\.tsx?)\s+\(saknar export default\)"
)

# Detect a top-level exportable symbol that we can default-export.
# Matches:
#   function Foo(           ->  "Foo"
#   async function Foo(     ->  "Foo"
#   const Foo = ...         ->  "Foo"
#   let Foo = ...           ->  "Foo"
#   var Foo = ...           ->  "Foo"
#   export function Foo(    ->  "Foo"
#   export const Foo = ...  ->  "Foo"
# We require the symbol name to start with an uppercase letter (React
# component convention). Lower-case symbols are ignored to avoid
# default-exporting helpers like ``cn`` or ``slugify`` that happen to
# live in the same file.
_EXPORTABLE_SYMBOL_RE = re.compile(
    r"^(?:export\s+)?(?:async\s+)?(?:function|const|let|var)\s+([A-Z]\w*)",
    flags=re.MULTILINE,
)

# Next.js App Router convention: the route component is the symbol
# named ``Page`` in app/<route>/page.tsx. The fix prefers it over any
# other component-cased symbol so a file that declares both ``Header``
# and ``Page`` default-exports ``Page`` (the canonical route entry),
# not the first declaration. Sprint 3B v1.1 fix - see ADR 0016.
_PAGE_SYMBOL = "Page"

# Mirrors checks._DEFAULT_EXPORT_RE so the fix never appends a default
# export to a file that already has one (idempotency safety net even
# though route-scan would not flag such a file).
_DEFAULT_EXPORT_RE = re.compile(
    r"export\s+default\s+(?:async\s+)?(?:function|class|const|let|var|\w+)"
    r"|export\s*\{\s*default\b",
    flags=re.MULTILINE,
)


@dataclass(frozen=True)
class MechanicalFixSpec:
    """Static descriptor of a mechanical fix.

    Pairs the ``governance/policies/fix-registry.v1.json`` entry with
    the Python callable that implements the body. Tests assert that
    every spec id matches a registry entry and vice versa.
    """

    fix_id: str
    stage: str
    priority: int
    idempotent: bool
    on_failure: str
    description: str


ENSURE_DEFAULT_EXPORT_SPEC = MechanicalFixSpec(
    fix_id="ensure-default-export",
    stage="post-codegen",
    priority=20,
    idempotent=True,
    on_failure="abort-pipeline",
    description=(
        "Append `export default <Symbol>;` to a page.tsx that already "
        "defines an unambiguous top-level component but is missing the "
        "default export."
    ),
)


def _candidate_paths(quality_result: QualityResult) -> list[str]:
    """Extract relative paths from route-scan findings tagged
    ``(saknar export default)``. Paths missing files (``(saknas)``)
    are intentionally skipped - this fix never invents structure.
    """
    paths: list[str] = []
    for check in quality_result.checks:
        if check.name != "route-scan":
            continue
        if check.status != "failed":
            continue
        for finding in check.findings:
            if _ROUTE_NO_EXPORT_MARKER not in finding:
                continue
            match = _FINDING_RE.search(finding)
            if not match:
                continue
            paths.append(match.group("relpath"))
    return paths


def _pick_exportable_symbol(text: str) -> str | None:
    """Choose which component-cased symbol to default-export, if any.

    Sprint 3B v1.1 heuristic (ADR 0016, replaces v1.0 first-match):

    1. If a top-level ``Page`` symbol exists, return ``"Page"``. That
       is the Next.js App Router convention for the route entry of
       ``app/<route>/page.tsx``; if the file declared it, it is by
       far the most likely intended default export.
    2. Else if exactly ONE component-cased symbol exists, return it.
       That covers single-component files (``Hero`` only, etc.).
    3. Else return None. Multiple candidates without ``Page`` are
       ambiguous; default-exporting an arbitrary one risks rendering
       the wrong component (the v1.0 first-match heuristic could
       export a header sub-component instead of the route page).
       Better to surface ``no exportable symbol`` and let the
       operator (or a Sprint 5+ LLM-fix) pick.
    """
    matches = _EXPORTABLE_SYMBOL_RE.findall(text)
    if not matches:
        return None

    if _PAGE_SYMBOL in matches:
        return _PAGE_SYMBOL

    unique = list(dict.fromkeys(matches))
    if len(unique) == 1:
        return unique[0]

    return None


def apply_ensure_default_export(
    target_dir: Path,
    quality_result: QualityResult,
) -> list[RepairFix]:
    """Walk route-scan findings and append ``export default`` where safe.

    Returns one ``RepairFix`` per attempted finding. ``success=True``
    means the file was mutated; ``success=False`` means the fix could
    not proceed (no exportable symbol, file unreadable, etc.) and the
    file was NOT mutated.

    The list is empty when no route-scan findings match the
    ``(saknar export default)`` marker. That is how the orchestrator
    distinguishes "fix did not apply" from "fix tried and failed".
    """
    fixes: list[RepairFix] = []
    seen_targets: set[str] = set()

    for raw_relpath in _candidate_paths(quality_result):
        # Normalise to POSIX separators so RepairFix.target is
        # platform-neutral. ``Path(target_dir / posix)`` still resolves
        # correctly on Windows because pathlib accepts forward
        # slashes there. The Quality Gate may emit ``app\foo\page.tsx``
        # on Windows but downstream consumers (Backoffice, eval batch,
        # repair-result.json) expect a single canonical separator.
        relpath = raw_relpath.replace("\\", "/")
        if relpath in seen_targets:
            continue
        seen_targets.add(relpath)

        full_path = target_dir / relpath
        try:
            text = full_path.read_text(encoding="utf-8")
        except OSError as exc:
            fixes.append(
                RepairFix(
                    kind="mechanical",
                    name="ensure-default-export",
                    target=relpath,
                    detail=f"Could not read file: {type(exc).__name__}: {exc}",
                    success=False,
                )
            )
            continue

        if _DEFAULT_EXPORT_RE.search(text):
            # Idempotency safety net: if the gate flagged this file
            # but a default export already exists, do not append a
            # second one. The gate ran against an older snapshot or
            # the file was edited concurrently.
            fixes.append(
                RepairFix(
                    kind="mechanical",
                    name="ensure-default-export",
                    target=relpath,
                    detail=(
                        "Default export already present; "
                        "no append needed (idempotency)."
                    ),
                    success=True,
                )
            )
            continue

        symbol = _pick_exportable_symbol(text)
        if symbol is None:
            fixes.append(
                RepairFix(
                    kind="mechanical",
                    name="ensure-default-export",
                    target=relpath,
                    detail=(
                        "No exportable component-cased symbol found; "
                        "skipping per fix-registry onFailure="
                        "abort-pipeline (do not invent a stub)."
                    ),
                    success=False,
                )
            )
            continue

        new_text = text.rstrip() + f"\n\nexport default {symbol};\n"
        try:
            full_path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            fixes.append(
                RepairFix(
                    kind="mechanical",
                    name="ensure-default-export",
                    target=relpath,
                    detail=f"Could not write file: {type(exc).__name__}: {exc}",
                    success=False,
                )
            )
            continue

        fixes.append(
            RepairFix(
                kind="mechanical",
                name="ensure-default-export",
                target=relpath,
                detail=f"Appended `export default {symbol};`.",
                success=True,
            )
        )

    return fixes
