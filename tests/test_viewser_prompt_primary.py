"""Guards for Viewser's canonical prompt surface.

Prompt-till-sajt MVP v1 introduced PromptBuilder as the operator-facing
prompt -> Project Input -> build_site.py path. The legacy ChatPanel was
removed entirely in the B46 audit-fix (2026-05-14); these guards lock
that PromptBuilder remains the canonical prompt surface and that no
restored ChatPanel can sneak in via app/page.tsx without tripping the
test.
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
        "ChatPanel was deleted in the B46 audit-fix; no app file may "
        "re-introduce the import without restoring the component plus "
        "the false-success surface that came with it."
    )
    assert "<ChatPanel" not in text, (
        "ChatPanel was deleted in the B46 audit-fix; PromptBuilder is "
        "the only operator-facing prompt surface on the Viewser home page."
    )
