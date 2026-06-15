"""Regression: backoffice runtime-scaffold-diagnostiken får inte driva från
resolverns auktoritativa register.

BO6: ``_RUNTIME_SCAFFOLD_IDS`` hardkodades tidigare till 2 scaffolds medan
resolverns ``_RUNTIME_SCAFFOLD_HINTS`` har 6 sedan Path B fas 1+2+3a. Listan
speglas nu read-only från resolvern; dessa tester låser set-likheten och att
varje scaffold faktiskt har en ``routes.json`` att peka mot.
"""

from __future__ import annotations

import pytest

from backoffice.discovery_wizard_diagnostics import (
    _RUNTIME_SCAFFOLD_IDS,
    SCAFFOLDS_DIR,
)
from packages.generation.discovery.resolve import _RUNTIME_SCAFFOLD_HINTS

pytestmark = pytest.mark.tooling


def test_backoffice_runtime_scaffold_ids_match_resolver():
    assert set(_RUNTIME_SCAFFOLD_IDS) == set(_RUNTIME_SCAFFOLD_HINTS.keys())
    assert len(_RUNTIME_SCAFFOLD_IDS) == 6  # drift-detektor: bumpa medvetet


def test_backoffice_runtime_scaffold_routes_exist():
    for sid in _RUNTIME_SCAFFOLD_IDS:
        assert (SCAFFOLDS_DIR / sid / "routes.json").exists()
