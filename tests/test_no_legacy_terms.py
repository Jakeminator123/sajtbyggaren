"""Make sure globally-forbidden terms haven't crept into product files.

This test scans .md, .py, .ts and .json under non-reference directories
and refuses any use of a globallyForbidden term that isn't inside an
explicit anti-pattern field (forbiddenTerms, aliasesForbidden, etc.).
"""

from __future__ import annotations

import json
import re

import pytest

from .conftest import REPO_ROOT

# Mirror the product directories the test should scan.
PRODUCT_PATHS = [
    "backoffice.py",
    "scripts",
    "docs",
    "packages",
    "apps",
    "tests",
    "README.md",
]

EXTENSIONS = {".md", ".mdc", ".py", ".ts", ".tsx", ".js", ".jsx", ".json"}
EXCLUDE_DIRS = {
    "node_modules",
    ".next",
    "dist",
    "build",
    "out",
    ".turbo",
    ".generated",
    # Operator-only reference workspace (gitignored) - never scan as product source
    "MIN_IDE",
    "övrigt",
    # Shared Cursor canvases (docs/canvases/) deliberately catalogue forbidden
    # aliases for pedagogy ("say X, not Y" tables) - same treatment as the
    # check_term_coverage exclusion for canvases.
    "canvases",
}

# Files that legitimately mention forbidden terms because their job is to
# verify the terms are removed (regression tests) or document why they are
# removed (cleanup READMEs). Keep this list short and explicit.
EXCLUDE_FILES = {
    "tests/test_naming_consistency.py",
    "packages/generation/orchestration/dossiers/README.md",
    "tests/test_no_legacy_terms.py",
    # Analysis snapshot comparing sajtmaskin (the read-only predecessor repo)
    # with this repo. Quoting sajtmaskin's legacy vocabulary (preview-host,
    # verify-lane) verbatim is the point of the document - it catalogues the
    # anti-lessons behind the forbidden list and must not be paraphrased.
    "docs/reports/sajtmaskin-vs-sajtbyggaren-analys-2026-06-10.md",
}

# Fields whose values are *meant* to list forbidden terms.
ANTI_PATTERN_KEYS = {
    "forbiddenTerms",
    "aliasesForbidden",
    "globallyForbidden",
    "mustNotDo",
    "avoid",
    "limitations",
    "negativeSignals",
}


def _strip_anti_pattern_values(node: object) -> str:
    """Collect text of all values that are NOT under an anti-pattern key."""
    chunks: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ANTI_PATTERN_KEYS:
                continue
            chunks.append(_strip_anti_pattern_values(value))
    elif isinstance(node, list):
        for item in node:
            chunks.append(_strip_anti_pattern_values(item))
    elif isinstance(node, str):
        chunks.append(node)
    return "\n".join(chunks)


def _iter_files():
    for entry in PRODUCT_PATHS:
        path = REPO_ROOT / entry
        if path.is_file():
            yield path
        elif path.is_dir():
            for sub in path.rglob("*"):
                if not sub.is_file():
                    continue
                if sub.suffix not in EXTENSIONS:
                    continue
                rel_parts = sub.relative_to(REPO_ROOT).parts
                if any(part in EXCLUDE_DIRS for part in rel_parts):
                    continue
                rel_posix = sub.relative_to(REPO_ROOT).as_posix()
                if rel_posix in EXCLUDE_FILES:
                    continue
                yield sub


def _load_forbidden() -> list[str]:
    naming = json.loads((REPO_ROOT / "governance" / "policies" / "naming-dictionary.v1.json").read_text(encoding="utf-8"))
    return [w for w in naming.get("globallyForbidden", []) if w]


@pytest.mark.governance
def test_no_legacy_term_used_in_product_files():
    forbidden = _load_forbidden()
    findings: list[str] = []

    # Build word-boundary patterns. Allow surrounding non-letters or string boundaries.
    patterns = {
        word: re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(word)}(?![A-Za-z0-9_-])", flags=re.IGNORECASE)
        for word in forbidden
    }

    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        # For JSON, parse and only check non-anti-pattern values.
        if path.suffix == ".json":
            try:
                data = json.loads(text)
                searchable = _strip_anti_pattern_values(data)
            except json.JSONDecodeError:
                searchable = text
        else:
            searchable = text

        rel = path.relative_to(REPO_ROOT).as_posix()
        for word, pattern in patterns.items():
            if pattern.search(searchable):
                findings.append(f"{rel}: contains forbidden term '{word}'")

    assert not findings, "Legacy forbidden terms found in product files:\n  " + "\n  ".join(findings)
