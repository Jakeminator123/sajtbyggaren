"""Guards for Viewser's canonical prompt surface.

Prompt-till-sajt MVP v1 introduced PromptBuilder as the operator-facing
prompt -> Project Input -> build_site.py path. The old ChatPanel remains
as a component for now, but must not be mounted as the primary prompt
surface on the Viewser home page.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGE_PATH = REPO_ROOT / "apps" / "viewser" / "app" / "page.tsx"


@pytest.mark.tooling
def test_prompt_builder_is_primary_home_prompt_surface() -> None:
    text = PAGE_PATH.read_text(encoding="utf-8")

    assert "PromptBuilder" in text, (
        "Viewser home page must mount PromptBuilder as the canonical "
        "prompt -> site flow."
    )
    assert 'from "@/components/chat-panel"' not in text, (
        "ChatPanel must not be imported by app/page.tsx. It is the old "
        "experimental chat surface and should not compete with PromptBuilder."
    )
    assert "<ChatPanel" not in text, (
        "ChatPanel must not be mounted on the Viewser home page. "
        "PromptBuilder is the primary prompt surface."
    )
