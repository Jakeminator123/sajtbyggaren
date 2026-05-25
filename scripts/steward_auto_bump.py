"""Auto-bump Steward handoff pointers after merged GitHub pull requests."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CURRENT_FOCUS = REPO_ROOT / "docs" / "current-focus.md"
DEFAULT_HANDOFF = REPO_ROOT / "docs" / "handoff.md"

SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
CURRENT_FOCUS_SHA_RE = re.compile(r"^Last verified state:\s*`([0-9a-fA-F]{7,40})`")
PR_NUMBER_RE = re.compile(r"\(#(?P<number>\d+)\)")
PROTECTED_TRIVIAL_PATHS = {
    "docs/current-focus.md",
    "docs/handoff.md",
    "docs/workboard.json",
    "docs/known-issues.md",
}


@dataclass(frozen=True)
class PullRequestSummary:
    number: int
    title: str


@dataclass(frozen=True)
class BumpResult:
    changed: bool
    reason: str


def validate_sha(value: str, *, field_name: str = "sha") -> str:
    """Return a normalized SHA or raise ValueError for unsafe input."""

    normalized = value.strip().lower()
    if not SHA_RE.fullmatch(normalized):
        msg = f"{field_name} must be a 7-40 character hexadecimal SHA"
        raise ValueError(msg)
    return normalized


def short_sha(value: str) -> str:
    return validate_sha(value)[:7]


def normalize_title(value: str) -> str:
    return " ".join(value.split()).strip()


def normalize_repo_path(value: str) -> str:
    return value.strip().replace("\\", "/").removeprefix("./")


def is_trivial_docs_only_diff(
    changed_paths: Sequence[str],
    *,
    additions: int,
    deletions: int,
) -> bool:
    """Return True when a merged PR should not trigger a Steward bump."""

    normalized_paths = [normalize_repo_path(path) for path in changed_paths if path.strip()]
    if not normalized_paths:
        return False

    line_delta = additions + deletions
    if line_delta >= 50:
        return False
    if any(not path.startswith("docs/") for path in normalized_paths):
        return False
    return not any(path in PROTECTED_TRIVIAL_PATHS for path in normalized_paths)


def parse_current_focus_sha(text: str) -> str:
    for line in text.splitlines():
        match = CURRENT_FOCUS_SHA_RE.match(line)
        if match:
            return validate_sha(match.group(1), field_name="current focus SHA")
    msg = "Could not find Last verified state SHA in current-focus.md"
    raise ValueError(msg)


def sha_already_verified(existing_sha: str, new_sha: str) -> bool:
    existing = validate_sha(existing_sha, field_name="existing SHA")
    new = validate_sha(new_sha, field_name="new SHA")
    return existing.startswith(new) or new.startswith(existing)


def parse_pr_summaries(raw_items: object) -> list[PullRequestSummary]:
    if not isinstance(raw_items, list):
        msg = "PR summary JSON must be a list"
        raise ValueError(msg)

    summaries: list[PullRequestSummary] = []
    seen: set[int] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            msg = "Each PR summary must be an object"
            raise ValueError(msg)
        number = int(item["number"])
        if number in seen:
            continue
        title = normalize_title(str(item["title"]))
        summaries.append(PullRequestSummary(number=number, title=title))
        seen.add(number)
    return summaries


def build_summary_line(pr_summaries: Sequence[PullRequestSummary]) -> str:
    if not pr_summaries:
        return "Nya PRs sedan föregående checkpoint: okänd PR-lista."

    entries = [f"PR #{item.number} — {item.title}" for item in pr_summaries]
    return "Nya PRs sedan föregående checkpoint: " + "; ".join(entries) + "."


def wrap_summary_line(summary_line: str) -> list[str]:
    return textwrap.wrap(
        summary_line,
        width=88,
        break_long_words=False,
        break_on_hyphens=False,
    )


def build_current_focus_block(
    *,
    merge_sha: str,
    pr_number: int,
    pr_title: str,
    pr_summaries: Sequence[PullRequestSummary],
    date_text: str,
) -> str:
    first_line = (
        f"Last verified state: `{short_sha(merge_sha)}` ({date_text} UTC, "
        f"steward-auto efter PR #{pr_number} — {normalize_title(pr_title)})."
    )
    return "\n".join([first_line, *wrap_summary_line(build_summary_line(pr_summaries))])


def build_handoff_header(
    *,
    merge_sha: str,
    pr_number: int,
    pr_title: str,
    pr_summaries: Sequence[PullRequestSummary],
    date_text: str,
) -> str:
    first_line = (
        f"**Datum:** {date_text} UTC, steward-auto efter PR #{pr_number} — "
        f"{normalize_title(pr_title)}. Verifierad `main` är `{short_sha(merge_sha)}`."
    )
    return "\n".join([first_line, "", *wrap_summary_line(build_summary_line(pr_summaries))])


def find_current_focus_block(lines: Sequence[str]) -> tuple[int, int]:
    start = next(
        (index for index, line in enumerate(lines) if line.startswith("Last verified state:")),
        None,
    )
    if start is None:
        msg = "Could not find Last verified state block in current-focus.md"
        raise ValueError(msg)

    for index in range(start + 1, len(lines)):
        line = lines[index]
        if (
            line.startswith("Sedan ")
            or line.startswith("## ")
            or line.startswith("Tidigare paragraf:")
            or line.startswith("Last verified state:")
        ):
            return start, index
    return start, len(lines)


def find_handoff_header_block(lines: Sequence[str]) -> tuple[int, int]:
    if not lines or not lines[0].startswith("# "):
        msg = "handoff.md must start with an H1 heading"
        raise ValueError(msg)

    start = 2 if len(lines) > 1 and lines[1] == "" else 1
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("**MCP-server-status:**") or line.startswith("## "):
            return start, index
    return start, len(lines)


def replace_line_block(text: str, *, span: tuple[int, int], replacement: str) -> str:
    lines = text.splitlines()
    start, end = span
    new_lines = [*lines[:start], *replacement.splitlines(), "", *lines[end:]]
    return "\n".join(new_lines).rstrip() + "\n"


def build_checkpoint_entry(
    *,
    source_name: str,
    old_block: str,
    previous_sha: str,
    date_text: str,
) -> str:
    return (
        f"### {date_text} UTC — {source_name} före `{short_sha(previous_sha)}`\n\n"
        f"{old_block.strip()}\n"
    )


def append_checkpoint(text: str, entry: str) -> str:
    lines = text.splitlines()
    heading = "## Föregående checkpoint"

    try:
        heading_index = lines.index(heading)
    except ValueError:
        return text.rstrip() + f"\n\n{heading}\n\n{entry.strip()}\n"

    insert_index = len(lines)
    for index in range(heading_index + 1, len(lines)):
        if lines[index].startswith("## ") and lines[index] != heading:
            insert_index = index
            break

    before = lines[:insert_index]
    after = lines[insert_index:]
    merged_lines = [*before, "", *entry.strip().splitlines()]
    if after:
        merged_lines.extend(["", *after])
    return "\n".join(merged_lines).rstrip() + "\n"


def rewrite_current_focus(
    text: str,
    *,
    new_block: str,
    previous_sha: str,
    date_text: str,
) -> str:
    lines = text.splitlines()
    span = find_current_focus_block(lines)
    old_block = "\n".join(lines[span[0] : span[1]]).strip()
    rewritten = replace_line_block(text, span=span, replacement=new_block)
    entry = build_checkpoint_entry(
        source_name="current-focus.md",
        old_block=old_block,
        previous_sha=previous_sha,
        date_text=date_text,
    )
    return append_checkpoint(rewritten, entry)


def rewrite_handoff(
    text: str,
    *,
    new_header: str,
    previous_sha: str,
    date_text: str,
) -> str:
    lines = text.splitlines()
    span = find_handoff_header_block(lines)
    old_block = "\n".join(lines[span[0] : span[1]]).strip()
    rewritten = replace_line_block(text, span=span, replacement=new_header)
    entry = build_checkpoint_entry(
        source_name="handoff.md",
        old_block=old_block,
        previous_sha=previous_sha,
        date_text=date_text,
    )
    return append_checkpoint(rewritten, entry)


def bump_documents(
    *,
    current_focus_path: Path,
    handoff_path: Path,
    merge_sha: str,
    pr_number: int,
    pr_title: str,
    pr_summaries: Sequence[PullRequestSummary],
    date_text: str | None = None,
) -> BumpResult:
    normalized_sha = validate_sha(merge_sha, field_name="merge SHA")
    effective_date = date_text or datetime.now(UTC).date().isoformat()

    current_focus_text = current_focus_path.read_text(encoding="utf-8")
    previous_sha = parse_current_focus_sha(current_focus_text)
    if sha_already_verified(previous_sha, normalized_sha):
        return BumpResult(changed=False, reason="already verified")

    handoff_text = handoff_path.read_text(encoding="utf-8")
    effective_summaries = list(pr_summaries) or [
        PullRequestSummary(number=pr_number, title=pr_title)
    ]
    current_focus_block = build_current_focus_block(
        merge_sha=normalized_sha,
        pr_number=pr_number,
        pr_title=pr_title,
        pr_summaries=effective_summaries,
        date_text=effective_date,
    )
    handoff_header = build_handoff_header(
        merge_sha=normalized_sha,
        pr_number=pr_number,
        pr_title=pr_title,
        pr_summaries=effective_summaries,
        date_text=effective_date,
    )

    new_current_focus = rewrite_current_focus(
        current_focus_text,
        new_block=current_focus_block,
        previous_sha=previous_sha,
        date_text=effective_date,
    )
    new_handoff = rewrite_handoff(
        handoff_text,
        new_header=handoff_header,
        previous_sha=previous_sha,
        date_text=effective_date,
    )

    changed = False
    if new_current_focus != current_focus_text:
        current_focus_path.write_text(new_current_focus, encoding="utf-8")
        changed = True
    if new_handoff != handoff_text:
        handoff_path.write_text(new_handoff, encoding="utf-8")
        changed = True

    return BumpResult(changed=changed, reason="updated" if changed else "no change")


def extract_pr_numbers_from_subjects(subjects: Sequence[str]) -> list[int]:
    numbers: list[int] = []
    seen: set[int] = set()
    for subject in subjects:
        for match in PR_NUMBER_RE.finditer(subject):
            number = int(match.group("number"))
            if number not in seen:
                numbers.append(number)
                seen.add(number)
    return numbers


def run_command(args: Sequence[str]) -> str:
    completed = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def fetch_pr_summary(number: int) -> PullRequestSummary | None:
    try:
        raw = run_command(["gh", "pr", "view", str(number), "--json", "number,title"])
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    data = json.loads(raw)
    return PullRequestSummary(number=int(data["number"]), title=str(data["title"]))


def collect_pr_summaries_from_git(
    *,
    previous_sha: str,
    head_sha: str,
    fallback: PullRequestSummary,
) -> list[PullRequestSummary]:
    previous = validate_sha(previous_sha, field_name="previous SHA")
    head = validate_sha(head_sha, field_name="head SHA")

    try:
        log_output = run_command(["git", "log", "--reverse", "--format=%s", f"{previous}..{head}"])
        subjects = [line for line in log_output.splitlines() if line.strip()]
        numbers = extract_pr_numbers_from_subjects(subjects)
    except (FileNotFoundError, subprocess.CalledProcessError):
        numbers = []

    if fallback.number not in numbers:
        numbers.append(fallback.number)

    summaries: list[PullRequestSummary] = []
    for number in numbers:
        summary = fetch_pr_summary(number)
        if summary is None and number == fallback.number:
            summary = fallback
        if summary is not None:
            summaries.append(summary)
    return summaries or [fallback]


def load_pr_summaries(path: Path | None, *, fallback: PullRequestSummary) -> list[PullRequestSummary]:
    if path is None:
        return [fallback]
    return parse_pr_summaries(json.loads(path.read_text(encoding="utf-8")))


def build_commit_title(*, merge_sha: str, pr_number: int, pr_title: str) -> str:
    normalized_sha = short_sha(merge_sha)
    return (
        f"docs(steward-auto): bump HEAD to {normalized_sha} "
        f"via PR #{pr_number} {normalize_title(pr_title)}"
    )


def add_common_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--current-focus", type=Path, default=DEFAULT_CURRENT_FOCUS)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    bump = subparsers.add_parser("bump", help="Rewrite current-focus.md and handoff.md")
    add_common_paths(bump)
    bump.add_argument("--sha", required=True)
    bump.add_argument("--pr-number", required=True, type=int)
    bump.add_argument("--pr-title", required=True)
    bump.add_argument("--pr-list-json", type=Path)
    bump.add_argument("--date")

    previous = subparsers.add_parser("previous-sha", help="Print current verified SHA")
    previous.add_argument("--current-focus", type=Path, default=DEFAULT_CURRENT_FOCUS)

    trivial = subparsers.add_parser("is-trivial", help="Exit 0 when diff is trivial")
    trivial.add_argument("--additions", required=True, type=int)
    trivial.add_argument("--deletions", required=True, type=int)
    trivial.add_argument("--paths-file", required=True, type=Path)

    collect = subparsers.add_parser("collect-prs", help="Collect PR summaries from git log")
    collect.add_argument("--previous-sha", required=True)
    collect.add_argument("--head-sha", required=True)
    collect.add_argument("--fallback-pr-number", required=True, type=int)
    collect.add_argument("--fallback-pr-title", required=True)

    title = subparsers.add_parser("commit-title", help="Print steward auto-bump commit title")
    title.add_argument("--sha", required=True)
    title.add_argument("--pr-number", required=True, type=int)
    title.add_argument("--pr-title", required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "bump":
            fallback = PullRequestSummary(number=args.pr_number, title=args.pr_title)
            result = bump_documents(
                current_focus_path=args.current_focus,
                handoff_path=args.handoff,
                merge_sha=args.sha,
                pr_number=args.pr_number,
                pr_title=args.pr_title,
                pr_summaries=load_pr_summaries(args.pr_list_json, fallback=fallback),
                date_text=args.date,
            )
            print(result.reason)
            return 0

        if args.command == "previous-sha":
            text = args.current_focus.read_text(encoding="utf-8")
            print(parse_current_focus_sha(text))
            return 0

        if args.command == "is-trivial":
            paths = args.paths_file.read_text(encoding="utf-8").splitlines()
            return 0 if is_trivial_docs_only_diff(
                paths,
                additions=args.additions,
                deletions=args.deletions,
            ) else 1

        if args.command == "collect-prs":
            fallback = PullRequestSummary(
                number=args.fallback_pr_number,
                title=args.fallback_pr_title,
            )
            summaries = collect_pr_summaries_from_git(
                previous_sha=args.previous_sha,
                head_sha=args.head_sha,
                fallback=fallback,
            )
            payload = [{"number": item.number, "title": item.title} for item in summaries]
            print(json.dumps(payload, ensure_ascii=False))
            return 0

        if args.command == "commit-title":
            print(
                build_commit_title(
                    merge_sha=args.sha,
                    pr_number=args.pr_number,
                    pr_title=args.pr_title,
                )
            )
            return 0
    except ValueError as exc:
        print(f"steward-auto-bump: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
