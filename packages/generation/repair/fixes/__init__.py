"""Mechanical fix implementations for Repair Pipeline.

Relation to the registry
------------------------
``governance/policies/fix-registry.v1.json:mechanicalFixes`` is the
authoritative spec - it lists EVERY mechanical fix that may run, with
stage / priority / onFailure / idempotent metadata. This package is
the IMPLEMENTATION SUBSET: each module here implements ONE registered
fix that Sprint 3B has actually wired into the dispatcher.

The registry is the contract; the dispatch list ``MECHANICAL_FIXES``
below is what ``packages/generation/repair/repair.py`` actually runs.
The two are NOT identical; the registry is a superset of the
implemented fixes by design (Sprint 3B v1 ships 1 of 8 mechanical
fixes; the rest are pluggable via the same dispatcher when later
sprints add them). Tests assert:

- Every entry in ``MECHANICAL_FIXES`` corresponds to a registry entry
  (no rogue fixes).
- For every implemented fix, the ``MechanicalFixSpec`` mirrors the
  registry entry byte-for-byte (id, stage, priority, idempotent,
  onFailure).
- ``unimplemented_registry_fixes()`` returns the list of registry ids
  that lack an implementation, so audit + Backoffice can surface "we
  declared this fix in policy but have not wired it yet".

Sprint 3B v1.1 implements:

- ``ensure_default_export`` (registry id ``ensure-default-export``,
  stage ``post-codegen``, priority 20, idempotent,
  ``onFailure="skip-and-log"``).
"""

from __future__ import annotations

import json
from pathlib import Path

from .ensure_default_export import ENSURE_DEFAULT_EXPORT_SPEC, MechanicalFixSpec

MECHANICAL_FIXES: list[MechanicalFixSpec] = [
    ENSURE_DEFAULT_EXPORT_SPEC,
]

_FIX_REGISTRY_PATH = (
    Path(__file__).resolve().parents[4]
    / "governance"
    / "policies"
    / "fix-registry.v1.json"
)


def _registry_mechanical_fix_ids() -> list[str]:
    """Read fix-registry.v1.json once and return all registered
    mechanical-fix ids. Used by audit + tests."""
    data = json.loads(_FIX_REGISTRY_PATH.read_text(encoding="utf-8"))
    return [entry["id"] for entry in data.get("mechanicalFixes", [])]


def unimplemented_registry_fixes() -> list[str]:
    """Return registry mechanical-fix ids that have no
    ``MechanicalFixSpec`` implementation yet. Sprint 3B v1.1 has 7 of 8
    here; later sprints shrink this list as fixes are wired.

    Backoffice can call this to render a "registry coverage" view, and
    tests use it to lock the explicit subset relationship (see
    ``tests/test_repair_fixes.py``).
    """
    implemented = {spec.fix_id for spec in MECHANICAL_FIXES}
    return [fid for fid in _registry_mechanical_fix_ids() if fid not in implemented]


__all__ = [
    "ENSURE_DEFAULT_EXPORT_SPEC",
    "MECHANICAL_FIXES",
    "MechanicalFixSpec",
    "unimplemented_registry_fixes",
]
