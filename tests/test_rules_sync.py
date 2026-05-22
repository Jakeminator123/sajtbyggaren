"""Verify that .cursor/rules/ is in sync with governance/rules/.

The mirror is the only acceptable state. Direct edits to .cursor/rules/
must be detected by this test.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from scripts.rules_sync import _rewrite_link_target, rewrite_links_for_mirror

from .conftest import CURSOR_RULES_DIR, REPO_ROOT, RULES_DIR, SCRIPTS_DIR


@pytest.mark.governance
@pytest.mark.tooling
def test_rules_sync_check_exits_zero():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "rules_sync.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        "rules_sync.py --check failed:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.mark.governance
def test_every_rule_has_a_mirror():
    sources = {p.stem for p in RULES_DIR.glob("*.md")}
    mirrors = {p.stem for p in CURSOR_RULES_DIR.glob("*.mdc")}
    missing = sources - mirrors
    extra = mirrors - sources
    assert not missing, f"Sources missing mirror in .cursor/rules: {sorted(missing)}"
    assert not extra, (
        "Mirror files in .cursor/rules without source in governance/rules: "
        f"{sorted(extra)}"
    )


# ---------------------------------------------------------------------------
# Link rewriting (governance/rules/ depth -> .cursor/rules/ depth)
# ---------------------------------------------------------------------------


@pytest.mark.governance
@pytest.mark.parametrize(
    "source,expected",
    [
        ("../policies/naming-dictionary.v1.json", "../../governance/policies/naming-dictionary.v1.json"),
        ("../schemas/discovery-taxonomy.schema.json", "../../governance/schemas/discovery-taxonomy.schema.json"),
        ("../decisions/0025-browser-fallback-preview.md", "../../governance/decisions/0025-browser-fallback-preview.md"),
        ("../policies/", "../../governance/policies/"),
    ],
)
def test_rewrite_parent_relative_links_point_into_governance(
    source: str, expected: str
) -> None:
    assert _rewrite_link_target(source) == expected


@pytest.mark.governance
@pytest.mark.parametrize(
    "source,expected",
    [
        ("term-discipline.md", "term-discipline.mdc"),
        ("always-swedish.md", "always-swedish.mdc"),
        ("term-discipline.md#headline", "term-discipline.mdc#headline"),
    ],
)
def test_rewrite_sibling_md_links_use_mdc_extension(
    source: str, expected: str
) -> None:
    assert _rewrite_link_target(source) == expected


@pytest.mark.governance
@pytest.mark.parametrize(
    "untouched",
    [
        "https://example.com/path",
        "http://localhost:3000",
        "mailto:operator@example.com",
        "tel:+46123",
        "#section-anchor",
        "/governance/policies/file.json",
        "../../already-deep/file.md",
        "sibling-without-md-extension",
    ],
)
def test_rewrite_leaves_absolute_and_already_deep_links_untouched(
    untouched: str,
) -> None:
    assert _rewrite_link_target(untouched) == untouched


@pytest.mark.governance
def test_rewrite_preserves_anchor_on_parent_relative_link() -> None:
    source = "../policies/naming-dictionary.v1.json#term-discovery-taxonomy"
    expected = "../../governance/policies/naming-dictionary.v1.json#term-discovery-taxonomy"
    assert _rewrite_link_target(source) == expected


@pytest.mark.governance
def test_rewrite_links_for_mirror_handles_full_paragraph() -> None:
    source = (
        "Se [`naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json) "
        "och [`term-discipline.md`](term-discipline.md) för canonical termer. "
        "Bilder: ![alt](logo.png) ska inte röras."
    )
    rewritten = rewrite_links_for_mirror(source)

    assert "(../../governance/policies/naming-dictionary.v1.json)" in rewritten
    assert "(term-discipline.mdc)" in rewritten
    assert "![alt](logo.png)" in rewritten  # bild-länkar ska inte röras


@pytest.mark.governance
def test_mirror_does_not_contain_broken_parent_dot_dot_policies_link() -> None:
    """Regression-lock för operator-rapporterad lint-varning 2026-05-22.

    Det fula mönstret var att källans ``../policies/...`` syntes ordagrant
    i ``.cursor/rules/*.mdc``, vilket resolverade till ``.cursor/policies/``
    och triggade markdown-link-validatorn. Efter rewriten ska inget ``mdc``-
    file innehålla en bare ``(../policies/`` eller ``(../schemas/`` eller
    ``(../decisions/`` referens.
    """
    bad_prefixes = ("(../policies/", "(../schemas/", "(../decisions/")
    for mirror_path in CURSOR_RULES_DIR.glob("*.mdc"):
        text = mirror_path.read_text(encoding="utf-8")
        for prefix in bad_prefixes:
            assert prefix not in text, (
                f"{mirror_path.relative_to(REPO_ROOT)} innehåller fortfarande "
                f"{prefix!r}. Kör 'python scripts/rules_sync.py' så skriver "
                "rewritern om länken automatiskt."
            )
