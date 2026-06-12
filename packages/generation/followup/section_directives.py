"""Follow-up section directives: resolve a sanctioned section_add to a capability.

A ``section_add`` follow-up ("lägg till en sektion om garantier", "lägg till en
FAQ-sektion") is the section_builder role. It adds ONE sanctioned section to the
site by mounting the section's capability through the SAME apply machinery a
``component_add`` already uses (``requestedCapabilities`` +
``selectedDossiers.required``), so the existing dossier mounts and the targeted
render reflects it. No new render path, no new engine - exactly the #207 restyle
pattern, just a capability instead of a theme directive.

Sanctioned section types (docs/openclaw-workspace/skills/section-add/SKILL.md).
A slug is listed here only when its capability clears BOTH gates: (a) it has an
implementing Dossier in ``capability-map.v1.json`` (so apply can mount it), AND
(b) an existing ``render_section_*``/``render_*`` renderer covers it (so the
section is not a dead-end). The set is the original ``team``/``faq``/``trust``/
``reviews`` plus the modules from Christopher's module drag-and-drop that REUSE
an existing Dossier + renderer (gallery, pricing, opening-hours, map,
contact-form). No type is invented and none is added without a Dossier + renderer
(``cta-banner`` has no Dossier, so it is intentionally absent; ``hero``/``services``
are page-level sections, not add-targets).

Mount-only contract (same as the original four): like every section_add today,
adding a type here mounts the capability + Dossier into the next version
(``requestedCapabilities`` + ``selectedDossiers.required``); the soft Dossiers are
instructions-only (no components, no extra routes), so the deterministic targeted
render produces no new section on its own - ``appliedVisibleEffect`` is honestly
``False``. Surfacing the mounted section visibly on the page is a separate
render-path concern, not something this resolver claims.

Honest by construction: an unknown type, or a sanctioned type whose capability has
no implementing Dossier, is reported as ``unsupported`` so the chain can do an
HONEST no-op (it never invents a section). Deterministic, offline, no LLM.

Conventions: identifiers + comments in English (governance/rules/code-in-english.md).
"""

from __future__ import annotations

__all__ = [
    "CONTACT_FORM_VISIBLE_SCAFFOLDS",
    "DOSSIER_PREFERENCE_CUES",
    "INLINE_SECTION_PLACEMENTS",
    "INLINE_SECTION_ROUTES",
    "INLINE_SECTION_SCAFFOLDS",
    "SECTION_TYPE_CAPABILITY",
    "VISIBLE_SECTION_ROUTES",
    "resolve_dossier_preferences",
    "resolve_inline_section_placements",
    "resolve_section_capabilities",
    "resolve_visible_section_pages",
]

# Sanctioned section-type slug (router ``componentIntent`` for ``section_add``)
# -> capability slug (``capability-map.v1.json`` key). Every value resolves to a
# default Dossier via ``filter_capabilities`` and has an existing renderer:
#   - faq/reviews/team/trust reuse the soft instructions-only faq-accordion /
#     reviews-display / team-roster / trust-guarantees Dossiers, rendered by the
#     existing render_section_faq / render_section_reviews-testimonials /
#     render_section_team / render_section_trust_proof renderers.
#   - gallery/pricing/hours/location/contact-form reuse the soft image-gallery /
#     pricing-table / opening-hours / map-embed / mailto-contact-form Dossiers,
#     rendered by the existing render_section_gallery + render_gallery /
#     render_pricing / render_section_hours_summary / render_map /
#     render_section_contact_cta + render_contact renderers. (The slug keys the
#     router emits; the capability values are capability-map.v1.json keys, hence
#     map->location.)
SECTION_TYPE_CAPABILITY: dict[str, str] = {
    "faq": "faq-section",
    "reviews": "reviews",
    "team": "team-section",
    "trust": "guarantees",
    "gallery": "gallery",
    "pricing": "pricing",
    "hours": "hours",
    "map": "location",
    "contact-form": "contact-form",
}

# Sanctioned types, spelled out for the honest "unsupported" reason text.
_SANCTIONED = (
    "team, faq, garantier/trust, recensioner, galleri, priser, öppettider, "
    "karta, kontaktformulär"
)

# Section capabilities that can be surfaced as a VISIBLE dedicated route instead
# of staying mount-only. Each maps the mounted capability slug to the wizard
# ``mustHave`` label that ``produce_site_plan`` already knows how to emit as a
# real page (planning._WIZARD_ROUTE_DEFINITIONS) plus that page's logical route
# id. Surfacing reuses the EXISTING render_* helper + extra-routes plumbing (no
# new render engine): the section_builder records the label on the next
# version's meta sidecar, so the targeted build emits the dedicated page and the
# deterministic file-diff reports an honest ``appliedVisibleEffect``.
#
# Only the local-service-business scaffold emits these wizard routes
# (planning._WIZARD_ROUTE_SCAFFOLDS), so a section_add on any other scaffold
# stays honestly mount-only. Kept narrow on purpose (faq + team first); the
# remaining route-capable types (gallery/pricing/location) can follow the same
# pattern once proven.
#
# B198 del b: ``contact-form`` surfaces on the EXISTING scaffold-default contact
# route (``/kontakt``, routeId ``contact``) rather than a wizard-extra route -
# the contact page already exists on the scaffolds that opt in (no new page, no
# dedup collision). It runs a NARROWER gate than faq/team: it surfaces only on
# the scaffolds in ``CONTACT_FORM_VISIBLE_SCAFFOLDS`` (today just ecommerce-lite)
# AND only when the implementing hard Dossier ``resend-contact-form`` is actually
# mounted (the grounded-content gate below). The mailto default has no visible
# component yet, so contact-form stays honestly mount-only there.
VISIBLE_SECTION_ROUTES: dict[str, dict[str, str]] = {
    "faq-section": {"wizardLabel": "FAQ", "routeId": "faq"},
    "team-section": {"wizardLabel": "Vårt team", "routeId": "team"},
    "contact-form": {"wizardLabel": "Kontaktformulär", "routeId": "contact"},
}

# Scaffolds that surface ``contact-form`` visibly on their existing contact
# route. Narrow allowlist mirroring ``INLINE_SECTION_SCAFFOLDS`` (B198 del b):
# a scaffold opts in deliberately rather than inheriting contact-form surfacing
# from the broad ``_WIZARD_ROUTE_SCAFFOLDS`` faq/team gate. ecommerce-lite
# qualifies because it ships ``/kontakt`` as a scaffold-default route and its
# ``render_contact`` injects ``<ResendContactForm>`` when the hard Dossier is
# mounted, so the targeted render diffs ``app/kontakt/page.tsx`` honestly.
CONTACT_FORM_VISIBLE_SCAFFOLDS: frozenset[str] = frozenset({"ecommerce-lite"})

# Capability slug -> inline section placement (ADR 0038, the section_builder's
# VISIBLE in-page render path). A mounted section capability listed here is
# turned into a ``directives.mountedSections`` entry so the renderer injects the
# section INLINE as a block on an existing route, instead of staying mount-only
# or surfacing a whole dedicated route. ``sectionId`` is the id of an existing
# ``render_section_*`` renderer (registered in
# ``packages/generation/build/dispatcher.py``) so no new renderer is invented;
# ``routeId`` is the logical route the block lands on.
#
# Honesty is enforced at RENDER time (the renderer drops an id with no registered
# renderer, an id already in the route's order, and a section whose renderer
# returns no grounded content), so this map only declares WHERE a section CAN go
# - never that it WILL render. The build's deterministic file-diff owns
# ``appliedVisibleEffect``.
#
# Only scaffolds in ``INLINE_SECTION_SCAFFOLDS`` get inline placements (slice 1:
# local-service-business; slice 4 / ADR 0042: + ecommerce-lite). On any other
# scaffold a section_add stays honestly mount-only. Kept narrow on purpose:
# ``hours`` is the slice-1 type because it had NO visible path before (it was
# mount-only) AND its renderer (``render_section_hours_summary``) emits a
# self-contained, grounded home ``<section>``. ``gallery`` is the slice-4 type
# (ADR 0042): its renderer (``render_section_gallery``) is already part of the
# default home order when gallery images exist, so the placement's job is to
# MOVE the section to the operator's explicit position (top/bottom) — the
# renderer treats an already-present section with an explicit position as a
# move, never a duplicate. Capabilities that already reach a VISIBLE dedicated
# route (``faq``/``team`` via ``VISIBLE_SECTION_ROUTES``) are deliberately NOT
# listed here, so they keep their dedicated-page path and are never
# double-surfaced (inline AND as a page). More capabilities join once each has
# a home-compatible ``<section>`` renderer + grounded-content gate.
INLINE_SECTION_PLACEMENTS: dict[str, dict[str, str]] = {
    "hours": {"sectionId": "hours-summary", "routeId": "home"},
    "gallery": {"sectionId": "gallery", "routeId": "home"},
}

# Scaffolds whose home renderer composes its section order from the section list
# (so an injected section actually renders). Mirrors the narrow-gate pattern of
# ``_scaffold_emits_wizard_routes``; kept as an explicit allowlist so a new
# scaffold opts in deliberately rather than inheriting inline injection silently.
# ecommerce-lite qualifies (ADR 0042) because its home goes through the SAME
# ``render_home`` shim as local-service-business (it is not in
# ``_DISPATCHED_SCAFFOLDS``), so the injection seam is already threaded.
INLINE_SECTION_SCAFFOLDS: frozenset[str] = frozenset(
    {"local-service-business", "ecommerce-lite"}
)

# Routes whose renderer reads ``directives.mountedSections`` and injects the
# section inline (slice 1: only ``home`` via ``render_home``). The resolver only
# emits a placement for a wired route, so a section_add can never persist a
# phantom directive for a route no renderer materialises (honesty contract).
# A new route opts in here once its renderer threads the injection seam.
INLINE_SECTION_ROUTES: frozenset[str] = frozenset({"home"})


def _capability_has_grounded_content(capability: str, project_input: dict) -> bool:
    """Honest content gate for a visible section route.

    A visible route is only surfaced when the operator/dossier actually supplies
    the grounded content its renderer reads. With no grounded content the
    section stays mount-only (mounted-but-no-content); the renderer must never
    invent a placeholder section.

    - ``faq-section``: grounded by construction. ``render_faq`` answers a small
      set of generic questions with the dossier's own service areas / opening
      hours (or a grounded blueprint FAQ) and never invents prices or
      warranties, so it always has honest content.
    - ``team-section``: grounded only when ``company.team`` lists at least one
      named member. An empty team would render a dashed "vi fyller på snart"
      placeholder, which is NOT grounded content, so it stays mount-only.
    - ``contact-form`` (B198 del b): grounded only when the implementing hard
      Dossier ``resend-contact-form`` is actually mounted
      (``selectedDossiers.required``). That is the ONLY contact-form variant
      with a visible component today (``render_contact`` injects
      ``<ResendContactForm>`` from the hard-dossier runtime). The mailto default
      has no visible component, so a mailto-only contact-form stays honestly
      mount-only - never a phantom "success with no visible change".
    """
    if capability == "faq-section":
        return True
    if capability == "team-section":
        company = project_input.get("company") if isinstance(project_input, dict) else None
        team = company.get("team") if isinstance(company, dict) else None
        return isinstance(team, list) and any(
            isinstance(member, dict) and str(member.get("name") or "").strip()
            for member in team
        )
    if capability == "contact-form":
        return _resend_contact_form_mounted(project_input)
    return False


def _resend_contact_form_mounted(project_input: dict) -> bool:
    """True when the resend-contact-form hard Dossier is mounted (B198 del b).

    The visible contact-form render path only exists for ``resend-contact-form``
    (``render_contact`` reads it from the hard-dossier runtime). Apply secures a
    named preference in ``selectedDossiers.required`` before this gate runs (step
    5 mounts dossiers, step 5c surfaces visible routes), so the merged next-
    version Project Input already lists ``resend-contact-form`` when the operator
    asked for it. A mailto-only contact-form is NOT mounted here, so it stays
    mount-only.
    """
    if not isinstance(project_input, dict):
        return False
    selected = project_input.get("selectedDossiers")
    required = selected.get("required") if isinstance(selected, dict) else None
    return isinstance(required, list) and "resend-contact-form" in required


def _scaffold_surfaces_capability(capability: str, project_input: dict) -> bool:
    """True when this version's scaffold emits a visible route for ``capability``.

    Two narrow gates, never broadened together:

    - ``contact-form`` (B198 del b) uses the dedicated
      ``CONTACT_FORM_VISIBLE_SCAFFOLDS`` allowlist (today just ecommerce-lite),
      because it surfaces on the scaffold's EXISTING contact route rather than a
      wizard-extra route. Other scaffolds keep contact-form mount-only.
    - every other route-capable capability (faq/team) uses the canonical wizard-
      route scaffold set (``_scaffold_emits_wizard_routes``), unchanged.
    """
    if capability == "contact-form":
        scaffold_id = (
            project_input.get("scaffoldId")
            if isinstance(project_input, dict)
            else None
        )
        return isinstance(scaffold_id, str) and scaffold_id in CONTACT_FORM_VISIBLE_SCAFFOLDS
    return _scaffold_emits_wizard_routes(project_input)


def _scaffold_emits_wizard_routes(project_input: dict) -> bool:
    """True when this version's scaffold actually emits the wizard routes.

    A visible section route is only honest when the scaffold's renderer set
    will emit it. ``produce_site_plan`` emits the wizard ``mustHave`` routes
    only for the scaffolds in ``planning.get_wizard_route_scaffolds()`` (today
    just ``local-service-business``); on any other scaffold (e.g.
    ``agency-studio``) the same ``mustHave`` label stays warning-shape and no
    ``/faq`` or ``/team`` page renders. Surfacing a visible route there would
    write a phantom ``sectionRoutesSurfaced``/``affectedRoutes`` the build never
    materialises - breaking the honesty contract (#221 P2). Gate on the SAME
    canonical scaffold set planning uses, so the two never drift.
    """
    from packages.generation.planning.plan import get_wizard_route_scaffolds

    scaffold_id = project_input.get("scaffoldId") if isinstance(project_input, dict) else None
    return isinstance(scaffold_id, str) and scaffold_id in get_wizard_route_scaffolds()


def resolve_visible_section_pages(
    capabilities: list[str],
    project_input: dict,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split mounted section capabilities into visible-route vs mount-only.

    Returns ``(visible, mount_only)`` where:

    - ``visible`` is ``[{"capability", "wizardLabel", "routeId"}]`` for the
      de-duplicated capabilities that ALL of: have a dedicated visible route
      (``VISIBLE_SECTION_ROUTES``), run on a scaffold that actually emits the
      wizard route (``_scaffold_emits_wizard_routes``) AND carry grounded
      content. Surfacing one makes the targeted render emit a NEW page ->
      honest ``appliedVisibleEffect=true``.
    - ``mount_only`` is ``[{"capability", "reason"}]`` for every mounted
      capability kept mount-only - because it has no dedicated visible route
      yet, the scaffold does not emit wizard routes, or the operator supplied
      no grounded content for it (the honest mounted-but-no-content signal).

    Deterministic, offline, no LLM. ``project_input`` is the merged next-version
    Project Input the apply step is about to write (so the scaffold + grounded-
    content gates reflect exactly what the build will render).
    """
    visible: list[dict[str, str]] = []
    mount_only: list[dict[str, str]] = []
    seen: set[str] = set()
    surfaced_routes: set[str] = set()
    for capability in capabilities:
        if not isinstance(capability, str) or not capability.strip():
            continue
        if capability in seen:
            continue
        seen.add(capability)
        route = VISIBLE_SECTION_ROUTES.get(capability)
        if route is None:
            mount_only.append(
                {
                    "capability": capability,
                    "reason": (
                        f"Capability {capability!r} har ingen dedikerad synlig "
                        "render-väg ännu; sektionen monteras men syns inte (följd)."
                    ),
                }
            )
            continue
        if not _scaffold_surfaces_capability(capability, project_input):
            scaffold_id = (
                project_input.get("scaffoldId")
                if isinstance(project_input, dict)
                else None
            )
            mount_only.append(
                {
                    "capability": capability,
                    "reason": (
                        f"Scaffold {scaffold_id!r} surfar inte capability "
                        f"{capability!r} som synlig route; sektionen monteras men "
                        "ingen synlig route surfas (faq/team surfar bara på "
                        "local-service-business, contact-form bara på "
                        "ecommerce-lite)."
                    ),
                }
            )
            continue
        if not _capability_has_grounded_content(capability, project_input):
            mount_only.append(
                {
                    "capability": capability,
                    "reason": (
                        f"Capability {capability!r} saknar grundat innehåll i "
                        "Project Input (mounted-but-no-content); ingen synlig "
                        "sektion renderas."
                    ),
                }
            )
            continue
        if route["routeId"] in surfaced_routes:
            continue
        surfaced_routes.add(route["routeId"])
        visible.append(
            {
                "capability": capability,
                "wizardLabel": route["wizardLabel"],
                "routeId": route["routeId"],
            }
        )
    return visible, mount_only


def resolve_inline_section_placements(
    capabilities: list[str],
    project_input: dict,
) -> list[dict[str, str]]:
    """Resolve mounted section capabilities to inline ``mountedSections`` entries.

    Returns the de-duplicated ``[{capability, sectionId, routeId}]`` placements
    for the capabilities that BOTH map to an inline section
    (``INLINE_SECTION_PLACEMENTS``) AND run on a scaffold that composes its route
    order from the section list (``INLINE_SECTION_SCAFFOLDS``). Each entry tells
    the renderer to inject the section INLINE as a block on ``routeId`` (ADR
    0038).

    This resolver intentionally does NOT check renderer-registration or grounded
    content: those are render-time concerns owned by the build package (and a
    package-layer must not import the build layer). The renderer drops an entry
    whose ``sectionId`` has no registered renderer, is already present in the
    route's order, or whose section renders empty - so an entry here means the
    section CAN render inline, never that it WILL. Deterministic, offline, no LLM.
    """
    scaffold_id = (
        project_input.get("scaffoldId") if isinstance(project_input, dict) else None
    )
    if not (isinstance(scaffold_id, str) and scaffold_id in INLINE_SECTION_SCAFFOLDS):
        return []
    placements: list[dict[str, str]] = []
    seen: set[str] = set()
    for capability in capabilities:
        if not isinstance(capability, str) or not capability.strip():
            continue
        if capability in seen:
            continue
        seen.add(capability)
        placement = INLINE_SECTION_PLACEMENTS.get(capability)
        if placement is None:
            continue
        # Only emit a placement for a route whose renderer actually injects the
        # section, so a section_add never persists a directive no build renders.
        if placement["routeId"] not in INLINE_SECTION_ROUTES:
            continue
        placements.append(
            {
                "capability": capability,
                "sectionId": placement["sectionId"],
                "routeId": placement["routeId"],
            }
        )
    return placements


# B198 (operatörsfynd 2026-06-11): a follow-up can name a SPECIFIC implementing
# Dossier ("skapa en sektion för min resend-funktion") rather than accepting the
# capability default (mailto). Deterministic prompt-cue lexicon, capability ->
# {dossier id -> cue words}. A cue only ever PREFERS a Dossier that capability-
# map.v1.json already lists for the SAME capability (validated in the resolver),
# so chat can never mount an unregistered/foreign Dossier. Kept narrow on
# purpose: resend-contact-form is the first (and so far only) named alternative.
DOSSIER_PREFERENCE_CUES: dict[str, dict[str, tuple[str, ...]]] = {
    "contact-form": {
        "resend-contact-form": ("resend",),
    },
}


# Negationsord som inom två ord före en cue betyder "INTE den dossiern"
# (extern granskning 2026-06-11, fynd 5: "kontaktformulär men inte resend"
# får aldrig välja resend-dossiern).
_NEGATION_WORDS = ("inte", "utan", "ej", "ingen", "inget", "aldrig", "slopa")


def _word_in_prompt(text: str, phrase: str) -> bool:
    import re

    return (
        re.search(r"(?<![\wåäö])" + re.escape(phrase) + r"(?![\wåäö])", text)
        is not None
    )


def _cue_is_negated(text: str, phrase: str) -> bool:
    """True när cue-ordet föregås av en negation inom två ord.

    Täcker "inte resend", "utan resend(-funktionen)", "ej resend" och
    "ingen/inget resend" med upp till ett mellanliggande ord ("inte någon
    resend"). Medvetet snäv: en negation långt ifrån cue-ordet ska inte
    blockera en i övrigt tydlig preferens.
    """
    import re

    negation = "|".join(_NEGATION_WORDS)
    pattern = (
        rf"(?<![\wåäö])(?:{negation})\s+(?:[\wåäö-]+\s+)?"
        + re.escape(phrase)
        + r"(?![\wåäö])"
    )
    return re.search(pattern, text) is not None


def resolve_dossier_preferences(
    prompt: str,
    capabilities: list[str],
) -> dict[str, str]:
    """Resolve named-Dossier preferences from the follow-up prompt (B198).

    Returns ``{capability: dossier_id}`` for every mounted capability whose
    prompt names a registered alternative Dossier (``DOSSIER_PREFERENCE_CUES``).
    Each candidate is validated against governance before it is returned: the
    Dossier must be listed for that capability in ``capability-map.v1.json``
    AND be enabled in its manifest - otherwise the preference is silently
    dropped and apply falls back to the capability default (the honest
    fallback; chat can never mount an unregistered/disabled Dossier).
    Deterministic, offline, no LLM.
    """
    if not prompt or not capabilities:
        return {}
    from packages.generation.planning import dossier_is_enabled, load_capability_map

    text = prompt.strip().lower()
    capability_entries = (load_capability_map() or {}).get("capabilities", {})
    preferences: dict[str, str] = {}
    for capability in capabilities:
        cues = DOSSIER_PREFERENCE_CUES.get(capability)
        if not cues:
            continue
        entry = capability_entries.get(capability)
        listed = entry.get("dossiers") if isinstance(entry, dict) else None
        listed_ids = listed if isinstance(listed, list) else []
        for dossier_id, words in cues.items():
            matched = [
                word
                for word in words
                if _word_in_prompt(text, word)
            ]
            if not matched:
                continue
            # Negationsguard (fynd 5): "kontaktformulär men inte resend" ska
            # behålla defaulten - en negerad cue räknas inte som preferens.
            if all(_cue_is_negated(text, word) for word in matched):
                continue
            if dossier_id not in listed_ids:
                continue
            if not dossier_is_enabled(dossier_id):
                continue
            preferences[capability] = dossier_id
            break
    return preferences


def resolve_section_capabilities(
    section_types: list[str | None],
) -> tuple[list[str], list[dict[str, str]]]:
    """Resolve sanctioned section types to mountable capabilities.

    Returns ``(capabilities, unsupported)`` where ``capabilities`` are the
    de-duplicated capability slugs that map to a sanctioned type AND have an
    implementing Dossier in ``capability-map.v1.json`` (so apply can mount them),
    and ``unsupported`` is ``[{"type": ..., "reason": ...}]`` for every requested
    type that is unknown or whose capability has no implementing Dossier - the
    honest no-op signal. Deterministic, offline, no LLM.
    """
    from packages.generation.planning import filter_capabilities, load_capability_map

    capability_map = load_capability_map()
    capabilities: list[str] = []
    unsupported: list[dict[str, str]] = []
    seen: set[str] = set()
    for section_type in section_types:
        if not section_type:
            unsupported.append(
                {
                    "type": "(okänd)",
                    "reason": (
                        "Ingen igenkänd sektionstyp i prompten; sanktionerade "
                        f"MVP-typer är {_SANCTIONED}."
                    ),
                }
            )
            continue
        if section_type in seen:
            continue
        seen.add(section_type)
        capability = SECTION_TYPE_CAPABILITY.get(section_type)
        if capability is None:
            unsupported.append(
                {
                    "type": section_type,
                    "reason": (
                        f"Sektionstypen {section_type!r} är inte sanktionerad i "
                        f"MVP ({_SANCTIONED})."
                    ),
                }
            )
            continue
        selected, _rejected = filter_capabilities([capability], capability_map)
        if not selected:
            unsupported.append(
                {
                    "type": section_type,
                    "reason": (
                        f"Capability {capability!r} saknar implementerande "
                        "dossier i capability-map.v1.json; ingen sektion monteras."
                    ),
                }
            )
            continue
        if capability not in capabilities:
            capabilities.append(capability)
    return capabilities, unsupported
