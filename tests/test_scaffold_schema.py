"""Tests for governance/schemas/scaffold.schema.json.

Scaffold files under packages/generation/orchestration/scaffolds/<id>/scaffold.json
all declare this schema via $schema. This test suite ensures that file exists
and that every committed scaffold.json validates against it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.artifacts import ArtifactSchemaError, validate_scaffold

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"


def _scaffold_json_files() -> list[Path]:
    if not SCAFFOLDS_DIR.exists():
        return []
    return sorted(SCAFFOLDS_DIR.glob("*/scaffold.json"))


@pytest.mark.tooling
def test_at_least_one_scaffold_json_exists():
    assert _scaffold_json_files(), "No scaffold.json files found under scaffolds/"


@pytest.mark.tooling
@pytest.mark.parametrize("scaffold_path", _scaffold_json_files(), ids=lambda p: p.parent.name)
def test_committed_scaffold_json_validates(scaffold_path: Path):
    payload = json.loads(scaffold_path.read_text(encoding="utf-8"))
    validate_scaffold(payload)


@pytest.mark.tooling
def test_scaffold_rejects_missing_required_field():
    payload = {
        "id": "demo-scaffold",
        "version": "1.0.0",
        "label": "Demo",
        # description missing
        "buildIntent": ["website"],
        "primaryJobs": ["show value"],
        "defaultPageCount": 1,
        "supportsSinglePage": True,
        "supportsMultiPage": False,
        "supportsAppFeatures": False,
    }
    with pytest.raises(ArtifactSchemaError, match="description"):
        validate_scaffold(payload)
