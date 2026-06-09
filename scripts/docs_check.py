r"""Read-only honesty-checker for narrative docs (lane A, opt-in).

This is a *diagnostic* helper, not a blocking guard. It flags a small set of
recurring doc-drift patterns that the docs honesty-cleanup keeps fixing by
hand, so a future Steward pass can catch them early:

1. Stale commit SHA near the top of ``docs/current-focus.md`` /
   ``docs/handoff.md`` (a SHA that git knows but that is *not* an ancestor of
   HEAD - i.e. left over from a pre-sync state). SHAs git cannot resolve at all
   are skipped, not flagged, so a partial clone does not produce noise.
2. ``examples/<siteId>.project-input.json`` asserted as the *runtime* /
   follow-up path. The runtime path is ``data/prompt-inputs/``; ``examples/``
   is correct only for committed example inputs.
3. ``section_add`` asserted as visibly rendered in preview. Today it is
   mount-only (``applied=true`` but ``appliedVisibleEffect=false``); claiming
   visible render is dishonest until that lands. Goal/roadmap/instruction
   phrasing ("synlig render av …", "gör … synligt", "överlova inte … synlig")
   is intentionally NOT flagged - those describe future work honestly.

It deliberately skips historical surfaces (``docs/archive/**``) and the
operator prompt files that *describe* this checker
(``docs/agent-prompts/cloud-grind/**``).

Run from the repo root:

    python scripts/docs_check.py            # report findings
    python scripts/docs_check.py --strict   # exit 1 if any finding

NOT wired into the blocking guard suite (governance/rules + CI) by design;
adding it there needs operator sign-off (see docs/agent-prompts/cloud-grind/).
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The two narrative files whose top block must track the real repo state.
TOP_STATE_FILES = ("docs/current-focus.md", "docs/handoff.md")

# How many leading lines count as "near the top".
TOP_LINES = 40

# Doc subtrees the per-file checks skip: archived history is historical by
# definition, and the cloud-grind prompts literally quote this checker's rules.
SKIP_DOC_PREFIXES = ("docs/archive/", "docs/agent-prompts/cloud-grind/")

# 7-40 hex chars bounded by non-word edges, optionally inside backticks.
_SHA_RE = re.compile(r"(?<![0-9a-fA-F])`?([0-9a-f]{7,40})`?(?![0-9a-fA-F])")

# A line that points at an example input file.
_EXAMPLE_INPUT_RE = re.compile(r"examples/[^\s`]*project-input\.json")

# Runtime cues that, next to an example-input path, signal the dishonest claim
# that the example file IS the runtime/follow-up artefact.
_RUNTIME_CUE_RE = re.compile(
    r"(runtime|f[öo]ljdprompt|/api/prompt|skrivs\s+som|skrivs\s+till|"
    r"runtime-?version|follow-?up-?version)",
    re.IGNORECASE,
)

# A correct line names the real runtime dir; treat that as a guard against
# false positives (e.g. the glossary line that contrasts the two locations).
_RUNTIME_DIR_GUARD_RE = re.compile(r"data/prompt-inputs", re.IGNORECASE)

# Visibility claims for a rendered section.
_VISIBLE_RE = re.compile(
    r"(synlig|syns\s+i\s+preview|visible\s+in\s+preview|renderas\s+synligt|"
    r"visas\s+i\s+preview)",
    re.IGNORECASE,
)

# Phrasings that make a "section_add … synlig" line honest: explicit negations,
# mount-only markers, and goal/roadmap/instruction framing (describing the work
# of *making* it visible, or an instruction not to over-claim it).
_VISIBLE_GUARD_RE = re.compile(
    r"(inte\b|[äa]nnu\s+inte|mount-?only|appliedvisibleeffect\s*=?\s*false|"
    r"synlig\s+render|g[öo]r\b|till\b|bli\b|gating|targeting|"
    r"[öo]verlova|[åa]terst[åa]r|ska\b|vill\b|m[åa]l\b|roadmap)",
    re.IGNORECASE,
)


def _run_git(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, (result.stdout or "").strip()


def top_shas(text: str, top_lines: int = TOP_LINES) -> list[str]:
    """Return candidate commit SHAs found in the first ``top_lines`` lines."""
    head = "\n".join(text.splitlines()[:top_lines])
    out: list[str] = []
    for match in _SHA_RE.finditer(head):
        token = match.group(1)
        # Require >= 7 hex AND at least one digit, to avoid matching plain
        # lowercase words like "added" / "deadbeef".
        if len(token) >= 7 and any(ch.isdigit() for ch in token):
            out.append(token)
    return out


def find_example_runtime_path(text: str) -> list[int]:
    """Return line numbers describing an example input file as runtime path."""
    out: list[int] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if not _EXAMPLE_INPUT_RE.search(line):
            continue
        if not _RUNTIME_CUE_RE.search(line):
            continue
        # If the same line also names the real runtime dir it is almost
        # certainly the correct "examples = committed, runtime = prompt-inputs"
        # contrast line, not a dishonest claim.
        if _RUNTIME_DIR_GUARD_RE.search(line):
            continue
        out.append(i)
    return out


def find_section_add_visible(text: str) -> list[int]:
    """Return line numbers asserting section_add renders visibly in preview."""
    out: list[int] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if "section_add" not in line:
            continue
        if not _VISIBLE_RE.search(line):
            continue
        if _VISIBLE_GUARD_RE.search(line):
            continue
        out.append(i)
    return out


def _iter_doc_files() -> list[Path]:
    docs_dir = REPO_ROOT / "docs"
    if not docs_dir.exists():
        return []
    out: list[Path] = []
    for path in sorted(docs_dir.rglob("*.md")):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(rel.startswith(prefix) for prefix in SKIP_DOC_PREFIXES):
            continue
        out.append(path)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only docs honesty checker.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 if any finding (default: exit 0, report only)",
    )
    args = parser.parse_args()

    findings: list[str] = []

    _, head_sha = _run_git(["rev-parse", "HEAD"])

    # Check 1 operates on the two top-state files.
    for rel in TOP_STATE_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if not head_sha:
            continue
        for sha in top_shas(text):
            code, _ = _run_git(["cat-file", "-e", f"{sha}^{{commit}}"])
            if code != 0:
                # git cannot resolve it (partial clone, squashed away). Cannot
                # verify -> do not flag, to avoid environment-dependent noise.
                continue
            anc, _ = _run_git(["merge-base", "--is-ancestor", sha, head_sha])
            if anc != 0:
                findings.append(
                    f"{rel}: top-block SHA `{sha}` is not an ancestor of HEAD "
                    f"({head_sha[:7]}) - likely stale after a sync."
                )

    # Check 2 + 3 operate on every active (non-archived) doc.
    for path in _iter_doc_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for ln in find_example_runtime_path(text):
            findings.append(
                f"{rel}:{ln}: an examples/<siteId>.project-input.json path is "
                f"described as a runtime/follow-up path. Runtime inputs live in "
                f"data/prompt-inputs/; examples/ is only for committed examples."
            )
        for ln in find_section_add_visible(text):
            findings.append(
                f"{rel}:{ln}: section_add is asserted as visible in preview. It "
                f"is mount-only today (appliedVisibleEffect=false); do not claim "
                f"visible render until that lands."
            )

    if not findings:
        print("OK: docs honesty-check found no issues.")
        return 0

    print(f"docs_check found {len(findings)} issue(s):\n")
    for item in findings:
        print(f"  - {item}")
    print(
        "\nThis is a diagnostic helper, not a blocking guard. Fix the prose or "
        "confirm the claim against the code/git."
    )
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
