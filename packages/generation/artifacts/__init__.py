"""Engine Run artefakt utilities.

Single home for jsonschema validation of canonical artefakts written under
``data/runs/<runId>/``. Both ``scripts/build_site.py`` and
``scripts/dev_generate.py`` go through this module so they cannot drift
apart on field shapes (the bug ADR 0013 was written to prevent).
"""

from .validate import (
    SCHEMAS,
    ArtifactSchemaError,
    load_schema,
    validate_artifact,
    validate_generation_package,
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
    "validate_scaffold",
    "validate_sections",
    "validate_site_brief",
    "validate_site_plan",
]
