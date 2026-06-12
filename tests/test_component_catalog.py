"""Tests for the Component Catalog reads + scaffold->starter map (ADR 0040 l3).

Locks the in-bounds catalog helpers the /faq renderer uses:

1. ``SCAFFOLD_STARTER_MAP`` is non-empty and maps local-service-business ->
   marketing-base; ``plan.SCAFFOLD_TO_STARTER`` is the SAME object (re-export).
2. ``capability_components`` reads the capability-map ``components`` key.
3. ``starter_component_names`` reads a Starter's component-manifest.
4. ``faq_accordion_component_available`` is per-build precise: True for a
   scaffold whose Starter vendors accordion, False for an unknown scaffold and
   False for a Starter that does NOT vendor accordion (the honesty requirement -
   never a union over all Starters).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.policies import component_catalog as cc  # noqa: E402

pytestmark = pytest.mark.tooling


def test_scaffold_starter_map_is_canonical_and_reexported() -> None:
    assert cc.SCAFFOLD_STARTER_MAP, "map must be non-empty"
    assert cc.SCAFFOLD_STARTER_MAP["local-service-business"] == "marketing-base"
    from packages.generation.planning import SCAFFOLD_TO_STARTER

    # plan.py re-exports the SAME object - single source of truth.
    assert SCAFFOLD_TO_STARTER is cc.SCAFFOLD_STARTER_MAP


def test_starter_for_scaffold() -> None:
    assert cc.starter_for_scaffold("local-service-business") == "marketing-base"
    assert cc.starter_for_scaffold("nope") is None
    assert cc.starter_for_scaffold(None) is None
    assert cc.starter_for_scaffold("") is None


def test_capability_components_reads_faq_section() -> None:
    assert "accordion" in cc.capability_components("faq-section")
    # Unknown capability -> empty list, never raises.
    assert cc.capability_components("does-not-exist") == []


def test_starter_component_names_reads_manifest() -> None:
    names = cc.starter_component_names("marketing-base")
    assert "accordion" in names
    # commerce-base has no components/ui -> empty inventory (ADR 0040).
    assert "accordion" not in cc.starter_component_names("commerce-base")
    assert cc.starter_component_names("nope") == set()
    assert cc.starter_component_names(None) == set()


def test_faq_accordion_gate_is_per_build_precise() -> None:
    # LSB -> marketing-base vendors accordion + capability-map lists it -> True.
    assert cc.faq_accordion_component_available(
        scaffold_id="local-service-business"
    ) is True
    # Unknown scaffold resolves no starter -> honest native fallback.
    assert cc.faq_accordion_component_available(scaffold_id="nope") is False
    assert cc.faq_accordion_component_available(scaffold_id=None) is False
    # ecommerce-lite -> commerce-base does NOT vendor accordion -> False. This is
    # the honesty requirement: a union over all Starters would wrongly return
    # True and emit a broken import.
    assert cc.faq_accordion_component_available(
        scaffold_id="ecommerce-lite"
    ) is False


def test_faq_accordion_gate_honours_pinned_starter() -> None:
    # An explicitly pinned starter wins over scaffold resolution.
    assert cc.faq_accordion_component_available(
        scaffold_id="ecommerce-lite", starter_id="marketing-base"
    ) is True


def test_faq_accordion_gate_false_when_capability_lacks_component(
    tmp_path: Path,
) -> None:
    """If capability-map does not list accordion for faq-section, gate is False
    even when the Starter vendors it (lager 2 gate)."""
    fake_map = tmp_path / "capability-map.json"
    fake_map.write_text(
        '{"capabilities": {"faq-section": {"dossiers": ["faq-accordion"]}}}',
        encoding="utf-8",
    )
    assert cc.faq_accordion_component_available(
        scaffold_id="local-service-business", capability_map_path=fake_map
    ) is False
