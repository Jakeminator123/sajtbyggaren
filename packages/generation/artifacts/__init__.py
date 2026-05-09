"""Engine Run artefakt utilities.

Single home for jsonschema validation of canonical artefakts written under
``data/runs/<runId>/``. Both ``scripts/build_site.py`` and
``scripts/dev_generate.py`` go through this module so they cannot drift
apart on field shapes (the bug ADR 0013 was written to prevent).

Sprint 3C-lite (ADR 0017) adds ``validate_quality_result`` and
``validate_repair_result`` so the four-Phase-3-artefakt-shapes
(quality-result.json + repair-result.json) gain the same schema-lock
that the brief / plan / generation-package artefakts already have.
"""

from .validate import (
    SCHEMAS,
    ArtifactSchemaError,
    load_schema,
    validate_artifact,
    validate_generation_package,
    validate_quality_result,
    validate_repair_result,
    validate_scaffold,
    validate_sections,
    validate_site_brief,
    validate_site_plan,
)

__all__ = [
    "ArtifactSchemaError",
    "SCHEMAS",
    "load_schema",
    "validate_artifact",
    "validate_generation_package",
    "validate_quality_result",
    "validate_repair_result",
    "validate_scaffold",
    "validate_sections",
    "validate_site_brief",
    "validate_site_plan",
]
