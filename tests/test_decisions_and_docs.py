"""Light tests on docs and decisions to avoid silent rot.

We don't validate prose, only structure: decisions are numbered uniquely,
required architecture docs exist, README.md links to expected files.
"""

from __future__ import annotations

import re

import pytest

from .conftest import DECISIONS_DIR, REPO_ROOT


@pytest.mark.governance
def test_decisions_are_uniquely_numbered():
    pattern = re.compile(r"^(\d{4})-")
    numbers: list[str] = []
    for path in DECISIONS_DIR.glob("*.md"):
        match = pattern.match(path.name)
        assert match, f"ADR filename does not start with NNNN-: {path.name}"
        numbers.append(match.group(1))
    duplicates = {n for n in numbers if numbers.count(n) > 1}
    assert not duplicates, f"Duplicate ADR numbers: {sorted(duplicates)}"


@pytest.mark.governance
def test_required_architecture_docs_exist():
    required = [
        "docs/architecture/system-overview.md",
        "docs/architecture/llm-flow.md",
        "docs/architecture/preview-runtime.md",
        "docs/architecture/scaffold-dossier-model.md",
        "docs/migration-plan.md",
        "docs/agent-handbook.md",
        "docs/PROJECT_BRIEF.md",
    ]
    missing = [p for p in required if not (REPO_ROOT / p).exists()]
    assert not missing, f"Required docs missing: {missing}"


@pytest.mark.governance
def test_readme_mentions_governance_first_principle():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    expected_phrases = [
        "Policies styr arkitekturen",
        "governance/",
        "backend.py",
    ]
    missing = [phrase for phrase in expected_phrases if phrase not in text]
    assert not missing, f"README.md missing expected phrases: {missing}"
