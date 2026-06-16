"""Tests for the GitHub Actions AI bug review helper."""

from __future__ import annotations

import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.ai_bug_review import (  # noqa: E402
    COMMENT_MARKER,
    DEFAULT_OPENAI_REVIEW_MODEL,
    GITHUB_ACTIONS_BOT_LOGIN,
    MAX_DIFF_CHARS,
    Finding,
    build_prompt,
    collect_diff,
    extract_json_array,
    github_api_get_paginated,
    is_actions_bot_comment,
    normalize_findings,
    post_pr_comment,
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


def test_run_openai_review_defaults_to_gpt_5_4(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        message = types.SimpleNamespace(content="[]")
        choice = types.SimpleNamespace(message=message)
        return types.SimpleNamespace(choices=[choice])

    def fake_openai(*, api_key: str):
        return types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=fake_create)
            )
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_REVIEW_MODEL", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "openai",
        types.SimpleNamespace(OpenAI=fake_openai),
    )

    run_openai_review("review this diff")

    assert DEFAULT_OPENAI_REVIEW_MODEL == "gpt-5.5"
    assert calls[0]["model"] == "gpt-5.5"


def test_build_prompt_includes_repo_specific_review_rules() -> None:
    prompt = build_prompt("diff --git a/x b/x", truncated=False)
    normalized_prompt = " ".join(prompt.split())

    assert "prompt -> small-business website" in normalized_prompt
    assert "direct edits to .cursor/rules instead of governance/rules" in normalized_prompt
    assert "scaffold/dossier/variant/route mapping drift" in normalized_prompt
    assert "preview/build behavior" in normalized_prompt
    assert "Prefer no findings over speculative findings" in normalized_prompt


def test_collect_diff_uses_full_push_range(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_ref_exists(ref: str) -> bool:
        return ref == "before-sha"

    def fake_run_git(args: list[str]) -> str:
        calls.append(args)
        return "diff"

    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setattr("scripts.ai_bug_review.git_ref_exists", fake_ref_exists)
    monkeypatch.setattr("scripts.ai_bug_review.run_git", fake_run_git)

    diff = collect_diff({"before": "before-sha", "after": "after-sha"})

    assert diff == "diff"
    assert calls == [["diff", "before-sha..after-sha"]]


def test_collect_diff_falls_back_when_before_sha_is_missing(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_ref_exists(ref: str) -> bool:
        return ref == "after-sha^"

    def fake_run_git(args: list[str]) -> str:
        calls.append(args)
        return "fallback diff"

    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setattr("scripts.ai_bug_review.git_ref_exists", fake_ref_exists)
    monkeypatch.setattr("scripts.ai_bug_review.run_git", fake_run_git)

    diff = collect_diff({"before": "missing-before", "after": "after-sha"})

    assert diff == "fallback diff"
    assert calls == [["diff", "after-sha^..after-sha"]]


def test_github_api_get_paginated_reads_all_pages(monkeypatch) -> None:
    urls: list[str] = []

    def fake_request(method: str, url: str, token: str, payload=None):
        urls.append(url)
        if url.endswith("page=1"):
            return [{"id": index} for index in range(100)]
        if url.endswith("page=2"):
            return [{"id": 100}]
        return []

    monkeypatch.setattr(
        "scripts.ai_bug_review.github_api_request",
        fake_request,
    )

    comments = github_api_get_paginated("https://api.example/comments", "token")

    assert len(comments) == 101
    assert urls == [
        "https://api.example/comments?per_page=100&page=1",
        "https://api.example/comments?per_page=100&page=2",
    ]


def test_is_actions_bot_comment_requires_actions_bot_user() -> None:
    assert is_actions_bot_comment(
        {"user": {"login": GITHUB_ACTIONS_BOT_LOGIN}}
    )
    assert not is_actions_bot_comment({"user": {"login": "jakob"}})


def test_post_pr_comment_does_not_update_human_marker_comment(monkeypatch) -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []
    event = {"pull_request": {"number": 67}}
    human_comment = {
        "body": COMMENT_MARKER,
        "url": "https://api.example/comments/1",
        "user": {"login": "jakob"},
    }

    def fake_paginated(url: str, token: str):
        return [human_comment]

    def fake_request(
        method: str,
        url: str,
        token: str,
        payload: dict[str, object] | None = None,
    ):
        calls.append((method, url, payload))
        return None

    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_API_URL", "https://api.example")
    monkeypatch.setattr(
        "scripts.ai_bug_review.github_api_get_paginated",
        fake_paginated,
    )
    monkeypatch.setattr("scripts.ai_bug_review.github_api_request", fake_request)

    post_pr_comment(event, "review body")

    assert calls == [
        (
            "POST",
            "https://api.example/repos/owner/repo/issues/67/comments",
            {"body": "review body"},
        )
    ]
