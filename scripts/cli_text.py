"""Shared CLI free-text resolver for the scripts/ entrypoints.

Why this exists (B204): operator free text (the prompt, the classifier /
follow-up message) used to reach the Python CLIs as a process ARGV argument
from apps/viewser (``spawn(python, [..., "--", trimmed])``). On some Windows
consoles a non-ASCII LEADING character in argv is mangled on the
Node→OS→Python hop — the operator saw "Ändra …" stored as "*ndra …". The TS
runners now stage that text in a UTF-8 temp file and pass ``--<label>-file
<path>`` instead; this helper reads the bytes back with ``encoding="utf-8"``
so every Swedish character (å/ä/ö/Å/Ä/Ö), including the leading one, survives
intact.

The positional argument stays supported for back-compat: programmatic
callers, the test-suite and the hosted sandbox path all still pass the text
positionally (the hosted path is safe — it crosses a Linux env expansion, not
a Windows console).

Conventions: code + identifiers in English (governance/rules/code-in-english.md).
"""

from __future__ import annotations

from pathlib import Path


def resolve_cli_text(
    positional: str | None,
    file_path: str | None,
    *,
    label: str,
) -> str:
    """Return operator free text from either the positional arg or a UTF-8 file.

    Exactly one source must be provided. ``--<label>-file`` wins when present
    and is read as UTF-8 (the B204-safe transport); otherwise the positional
    value is used. Raises ``ValueError`` when both or neither are supplied, or
    when the file cannot be read, so each CLI can surface a clean
    ``SystemExit`` / non-zero return with a readable message.
    """
    if file_path is not None:
        if positional is not None:
            raise ValueError(
                f"Pass the {label} either positionally or via "
                f"--{label}-file, not both."
            )
        try:
            return Path(file_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(
                f"Could not read --{label}-file {file_path!r}: {exc}"
            ) from exc
    if positional is None:
        raise ValueError(
            f"A {label} is required (positional argument or --{label}-file)."
        )
    return positional
