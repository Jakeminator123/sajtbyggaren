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

__all__ = ["SECTION_TYPE_CAPABILITY", "resolve_section_capabilities"]

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
