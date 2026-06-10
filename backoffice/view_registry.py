"""Canonical registry of backoffice sections and views.

Single source of truth for *which* views exist and *in which* section. Both
``backoffice.py`` (the sidebar navigation) and the governance lock
(``governance/policies/backoffice-views.v1.json`` +
``tests/test_backoffice_registry.py``) read from here, so a view can never be
added to the UI without a matching, machine-verified policy entry.

This module is intentionally free of side effects at import time (no
``st.set_page_config`` call) so tests can import it without spinning up the
Streamlit page. Importing the view modules only defines functions; it does not
render anything.
"""

from __future__ import annotations

from collections.abc import Callable

from backoffice.views import (
    building_blocks,
    engine_runs,
    evals,
    governance,
    identity,
    llm_engine,
    maintenance,
    playground,
    status,
)

# Section label -> owning view module. This is the source the sidebar and the
# governance lock both derive from; ``ownerSource`` in the policy must match
# each module's dotted ``__name__``.
SECTION_MODULES = {
    "Status": status,
    "Governance": governance,
    "Identitet": identity,
    "LLM Engine": llm_engine,
    "Building Blocks": building_blocks,
    "Runs": engine_runs,
    "Playground": playground,
    "Evals": evals,
    "Underhåll": maintenance,
}

# Section label -> {view label: render callable}. Built from the modules so it
# can never drift from what the modules actually expose.
SECTIONS: dict[str, dict[str, Callable[[], None]]] = {
    label: module.VIEWS for label, module in SECTION_MODULES.items()
}


def iter_views() -> list[tuple[str, str]]:
    """Yield ``(section, view)`` pairs for every registered view."""
    pairs: list[tuple[str, str]] = []
    for section, views in SECTIONS.items():
        for name in views:
            pairs.append((section, name))
    return pairs
