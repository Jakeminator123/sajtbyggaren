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
    "SECTION_TYPE_CAPABILITY",
    "VISIBLE_SECTION_ROUTES",
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
VISIBLE_SECTION_ROUTES: dict[str, dict[str, str]] = {
    "faq-section": {"wizardLabel": "FAQ", "routeId": "faq"},
    "team-section": {"wizardLabel": "Vårt team", "routeId": "team"},
}


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
    return False


def resolve_visible_section_pages(
    capabilities: list[str],
    project_input: dict,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split mounted section capabilities into visible-route vs mount-only.

    Returns ``(visible, mount_only)`` where:

    - ``visible`` is ``[{"capability", "wizardLabel", "routeId"}]`` for the
      de-duplicated capabilities that BOTH have a dedicated visible route
      (``VISIBLE_SECTION_ROUTES``) AND carry grounded content. Surfacing one
      makes the targeted render emit a NEW page -> honest
      ``appliedVisibleEffect=true``.
    - ``mount_only`` is ``[{"capability", "reason"}]`` for every mounted
      capability kept mount-only - either because it has no dedicated visible
      route yet, or because the operator supplied no grounded content for it
      (the honest mounted-but-no-content signal).

    Deterministic, offline, no LLM. ``project_input`` is the merged next-version
    Project Input the apply step is about to write (so the grounded-content gate
    reflects exactly what the build will render).
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
