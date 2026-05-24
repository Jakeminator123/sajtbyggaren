"""Run an AI bug review for the current GitHub Actions diff.

The script is intentionally CI-friendly:

- it skips cleanly when OPENAI_API_KEY is not configured
- it writes a GitHub step summary for every event
- it posts a sticky PR comment when running on pull_request events

The model is asked to return JSON findings, but the parser tolerates fenced
JSON because model responses can still wrap structured output in markdown.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMENT_MARKER = "<!-- sajtbyggaren-ai-bug-review -->"
GITHUB_ACTIONS_BOT_LOGIN = "github-actions[bot]"
MAX_DIFF_CHARS = 120_000
DEFAULT_OPENAI_REVIEW_MODEL = "gpt-5.4"


@dataclass(frozen=True)
class Finding:
    title: str
    file: str
    probability_percent: int
    impact_score: int
    comment: str


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def git_ref_exists(ref: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}^{{commit}}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def load_event() -> dict[str, Any]:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return {}
    return json.loads(Path(event_path).read_text(encoding="utf-8"))


def github_event_name() -> str:
    return os.environ.get("GITHUB_EVENT_NAME", "")


def collect_diff(event: dict[str, Any]) -> str:
    event_name = github_event_name()
    if event_name == "pull_request":
        base_sha = event["pull_request"]["base"]["sha"]
        head_sha = event["pull_request"]["head"]["sha"]
        return run_git(["diff", f"{base_sha}...{head_sha}"])

    before = event.get("before")
    after = event.get("after") or os.environ.get("GITHUB_SHA", "HEAD")
    if before and not before.startswith("0000000") and git_ref_exists(before):
        return run_git(["diff", f"{before}..{after}"])

    if git_ref_exists(f"{after}^"):
        return run_git(["diff", f"{after}^..{after}"])

    if git_ref_exists("origin/main"):
        return run_git(["diff", f"origin/main...{after}"])

    raise subprocess.CalledProcessError(
        returncode=1,
        cmd=["git", "diff", "<fallback>", after],
        stderr="could not resolve a safe diff base",
    )


def truncate_diff(diff: str) -> tuple[str, bool]:
    if len(diff) <= MAX_DIFF_CHARS:
        return diff, False
    return diff[:MAX_DIFF_CHARS], True


def build_prompt(diff: str, *, truncated: bool) -> str:
    truncation_note = (
        "\nThe diff was truncated because it was too large. Review only the visible diff."
        if truncated
        else ""
    )
    return textwrap.dedent(
        f"""
        You are Sajtbyggaren's AI bug review bot.

        Product context:
        - Sajtbyggaren's core loop is prompt -> small-business website ->
          preview -> follow-up prompt -> new version.
        - The Python layer owns governance, orchestration, planning, codegen,
          quality gates, repair, and deterministic builder tooling.
        - The generated output is a Next.js project; generated sites and run
          artifacts must not leak into normal source changes.

        Review only the changed code in the git diff below. Prioritize concrete
        bugs and regressions that can break the product loop, generated output,
        CI/governance, or PR safety. Do not report style issues, generic
        suggestions, or findings with weak evidence.

        Repo-specific risks to look for:
        - secrets, .env files, generated artifacts, node_modules, .next,
          .generated, or data/runs accidentally entering tracked changes
        - direct edits to .cursor/rules instead of governance/rules
        - scaffold/dossier/variant/route mapping drift that can send the builder
          to the wrong starter, route set, section set, or quality contract
        - hardcoded customer copy or hardcoded routes where scaffold data should
          drive generated output
        - changes that bypass schema validation, term coverage, rules sync,
          quality gates, build status, or repair-pipeline contracts
        - preview/build behavior that can report ready/success for the wrong
          site, wrong run, wrong port, missing asset, or stale artifact
        - GitHub Actions changes that create duplicate noise, unsafe permissions,
          skipped review paths, or branch/PR event drift
        - test changes that hide failures instead of preserving the shipped
          behavior and governance invariants

        Return only a JSON array. Each item must have exactly:
        - title: short English title
        - file: repository-relative path
        - probability_percent: integer 0-100
        - impact_score: integer 1-10
        - comment: one short sentence explaining the risk

        Use probability_percent >= 70 unless the issue is exceptional. Prefer no
        findings over speculative findings. If there are no high-signal findings,
        return [].
        {truncation_note}

        Diff:
        ```diff
        {diff}
        ```
        """
    ).strip()


def run_openai_review(prompt: str) -> str:
    try:
        import openai
    except ModuleNotFoundError as exc:
        raise RuntimeError("openai is not installed") from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_REVIEW_MODEL", DEFAULT_OPENAI_REVIEW_MODEL),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a repo-aware bug review bot for Sajtbyggaren. "
                        "Return only JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI review request failed: {exc}") from exc

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI review returned an empty response")
    return content


def extract_json_array(raw_text: str) -> list[Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if not text.startswith("["):
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end < start:
            raise ValueError("AI review did not contain a JSON array")
        text = text[start : end + 1]

    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("AI review response must be a JSON array")
    return parsed


def normalize_findings(items: list[Any]) -> list[Finding]:
    findings: list[Finding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            probability = int(item["probability_percent"])
            impact = int(item["impact_score"])
            finding = Finding(
                title=str(item["title"]).strip(),
                file=str(item["file"]).strip(),
                probability_percent=max(0, min(100, probability)),
                impact_score=max(1, min(10, impact)),
                comment=str(item["comment"]).strip(),
            )
        except (KeyError, TypeError, ValueError):
            continue
        if finding.title and finding.file and finding.comment:
            findings.append(finding)
    return findings


def render_markdown(findings: list[Finding], *, skipped_reason: str | None = None) -> str:
    if skipped_reason:
        return textwrap.dedent(
            f"""
            {COMMENT_MARKER}
            ## AI Bug Review

            Skipped: {skipped_reason}
            """
        ).strip()

    if not findings:
        return textwrap.dedent(
            f"""
            {COMMENT_MARKER}
            ## AI Bug Review

            No high-signal bug findings in this diff.
            """
        ).strip()

    lines = [
        COMMENT_MARKER,
        "## AI Bug Review",
        "",
        "| Title | File | Probability | Impact | Comment |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for finding in findings:
        lines.append(
            "| "
            f"{escape_table_cell(finding.title)} | "
            f"`{finding.file}` | "
            f"{finding.probability_percent}% | "
            f"{finding.impact_score}/10 | "
            f"{escape_table_cell(finding.comment)} |"
        )
    return "\n".join(lines)


def escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def append_step_summary(markdown: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        print(markdown)
        return
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write(markdown)
        handle.write("\n")


def github_api_request(
    method: str, url: str, token: str, payload: dict[str, Any] | None = None
) -> Any:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=20) as response:
        response_body = response.read().decode("utf-8")
    return json.loads(response_body) if response_body else None


def github_api_get_paginated(url: str, token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    separator = "&" if "?" in url else "?"
    page = 1
    while True:
        page_url = f"{url}{separator}per_page=100&page={page}"
        page_items = github_api_request("GET", page_url, token)
        if not isinstance(page_items, list) or not page_items:
            return items
        items.extend(
            item for item in page_items if isinstance(item, dict)
        )
        if len(page_items) < 100:
            return items
        page += 1


def is_actions_bot_comment(comment: dict[str, Any]) -> bool:
    user = comment.get("user")
    return isinstance(user, dict) and user.get("login") == GITHUB_ACTIONS_BOT_LOGIN


def post_pr_comment(event: dict[str, Any], markdown: str) -> None:
    if github_event_name() != "pull_request":
        return

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("Skipping PR comment: GITHUB_TOKEN or GITHUB_REPOSITORY is missing")
        return

    issue_number = event["pull_request"]["number"]
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    comments_url = f"{api_url}/repos/{repo}/issues/{issue_number}/comments"

    try:
        comments = github_api_get_paginated(comments_url, token)
        for comment in comments:
            body = comment.get("body", "")
            if COMMENT_MARKER in body and is_actions_bot_comment(comment):
                github_api_request("PATCH", comment["url"], token, {"body": markdown})
                return
        github_api_request("POST", comments_url, token, {"body": markdown})
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Failed to post PR comment: {exc}", file=sys.stderr)


def main() -> int:
    event = load_event()
    try:
        diff, truncated = truncate_diff(collect_diff(event))
    except (KeyError, subprocess.CalledProcessError) as exc:
        markdown = render_markdown([], skipped_reason=f"could not collect diff ({exc})")
        append_step_summary(markdown)
        return 0

    if not diff.strip():
        markdown = render_markdown([])
        append_step_summary(markdown)
        post_pr_comment(event, markdown)
        return 0

    if not os.environ.get("OPENAI_API_KEY"):
        markdown = render_markdown([], skipped_reason="OPENAI_API_KEY is not configured")
        append_step_summary(markdown)
        post_pr_comment(event, markdown)
        return 0

    try:
        raw_review = run_openai_review(build_prompt(diff, truncated=truncated))
        findings = normalize_findings(extract_json_array(raw_review))
        markdown = render_markdown(findings)
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        markdown = render_markdown([], skipped_reason=str(exc))

    append_step_summary(markdown)
    post_pr_comment(event, markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
