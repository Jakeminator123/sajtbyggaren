"""Mechanical fix implementations for Repair Pipeline.

Each module under this package implements ONE registered fix from
``governance/policies/fix-registry.v1.json:mechanicalFixes``. The
registry is the contract; the modules are the implementation.

Sprint 3B v1 ships a single fix:

- ``ensure_default_export`` (registry id ``ensure-default-export``,
  stage ``post-codegen``, priority 20, ``onFailure="abort-pipeline"``).
  Mirrors the registry entry verbatim; modifying behaviour without
  updating the registry breaks the contract that
  ``packages/generation/repair/repair.py:run_repair_pipeline`` enforces.

The dispatch list ``MECHANICAL_FIXES`` is what
``run_repair_pipeline`` iterates over. New fixes land here AND in the
registry; tests verify both halves stay in sync.
"""

from .ensure_default_export import ENSURE_DEFAULT_EXPORT_SPEC, MechanicalFixSpec

MECHANICAL_FIXES: list[MechanicalFixSpec] = [
    ENSURE_DEFAULT_EXPORT_SPEC,
]

__all__ = [
    "ENSURE_DEFAULT_EXPORT_SPEC",
    "MECHANICAL_FIXES",
    "MechanicalFixSpec",
]
