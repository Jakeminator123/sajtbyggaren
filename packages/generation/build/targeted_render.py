"""Targeted render + version-build derivation (KÖR-7d).

Pure, dependency-light helpers (stdlib + pydantic only, like
``immutable_builds.py``) that turn a KÖR-7c apply into the *targeted* layer the
orchestrator (``scripts/build_site.py:build_targeted_version``) wraps around the
existing project-wide ``build()``:

- **derive the affected routes** from the apply (the route a kor-7b patch named,
  carried on the apply's ``appliedCapabilities[].patchField``),
- **diff which routes actually changed** between the previous active build's
  generated-files snapshot and the new run's snapshot (reasonable verification
  of the affected route), and
- **decide whether the preview should refresh** - only on a shippable build
  (``ok``/``degraded``) *and* an honest visible change (no-op never refreshes).

What this module deliberately does NOT do (kor-7d "Targeted = render, inte
partiell Next build"): it builds no partial Next build system. The deterministic
builder re-renders the whole site from the new Project Input version; because the
render is deterministic, only the affected route's files actually change vs the
previous build, and these helpers verify exactly that. ``npm run build`` /
typecheck / Quality Gate stay project-wide (v1).

Nothing here writes a build, swaps ``current.json`` or touches a run; it only
derives, diffs and decides. The orchestrator owns I/O and reuses the immutable
build + atomic pointer swap from ``immutable_builds.py`` unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime import cycle.
    from ..orchestration.apply import ApplyResult

__all__ = [
    "ROOT_ROUTE_ID",
    "SHARED_ROUTE_ID",
    "TargetedRenderError",
    "TargetedRenderPlan",
    "TargetedRenderResult",
    "affected_routes_from_apply",
    "changed_routes_between_snapshots",
    "decide_preview_refresh",
    "derive_targeted_render_plan",
    "route_id_for_generated_file",
    "route_id_from_patch_field",
]

#: Logical route id for the root page (``app/page.tsx``). The kor-7b planner's
#: default route id is also ``home`` (see patch/planner.py:_DEFAULT_ROUTE_ID), so
#: a patch addressing ``contentBlocks.home.*`` lines up with this file.
ROOT_ROUTE_ID = "home"

#: Bucket for files that are not a single route's page (layout, globals.css,
#: shared components, public assets). A change here can affect several routes, so
#: it is reported separately from a named route rather than mislabelled as one.
SHARED_ROUTE_ID = "(shared)"

# Visible (rendered) output suffixes + roots. Mirrors build_site.py's
# _VISIBLE_EFFECT_* sets so this module's diff agrees with the build's honest
# appliedVisibleEffect signal, without importing the monolith (no cycle).
_VISIBLE_SUFFIXES = frozenset(
    {
        ".css",
        ".gif",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".jsx",
        ".png",
        ".svg",
        ".ts",
        ".tsx",
        ".webp",
    }
)
_VISIBLE_ROOTS = ("app", "public")

_SHIPPABLE_STATUSES = frozenset({"ok", "degraded"})

# ``contentBlocks.<routeId>.<sectionId>.<leaf>`` - the kor-1a addressing contract
# the kor-7b planner emits. The route id is the 2nd dotted segment.
_PATCH_FIELD_RE = re.compile(r"^contentBlocks\.([A-Za-z0-9_-]+)\.")


# ---------------------------------------------------------------------------
# Transient result/plan shapes (never persisted; like PatchPlan / ApplyResult)
# ---------------------------------------------------------------------------


class TargetedRenderError(Exception):
    """Raised when kor-7d must refuse to build (STOP and report).

    The build path may only build a version produced by the internal
    kor-7b(plan) -> kor-7c(apply) chain (kor-7d revalidation assumption). When a
    version with no apply provenance reaches the build path and the caller did
    not explicitly opt in to the planner-rails re-validation fallback, the build
    is refused here instead of rendering un-revalidated input.
    """


class TargetedRenderPlan(BaseModel):
    """The transient render plan derived from an apply, before the build runs."""

    siteId: str
    version: int | None = None
    previousVersion: int | None = None
    affectedRoutes: list[str] = Field(default_factory=list)
    rationale: str = ""


class TargetedRenderResult(BaseModel):
    """The transient outcome of one targeted version-build.

    ``previewShouldRefresh`` is the single honest actuation signal: it is ``True``
    only for a shippable build (``ok``/``degraded``) that produced a real visible
    change. A no-op (``appliedVisibleEffect`` false), a non-shippable build
    (``failed``/``skipped``) or a swallowed apply (skipped/unmapped) all leave it
    ``False`` so the operator preview is never restarted on nothing.
    """

    siteId: str
    version: int | None = None
    previousVersion: int | None = None
    outcome: Literal["applied", "no-op", "skipped", "failed"] = "no-op"
    affectedRoutes: list[str] = Field(default_factory=list)
    changedRoutes: list[str] = Field(default_factory=list)
    buildStatus: str | None = None
    appliedVisibleEffect: bool = False
    previewShouldRefresh: bool = False
    activeBuildId: str | None = None
    runId: str | None = None
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Affected-route derivation (from the kor-7c apply)
# ---------------------------------------------------------------------------


def route_id_from_patch_field(field: str | None) -> str | None:
    """Return the route id a kor-7b patch field addresses, or ``None``.

    ``contentBlocks.<routeId>.<sectionId>.<leaf>`` -> ``<routeId>``. Anything
    that is not a section-addressed contentBlocks field carries no route.
    """
    if not field:
        return None
    match = _PATCH_FIELD_RE.match(field)
    return match.group(1) if match else None


def affected_routes_from_apply(apply_result: ApplyResult) -> list[str]:
    """Return the ordered, de-duplicated route ids a kor-7c apply touched.

    The apply maps a kor-7b ``component_add`` onto ``requestedCapabilities`` but
    keeps the originating patch field on ``appliedCapabilities[].patchField``;
    the route the patch named is recovered from there. An apply with no patch
    field information yields an empty list (the orchestrator then falls back to
    the root route with an explicit note).
    """
    routes: list[str] = []
    for entry in apply_result.appliedCapabilities:
        route_id = route_id_from_patch_field(getattr(entry, "patchField", None))
        if route_id and route_id not in routes:
            routes.append(route_id)
    return routes


def derive_targeted_render_plan(apply_result: ApplyResult) -> TargetedRenderPlan:
    """Build the transient render plan from a kor-7c :class:`ApplyResult`."""
    routes = affected_routes_from_apply(apply_result)
    if routes:
        rationale = (
            "Affected routes derived from the applied patch fields "
            f"({', '.join(routes)})."
        )
    else:
        routes = [ROOT_ROUTE_ID]
        rationale = (
            "No route on the apply's patch fields; defaulting to the root route "
            f"({ROOT_ROUTE_ID})."
        )
    return TargetedRenderPlan(
        siteId=apply_result.siteId,
        version=apply_result.version,
        previousVersion=apply_result.previousVersion,
        affectedRoutes=routes,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Per-route change verification (snapshot diff)
# ---------------------------------------------------------------------------


def route_id_for_generated_file(rel_path: str) -> str:
    """Map a generated-files relative path to a logical route id.

    - ``app/page.tsx`` -> ``home`` (root route).
    - ``app/<segment>/page.tsx`` -> ``<segment>`` (the route's own page).
    - ``app/<a>/<b>/.../page.tsx`` -> ``<a>`` (top segment; nested routes are
      attributed to their top-level path for v1 verification).
    - everything else (``layout.tsx``, ``globals.css``, shared components,
      ``public/**``) -> ``(shared)`` since it is not a single route's page.
    """
    parts = Path(rel_path).as_posix().split("/")
    if not parts or parts[0] not in _VISIBLE_ROOTS:
        return SHARED_ROUTE_ID
    if parts[0] == "app" and parts[-1] == "page.tsx":
        middle = parts[1:-1]
        if not middle:
            return ROOT_ROUTE_ID
        return middle[0]
    return SHARED_ROUTE_ID


def _visible_files(snapshot_dir: Path) -> dict[str, bytes] | None:
    """Return ``{relPath: bytes}`` for visible source/assets in a snapshot.

    Stdlib-only re-implementation of build_site.py's visible-bytes reader so
    this module stays import-cycle-free. Returns ``None`` when the snapshot is
    missing/unreadable so the caller can fall back instead of asserting a diff.
    """
    if not snapshot_dir.is_dir():
        return None
    files: dict[str, bytes] = {}
    try:
        for root_name in _VISIBLE_ROOTS:
            root = snapshot_dir / root_name
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in _VISIBLE_SUFFIXES:
                    continue
                files[path.relative_to(snapshot_dir).as_posix()] = path.read_bytes()
    except OSError:
        return None
    return files


def changed_routes_between_snapshots(
    previous_snapshot: Path | None,
    current_snapshot: Path,
) -> set[str] | None:
    """Return the set of route ids whose visible files differ between snapshots.

    Compares the previous active build's ``generated-files`` snapshot to the new
    run's snapshot. A file present in one and absent in the other, or with
    different bytes, marks its route as changed. Returns ``None`` when either
    snapshot is unreadable (the caller then cannot verify per-route scope).
    """
    current_files = _visible_files(current_snapshot)
    if current_files is None:
        return None
    previous_files = (
        _visible_files(previous_snapshot) if previous_snapshot is not None else None
    )
    if previous_files is None:
        return None
    changed: set[str] = set()
    for rel_path in set(previous_files) | set(current_files):
        if previous_files.get(rel_path) != current_files.get(rel_path):
            changed.add(route_id_for_generated_file(rel_path))
    return changed


def decide_preview_refresh(
    *,
    build_status: str | None,
    applied_visible_effect: bool,
) -> bool:
    """Whether the operator preview should refresh after a targeted build.

    True only for a shippable build (``ok``/``degraded`` - the same gate the
    immutable ``current.json`` swap uses) that produced an honest visible change.
    A no-op or a non-shippable build never refreshes the preview.
    """
    return build_status in _SHIPPABLE_STATUSES and applied_visible_effect
