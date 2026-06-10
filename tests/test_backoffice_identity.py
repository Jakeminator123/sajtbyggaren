"""ADR 0044: the Backoffice "Identitet (SOUL)" view (source + registry locks).

The view lets the operator read/edit the conductor constitution
(``docs/openclaw-workspace/SOUL.md``) and read TOOLS.md read-only. The hard
security rails are pinned here:

- the editor writes ONLY SOUL.md (a path lock — no free filesystem write, no
  path input from the UI),
- a max-length + empty-text guard runs before any write,
- TOOLS.md is never written from the UI,
- the operator is warned the change affects every site's chat persona,
- the view is registered in the governance view registry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
IDENTITY_PY = REPO_ROOT / "backoffice" / "views" / "identity.py"
POLICY_PATH = REPO_ROOT / "governance" / "policies" / "backoffice-views.v1.json"


@pytest.mark.tooling
def test_identity_view_is_registered_in_module() -> None:
    from backoffice.views import identity

    assert "Identitet (SOUL)" in identity.VIEWS
    assert callable(identity.VIEWS["Identitet (SOUL)"])


@pytest.mark.tooling
def test_identity_paths_are_locked_to_openclaw_workspace() -> None:
    """SOUL_PATH/TOOLS_PATH must resolve under docs/openclaw-workspace/."""
    from backoffice.views import identity

    workspace = REPO_ROOT / "docs" / "openclaw-workspace"
    assert identity.SOUL_PATH == workspace / "SOUL.md"
    assert identity.TOOLS_PATH == workspace / "TOOLS.md"


@pytest.mark.tooling
def test_editor_writes_only_soul_md_path_locked() -> None:
    """PATH LOCK: the only write target is SOUL_PATH. There must be no write to
    TOOLS_PATH and no free-form path input that could redirect the write."""
    text = IDENTITY_PY.read_text(encoding="utf-8")

    assert "atomic_write_text(SOUL_PATH" in text, (
        "identity.py must write SOUL.md via the path-locked SOUL_PATH constant."
    )
    assert "atomic_write_text(TOOLS_PATH" not in text, (
        "identity.py must never write TOOLS.md — TOOLS is read-only."
    )
    # No free-form path input from the UI (the write target is a constant, not
    # operator-supplied), so a crafted label can never redirect the write.
    assert "st.text_input" not in text, (
        "identity.py must not expose a free path input — the write target is "
        "path-locked to SOUL_PATH."
    )


@pytest.mark.tooling
def test_editor_enforces_max_length_and_non_empty() -> None:
    text = IDENTITY_PY.read_text(encoding="utf-8")

    assert "SOUL_MAX_CHARS" in text and "len(new_text) > SOUL_MAX_CHARS" in text, (
        "identity.py must reject SOUL text over SOUL_MAX_CHARS before writing."
    )
    assert "för lång" in text, (
        "identity.py must surface a Swedish 'för lång' error on over-length input."
    )
    assert "not new_text.strip()" in text, (
        "identity.py must reject empty SOUL text before writing."
    )


@pytest.mark.tooling
def test_editor_warns_change_affects_all_sites() -> None:
    text = IDENTITY_PY.read_text(encoding="utf-8")

    assert "st.warning(" in text, "identity.py must show a warning before editing."
    assert "ALLA sajter" in text, (
        "identity.py must warn that the edit affects the chat persona for ALL "
        "sites."
    )
    # No git commit from the UI — the operator commits as usual.
    assert "Ingen git-commit" in text or "ingen git-commit" in text.lower(), (
        "identity.py must state that no git commit happens from the UI."
    )


@pytest.mark.tooling
def test_tools_is_rendered_read_only() -> None:
    text = IDENTITY_PY.read_text(encoding="utf-8")

    assert "TOOLS_PATH.read_text(" in text, (
        "identity.py must read TOOLS.md to render it read-only."
    )
    assert "read-only" in text, (
        "identity.py must label the TOOLS view as read-only."
    )


@pytest.mark.governance
def test_identity_view_registered_in_policy() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert "Identitet" in policy["sections"]
    entry = next(
        (e for e in policy["views"] if e["view"] == "Identitet (SOUL)"), None
    )
    assert entry is not None, "Identitet (SOUL) must be registered in the policy."
    assert entry["section"] == "Identitet"
    assert entry["ownerSource"] == "backoffice.views.identity"
    assert entry["readsFrom"] == ["docs/openclaw-workspace"]
