"""Source locks for ADR 0044: the conductor SOUL wired into the chat persona.

These are *source locks* (not live behaviour): they read the TypeScript source
as text and assert the contract shape, the same discipline the other
``tests/test_viewser_*.py`` files use. Live behaviour (a real OpenAI chat with a
SOUL-derived persona) is verified by the operator with a key.

What they pin:
  1. ``lib/soul.ts`` reads docs/openclaw-workspace/SOUL.md, truncates to a safe
     length, caches per process and degrades defensively (null on any failure).
  2. ``generateConversationAnswer`` builds its system prompt from the SOUL base
     AND appends the dynamic honesty lines AFTER it, so the SOUL text can never
     override the honesty contract (the order is the security rail).
  3. A safe-length guard drops the SOUL base — never the dynamic lines — if the
     combined system message would exceed lib/openai.ts's cap.
"""

from __future__ import annotations

import re

import pytest

from tests.support.viewser import VIEWSER_DIR

# Core-lane: this is the chat-persona half of the core loop's follow-up answer.
pytestmark = pytest.mark.core

SOUL_TS = VIEWSER_DIR / "lib" / "soul.ts"
ROUTE_TS = VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts"


def test_soul_loader_reads_workspace_file_and_caches_defensively() -> None:
    """lib/soul.ts must read the workspace SOUL.md, truncate, cache per process
    and never throw — a missing/unreadable file degrades to null so the caller
    falls back to its hardcoded persona lines."""
    text = SOUL_TS.read_text(encoding="utf-8")

    assert "export function loadSoulBaseLines" in text, (
        "soul.ts must export loadSoulBaseLines() — the per-process SOUL base "
        "loader the chat persona reads."
    )
    assert '"docs/openclaw-workspace/SOUL.md"' in text, (
        "soul.ts must read the canonical workspace path "
        "docs/openclaw-workspace/SOUL.md (the single source of truth, ADR 0044)."
    )
    # Truncation to a safe length (so the assembled system message can never
    # approach lib/openai.ts's 8000-char/message cap).
    assert "SOUL_MAX_CHARS" in text and "slice(0, SOUL_MAX_CHARS)" in text, (
        "soul.ts must cap the SOUL text via SOUL_MAX_CHARS before turning it "
        "into persona lines."
    )
    # Per-process cache: the read happens at most once.
    assert "soulLoadAttempted" in text and "soulBaseCache" in text, (
        "soul.ts must cache the load (success OR failure) per process so a "
        "missing file does not cost a read on every chat turn."
    )
    # Defensive: any failure -> null cache -> caller falls back.
    assert "catch" in text and "soulBaseCache = null;" in text, (
        "soul.ts must degrade to a null cache on any read/parse failure so the "
        "caller can fall back to its hardcoded persona lines."
    )
    # The repo root is resolved cwd-independently (mirrors generated-dir.ts).
    assert "repoRoot()" in text, (
        "soul.ts must resolve the repo root via repoRoot() so SOUL.md is found "
        "regardless of the process cwd."
    )


def test_route_loads_soul_with_hardcoded_fallback() -> None:
    """route.ts must import the SOUL loader and use it with a defensive
    fallback to the hardcoded persona lines."""
    text = ROUTE_TS.read_text(encoding="utf-8")

    assert 'import { loadSoulBaseLines } from "@/lib/soul";' in text, (
        "route.ts must import loadSoulBaseLines from @/lib/soul."
    )
    assert "CONVERSATION_SOUL_FALLBACK_LINES" in text, (
        "route.ts must define CONVERSATION_SOUL_FALLBACK_LINES — the hardcoded "
        "persona base used when SOUL.md is missing/unreadable."
    )
    assert (
        "const soulBaseLines = loadSoulBaseLines() ?? CONVERSATION_SOUL_FALLBACK_LINES;"
        in text
    ), (
        "generateConversationAnswer must load the SOUL base with a defensive "
        "fallback to CONVERSATION_SOUL_FALLBACK_LINES (ADR 0044)."
    )
    # The fallback must be the OLD hardcoded persona lines, so a missing file
    # degrades to today's behaviour rather than an empty persona.
    assert (
        "Du är OpenClaw, dirigenten i Sajtbyggaren — operatörens chattassistent."
        in text
    ), "The hardcoded persona fallback must keep the original OpenClaw intro line."


def test_dynamic_honesty_lines_come_after_soul_base() -> None:
    """SECURITY RAIL (ADR 0044): the SOUL base must be placed BEFORE the dynamic
    honesty lines so the honest contract always wins. The dynamic lines keep the
    B193 build-history memory + the 'inget ändrat i DENNA tur' line, and they
    are spread AFTER the SOUL base — never before."""
    text = ROUTE_TS.read_text(encoding="utf-8")

    # The assembled order: SOUL base first, dynamic lines after.
    assert "const systemLines = [...soulBaseLines, ...dynamicLines];" in text, (
        "systemLines must be [...soulBaseLines, ...dynamicLines] so the dynamic "
        "honesty lines always come AFTER the SOUL base and win."
    )
    # The reverse order would let SOUL override honesty — forbid it.
    assert "[...dynamicLines, ...soulBaseLines]" not in text, (
        "The SOUL base must never be appended AFTER the dynamic lines — that "
        "would let SOUL override the honesty contract."
    )

    # The dynamic array (defined after soulBaseLines) carries the honesty +
    # history lines, and is assigned after the SOUL base.
    soul_idx = text.index("const soulBaseLines = loadSoulBaseLines()")
    dynamic_idx = text.index("const dynamicLines = [")
    honesty_idx = text.index("Du har INTE ändrat sajten i DENNA tur")
    history_idx = text.index("Byggrollernas historik (FAKTA du får referera):")
    assert soul_idx < dynamic_idx < honesty_idx, (
        "The SOUL base must be resolved before the dynamic honesty lines are "
        "assembled (order = security rail)."
    )
    assert soul_idx < history_idx, (
        "The build-history memory line (B193) must live in the dynamic block "
        "that follows the SOUL base."
    )


def test_system_message_overflow_drops_soul_base_not_honesty() -> None:
    """The combined system message must stay under lib/openai.ts's cap. On
    overflow we drop the SOUL base (lowest priority) — never the dynamic honesty
    lines — so the call never throws and honesty is always present."""
    text = ROUTE_TS.read_text(encoding="utf-8")

    assert "CONVERSATION_SYSTEM_SAFE_CHARS" in text, (
        "route.ts must define a CONVERSATION_SYSTEM_SAFE_CHARS ceiling for the "
        "assembled system message."
    )
    # On overflow the ternary must resolve to dynamicLines.join (honest lines),
    # dropping the SOUL base — whitespace-insensitive so formatting cannot
    # silently invert the rail.
    assert re.search(
        r"combinedSystem\.length\s*>\s*CONVERSATION_SYSTEM_SAFE_CHARS"
        r"\s*\?\s*dynamicLines\.join",
        text,
    ), (
        "On overflow the system content must fall back to dynamicLines.join "
        "(the honest lines), dropping the SOUL base — never the reverse."
    )
    assert ": combinedSystem;" in text, (
        "Under the cap the full SOUL-base + dynamic combined system message is "
        "used."
    )
    # The user prompt is still bounded to the per-message cap.
    assert 'content: prompt.slice(0, 8000)' in text, (
        "The user message must stay bounded to lib/openai.ts's per-message cap."
    )
