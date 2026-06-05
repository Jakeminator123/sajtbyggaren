"""Read-only Context Assembler (KÖR-7a).

One function per ``contextLevel`` the deterministic router (KÖR-6a) can set.
Each returns *exactly* what its level requires - nothing more (kor-7a step
1) - inside a hard character budget (budgets.py), with anti-bloat
suppression of files the previous version already showed.

Hard guarantees of this slice (kor-7a "Definition of done"):
- **Read-only.** Nothing here writes a file, creates a directory, creates a
  run, starts a build, or starts a preview/adapter. ``preview_dom`` only
  *reads* an already-captured snapshot; it never boots a PreviewRuntime.
- **external_reference is gated.** It performs no network I/O itself: it
  requires an explicit permission grant *and* a caller-supplied fetch tool,
  and makes no call without the grant.
- **Budgeted.** ``AssembledContext.charCount <= charBudget`` always holds.

The result is returned to the caller exactly like the router's decision -
it is never persisted as a new canonical artefakt.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .budgets import (
    fill_list_within_budget,
    fill_mapping_within_budget,
    resolve_budget,
    serialized_len,
    set_blob_within_budget,
)
from .models import AssembledContext, ContextLevel, PriorContext, ReferencePermission
from .sources import (
    ContextPaths,
    list_generated_files,
    read_capability_map,
    read_dossier_manifests,
    read_generated_file,
    read_meta,
    read_run_artifact,
    read_sections,
)

__all__ = [
    "assemble_artifacts",
    "assemble_artifacts_plus_sections",
    "assemble_component_registry",
    "assemble_context",
    "assemble_external_reference",
    "assemble_manifest",
    "assemble_none",
    "assemble_preview_dom",
    "assemble_project_dna",
    "assemble_selected_files",
]

FetchReference = Callable[[str], str]

# Compact projection of a dossier manifest for the component_registry level:
# enough to know what is *available* without the heavy instructions/file lists.
_DOSSIER_FIELDS = (
    "id",
    "label",
    "capability",
    "class",
    "codeFidelity",
    "complexity",
    "summary",
    "exposes",
    "enabled",
    "defaultForCapability",
)

_ARTIFACT_FILES: tuple[tuple[str, str], ...] = (
    ("siteBrief", "site-brief.json"),
    ("sitePlan", "site-plan.json"),
    ("generationPackage", "generation-package.json"),
)


def _finalize(ctx: AssembledContext, budget: int) -> AssembledContext:
    """Stamp the budget and the honest payload char count onto the envelope.

    Safety net for the budget invariant: if even the structural scaffolding
    of the payload (empty container/keys) exceeds the budget, no meaningful
    content fits, so the payload is emptied. This keeps
    ``charCount <= charBudget`` airtight for any budget, including 0.
    """
    ctx.charBudget = budget
    ctx.charCount = serialized_len(ctx.payload)
    if ctx.charCount > budget:
        ctx.payload = {}
        ctx.truncated = True
        ctx.charCount = serialized_len(ctx.payload)
    return ctx


def _paths(paths: ContextPaths | None) -> ContextPaths:
    return paths if paths is not None else ContextPaths()


# ---------------------------------------------------------------------------
# none
# ---------------------------------------------------------------------------


def assemble_none() -> AssembledContext:
    """The ``none`` level: no context at all (e.g. a pure ``answer_only``)."""
    return _finalize(AssembledContext(contextLevel="none"), resolve_budget("none"))


# ---------------------------------------------------------------------------
# project_dna  (data/prompt-inputs/<siteId>.meta.json)
# ---------------------------------------------------------------------------


def assemble_project_dna(
    site_id: str,
    *,
    version: int | None = None,
    paths: ContextPaths | None = None,
    budgets: dict[str, int] | None = None,
) -> AssembledContext:
    """Project DNA identity: siteId/projectId/version, scaffold/variant (02 §4).

    Reads only the prompt-inputs sidecar and returns the identity fields plus
    the ``projectDna`` snapshot the sidecar carries - the DNA this level is
    named for, and nothing else.
    """
    budget = resolve_budget("project_dna", budgets)
    ctx = AssembledContext(contextLevel="project_dna", siteId=site_id)
    meta = read_meta(_paths(paths), site_id, version=version)
    if meta is None:
        ctx.notes.append(
            f"No prompt-inputs sidecar for siteId={site_id!r}"
            + (f" v{version}" if version is not None else "")
            + " - nothing read, nothing created."
        )
        return _finalize(ctx, budget)

    entries: list[tuple[str, Any]] = [
        ("siteId", meta.get("siteId") or site_id),
        ("projectId", meta.get("projectId")),
        ("version", meta.get("version")),
        ("scaffoldId", meta.get("scaffoldId")),
        ("variantId", meta.get("variantId")),
        ("projectDna", meta.get("projectDna")),
    ]
    entries = [(k, v) for k, v in entries if v is not None]
    ctx.dropped = fill_mapping_within_budget(ctx.payload, entries, budget)
    ctx.truncated = bool(ctx.dropped)
    return _finalize(ctx, budget)


# ---------------------------------------------------------------------------
# artifacts  (data/runs/<runId>/{site-brief,site-plan,generation-package}.json)
# ---------------------------------------------------------------------------


def _collect_artifacts(
    paths: ContextPaths,
    run_id: str,
) -> tuple[list[tuple[str, Any]], list[str]]:
    """Return (present (key,value) artefakts in doc order, missing filenames)."""
    present: list[tuple[str, Any]] = []
    missing: list[str] = []
    for key, filename in _ARTIFACT_FILES:
        data = read_run_artifact(paths, run_id, filename)
        if data is None:
            missing.append(filename)
        else:
            present.append((key, data))
    return present, missing


def _pack_artifacts(ctx: AssembledContext, present: list[tuple[str, Any]], budget: int) -> None:
    """Pack whole artefakts in priority order; clip the top one if none fit."""
    ctx.dropped = fill_mapping_within_budget(ctx.payload, present, budget)
    ctx.truncated = bool(ctx.dropped)
    if not ctx.payload and present:
        # Even the highest-priority artefakt does not fit as a dict: include a
        # clipped JSON string of it so the level is not silently empty.
        top_key, top_val = present[0]
        blob = json.dumps(top_val, ensure_ascii=False, sort_keys=True)
        set_blob_within_budget(ctx.payload, f"{top_key}Json", blob, budget)
        ctx.truncated = True


def assemble_artifacts(
    run_id: str,
    *,
    paths: ContextPaths | None = None,
    budgets: dict[str, int] | None = None,
) -> AssembledContext:
    """The three Engine Run artefakts for a run: brief, plan, generation package."""
    budget = resolve_budget("artifacts", budgets)
    resolved = _paths(paths)
    ctx = AssembledContext(contextLevel="artifacts", runId=run_id)
    present, missing = _collect_artifacts(resolved, run_id)
    if missing:
        ctx.notes.append("Missing artefakts (not created): " + ", ".join(missing))
    if not present:
        ctx.notes.append(f"No run artefakts under runId={run_id!r}.")
        return _finalize(ctx, budget)
    _pack_artifacts(ctx, present, budget)
    return _finalize(ctx, budget)


# ---------------------------------------------------------------------------
# artifacts_plus_sections  (+ Site Plan routePlan + scaffold sections.json)
# ---------------------------------------------------------------------------


def _derive_route_sections(
    route_plan: Any,
    sections_map: dict[str, Any] | None,
) -> dict[str, list[str]]:
    """routeId -> ordered [sectionId,...] for the planned routes.

    This is the projection the router (kor-6a) consumes as
    ``RouterContext.routeSections`` to resolve a ``sectionOrdinal`` ("andra
    sektionen") to a concrete ``sectionId`` - so the assembler hands the
    router exactly the map it needs, without the router touching disk.
    """
    out: dict[str, list[str]] = {}
    if not isinstance(sections_map, dict) or not isinstance(route_plan, list):
        return out
    for route in route_plan:
        if not isinstance(route, dict):
            continue
        route_id = route.get("id")
        spec = sections_map.get(route_id) if isinstance(route_id, str) else None
        if not isinstance(spec, dict):
            continue
        ordered = list(spec.get("requiredSections", [])) + list(spec.get("optionalSections", []))
        out[route_id] = ordered
    return out


def assemble_artifacts_plus_sections(
    run_id: str,
    *,
    scaffold_id: str | None = None,
    paths: ContextPaths | None = None,
    budgets: dict[str, int] | None = None,
) -> AssembledContext:
    """Artefakts plus the scaffold's route/section map (02 §4).

    Priority under a tight budget favours the pieces that make this level
    distinct from ``artifacts`` - the plan, the section map and the derived
    ordinal->sectionId projection - because that is what a placement/edit
    decision needs; the brief is the first to drop.
    """
    budget = resolve_budget("artifacts_plus_sections", budgets)
    resolved = _paths(paths)
    ctx = AssembledContext(contextLevel="artifacts_plus_sections", runId=run_id)

    by_key = {key: data for key, data in _collect_artifacts(resolved, run_id)[0]}
    site_plan = by_key.get("sitePlan")

    effective_scaffold = scaffold_id
    if effective_scaffold is None and isinstance(site_plan, dict):
        effective_scaffold = site_plan.get("scaffoldId")

    sections_map: dict[str, Any] | None = None
    if effective_scaffold:
        sections_map = read_sections(resolved, effective_scaffold)
        if sections_map is None:
            ctx.notes.append(f"No sections.json for scaffoldId={effective_scaffold!r}.")
    else:
        ctx.notes.append("No scaffoldId available - section map omitted.")

    route_plan = site_plan.get("routePlan") if isinstance(site_plan, dict) else None
    route_sections = _derive_route_sections(route_plan, sections_map)

    # Priority order: the level's distinguishing context first, brief last.
    entries: list[tuple[str, Any]] = []
    if site_plan is not None:
        entries.append(("sitePlan", site_plan))
    if sections_map is not None:
        entries.append(("sections", sections_map))
    if route_sections:
        entries.append(("routeSections", route_sections))
    if "generationPackage" in by_key:
        entries.append(("generationPackage", by_key["generationPackage"]))
    if "siteBrief" in by_key:
        entries.append(("siteBrief", by_key["siteBrief"]))

    if not entries:
        ctx.notes.append(f"No artefakts or sections available for runId={run_id!r}.")
        return _finalize(ctx, budget)

    ctx.dropped = fill_mapping_within_budget(ctx.payload, entries, budget)
    ctx.truncated = bool(ctx.dropped)
    return _finalize(ctx, budget)


# ---------------------------------------------------------------------------
# component_registry  (capability-map.v1.json + dossier manifests)
# ---------------------------------------------------------------------------


def _compact_dossier(manifest: dict[str, Any]) -> dict[str, Any]:
    return {field: manifest[field] for field in _DOSSIER_FIELDS if field in manifest}


def assemble_component_registry(
    *,
    paths: ContextPaths | None = None,
    budgets: dict[str, int] | None = None,
) -> AssembledContext:
    """Available capabilities + dossiers - what the user can choose from (02 §4).

    Used by ``component_discovery`` ("vilka klockor finns?"): it lists the
    options from the capability map and the dossier manifests, trimmed to the
    "what is available" fields. No build is implied - this is read-only.
    """
    budget = resolve_budget("component_registry", budgets)
    resolved = _paths(paths)
    ctx = AssembledContext(contextLevel="component_registry")

    cap_map = read_capability_map(resolved)
    capabilities = cap_map.get("capabilities", {}) if isinstance(cap_map, dict) else {}
    cap_items: list[dict[str, Any]] = []
    for slug, spec in sorted(capabilities.items()):
        if not isinstance(spec, dict):
            continue
        item: dict[str, Any] = {"capability": slug, "dossiers": spec.get("dossiers", [])}
        if spec.get("default") is not None:
            item["default"] = spec["default"]
        cap_items.append(item)

    dossier_items = [_compact_dossier(m) for m in read_dossier_manifests(resolved)]

    dropped_caps = fill_list_within_budget(ctx.payload, "capabilities", cap_items, budget)
    dropped_dossiers = fill_list_within_budget(ctx.payload, "dossiers", dossier_items, budget)
    if dropped_caps:
        ctx.dropped.append(f"capabilities:{len(dropped_caps)}")
    if dropped_dossiers:
        ctx.dropped.append(f"dossiers:{len(dropped_dossiers)}")
    ctx.truncated = bool(ctx.dropped)
    if not cap_items and not dossier_items:
        ctx.notes.append("Capability map and dossiers were both empty/unavailable.")
    return _finalize(ctx, budget)


# ---------------------------------------------------------------------------
# manifest  (generated-files/ listing)
# ---------------------------------------------------------------------------


def assemble_manifest(
    run_id: str,
    *,
    prior: PriorContext | None = None,
    paths: ContextPaths | None = None,
    budgets: dict[str, int] | None = None,
) -> AssembledContext:
    """A file listing of ``generated-files/`` (path + byte size), no content.

    Anti-bloat: any path the previous version already knew (``prior.knownFiles``)
    is suppressed from the listing - the model has already seen that the file
    exists (02 §4).
    """
    budget = resolve_budget("manifest", budgets)
    resolved = _paths(paths)
    ctx = AssembledContext(contextLevel="manifest", runId=run_id)
    known = prior.knownFiles if prior else {}

    files = list_generated_files(resolved, run_id)
    if not files:
        ctx.notes.append(f"No generated-files/ under runId={run_id!r} (nothing created).")
        ctx.payload["files"] = []
        return _finalize(ctx, budget)

    entries: list[dict[str, Any]] = []
    for path, size in files:
        if path in known:
            ctx.suppressed.append(path)
            continue
        entries.append({"path": path, "bytes": size})

    dropped = fill_list_within_budget(ctx.payload, "files", entries, budget)
    if dropped:
        ctx.dropped.append(f"files:{len(dropped)}")
    ctx.truncated = bool(dropped)
    return _finalize(ctx, budget)


# ---------------------------------------------------------------------------
# selected_files  (generated-files/<path> content)
# ---------------------------------------------------------------------------


def _fit_last_file(ctx: AssembledContext, entry: dict[str, Any], content: str, budget: int) -> bool:
    """Fit the just-appended file entry's content into the remaining budget.

    Returns whether the entry fits at all (its content may be clipped, even to
    empty). The binary search measures the *whole* payload so earlier files
    are accounted for.
    """
    entry["content"] = content
    entry["truncated"] = False
    if serialized_len(ctx.payload) <= budget:
        return True

    entry["truncated"] = True
    lo, hi = 0, len(content)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        entry["content"] = content[:mid] + "…[truncated]"
        if serialized_len(ctx.payload) <= budget:
            lo = mid
        else:
            hi = mid - 1
    entry["content"] = (content[:lo] + "…[truncated]") if lo > 0 else ""
    return serialized_len(ctx.payload) <= budget


def assemble_selected_files(
    run_id: str,
    rel_paths: list[str],
    *,
    prior: PriorContext | None = None,
    paths: ContextPaths | None = None,
    budgets: dict[str, int] | None = None,
) -> AssembledContext:
    """Content of selected ``generated-files/<path>`` files.

    Anti-bloat: a file is suppressed only when its path *and* content digest
    match ``prior.knownFiles`` (unchanged since the previous version). A
    changed file at a known path is still returned, because its content is
    new (02 §4). The path is sandbox-confined to ``generated-files/``.
    """
    budget = resolve_budget("selected_files", budgets)
    resolved = _paths(paths)
    ctx = AssembledContext(contextLevel="selected_files", runId=run_id)
    known = prior.knownFiles if prior else {}
    ctx.payload["files"] = []

    seen: set[str] = set()
    for rel_path in rel_paths:
        if rel_path in seen:
            continue
        seen.add(rel_path)
        result = read_generated_file(resolved, run_id, rel_path)
        if result is None:
            ctx.notes.append(f"Not found or outside sandbox: {rel_path}")
            continue
        size, digest, content = result
        if rel_path in known and known[rel_path] and known[rel_path] == digest:
            ctx.suppressed.append(rel_path)
            continue
        entry: dict[str, Any] = {
            "path": rel_path,
            "bytes": size,
            "sha256": digest,
            "content": "",
            "truncated": False,
        }
        ctx.payload["files"].append(entry)
        if not _fit_last_file(ctx, entry, content, budget):
            ctx.payload["files"].pop()
            ctx.dropped.append(rel_path)

    ctx.truncated = bool(ctx.dropped) or any(
        f.get("truncated") for f in ctx.payload["files"]
    )
    return _finalize(ctx, budget)


# ---------------------------------------------------------------------------
# preview_dom  (read an already-captured snapshot; never starts a preview)
# ---------------------------------------------------------------------------


def assemble_preview_dom(
    *,
    route: str | None = None,
    snapshot: str | None = None,
    snapshot_path: str | None = None,
    budgets: dict[str, int] | None = None,
) -> AssembledContext:
    """Read a preview DOM snapshot - the assembler never starts a preview.

    The snapshot must be supplied (already captured) either inline via
    ``snapshot`` or as a path to a previously-written file via
    ``snapshot_path``. No PreviewRuntime/adapter is touched and no preview is
    booted (kor-7a read-only + 03 §4 "preview startas inte i onödan").
    """
    budget = resolve_budget("preview_dom", budgets)
    ctx = AssembledContext(contextLevel="preview_dom")
    if route:
        ctx.payload["route"] = route

    text: str | None = None
    if snapshot is not None:
        text = snapshot
    elif snapshot_path:
        path = Path(snapshot_path)
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
        else:
            ctx.notes.append(f"Preview snapshot file not found: {snapshot_path}")
    else:
        ctx.notes.append(
            "No preview snapshot supplied; the assembler does not start a preview."
        )

    if text is not None:
        ctx.truncated = set_blob_within_budget(ctx.payload, "snapshot", text, budget)
    return _finalize(ctx, budget)


# ---------------------------------------------------------------------------
# external_reference  (tool call, behind a permission gate)
# ---------------------------------------------------------------------------


def assemble_external_reference(
    url: str,
    *,
    permission: ReferencePermission | None = None,
    fetch: FetchReference | None = None,
    budgets: dict[str, int] | None = None,
) -> AssembledContext:
    """Fetch an external reference - behind a permission gate (02 §4, kor-7a step 3).

    The assembler performs **no** network I/O of its own. It requires an
    explicit ``permission.allow=True`` grant *and* a caller-supplied ``fetch``
    tool; without the grant it returns an empty, gated result and never calls
    the fetcher. The risk note mirrors the router: never copy the exact
    design or code.
    """
    budget = resolve_budget("external_reference", budgets)
    ctx = AssembledContext(contextLevel="external_reference", permissionRequired=True)
    ctx.payload["url"] = url

    if permission is None or not permission.allow:
        ctx.permissionGranted = False
        reason = f" ({permission.reason})" if permission and permission.reason else ""
        ctx.notes.append(
            "External reference denied: permission gate not granted" + reason + "."
            " No network call made."
        )
        return _finalize(ctx, budget)

    ctx.permissionGranted = True
    if fetch is None:
        ctx.notes.append(
            "Permission granted but no fetch tool supplied; the assembler performs"
            " no network I/O itself."
        )
        return _finalize(ctx, budget)

    fetched = fetch(url) or ""
    ctx.truncated = set_blob_within_budget(ctx.payload, "content", fetched, budget)
    ctx.notes.append(
        "External reference fetched via the supplied tool; analyse it and propose an"
        " own variant - do not copy the exact design or code."
    )
    return _finalize(ctx, budget)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def assemble_context(
    level: ContextLevel,
    *,
    site_id: str | None = None,
    run_id: str | None = None,
    scaffold_id: str | None = None,
    version: int | None = None,
    rel_paths: list[str] | None = None,
    prior: PriorContext | None = None,
    permission: ReferencePermission | None = None,
    fetch: FetchReference | None = None,
    url: str | None = None,
    route: str | None = None,
    snapshot: str | None = None,
    snapshot_path: str | None = None,
    paths: ContextPaths | None = None,
    budgets: dict[str, int] | None = None,
) -> AssembledContext:
    """Assemble the context for the level the router (kor-6a) chose.

    A convenience front door: it routes ``level`` to the matching per-level
    function with the identifiers the caller has. When a required identifier
    is missing it returns an empty, budgeted result with an explanatory note
    rather than raising - the router turn must never crash on a missing id.
    """
    if level == "none":
        return assemble_none()

    if level == "project_dna":
        if not site_id:
            return _missing(level, "site_id", budgets)
        return assemble_project_dna(site_id, version=version, paths=paths, budgets=budgets)

    if level == "artifacts":
        if not run_id:
            return _missing(level, "run_id", budgets)
        return assemble_artifacts(run_id, paths=paths, budgets=budgets)

    if level == "artifacts_plus_sections":
        if not run_id:
            return _missing(level, "run_id", budgets)
        return assemble_artifacts_plus_sections(
            run_id, scaffold_id=scaffold_id, paths=paths, budgets=budgets
        )

    if level == "component_registry":
        return assemble_component_registry(paths=paths, budgets=budgets)

    if level == "manifest":
        if not run_id:
            return _missing(level, "run_id", budgets)
        return assemble_manifest(run_id, prior=prior, paths=paths, budgets=budgets)

    if level == "selected_files":
        if not run_id:
            return _missing(level, "run_id", budgets)
        return assemble_selected_files(
            run_id, rel_paths or [], prior=prior, paths=paths, budgets=budgets
        )

    if level == "preview_dom":
        return assemble_preview_dom(
            route=route, snapshot=snapshot, snapshot_path=snapshot_path, budgets=budgets
        )

    if level == "external_reference":
        if not url:
            return _missing(level, "url", budgets)
        return assemble_external_reference(
            url, permission=permission, fetch=fetch, budgets=budgets
        )

    # Unknown level (defensive; the enum is closed): empty result.
    ctx = AssembledContext(contextLevel=level)
    ctx.notes.append(f"Unsupported context level: {level!r}.")
    return _finalize(ctx, resolve_budget(level, budgets))


def _missing(level: ContextLevel, arg: str, budgets: dict[str, int] | None) -> AssembledContext:
    ctx = AssembledContext(contextLevel=level)
    ctx.notes.append(f"Cannot assemble {level!r}: missing required {arg!r}.")
    return _finalize(ctx, resolve_budget(level, budgets))
