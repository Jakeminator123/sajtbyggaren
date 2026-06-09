"""Wizard capability slugs vs capability-map: contract lock.

Review finding (2026-06-09, msg-0056/msg-0057 follow-up): the wizard's
``FUNCTION_GROUPS`` (apps/viewser/components/discovery-wizard/
wizard-constants.ts) sends capability slugs in the ``selectedFunctions``
payload, but only SOME were canonical ``capability-map.v1.json`` keys. A
non-canonical slug that the resolver's alias table also misses lands as
capability-unknown noise in operator review.

This file locks the contract from the Python side: every ``capability:``
value in FUNCTION_GROUPS must either (a) normalize (via
``normalize_capability_slug``) to a canonical capability-map key, or (b) be
listed in the explicit, documented ``KNOWN_UNMAPPED`` set below. Adding a new
wizard function with an unknown slug fails here until it is either aliased,
added to the capability-map, or deliberately registered as unmapped.

Deterministic, offline: reads the TS source with a regex (same source-lock
pattern as tests/test_viewser_files.py) and the governance policy JSON.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.discovery.resolve import (  # noqa: E402
    normalize_capability_slug,
)

_WIZARD_CONSTANTS = (
    REPO_ROOT
    / "apps"
    / "viewser"
    / "components"
    / "discovery-wizard"
    / "wizard-constants.ts"
)
_CAPABILITY_MAP = (
    REPO_ROOT / "governance" / "policies" / "capability-map.v1.json"
)

# Wizard functions whose slug deliberately has NO capability-map home yet.
# Each entry is a conscious product decision, not an oversight: the resolver
# reports them as capability-unknown/-gap so Backoffice sees the wish, and a
# future slice either adds the capability to the map or an alias above.
# user-auth stays unmapped ON PURPOSE: auth/billing is scope-gated by
# ADR 0035 and must not silently resolve to the gated ``auth`` capability.
KNOWN_UNMAPPED: frozenset[str] = frozenset(
    {
        "about-page",
        "blog",
        "checkout-flow",
        "click-to-call",
        "customer-portal",
        "inventory-display",
        "live-chat",
        "multi-language",
        "online-ordering",
        "product-catalog",
        "product-reviews",
        "quote-request",
        "scroll-animations",
        "shopping-cart",
        "table-reservation",
        "user-auth",
    }
)


def _wizard_capabilities() -> set[str]:
    text = _WIZARD_CONSTANTS.read_text(encoding="utf-8")
    return set(re.findall(r'capability:\s*"([a-z0-9-]+)"', text))


def _capability_map_keys() -> set[str]:
    payload = json.loads(_CAPABILITY_MAP.read_text(encoding="utf-8"))
    capabilities = payload.get("capabilities", payload)
    assert isinstance(capabilities, dict)
    return set(capabilities.keys())


def test_every_wizard_capability_is_canonical_aliased_or_known_unmapped() -> None:
    """The contract: no wizard slug may silently miss both the map and the
    alias table without being a documented, deliberate gap."""
    wizard = _wizard_capabilities()
    assert wizard, "no capability slugs found - did wizard-constants.ts move?"
    canonical = _capability_map_keys()

    unexplained: dict[str, str] = {}
    for slug in sorted(wizard):
        normalized = normalize_capability_slug(slug)
        if normalized in canonical:
            continue
        if slug in KNOWN_UNMAPPED:
            continue
        unexplained[slug] = normalized
    assert not unexplained, (
        "wizard capability slugs neither resolve to a canonical "
        "capability-map key nor are registered in KNOWN_UNMAPPED: "
        f"{unexplained!r}. Add an alias in packages/generation/discovery/"
        "resolve.py (_CAPABILITY_ALIASES), add the capability to "
        "capability-map.v1.json, or register the gap here deliberately."
    )


def test_known_unmapped_stays_minimal() -> None:
    """KNOWN_UNMAPPED may not silently accumulate entries that HAVE become
    mappable: every entry must still be absent from the capability-map (after
    normalization), so a slug whose capability lands in the map gets promoted
    out of the gap list instead of lingering."""
    canonical = _capability_map_keys()
    stale = {
        slug
        for slug in KNOWN_UNMAPPED
        if normalize_capability_slug(slug) in canonical
    }
    assert not stale, (
        f"KNOWN_UNMAPPED entries now resolve to canonical capabilities: "
        f"{sorted(stale)!r} - remove them from KNOWN_UNMAPPED."
    )


def test_display_aliases_resolve_to_canonical() -> None:
    """The wizard's legacy *-display/embed slugs (msg-0056 point 3) must keep
    resolving to canonical capability-map keys via the alias table."""
    canonical = _capability_map_keys()
    for legacy, expected in {
        "menu-display": "menu",
        "team-display": "team-section",
        "reviews-display": "reviews",
        "image-gallery": "gallery",
        "pricing-display": "pricing",
        "map-embed": "location",
        "opening-hours": "hours",
        "newsletter-signup": "newsletter-subscribe",
        "video-hero": "hero-video",
    }.items():
        assert normalize_capability_slug(legacy) == expected, legacy
        assert expected in canonical, expected
