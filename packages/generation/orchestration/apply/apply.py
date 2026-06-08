"""Apply a validated artefakt patch by creating the next Project Input version (KÖR-7c).

``apply_patch_plan`` consumes a **validated** :class:`PatchPlan` (from KÖR-7b)
and produces the **next** Project Input version snapshot - never an in-place
edit of history. A follow-up is "a new version of the same site, not a new
site": identity (``projectId`` / ``siteId``) is preserved and scaffold/variant
are frozen, exactly like today's follow-up prompt (03 §3).

Reuse, don't duplicate (kor-7c scope): the whole version/merge/write spine is
the existing follow-up logic in ``scripts/prompt_to_project_input.py`` -
``read_existing_meta`` / ``read_existing_project_input`` /
``read_base_run_snapshot`` (read the prior immutable version),
``merge_followup_project_input`` (identity-preservation + additive merge,
frozen scaffold/variant), ``_build_project_dna_snapshot`` (DNA),
``_validate_against_schema`` and ``write_project_input`` (immutable
``<siteId>.v<N+1>`` snapshot via ``O_EXCL`` + atomic pointer files). This module
only adds the genuinely new part: mapping the validated patch onto an existing
Project Input field and recording apply provenance.

Hard guarantees (kor-7c):

- **Patch-driven, not prompt-driven.** The merge runs with an empty follow-up
  prompt so it stays a deterministic additive merge; the authoritative intent is
  the validated patch, never re-parsed prompt heuristics.
- **Immutable.** Only the next ``v<N+1>`` snapshot is written (``write_project_input``
  refuses to overwrite an existing version). No previous ``vN`` snapshot and no
  ``data/runs/<älder runId>/`` artefakt is touched.
- **No build, no ``current.json``.** The build pointer (``.generated/<siteId>/current.json``)
  is kor-7d's; ``write_project_input`` only advances the prompt-inputs version
  pointer (``<siteId>.project-input.json``), which is what a follow-up is meant
  to do.
- **Rejected/invalid never applies.** A plan that did not pass kor-7b's rails is
  refused with :class:`PatchApplyError`; a valid plan with an unmappable patch
  writes nothing and reports the gap.
- **Mock-safe.** No LLM, no ``OPENAI_API_KEY`` (the empty-prompt merge path runs
  the deterministic branch only).
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..patch import PatchPlan
from .mapping import classify_patch
from .models import (
    AppliedCapability,
    ApplyResult,
    PatchApplyError,
    UnmappedPatch,
)
from .trace import log_patch_apply_to_existing_run

if TYPE_CHECKING:
    from packages.generation.followup.theme_directives import ThemeDirective

__all__ = ["apply_patch_plan"]


def _implementing_dossiers(capabilities: list[str]) -> list[str]:
    """Resolve the implementing Dossier id(s) for applied capability slugs.

    KÖR-7-STAB #175 P1: reuses the canonical planning capability -> Dossier
    resolver (``filter_capabilities`` over ``capability-map.v1.json``) instead
    of re-deriving the mapping. ``filter_capabilities`` returns the default
    Dossier for each capability that has one (deduped, order-preserving) and
    drops gaps (empty ``dossiers``) / disabled defaults to ``rejected`` - we
    take only the selected Dossiers so apply never mounts an unimplemented or
    disabled Dossier. Lazy import keeps ``import ...apply`` free of the planning
    import chain, mirroring the ``scripts.prompt_to_project_input`` lazy import
    in ``apply_patch_plan``.
    """
    if not capabilities:
        return []
    from packages.generation.planning import filter_capabilities, load_capability_map

    selected, _rejected = filter_capabilities(capabilities, load_capability_map())
    return selected


def _ensure_required_dossiers(
    project_input: dict, dossier_ids: list[str]
) -> None:
    """Ensure ``selectedDossiers.required`` contains ``dossier_ids`` (in place).

    KÖR-7-STAB #175 P1: deterministic codegen mounts only
    ``selectedDossiers.required``. The object form is canonical (project-input.
    schema.json), so a missing/legacy shape is normalised to the object form
    with the previously listed Dossiers treated as required (codegen ignores any
    other bucket). Order-preserving and idempotent: re-applying the same
    capability never duplicates its Dossier.
    """
    if not dossier_ids:
        return
    selected = project_input.get("selectedDossiers")
    if isinstance(selected, dict):
        existing = selected.get("required")
        required = list(existing) if isinstance(existing, list) else []
    elif isinstance(selected, list):
        # Legacy plain-list form -> promote to object form; the listed Dossiers
        # are the ones the operator pinned, which is exactly what codegen mounts.
        required = [item for item in selected if isinstance(item, str)]
        selected = {"required": required}
        project_input["selectedDossiers"] = selected
    else:
        selected = {"required": []}
        required = []
        project_input["selectedDossiers"] = selected
    for dossier_id in dossier_ids:
        if dossier_id not in required:
            required.append(dossier_id)
    selected["required"] = required


def apply_patch_plan(
    plan: PatchPlan,
    *,
    site_id: str,
    follow_up_prompt: str = "",
    output_dir: Path | None = None,
    base_run_id: str | None = None,
    runs_dir: Path | None = None,
    trace_run_dir: Path | str | None = None,
    theme_directive: ThemeDirective | None = None,
    added_capabilities: list[str] | None = None,
) -> ApplyResult:
    """Apply a validated patch plan as the next Project Input version.

    ``site_id`` selects which site's latest meta/version to follow on from.
    ``base_run_id`` (optional) iterates from a historical version instead of the
    rolling latest, identical to today's follow-up "iterate from version N".
    ``follow_up_prompt`` is stored verbatim on the meta sidecar for provenance
    only - it never drives the merge (apply is patch-driven).

    ``theme_directive`` (optional, the restyle/visual_style edit) carries
    EXPLICIT brand/tone values already extracted from the prompt by the caller
    (``packages.generation.followup.theme_directives.extract_theme_directive``).
    It is still patch-driven, not prompt-driven: apply sets only the named
    ``brand.primaryColorHex``/``brand.accentColorHex``/``tone.primary`` fields
    from the directive's explicit values; it never re-parses the prompt. When a
    theme directive is present apply writes the next version even if the patch
    plan carries no capability patch (a theme-only restyle), so a
    ``visual_style`` follow-up materialises instead of being a no-op.

    ``added_capabilities`` (optional, the section_builder ``section_add`` edit)
    carries capability slugs the caller already resolved from a sanctioned section
    type (``packages.generation.followup.section_directives.resolve_section_capabilities``,
    which only returns capabilities that HAVE an implementing Dossier). They are
    mounted exactly like an applied ``component_add`` capability - added to
    ``requestedCapabilities`` and their implementing Dossier secured in
    ``selectedDossiers.required`` - so the same targeted render applies, no new
    render path. Like a theme-only restyle, a section-only follow-up (no patch,
    no theme) with ``added_capabilities`` still writes the next version.

    ``trace_run_dir`` (optional) is the directory of the **new** version's run,
    if one already exists, to append an append-only apply Engine Event to its
    ``trace.ndjson``. It defaults to ``None`` so apply touches no run at all -
    never a *previous* run's directory (that would break the immutability
    diff). When supplied, **every** outcome is traced (applied, empty no-op,
    unmapped, rejected) so no apply is ever silently dropped (kor-7d FYND1).
    Returns a transient :class:`ApplyResult`.
    """
    # Lazy import: keep ``import ...apply`` (models/mapping) free of the brief/
    # discovery import chain that scripts.prompt_to_project_input pulls in, and
    # mirror the lazy ``from scripts import build_site`` pattern in
    # packages/generation/build/renderers.py.
    from scripts.prompt_to_project_input import (
        DEFAULT_OUTPUT_DIR,
        DEFAULT_RUNS_DIR,
        _build_project_dna_snapshot,
        _validate_against_schema,
        merge_followup_project_input,
        read_base_run_snapshot,
        read_existing_meta,
        read_existing_project_input,
        write_project_input,
    )

    output_dir = output_dir if output_dir is not None else DEFAULT_OUTPUT_DIR
    runs_dir = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR

    def _trace(result: ApplyResult) -> ApplyResult:
        # FYND1 (kor-7d trace-gap): every outcome - applied, empty no-op,
        # unmapped, rejected - leaves an honest append-only trace event when a
        # run dir is available, so a skipped/rejected apply is never silent.
        # ``trace_run_dir`` still defaults to None, so apply touches no run
        # unless a caller (the kor-7d orchestrator) supplies the new version's
        # run dir - never a previous run's dir (immutability diff).
        if trace_run_dir is not None:
            log_patch_apply_to_existing_run(trace_run_dir, result)
        return result

    # 1. Rejected/invalid plan -> never applied (kor-7c DoD). A kor-7b planner
    #    sets valid=False whenever it put a rail-breaking patch in rejected; we
    #    also refuse any hand-built plan that smuggles rejected entries. The
    #    refusal is traced (FYND1) before raising so it is never silent.
    if plan.rejected or not plan.valid:
        _trace(
            ApplyResult(
                applied=False,
                siteId=site_id,
                notes=[
                    "Patch plan rejected/ogiltig (valid=False eller rejected ej "
                    "tom); appliceras aldrig (kor-7c).",
                ],
            )
        )
        raise PatchApplyError(
            "Patch plan är inte giltig (valid=False eller rejected ej tom); "
            "en rejected/ogiltig patch appliceras aldrig (kor-7c)."
        )

    # A restyle (visual_style) carries an explicit theme directive instead of a
    # capability patch. It counts as a real change, so a theme-only follow-up
    # still writes the next version below (the empty-plan no-op only applies when
    # there is ALSO no theme to materialise).
    theme_changes = theme_directive is not None and bool(
        theme_directive.primaryColorHex
        or theme_directive.accentColorHex
        or theme_directive.toneVibe
    )

    # A section_add carries pre-resolved capability slugs (each already verified
    # to have an implementing Dossier by the caller). Like a theme-only restyle it
    # counts as a real change, so a section-only follow-up still writes the next
    # version below.
    section_capabilities = [
        cap for cap in (added_capabilities or []) if isinstance(cap, str) and cap.strip()
    ]

    # 2. Empty valid plan AND no theme AND no section capability -> nothing to
    #    apply (not an error). No write.
    if not plan.patches and not theme_changes and not section_capabilities:
        return _trace(
            ApplyResult(
                applied=False,
                siteId=site_id,
                notes=[
                    "Tom patch-plan; ingen ändring att applicera, ingen ny "
                    "version skapad.",
                ],
            )
        )

    # 3. Map every patch onto an existing Project Input field. All-or-nothing:
    #    if any patch has no existing home, write nothing and report the gap.
    capabilities: list[AppliedCapability] = []
    unmapped: list[UnmappedPatch] = []
    for patch in plan.patches:
        capability, reason = classify_patch(patch)
        if capability is not None:
            capabilities.append(
                AppliedCapability(patchField=patch.field, capability=capability)
            )
        else:
            unmapped.append(
                UnmappedPatch(
                    patchField=patch.field,
                    op=patch.op,
                    value=patch.value,
                    reason=reason or "okänd anledning",
                )
            )

    if unmapped:
        return _trace(
            ApplyResult(
                applied=False,
                siteId=site_id,
                appliedCapabilities=capabilities,
                unmapped=unmapped,
                notes=[
                    "Ingen version skrevs (all-or-nothing): minst en validerad "
                    "patch saknar befintligt Project Input-fält och får inte "
                    "uppfinna ett nytt runtime-kontrakt. Eskalera till operatör "
                    "(ADR) eller dela upp planen.",
                ],
            )
        )

    # section_add: the caller's pre-resolved section capabilities are applied
    # exactly like a mapped component_add capability - unioned into
    # requestedCapabilities and their Dossier secured in selectedDossiers.required
    # below. The synthetic patchField has no contentBlocks route, so the targeted
    # render defaults the affected route to the root (home), where sections land.
    for capability in section_capabilities:
        if any(entry.capability == capability for entry in capabilities):
            continue
        capabilities.append(
            AppliedCapability(
                patchField=f"sectionAdd:{capability}", capability=capability
            )
        )

    # 4. Read the prior immutable version (rolling latest, or a historical
    #    version when base_run_id is given) - identical to generate_followup.
    existing_meta = read_existing_meta(site_id, output_dir=output_dir)
    latest_version = existing_meta["version"]
    if base_run_id is not None:
        previous_pi, previous_meta = read_base_run_snapshot(
            site_id, base_run_id, output_dir=output_dir, runs_dir=runs_dir
        )
        previous_version = previous_meta["version"]
        next_version = max(latest_version, previous_version) + 1
    else:
        previous_pi = read_existing_project_input(site_id, output_dir=output_dir)
        previous_meta = existing_meta
        previous_version = latest_version
        next_version = latest_version + 1

    # 5. Build the candidate Project Input: a copy of the prior version with the
    #    patch's capability slugs added to requestedCapabilities. The existing
    #    follow-up merge then preserves identity, freezes scaffold/variant and
    #    unions requestedCapabilities (with an empty prompt so it stays a
    #    deterministic additive merge - patch-driven, never prompt-driven).
    candidate = copy.deepcopy(previous_pi)
    existing_capabilities = candidate.get("requestedCapabilities")
    candidate["requestedCapabilities"] = (
        list(existing_capabilities) if isinstance(existing_capabilities, list) else []
    ) + [entry.capability for entry in capabilities]

    merged = merge_followup_project_input(
        previous_pi,
        candidate,
        follow_up_prompt="",
        enable_llm_fallback=False,
    )

    # 5b. KÖR-7-STAB #175 P1: a capability only reaching requestedCapabilities is
    #     not enough. Deterministic codegen mounts ONLY
    #     ``selectedDossiers.required`` (build_site.py:selected_required_dossiers),
    #     and the follow-up merge freezes the prior version's selectedDossiers, so
    #     a newly applied capability whose Dossier was not already required would
    #     land in requestedCapabilities yet never be mounted - exactly the gap the
    #     build's unapplied-follow-up observer flags (prompt_to_project_input.py:
    #     compute_unapplied_followup_intents). Reuse the planning capability ->
    #     Dossier resolver (filter_capabilities over capability-map.v1.json) to
    #     secure the implementing Dossier(s) for the applied capabilities in
    #     selectedDossiers.required so the build actually mounts them. A capability
    #     that is a documented gap (empty dossiers) or whose default Dossier is
    #     disabled yields no Dossier and is left honestly unmounted - apply never
    #     invents one.
    mounted_dossiers = _implementing_dossiers(
        [entry.capability for entry in capabilities]
    )
    _ensure_required_dossiers(merged, mounted_dossiers)

    # visual_style restyle: set the named brand/tone fields from the directive's
    # EXPLICIT values (patch-driven; the prompt is never re-parsed here). These
    # are schema-declared Project Input fields rendered by patch_globals_css, so
    # the targeted rebuild reflects the new colour/font.
    theme_applied = False
    if theme_changes:
        from packages.generation.followup.theme_directives import (
            apply_theme_directive,
        )

        theme_applied = apply_theme_directive(merged, theme_directive)

    _validate_against_schema(merged)

    # 6. Build the meta sidecar by carrying the prior version's meta forward and
    #    overriding only the per-version keys (projectId stays the canonical
    #    one). appliedPatchPlan is provenance on the sidecar - not a Project
    #    Input schema field and not a run artefakt.
    now = datetime.now(UTC).isoformat(timespec="seconds")
    meta = copy.deepcopy(previous_meta)
    meta["projectId"] = existing_meta["projectId"]
    meta["siteId"] = site_id
    meta["version"] = next_version
    meta["previousVersion"] = previous_version
    meta["mode"] = "followup"
    meta["scaffoldId"] = merged["scaffoldId"]
    meta["variantId"] = merged["variantId"]
    meta.setdefault("createdAt", now)
    meta["updatedAt"] = now
    # KÖR-7-STAB #175: apply is patch-driven, never prompt-driven. Drop any
    # stale per-version follow-up provenance carried forward from previous_meta
    # (a prior prompt-driven follow-up may have written followUpPrompt/baseRunId)
    # so v<N+1> never makes a false claim. These keys are re-set below ONLY when
    # THIS apply call actually supplied them.
    meta.pop("followUpPrompt", None)
    meta.pop("baseRunId", None)
    meta.pop("unappliedFollowupIntents", None)
    if follow_up_prompt:
        meta["followUpPrompt"] = follow_up_prompt
    if base_run_id is not None:
        meta["baseRunId"] = base_run_id
    meta["appliedPatchPlan"] = {
        "source": "kor-7c-artifact-apply",
        "patchCount": len(plan.patches),
        "appliedCapabilities": [entry.model_dump() for entry in capabilities],
        "themeApplied": theme_applied,
    }
    meta["projectDna"] = _build_project_dna_snapshot(
        merged,
        previous_project_input=previous_pi,
        previous_project_dna=previous_meta.get("projectDna")
        if isinstance(previous_meta.get("projectDna"), dict)
        else None,
        version=next_version,
        mode="followup",
        follow_up_prompt="",
    )

    # 7. Write the immutable next version snapshot (refuses to overwrite vN) +
    #    advance the prompt-inputs version pointer. No build, no current.json.
    project_input_path, meta_path = write_project_input(
        merged, meta, output_dir=output_dir
    )

    notes = [
        f"Applicerade {len(capabilities)} capability-patch(ar) som "
        f"requestedCapabilities i ny version v{next_version}.",
    ]
    if theme_applied:
        notes.append(
            f"Applicerade restyle (brand/tone) i v{next_version} från "
            "visual_style-direktivet."
        )
    result = ApplyResult(
        applied=True,
        siteId=site_id,
        projectId=meta["projectId"],
        previousVersion=previous_version,
        version=next_version,
        projectInputPath=str(project_input_path),
        metaPath=str(meta_path),
        appliedCapabilities=capabilities,
        notes=notes,
    )

    # 8. FYND1: trace the applied outcome too (append-only, only for an
    #    explicitly supplied new run dir - never a previous run).
    return _trace(result)
