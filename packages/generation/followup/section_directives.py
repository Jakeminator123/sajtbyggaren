"""Follow-up section directives: resolve a sanctioned section_add to a capability.

A ``section_add`` follow-up ("lägg till en sektion om garantier", "lägg till en
FAQ-sektion") is the section_builder role. It adds ONE sanctioned section to the
site by mounting the section's capability through the SAME apply machinery a
``component_add`` already uses (``requestedCapabilities`` +
``selectedDossiers.required``), so the existing dossier mounts and the targeted
render reflects it. No new render path, no new engine - exactly the #207 restyle
pattern, just a capability instead of a theme directive.

Sanctioned MVP types (docs/openclaw-workspace/skills/section-add/SKILL.md):
``team``, ``faq``, ``garantier/trust``, ``recensioner/reviews``. Each maps to a
capability that has an implementing Dossier in ``capability-map.v1.json``
(``faq``/``reviews`` reuse the existing faq-accordion / reviews-display Dossiers;
``team``/``trust`` use the soft instructions-only team-roster / trust-guarantees
Dossiers, rendered by the existing ``render_section_team`` /
``render_section_trust_proof`` renderers).

Honest by construction: an unknown type, or a sanctioned type whose capability has
no implementing Dossier, is reported as ``unsupported`` so the chain can do an
HONEST no-op (it never invents a section). Deterministic, offline, no LLM.

Conventions: identifiers + comments in English (governance/rules/code-in-english.md).
"""

from __future__ import annotations

__all__ = ["SECTION_TYPE_CAPABILITY", "resolve_section_capabilities"]

# Sanctioned section-type slug (router ``componentIntent`` for ``section_add``)
# -> capability slug (``capability-map.v1.json`` key). faq/reviews reuse the
# existing Dossiers; team/trust use the soft instructions-only Dossiers added with
# the section_builder slice, rendered by the existing render_section_* renderers.
SECTION_TYPE_CAPABILITY: dict[str, str] = {
    "faq": "faq-section",
    "reviews": "reviews",
    "team": "team-section",
    "trust": "guarantees",
}

# Sanctioned types, spelled out for the honest "unsupported" reason text.
_SANCTIONED = "team, faq, garantier/trust, recensioner"


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
