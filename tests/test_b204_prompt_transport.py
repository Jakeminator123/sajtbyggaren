"""B204 — UTF-8-safe prompt/message transport across the viewser→CLI boundary.

Operator finding (2026-06-14, site ``olkultur-ab-e9594d``): a follow-up prompt
beginning with "Ä" ("Ändra …") was stored as "*ndra …". Root cause: the
operator free text crossed the apps/viewser → Python-CLI boundary as a process
ARGV argument (``spawn(python, [..., "--", trimmed])``); on the operator's
Windows console a non-ASCII LEADING character is mangled on the Node→OS→Python
hop. The fix routes the text through a UTF-8 temp file (``--prompt-file`` /
``--message-file``) so every Swedish character round-trips intact.

These tests lock the TRANSPORT INVARIANT. The full Windows mangling cannot be
reproduced in this CI environment, so final verification runs on the operator's
machine (see docs/known-issues.md B204). Here we assert:

1. Functional — ``scripts/cli_text.resolve_cli_text`` reads a UTF-8 file back
   byte-for-byte (incl. a leading å/ä/ö); the positional arg stays supported
   for back-compat; both/neither/unreadable sources raise cleanly.
2. Source-lock (Python) — all three prompt-bearing CLIs register the
   ``--*-file`` flag and resolve via ``resolve_cli_text``.
3. Source-lock (TS) — the shared ``writeTextArgFile`` helper writes UTF-8, and
   the classifier + OpenClaw spawn seams pass ``--message-file`` instead of raw
   argv (``prompt-runner.ts`` is locked in tests/test_viewser_api_prompt.py).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
VIEWSER_LIB = REPO_ROOT / "apps" / "viewser" / "lib"

sys.path.insert(0, str(REPO_ROOT))

from scripts.cli_text import resolve_cli_text  # noqa: E402

# Free text round-tripping intact is part of the core prompt -> build loop.
pytestmark = pytest.mark.core


# Exactly the failure mode: a LEADING Swedish character (the operator saw
# "Ändra …" become "*ndra …").
SWEDISH_SAMPLES = [
    "Ändra rubriken till X",
    "Åäö-test",
    "Ändra namnet till Café Smörgås",
    "Övre menyn ska vara blå",
    "ändra färgen till röd",
]


# ---------------------------------------------------------------------------
# 1. Functional: UTF-8 file round-trip + back-compat + edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", SWEDISH_SAMPLES)
def test_text_file_round_trips_swedish_chars_intact(tmp_path: Path, text: str) -> None:
    """A UTF-8 file written exactly as apps/viewser writes it (no trailing
    newline) reads back byte-for-byte — the leading "Ä"/"Å"/"Ö" survives."""
    value_file = tmp_path / "value.txt"
    value_file.write_text(text, encoding="utf-8")

    resolved = resolve_cli_text(None, str(value_file), label="prompt")

    assert resolved == text
    # The leading character is the exact B204 failure mode (it became "*").
    assert resolved.startswith(text[0])
    assert not resolved.startswith("*")


def test_message_file_round_trips_multiline_utf8(tmp_path: Path) -> None:
    text = "Ändra\nrubriken\noch lägg till en blå knapp"
    value_file = tmp_path / "value.txt"
    value_file.write_text(text, encoding="utf-8")
    assert resolve_cli_text(None, str(value_file), label="message") == text


def test_positional_text_still_supported_for_back_compat() -> None:
    """The hosted sandbox path + tests + programmatic callers still pass the
    text positionally; resolve_cli_text returns it unchanged."""
    assert resolve_cli_text("Ändra rubriken", None, label="prompt") == "Ändra rubriken"


def test_both_sources_is_a_clean_error(tmp_path: Path) -> None:
    value_file = tmp_path / "value.txt"
    value_file.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not both"):
        resolve_cli_text("x", str(value_file), label="prompt")


def test_neither_source_is_a_clean_error() -> None:
    with pytest.raises(ValueError, match="required"):
        resolve_cli_text(None, None, label="message")


def test_missing_file_is_a_clean_error(tmp_path: Path) -> None:
    missing = tmp_path / "nope.txt"
    with pytest.raises(ValueError, match="Could not read"):
        resolve_cli_text(None, str(missing), label="prompt")


# ---------------------------------------------------------------------------
# 2. Source-lock (Python): the prompt-bearing CLIs use the file transport
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_prompt_to_project_input_reads_prompt_file_via_resolver() -> None:
    text = (SCRIPTS_DIR / "prompt_to_project_input.py").read_text(encoding="utf-8")
    assert '"--prompt-file"' in text, "must register --prompt-file (B204)."
    assert "resolve_cli_text(" in text, "must resolve the prompt via scripts.cli_text."
    assert "from scripts.cli_text import resolve_cli_text" in text


@pytest.mark.tooling
@pytest.mark.parametrize("script", ["classify_message.py", "run_openclaw_followup.py"])
def test_message_clis_read_message_file_via_resolver(script: str) -> None:
    text = (SCRIPTS_DIR / script).read_text(encoding="utf-8")
    assert '"--message-file"' in text, f"{script} must register --message-file (B204)."
    assert "resolve_cli_text(" in text, f"{script} must resolve via scripts.cli_text."


@pytest.mark.tooling
def test_cli_text_reads_with_explicit_utf8() -> None:
    text = (SCRIPTS_DIR / "cli_text.py").read_text(encoding="utf-8")
    assert 'read_text(encoding="utf-8")' in text, (
        "scripts/cli_text.py måste läsa --*-file med explicit encoding=utf-8."
    )


# ---------------------------------------------------------------------------
# 3. Source-lock (TS): shared helper writes UTF-8; spawn seams pass --*-file
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_text_arg_file_writes_utf8() -> None:
    text = (VIEWSER_LIB / "text-arg-file.ts").read_text(encoding="utf-8")
    assert "export function writeTextArgFile" in text
    assert 'encoding: "utf-8"' in text, "text-arg-file.ts måste skriva UTF-8."


@pytest.mark.tooling
@pytest.mark.parametrize(
    "runner",
    ["router-classify-runner.ts", "openclaw-runner.ts"],
)
def test_message_runners_use_file_transport_not_argv(runner: str) -> None:
    text = (VIEWSER_LIB / runner).read_text(encoding="utf-8")
    raw_argv = re.compile(r"args\.push\(\s*\"--\"\s*,\s*trimmed\s*\)", re.MULTILINE)
    assert not raw_argv.search(text), (
        f"{runner} får inte skicka meddelandet som rå argv (B204)."
    )
    assert "writeTextArgFile(trimmed" in text, (
        f"{runner} måste skriva meddelandet till en UTF-8-tempfil (B204)."
    )
    assert '"--message-file"' in text, (
        f"{runner} måste skicka --message-file till Python-CLI:t (B204)."
    )
