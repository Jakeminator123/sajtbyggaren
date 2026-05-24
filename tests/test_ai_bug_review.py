"""Tests for the GitHub Actions AI bug review helper."""

from __future__ import annotations

import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.ai_bug_review import (  # noqa: E402
    COMMENT_MARKER,
    MAX_DIFF_CHARS,
    Finding,
    extract_json_array,
    normalize_findings,
    render_markdown,
    run_openai_review,
    truncate_diff,
)


def test_extract_json_array_accepts_fenced_json() -> None:
    raw = """```json
[
  {
    "title": "Wrong site target",
    "file": "apps/viewser/app/page.tsx",
    "probability_percent": 97,
    "impact_score": 9,
    "comment": "Fallback can select the wrong generated site."
  }
]
```"""

    parsed = extract_json_array(raw)

    assert parsed[0]["title"] == "Wrong site target"


def test_normalize_findings_clamps_numeric_ranges() -> None:
    findings = normalize_findings(
        [
            {
                "title": "Risk",
                "file": "scripts/build_site.py",
                "probability_percent": 125,
                "impact_score": 99,
                "comment": "The score should be clamped.",
            }
        ]
    )

    assert findings == [
        Finding(
            title="Risk",
            file="scripts/build_site.py",
            probability_percent=100,
            impact_score=10,
            comment="The score should be clamped.",
        )
    ]


def test_render_markdown_includes_marker_and_table() -> None:
    markdown = render_markdown(
        [
            Finding(
                title="Builder mode can target wrong site",
                file="apps/viewser/app/page.tsx",
                probability_percent=97,
                impact_score=9,
                comment="Falls back to selectedSiteId when run.siteId is unknown.",
            )
        ]
    )

    assert COMMENT_MARKER in markdown
    assert "| Title | File | Probability | Impact | Comment |" in markdown
    assert "`apps/viewser/app/page.tsx`" in markdown
    assert "97%" in markdown


def test_truncate_diff_marks_large_diff() -> None:
    diff = "x" * (MAX_DIFF_CHARS + 1)

    truncated, was_truncated = truncate_diff(diff)

    assert len(truncated) == MAX_DIFF_CHARS
    assert was_truncated is True


def test_run_openai_review_uses_configured_model(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        message = types.SimpleNamespace(content="[]")
        choice = types.SimpleNamespace(message=message)
        return types.SimpleNamespace(choices=[choice])

    def fake_openai(*, api_key: str):
        calls.append({"api_key": api_key})
        return types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=fake_create)
            )
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_REVIEW_MODEL", "gpt-test-review")
    monkeypatch.setitem(
        sys.modules,
        "openai",
        types.SimpleNamespace(OpenAI=fake_openai),
    )

    raw = run_openai_review("review this diff")

    assert raw == "[]"
    assert calls[0] == {"api_key": "test-key"}
    assert calls[1]["model"] == "gpt-test-review"
