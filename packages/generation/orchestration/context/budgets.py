"""Per-level character budgets and deterministic packing helpers (KÖR-7a).

The Context Assembler fetches *lagom* much context per question. sajtmaskin
allowed its "full" tier up to ~180k characters; per 02 §4 we deliberately
set tighter caps. Every level has a hard character budget, and the helpers
here guarantee the assembled payload never exceeds it.

All packing is deterministic (no clocks, no randomness): the same inputs
and budget always produce the same payload, the same ``dropped`` list and
the same ``truncated`` flag. ``charCount`` is measured on the payload that
would actually be handed to the model, so the cap is an honest byte budget,
not an estimate.
"""

from __future__ import annotations

import json
from typing import Any

from ..router.models import ContextLevel

__all__ = [
    "DEFAULT_BUDGETS",
    "TRUNCATION_MARKER",
    "clip_text",
    "fill_list_within_budget",
    "fill_mapping_within_budget",
    "resolve_budget",
    "serialized_len",
    "set_blob_within_budget",
]

# Hard character caps per level. Tighter than sajtmaskin's 180k "full" tier
# on purpose (02 §4: "vi sätter snålare tak"). ``none`` is 0 by definition.
DEFAULT_BUDGETS: dict[ContextLevel, int] = {
    "none": 0,
    "project_dna": 2_000,
    "artifacts": 24_000,
    "artifacts_plus_sections": 32_000,
    "component_registry": 12_000,
    "manifest": 8_000,
    "selected_files": 40_000,
    "preview_dom": 24_000,
    "external_reference": 24_000,
}

TRUNCATION_MARKER = "…[truncated]"


def resolve_budget(
    level: ContextLevel,
    budgets: dict[str, int] | None = None,
) -> int:
    """Return the character cap for ``level``.

    A caller may pass a partial ``budgets`` override (e.g. tiny values in a
    test) keyed by level name; unspecified levels fall back to
    ``DEFAULT_BUDGETS``. A negative override is clamped to 0.
    """
    if budgets and level in budgets:
        return max(0, int(budgets[level]))
    return DEFAULT_BUDGETS.get(level, 0)


def serialized_len(payload: Any) -> int:
    """Length of the payload as the caller would serialise it for the model.

    An empty container/blank value counts as 0 characters so the ``none``
    level (and any fully-dropped payload) can satisfy a 0 budget - otherwise
    ``json.dumps({})`` would report 2 characters for "no content".
    """
    if not payload:
        return 0
    return len(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


def clip_text(text: str, budget: int) -> tuple[str, bool]:
    """Clip a standalone string to ``budget`` characters.

    Returns ``(clipped, truncated)``. A truncation marker is appended when
    there is room for it; for a budget smaller than the marker the text is
    hard-cut. A 0 (or negative) budget yields an empty string, truncated iff
    the input had any content.
    """
    if budget <= 0:
        return "", bool(text)
    if len(text) <= budget:
        return text, False
    if budget <= len(TRUNCATION_MARKER):
        return text[:budget], True
    return text[: budget - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER, True


def fill_mapping_within_budget(
    payload: dict[str, Any],
    entries: list[tuple[str, Any]],
    budget: int,
) -> list[str]:
    """Add ``(key, value)`` entries to ``payload`` in priority order, within budget.

    An entry whose addition would push the serialised payload over ``budget``
    is skipped and its key recorded in the returned ``dropped`` list. Later
    (smaller) entries are still tried, so the budget is used greedily but the
    relative priority of earlier entries is honoured. ``payload`` is mutated
    in place and the invariant ``serialized_len(payload) <= budget`` holds on
    return.
    """
    dropped: list[str] = []
    for key, value in entries:
        payload[key] = value
        if serialized_len(payload) > budget:
            del payload[key]
            dropped.append(key)
    return dropped


def fill_list_within_budget(
    payload: dict[str, Any],
    key: str,
    items: list[Any],
    budget: int,
) -> list[Any]:
    """Fill ``payload[key]`` with as many ``items`` as fit, in order.

    Items that do not fit are returned as ``dropped`` (and never appended).
    The list key is always present (possibly empty) so the payload shape is
    stable. ``payload`` is mutated in place; the budget invariant holds on
    return.
    """
    payload[key] = []
    dropped: list[Any] = []
    for item in items:
        payload[key].append(item)
        if serialized_len(payload) > budget:
            payload[key].pop()
            dropped.append(item)
    return dropped


def set_blob_within_budget(
    payload: dict[str, Any],
    key: str,
    text: str,
    budget: int,
) -> bool:
    """Set ``payload[key]`` to ``text``, clipping so the payload fits ``budget``.

    Because JSON escaping changes length, the clip point is found by binary
    search on the source string against the *serialised payload* length (so
    other keys already in ``payload`` are accounted for). Returns whether the
    text was truncated. The budget invariant holds on return.
    """
    payload[key] = text
    if serialized_len(payload) <= budget:
        return False

    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        payload[key] = text[:mid] + TRUNCATION_MARKER
        if serialized_len(payload) <= budget:
            lo = mid
        else:
            hi = mid - 1

    payload[key] = (text[:lo] + TRUNCATION_MARKER) if lo > 0 else ""
    if serialized_len(payload) > budget:
        # No room even for the marker (very small budget) - drop the content.
        payload[key] = ""
    return True
