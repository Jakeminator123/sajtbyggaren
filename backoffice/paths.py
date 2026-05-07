"""Filesystem path constants used across the backoffice."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOVERNANCE_DIR = REPO_ROOT / "governance"
POLICIES_DIR = GOVERNANCE_DIR / "policies"
SCHEMAS_DIR = GOVERNANCE_DIR / "schemas"
RULES_DIR = GOVERNANCE_DIR / "rules"
DECISIONS_DIR = GOVERNANCE_DIR / "decisions"
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs"
REFERENS_DIR = REPO_ROOT / "referens"
CURSOR_RULES_DIR = REPO_ROOT / ".cursor" / "rules"
TESTS_DIR = REPO_ROOT / "tests"
