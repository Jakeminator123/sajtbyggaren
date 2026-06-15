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
- **Mock-safe.** The empty-prompt merge path runs the deterministic branch only.
  One scoped exception (ADR 0047): a ``copy_change`` against a whitelisted
  section text field whose new copy cannot be derived deterministically MAY call
  ``copyDirectiveModel`` (editPlan) to GENERATE the rewrite from the section's
  current copy + the follow-up - but only when ``OPENAI_API_KEY`` is set and only
  through ADR 0043's ``directives.sectionContentOverrides`` path (the same
  public-copy + grounding guards as ``copyDirectives``, never a new write
  surface). Without ``OPENAI_API_KEY`` it is an unchanged honest no-op
  (mock parity).
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

# Stdlib-only shared module (B173) - importing it pulls in no brief/discovery
# chain, so the top-level import keeps ``import ...apply`` as light as before.
from packages.generation.followup.hero_headline_pin import (
    latest_run_dir_for_site,
    pin_previous_hero_headline,
)
from packages.generation.followup.section_content_overrides import (
    build_section_override_key,
    current_section_text,
    derive_section_edit,
    parse_section_content_field,
    plan_section_edit_via_llm,
    render_section_override_text,
    section_base_text,
)

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


def _implementing_dossiers(
    capabilities: list[str],
    preferences: dict[str, str] | None = None,
) -> list[str]:
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

    ``preferences`` (B198, optional): ``{capability: dossier_id}`` for follow-ups
    that NAMED a specific implementing Dossier (e.g. resend-contact-form instead
    of the mailto default). A preference is honoured only when the named Dossier
    is listed for that capability in the map AND enabled - otherwise the
    capability falls back to the default resolver, so apply still never mounts
    an unregistered or disabled Dossier.

    Returns ``(mounted, displaced)``: ``mounted`` is the Dossier ids to secure
    in ``selectedDossiers.required``; ``displaced`` is the sibling Dossier ids
    an HONOURED preference replaces for the same capability (extern granskning
    2026-06-11, fynd 3: a named switch is EXCLUSIVE per capability - a site
    that mounted the mailto default in v2 and asks for resend in v3 must not
    keep BOTH contact forms). Displacement only ever happens on an explicit
    named preference; default mounting never removes anything.
    """
    if not capabilities:
        return [], []
    from packages.generation.planning import (
        dossier_is_enabled,
        filter_capabilities,
        load_capability_map,
    )

    capability_map = load_capability_map()
    capability_entries = (
        capability_map.get("capabilities", {})
        if isinstance(capability_map, dict)
        else {}
    )
    prefs = preferences or {}
    resolved: list[str] = []
    displaced: list[str] = []
    seen: set[str] = set()
    for capability in capabilities:
        if capability in seen:
            continue
        seen.add(capability)
        preferred = prefs.get(capability)
        if preferred:
            entry = capability_entries.get(capability)
            listed = entry.get("dossiers") if isinstance(entry, dict) else None
            if (
                isinstance(listed, list)
                and preferred in listed
                and dossier_is_enabled(preferred)
            ):
                if preferred not in resolved:
                    resolved.append(preferred)
                for sibling in listed:
                    if (
                        isinstance(sibling, str)
                        and sibling != preferred
                        and sibling not in displaced
                    ):
                        displaced.append(sibling)
                continue
            # Invalid/disabled preference -> honest fallback to the default.
        selected, _rejected = filter_capabilities([capability], capability_map)
        for dossier_id in selected:
            if dossier_id not in resolved:
                resolved.append(dossier_id)
    # A Dossier both mounted (for another capability) and displaced keeps its
    # mount - displacement is per-capability, never a global ban.
    displaced = [d for d in displaced if d not in resolved]
    return resolved, displaced


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


def _remove_displaced_dossiers(
    project_input: dict, displaced: list[str]
) -> None:
    """Remove ``displaced`` Dossier ids from ``selectedDossiers.required``.

    The exclusivity half of a named-Dossier switch (B198, extern granskning
    2026-06-11 fynd 3): when a follow-up explicitly picks e.g.
    resend-contact-form, a previously mounted sibling (mailto-contact-form,
    carried forward from an earlier version's required list) is dropped so the
    site never builds a hybrid with two contact forms. Only ever called with
    the siblings of an HONOURED preference; a no-preference apply removes
    nothing. Defensive on shape (object form only - the legacy list form was
    already normalised by ``_ensure_required_dossiers``).
    """
    if not displaced:
        return
    selected = project_input.get("selectedDossiers")
    if not isinstance(selected, dict):
        return
    required = selected.get("required")
    if not isinstance(required, list):
        return
    selected["required"] = [d for d in required if d not in displaced]


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
    section_positions: dict[str, str] | None = None,
    dossier_preferences: dict[str, str] | None = None,
    disabled_routes: list[str] | None = None,
    hidden_nav_routes: list[str] | None = None,
    generative_components: list[dict] | None = None,
    unapplied_followup_intents: list[dict[str, str]] | None = None,
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

    ``dossier_preferences`` (optional, B198) maps an applied capability to the
    NAMED implementing Dossier the follow-up asked for (e.g. resend-contact-form
    instead of the mailto default). Validated inside the resolver against
    capability-map.v1.json + the manifest's enabled flag; an invalid/disabled
    preference falls back to the capability default - chat can never mount an
    unregistered Dossier.

    ``disabled_routes`` (optional, the route_remove edit, Route/Nav Mutation V1 /
    ADR 0060) carries scaffold routeIds the caller already resolved + validated
    (``packages.generation.followup.route_directives.resolve_disabled_routes``,
    which only returns ids that exist in the scaffold AND are not required). They
    are recorded STICKY on ``directives.disabledRoutes`` - union of the prior
    version's list (carried forward by the deep-copy merge) with this call's ids -
    so a page removed in v2 does not reappear on a later unrelated follow-up.
    ``build_site.py`` computes ``activeRoutes = scaffold defaultRoutes minus
    disabledRoutes`` in one filter point, so the page is dropped from nav,
    write_pages and the route guards. Like a theme-only restyle, a route-remove-
    only follow-up (no patch, no theme, no section) still writes the next version.

    ``hidden_nav_routes`` (optional, the nav_hide edit, Route/Nav Mutation V1 /
    ADR 0060) is the NON-destructive sibling: pre-resolved + validated scaffold
    routeIds whose nav link is hidden (``route_directives.resolve_hidden_nav_routes``).
    Recorded STICKY on ``directives.hiddenNavRoutes`` (union with the prior
    version). Unlike ``disabled_routes`` these are NOT filtered out of
    ``activeRoutes`` - ``build_site.py`` drops only the header/footer nav item, so
    the page.tsx, route guards and contact-route lookup keep the full route set.
    Like a route-remove-only follow-up, a nav-hide-only follow-up still writes the
    next version.

    ``generative_components`` (optional, the component_add generative path,
    Generative Component V1 / ADR 0061) carries pre-resolved + validated
    ``{recipe, count, routeId, id}`` specs (each one already verified to name a
    WHITELISTED recipe by the caller's
    ``packages.generation.followup.generative_component_directives``). They are
    recorded STICKY on ``directives.generativeComponents`` - union of the prior
    version's list (carried forward by the deep-copy merge) with this call's specs,
    de-duplicated by ``id`` - so a component materialised in v2 does not vanish on a
    later unrelated follow-up. ``build_site.py`` reads the directive after
    ``write_pages`` and materialises each spec as ONE new
    ``components/generated/<id>.tsx`` spliced into its route's page.tsx. Like a
    theme-only restyle, a generative-only follow-up (no patch, no theme, no section,
    no route) still writes the next version.

    ``trace_run_dir`` (optional) is the directory of the **new** version's run,
    if one already exists, to append an append-only apply Engine Event to its
    ``trace.ndjson``. It defaults to ``None`` so apply touches no run at all -
    never a *previous* run's directory (that would break the immutability
    diff). When supplied, **every** outcome is traced (applied, empty no-op,
    unmapped, rejected) so no apply is ever silently dropped (kor-7d FYND1).

    ``unapplied_followup_intents`` (optional, B155 follow-up) carries bounded
    ``{target, reason}`` posts the caller computed for compound follow-up parts
    no executor applied (router subtask edit kinds with no owner, or owners that
    materialised nothing). It is pure provenance on the meta sidecar - it never
    drives the merge - written onto the new version's meta after the stale-scrub
    so the deterministic builder surfaces it in ``build-result.json`` via the
    EXISTING ``unappliedFollowupIntents`` channel. ``None``/empty (the default)
    reproduces today's behaviour exactly: the field is only scrubbed, never set.
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

    # A route_remove carries pre-resolved + validated scaffold routeIds (each one
    # already verified to exist in the scaffold and not be required by the
    # caller's route_directives resolver). Like a theme-only restyle it counts as
    # a real change, so a route-remove-only follow-up still writes the next
    # version below (ADR 0060).
    disabled_route_ids = [
        route_id
        for route_id in (disabled_routes or [])
        if isinstance(route_id, str) and route_id.strip()
    ]

    # A nav_hide carries pre-resolved + validated scaffold routeIds whose nav
    # link is hidden while the page stays (route_editor, ADR 0060). Like a
    # route-remove it counts as a real change, so a nav-hide-only follow-up still
    # writes the next version below.
    hidden_nav_route_ids = [
        route_id
        for route_id in (hidden_nav_routes or [])
        if isinstance(route_id, str) and route_id.strip()
    ]

    # A component_add generative path carries pre-resolved + validated specs (each
    # already verified to name a WHITELISTED recipe by the caller's
    # generative_component_directives, ADR 0061). Like a theme-only restyle it
    # counts as a real change, so a generative-only follow-up still writes the next
    # version below. Filtered defensively to specs that carry a usable id.
    generative_component_specs = [
        spec
        for spec in (generative_components or [])
        if isinstance(spec, dict)
        and isinstance(spec.get("id"), str)
        and spec.get("id", "").strip()
    ]

    # 2. Empty valid plan AND no theme AND no section capability AND no disabled
    #    route AND no hidden nav route AND no generative component -> nothing to
    #    apply (not an error). No write.
    if (
        not plan.patches
        and not theme_changes
        and not section_capabilities
        and not disabled_route_ids
        and not hidden_nav_route_ids
        and not generative_component_specs
    ):
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
    #
    #    Two mapped shapes have a home today:
    #    - a capability-backed component_add -> requestedCapabilities (classify_patch).
    #    - a copy_change against a whitelisted section text field
    #      (contentBlocks.<route>.<section>.<headline|subheadline|body>) ->
    #      directives.sectionContentOverrides (ADR 0043). The new copy is derived
    #      from the follow-up prompt here (deterministic, guarded), since the
    #      planner deliberately leaves a copy_change value=None. A whitelisted
    #      target whose copy cannot be derived stays an honest no-op.
    capabilities: list[AppliedCapability] = []
    unmapped: list[UnmappedPatch] = []
    # (routeId, sectionId, field, operation, value) for each derivable override.
    override_edits: list[tuple[str, str, str, str, str]] = []

    # ADR 0047 generative editPlan needs the section's CURRENT copy as the
    # rewrite base + grounding source. Read the prior immutable version lazily
    # and cache it (only fires when a value-less section copy_change reaches the
    # planner branch, which is rare) so the common path never pays the read.
    # This is strictly additive - it does NOT move the authoritative step-4 read
    # below and never touches apply_patch_plan's signature, so it stays disjoint
    # from the parallel compound-prompt slice.
    _prev_pi_cache: dict | None = None

    def _previous_section_base(route_id: str, section_id: str, field: str) -> str | None:
        nonlocal _prev_pi_cache
        if _prev_pi_cache is None:
            if base_run_id is not None:
                _prev_pi_cache, _ = read_base_run_snapshot(
                    site_id, base_run_id, output_dir=output_dir, runs_dir=runs_dir
                )
                # Sökvägen är redan validerad av read_base_run_snapshot ovan.
                pin_run_dir = (runs_dir / base_run_id).resolve()
            else:
                _prev_pi_cache = read_existing_project_input(
                    site_id, output_dir=output_dir
                )
                pin_run_dir = latest_run_dir_for_site(runs_dir, site_id)
            # B173-paritet (review-fynd #283): basen för en hero-headline-
            # rewrite måste vara samma H1 som föregående bygge FAKTISKT
            # renderade — samma pin-källa (run-direns blueprint-headline) som
            # steg 4b nedan använder för merge-basen. Utan pinnen läste den
            # här lazy-läsningen company.name som rewrite-bas när operatören
            # aldrig satt en explicit heroHeadline, så modellen skrev om fel
            # text. No-op när en explicit heroHeadline redan finns eller när
            # sajten saknar en komplett run (samma regler som pinnen själv).
            pin_previous_hero_headline(_prev_pi_cache, run_dir=pin_run_dir)
        return current_section_text(_prev_pi_cache, route_id, section_id, field)

    for patch in plan.patches:
        capability, reason = classify_patch(patch)
        if capability is not None:
            capabilities.append(
                AppliedCapability(patchField=patch.field, capability=capability)
            )
            continue
        parsed = parse_section_content_field(patch.field)
        if parsed is not None:
            route_id, section_id, leaf = parsed
            edit = derive_section_edit(leaf, follow_up_prompt)
            if edit is None:
                # ADR 0047: no literal value, but a vibe rewrite of a whitelisted
                # section field -> generate new copy via copyDirectiveModel
                # (editPlan), guarded + grounded exactly like copyDirectives.
                # Without OPENAI_API_KEY this returns None (honest no-op / mock
                # parity), so the value-less prompt stays an unmapped no-op below.
                edit = plan_section_edit_via_llm(
                    leaf,
                    follow_up_prompt,
                    base_text=_previous_section_base(route_id, section_id, leaf),
                    language=str(
                        (_prev_pi_cache or {}).get("language") or "sv"
                    ),
                )
            if edit is not None:
                operation, value = edit
                override_edits.append((route_id, section_id, leaf, operation, value))
                continue
            unmapped.append(
                UnmappedPatch(
                    patchField=patch.field,
                    op=patch.op,
                    value=patch.value,
                    reason=(
                        f"copy_change {patch.field!r} träffar ett vitlistat "
                        "sektionstextfält men ingen ny text kunde härledas ur "
                        "följdprompten (planeraren uppfinner aldrig copy). Ange "
                        "den nya texten explicit (t.ex. ... till \"X\") — ärlig "
                        "no-op tills dess."
                    ),
                )
            )
            continue
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

    # 4b. B173 hero-headline carry-forward: pin the previously RENDERED hero H1
    #     onto the merge base when the operator never set an explicit
    #     heroHeadline. Without this, the targeted rebuild regenerates the
    #     brief (positioning.oneLiner -> blueprint headline) and the H1 drifts
    #     on EVERY apply-driven follow-up (the /studio OpenClaw apply-bridge
    #     path, which never goes through generate_followup - Scout-fynd på PR
    #     #264, painter-palma). Same shared seam + cap/fallback rules as
    #     generate_followup; an already-set explicit heroHeadline is never
    #     touched, and a site with no completed run is left unpinned.
    base_run_dir = (
        # Path already validated by read_base_run_snapshot (pattern + resolve).
        (runs_dir / base_run_id).resolve()
        if base_run_id is not None
        else latest_run_dir_for_site(runs_dir, site_id)
    )
    pin_previous_hero_headline(previous_pi, run_dir=base_run_dir)

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
    # B198: a follow-up that NAMED a specific implementing Dossier ("resend")
    # prefers it over the capability default; an invalid/disabled preference
    # falls back to the default inside the resolver (never an invented mount).
    # The named switch is EXCLUSIVE per capability: siblings the preference
    # displaces are removed from required (a v2-mounted mailto must not live
    # on next to a v3-chosen resend - no hybrid contact forms).
    mounted_dossiers, displaced_dossiers = _implementing_dossiers(
        [entry.capability for entry in capabilities],
        preferences=dossier_preferences,
    )
    _ensure_required_dossiers(merged, mounted_dossiers)
    _remove_displaced_dossiers(merged, displaced_dossiers)

    # 5b2. section_add INLINE render (ADR 0038): a mounted section capability that
    #      maps to an inline section on a supported scaffold is recorded as a
    #      ``directives.mountedSections`` entry on the NEW version's Project Input
    #      so the renderer injects the section as a block on its route (instead of
    #      staying mount-only / dedicated-route-only). The list is replaced per
    #      version (never accumulated): re-run from the same base does not stack
    #      duplicates, and a section that is no longer requested drops out. Render
    #      time owns honesty - the renderer skips an id with no registered
    #      renderer, one already in the route order, or one whose section renders
    #      empty - so writing the entry here never forces a visible effect.
    from packages.generation.followup.section_directives import (
        resolve_inline_section_placements,
    )

    # Inline-eligible capabilities for THIS version are the union of:
    #
    #   1. CARRIED FORWARD: capabilities of the previous version's
    #      ``mountedSections`` entries that are STILL requested on the merged
    #      version (``merge_followup_project_input`` deep-copies the previous
    #      version, so the prior directive + the requestedCapabilities union ride
    #      along). This keeps the directive COMPOSING across versions - a section
    #      mounted in v2 survives a v3 copy/theme follow-up - while a capability
    #      that is genuinely no longer requested falls out.
    #   2. NEW: ONLY this apply call's ``section_capabilities`` (the explicit
    #      section_add intent). Codex review fix: deriving new placements from the
    #      FULL merged ``requestedCapabilities`` meant a plain ``component_add``
    #      that happened to mount an inline-capable capability (e.g. hours via a
    #      widget patch) silently injected a whole NEW home section the user
    #      never asked for. Only a section_add may CREATE an inline placement;
    #      everything else can at most PRESERVE one.
    #
    # The list is still per-version (rebuilt, never appended to), so it cannot
    # drift from what the build can render.
    merged_caps = {
        cap
        for cap in (merged.get("requestedCapabilities") or [])
        if isinstance(cap, str) and cap.strip()
    }
    directives = merged.get("directives")
    carried_caps: list[str] = []
    prior_mounted = (
        directives.get("mountedSections") if isinstance(directives, dict) else None
    )
    if isinstance(prior_mounted, list):
        for prev in prior_mounted:
            if not isinstance(prev, dict):
                continue
            cap = prev.get("capability")
            if isinstance(cap, str) and cap in merged_caps and cap not in carried_caps:
                carried_caps.append(cap)
    eligible_caps = carried_caps + [
        cap for cap in section_capabilities if cap not in carried_caps
    ]
    inline_placements = resolve_inline_section_placements(eligible_caps, merged)
    if inline_placements:
        if not isinstance(directives, dict):
            directives = {}
            merged["directives"] = directives
        # Position precedence: an EXPLICIT position from THIS call's router target
        # wins; otherwise carry forward the position a prior version already
        # recorded for the same section (so a v2 "överst" survives a v3 follow-up
        # that does not re-mention the section); otherwise the default slot.
        new_positions = section_positions or {}
        prior_positions: dict[str, str] = {}
        prior = directives.get("mountedSections")
        if isinstance(prior, list):
            for prev in prior:
                if isinstance(prev, dict):
                    cap = prev.get("capability")
                    pos = prev.get("position")
                    if isinstance(cap, str) and pos in ("top", "bottom", "before-contact"):
                        prior_positions[cap] = pos
        entries: list[dict[str, str]] = []
        for placement in inline_placements:
            entry = {
                "sectionId": placement["sectionId"],
                "routeId": placement["routeId"],
                "capability": placement["capability"],
            }
            # Coarse placement from the router target ("överst"/"längst ner").
            # Only the schema-valid positions are honoured; anything else (incl.
            # left/right/center, which are intra-section, not route-order) drops
            # to the default before-contact slot.
            position = new_positions.get(placement["capability"]) or prior_positions.get(
                placement["capability"]
            )
            if position in ("top", "bottom", "before-contact"):
                entry["position"] = position
            entries.append(entry)
        directives["mountedSections"] = entries
    elif isinstance(directives, dict):
        # No inline-eligible capability remains requested -> the directive must
        # not linger (honest: nothing inline to render this version).
        directives.pop("mountedSections", None)

    # route_remove (ADR 0060): record the disabled scaffold routes on the NEW
    # version's directives. STICKY by design - union the carried-forward prior
    # list (merge_followup_project_input deep-copies the previous version, so a
    # route disabled in v2 rides along) with THIS call's disabled_route_ids, so a
    # removed page never reappears on a later unrelated follow-up. build_site.py
    # computes activeRoutes = scaffold defaultRoutes minus this list in one filter
    # point, so nav, write_pages and the route guards all stop seeing the page.
    # route_directives already dropped unknown/required ids before they reached
    # here, so an honest no-op upstream never persists a phantom disabled route.
    if disabled_route_ids:
        route_directives = merged.get("directives")
        if not isinstance(route_directives, dict):
            route_directives = {}
            merged["directives"] = route_directives
        existing_disabled = route_directives.get("disabledRoutes")
        union_disabled: list[str] = []
        for route_id in (
            (existing_disabled if isinstance(existing_disabled, list) else [])
            + disabled_route_ids
        ):
            if (
                isinstance(route_id, str)
                and route_id.strip()
                and route_id not in union_disabled
            ):
                union_disabled.append(route_id)
        if union_disabled:
            route_directives["disabledRoutes"] = union_disabled

    # nav_hide (route_editor, ADR 0060): record the hidden nav routeIds STICKY on
    # directives.hiddenNavRoutes (union with the prior version, same as
    # disabledRoutes). Unlike disabledRoutes these are NOT filtered out of
    # activeRoutes - build_site drops only the nav (href,label) item, so the page
    # stays. route_directives already dropped unknown/home ids upstream.
    if hidden_nav_route_ids:
        nav_directives = merged.get("directives")
        if not isinstance(nav_directives, dict):
            nav_directives = {}
            merged["directives"] = nav_directives
        existing_hidden = nav_directives.get("hiddenNavRoutes")
        union_hidden: list[str] = []
        for route_id in (
            (existing_hidden if isinstance(existing_hidden, list) else [])
            + hidden_nav_route_ids
        ):
            if (
                isinstance(route_id, str)
                and route_id.strip()
                and route_id not in union_hidden
            ):
                union_hidden.append(route_id)
        if union_hidden:
            nav_directives["hiddenNavRoutes"] = union_hidden

    # Generative Component V1 (ADR 0061): record the generative-component specs on
    # the NEW version's directives. STICKY by design - union the carried-forward
    # prior list (merge_followup_project_input deep-copies the previous version, so
    # a component generated in v2 rides along) with THIS call's specs, de-duplicated
    # by id. LAST WINS (matris #1 fix): THIS call's spec replaces the prior spec
    # with the same id IN PLACE (keeping its position), so a repeat "lägg till N
    # bildplatshållare" UPDATES the existing grid's count instead of being silently
    # dropped by a first-wins union. build_site.py reads directives.generativeComponents
    # after write_pages and materialises each spec as one components/generated/<id>.tsx
    # spliced into its route's page.tsx. generative_component_directives already
    # dropped non-whitelisted recipes/components before they reached here, so an
    # honest no-op upstream never persists a phantom component.
    if generative_component_specs:
        gen_directives = merged.get("directives")
        if not isinstance(gen_directives, dict):
            gen_directives = {}
            merged["directives"] = gen_directives
        existing_gen = gen_directives.get("generativeComponents")
        union_by_id: dict[str, dict] = {}
        union_order: list[str] = []
        for entry in (
            (existing_gen if isinstance(existing_gen, list) else [])
            + generative_component_specs
        ):
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("id")
            if not isinstance(entry_id, str) or not entry_id.strip():
                continue
            if entry_id not in union_by_id:
                union_order.append(entry_id)
            # Last wins: a re-issued same-id spec overwrites the prior one in place.
            union_by_id[entry_id] = entry
        union_gen = [union_by_id[entry_id] for entry_id in union_order]
        if union_gen:
            gen_directives["generativeComponents"] = union_gen

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

    # ADR 0043 section content overrides: map each derivable copy_change onto
    # directives.sectionContentOverrides on the NEW version. The map LIVES in
    # Project Input and is carried forward by the deep-copy merge (it survives
    # brief reuse B180 + the hero pin B173); this apply only adds/updates its
    # own keys, never clearing a prior section edit. Render-time precedence
    # (override wins over the regenerated blueprint copy) lives in
    # packages/generation/build, mirroring the company.heroHeadline pin.
    applied_overrides: list[str] = []
    if override_edits:
        overrides_directives = merged.get("directives")
        if not isinstance(overrides_directives, dict):
            overrides_directives = {}
            merged["directives"] = overrides_directives
        existing = overrides_directives.get("sectionContentOverrides")
        overrides = dict(existing) if isinstance(existing, dict) else {}
        for route_id, section_id, field, operation, value in override_edits:
            key = build_section_override_key(route_id, section_id, field)
            # An "include" appends to the CURRENT effective copy: a prior
            # override for this exact field if one is carried forward, else the
            # structured Project Input copy the renderer reads.
            prior = overrides.get(key)
            base = (
                prior
                if isinstance(prior, str) and prior.strip()
                else section_base_text(merged, route_id, section_id, field)
            )
            text = render_section_override_text(
                field, operation, value, base_text=base
            )
            if text is None:
                continue
            overrides[key] = text
            applied_overrides.append(key)
        if overrides:
            overrides_directives["sectionContentOverrides"] = overrides

    _validate_against_schema(merged)

    # 5c. section_add visible surfacing (the section_builder's visible-render
    #     follow-up). A mounted section capability that has a dedicated, grounded
    #     visible route is surfaced by recording its wizard ``mustHave`` label on
    #     the NEW version's meta sidecar; the next targeted build then emits the
    #     dedicated page (reusing the existing render_* + extra-routes plumbing),
    #     so the deterministic file-diff reports an honest appliedVisibleEffect.
    #     Only the synthetic section_add capabilities (``sectionAdd:`` patchField)
    #     are considered - a component_add never changes the route plan here. A
    #     capability with no dedicated visible route, or with no grounded content,
    #     stays mount-only (honest mounted-but-no-content) and is reported in the
    #     notes. Behaviour-preserving: the label lands ONLY on this version's meta
    #     (per-site, per-version), so init builds and other sites are untouched,
    #     and a scaffold whose renderer set does not emit the wizard route keeps
    #     the section mount-only at build time.
    surfaced_routes: list[str] = []
    surfaced_wizard_pages: list[str] = []
    section_mount_only: list[dict[str, str]] = []
    # Visible surfacing considers the pre-resolved section_add capabilities
    # DIRECTLY (deduped, order-preserving), not the merged ``capabilities`` list
    # filtered by ``sectionAdd:`` patchField. When the SAME capability ALSO
    # arrives via a component patch, the dedupe above keeps only the patch entry
    # (whose patchField is not ``sectionAdd:``), which would otherwise drop the
    # section_add surfacing intent and leave the dedicated route invisible even
    # on a wizard-route scaffold (#221 P2). The section_add intent is preserved
    # separately from capability-dedupe, independent of how the capability was
    # mounted. Each entry is already verified to have an implementing Dossier by
    # the caller, so it is genuinely mounted.
    section_capabilities_applied: list[str] = []
    for capability in section_capabilities:
        if capability not in section_capabilities_applied:
            section_capabilities_applied.append(capability)
    if section_capabilities_applied:
        from packages.generation.followup.section_directives import (
            resolve_visible_section_pages,
        )

        visible_pages, section_mount_only = resolve_visible_section_pages(
            section_capabilities_applied, merged
        )
        for page in visible_pages:
            if page["wizardLabel"] not in surfaced_wizard_pages:
                surfaced_wizard_pages.append(page["wizardLabel"])
            if page["routeId"] not in surfaced_routes:
                surfaced_routes.append(page["routeId"])

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
    # B155 follow-up: re-set the honest unapplied-intents observer AFTER the
    # stale-scrub, only when THIS apply call supplied a non-empty list (so a
    # patch-driven apply with nothing unapplied keeps today's clean sidecar).
    # The deterministic builder reads it from the sidecar and surfaces it in
    # build-result.json via the existing unappliedFollowupIntents channel.
    if unapplied_followup_intents:
        meta["unappliedFollowupIntents"] = list(unapplied_followup_intents)
    # section_add visible surfacing: union the surfaced wizard ``mustHave``
    # labels into the next version's meta so the build emits the dedicated page.
    # Order-preserving + idempotent: re-surfacing the same page never duplicates
    # it, and any labels the operator already had carry forward.
    if surfaced_wizard_pages:
        existing_pages = meta.get("wizardMustHave")
        pages = (
            [page for page in existing_pages if isinstance(page, str)]
            if isinstance(existing_pages, list)
            else []
        )
        for label in surfaced_wizard_pages:
            if label not in pages:
                pages.append(label)
        meta["wizardMustHave"] = pages
    meta["appliedPatchPlan"] = {
        "source": "kor-7c-artifact-apply",
        "patchCount": len(plan.patches),
        "appliedCapabilities": [entry.model_dump() for entry in capabilities],
        "themeApplied": theme_applied,
        "sectionRoutesSurfaced": list(surfaced_routes),
        "sectionContentOverrides": list(applied_overrides),
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
    if applied_overrides:
        notes.append(
            f"Applicerade {len(applied_overrides)} sektionscopy-override(s) "
            f"({', '.join(applied_overrides)}) i directives."
            "sectionContentOverrides; renderaren låter dem vinna över "
            "blueprint-copyn."
        )
    if theme_applied:
        notes.append(
            f"Applicerade restyle (brand/tone) i v{next_version} från "
            "visual_style-direktivet."
        )
    if surfaced_wizard_pages:
        notes.append(
            "Synliggjorde sektion(er) som dedikerad route "
            f"({', '.join(surfaced_routes)}) via wizardMustHave "
            f"({', '.join(surfaced_wizard_pages)}); targeted render avgör "
            "appliedVisibleEffect."
        )
    for entry in section_mount_only:
        notes.append(
            f"Sektion {entry['capability']!r} förblir mount-only: {entry['reason']}"
        )
    if disabled_route_ids:
        notes.append(
            f"Stängde av route(s) ({', '.join(disabled_route_ids)}) via "
            f"directives.disabledRoutes i v{next_version}; build filtrerar bort "
            "dem ur activeRoutes (sida, nav och route-guards)."
        )
    if hidden_nav_route_ids:
        notes.append(
            f"Dolde nav-länk(ar) ({', '.join(hidden_nav_route_ids)}) via "
            f"directives.hiddenNavRoutes i v{next_version}; build döljer dem ur "
            "header/footer-navet men behåller sidan (page.tsx + route-guards)."
        )
    if generative_component_specs:
        recipe_summary = ", ".join(
            f"{spec.get('recipe')}(x{spec.get('count')})"
            for spec in generative_component_specs
        )
        notes.append(
            f"Genererade komponent(er) ({recipe_summary}) via "
            f"directives.generativeComponents i v{next_version}; build skriver dem "
            "som components/generated/<id>.tsx och splice:ar in dem i routens "
            "page.tsx (deterministiskt recept, inga nya npm-beroenden)."
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
        sectionRoutesSurfaced=list(surfaced_routes),
        notes=notes,
    )

    # 8. FYND1: trace the applied outcome too (append-only, only for an
    #    explicitly supplied new run dir - never a previous run).
    return _trace(result)
