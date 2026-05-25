"""Regression tests for GitHub Actions workflow wiring."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "governance.yml"
STEWARD_AUTO_BUMP_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "steward-auto-bump.yml"


def test_governance_workflow_limits_push_branches() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'branches: ["**"]' not in workflow
    assert "      - main\n      - jakob-be" in workflow


def test_ai_bug_review_is_a_dedicated_pr_check() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    ai_job = workflow.split("  ai-bug-review:", maxsplit=1)[1]
    governance_job = workflow.split("  builder-smoke:", maxsplit=1)[0]

    assert "    if: github.event_name == 'pull_request'" in ai_job
    assert "      issues: write" in ai_job
    assert "      pull-requests: write" in ai_job
    assert "python scripts/ai_bug_review.py" in ai_job
    assert "python scripts/ai_bug_review.py" not in governance_job


def test_steward_auto_bump_is_intentionally_main_only() -> None:
    workflow = STEWARD_AUTO_BUMP_WORKFLOW.read_text(encoding="utf-8")

    assert "github.event.pull_request.base.ref == 'main'" in workflow
    assert "HEAD:main" in workflow
    assert "python-version: \"3.12\"" in workflow
    assert "base.ref == 'jakob-be'" not in workflow
