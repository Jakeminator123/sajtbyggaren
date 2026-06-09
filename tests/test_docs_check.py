"""Unit tests for the opt-in docs honesty checker (scripts/docs_check.py).

These exercise the pure text-matching helpers on synthetic strings so the
checker's heuristics (and their negation/goal guards) cannot silently drift.
The git-dependent SHA check in ``main()`` is not exercised here - it is
covered by running the script against the live repo.
"""

from __future__ import annotations

import pytest

from scripts.docs_check import (
    find_example_runtime_path,
    find_section_add_visible,
    top_shas,
)


@pytest.mark.tooling
def test_top_shas_finds_hex_with_digit_near_top():
    text = "Last verified state: `abc1234`\nold ref f56ac30 here\n"
    found = top_shas(text)
    assert "abc1234" in found
    assert "f56ac30" in found


@pytest.mark.tooling
def test_top_shas_ignores_plain_hex_words_without_digits():
    # 'deadbeef' / 'feedface' are all-hex but have no digit -> not a SHA claim.
    text = "the deadbeef and feedface words are not commit refs\n"
    assert top_shas(text) == []


@pytest.mark.tooling
def test_top_shas_respects_top_line_window():
    lines = ["padding"] * 50 + ["buried sha abc1234"]
    text = "\n".join(lines)
    assert top_shas(text, top_lines=40) == []


@pytest.mark.tooling
def test_find_example_runtime_path_flags_dishonest_claim():
    text = "Följdprompten skrivs som examples/painter.project-input.json\n"
    assert find_example_runtime_path(text) == [1]


@pytest.mark.tooling
def test_find_example_runtime_path_allows_correct_contrast_line():
    # The correct line names data/prompt-inputs -> guarded, not flagged.
    text = (
        "Committade exempel: examples/painter.project-input.json; "
        "runtime/följdprompt skrivs till data/prompt-inputs/.\n"
    )
    assert find_example_runtime_path(text) == []


@pytest.mark.tooling
def test_find_example_runtime_path_ignores_plain_example_mention():
    text = "Se examples/painter.project-input.json för ett committat exempel.\n"
    assert find_example_runtime_path(text) == []


@pytest.mark.tooling
def test_find_section_add_visible_flags_false_visibility_claim():
    text = "section_add är nu synlig i preview\n"
    assert find_section_add_visible(text) == [1]


@pytest.mark.tooling
def test_find_section_add_visible_allows_honest_mount_only_line():
    text = (
        "section_add är mount-only och ännu inte synlig i preview "
        "(appliedVisibleEffect=false)\n"
    )
    assert find_section_add_visible(text) == []


@pytest.mark.tooling
def test_find_section_add_visible_allows_goal_and_instruction_framing():
    # Goal/roadmap/instruction lines describe FUTURE work honestly and must
    # not be flagged (these are the real false positives we tuned out).
    text = (
        "Synlig render av monterade section_add-sektioner + targeting\n"
        "gating för synlig section_add\n"
        "överlova inte section_add som synlig\n"
        "gör section_add faktiskt synligt i preview\n"
    )
    assert find_section_add_visible(text) == []


@pytest.mark.tooling
def test_find_section_add_visible_ignores_unrelated_lines():
    text = "section_add monterar capability + dossier\n"
    assert find_section_add_visible(text) == []
