"""Marked-section follow-up signal (ADR 0046).

The preview overlay lets the operator mark up to five sections
(``{routeId, sectionId, note?}``) before sending a follow-up prompt.
This module owns the honesty gates for that signal:

- :func:`parse_marked_sections` shape-validates the raw CLI JSON
  (``--marked-sections``) without touching disk.
- :func:`validate_marked_sections` checks every marking against the
  base run's facit — primarily ``emittedSections`` in
  ``build-result.json`` (suppression-aware), with a fallback to the
  site plan's routePlan + the scaffold's declared ``sections.json``
  vocabulary for runs built before the marker injection landed. An
  unknown route/section is DROPPED with a structured warning, never
  guessed or remapped.
- :func:`focus_note_for_llm` renders the validated markings into a
  short Swedish context note for the copyDirective planner and the
  styleDirective extractor. The note is a soft prioritisation signal:
  it never triggers a build and never changes intent classification.

Conventions: code identifiers in English, operator-facing strings in
Swedish (governance/rules/code-in-english.md).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MAX_MARKED_SECTIONS = 5

# Same id grammar as the data-section-id marker pattern in build_site.py
# and the siteId/runId patterns across the repo: lower-case slug tokens.
_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_NOTE_MAX_LENGTH = 200

# Scaffold sections.json fallback (older base runs without
# ``emittedSections``): the declared vocabulary lives next to the
# orchestration scaffolds, keyed by routeId.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCAFFOLDS_DIR = _REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"


def parse_marked_sections(raw: str) -> list[dict[str, str]]:
    """Parse + shape-validate the ``--marked-sections`` JSON payload.

    Returns a deduplicated list (max :data:`MAX_MARKED_SECTIONS`) of
    ``{"routeId": ..., "sectionId": ..., "note": ...?}`` dicts. Raises
    ``ValueError`` with an operator-readable Swedish message on any
    malformed payload — the CLI converts that into a clean exit instead
    of a stack trace.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--marked-sections är inte giltig JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("--marked-sections måste vara en JSON-lista.")
    parsed: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("--marked-sections: varje post måste vara ett objekt.")
        route_id = item.get("routeId")
        section_id = item.get("sectionId")
        if not isinstance(route_id, str) or not _ID_PATTERN.match(route_id):
            raise ValueError(
                f"--marked-sections: ogiltigt routeId {route_id!r} "
                "(förväntar gemener/siffror/bindestreck)."
            )
        if not isinstance(section_id, str) or not _ID_PATTERN.match(section_id):
            raise ValueError(
                f"--marked-sections: ogiltigt sectionId {section_id!r} "
                "(förväntar gemener/siffror/bindestreck)."
            )
        key = (route_id, section_id)
        if key in seen:
            continue
        seen.add(key)
        entry: dict[str, str] = {"routeId": route_id, "sectionId": section_id}
        note = item.get("note")
        if isinstance(note, str):
            trimmed = note.strip()
            if trimmed:
                entry["note"] = trimmed[:_NOTE_MAX_LENGTH]
        parsed.append(entry)
        if len(parsed) >= MAX_MARKED_SECTIONS:
            break
    return parsed


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _emitted_sections_facit(base_run_dir: Path) -> dict[str, set[str]] | None:
    """The suppression-aware facit from the base run's build-result.json."""
    build_result = _read_json(base_run_dir / "build-result.json")
    if build_result is None:
        return None
    raw = build_result.get("emittedSections")
    if not isinstance(raw, dict) or not raw:
        return None
    facit: dict[str, set[str]] = {}
    for route_id, section_ids in raw.items():
        if not isinstance(route_id, str) or not isinstance(section_ids, list):
            continue
        facit[route_id] = {
            section_id for section_id in section_ids if isinstance(section_id, str)
        }
    return facit or None


def _scaffold_sections_facit(base_run_dir: Path) -> dict[str, set[str]] | None:
    """Fallback facit: routePlan ids + the scaffold's declared sections.

    Used for base runs built before the marker injection landed. The
    declared vocabulary is a superset of what actually rendered
    (suppression-unaware) — acceptable because the marking is a soft
    signal (ADR 0046, known limitation).
    """
    site_plan = _read_json(base_run_dir / "site-plan.json")
    if site_plan is None:
        return None
    route_plan = site_plan.get("routePlan")
    scaffold_id = site_plan.get("scaffoldId")
    if not isinstance(route_plan, list) or not isinstance(scaffold_id, str):
        return None
    route_ids = {
        entry.get("id")
        for entry in route_plan
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    if not route_ids:
        return None
    sections_payload = _read_json(_SCAFFOLDS_DIR / scaffold_id / "sections.json")
    if sections_payload is None:
        return None
    facit: dict[str, set[str]] = {}
    for route_id in route_ids:
        declared = sections_payload.get(route_id)
        if not isinstance(declared, dict):
            # Route exists in the plan but the scaffold declares no
            # section vocabulary for it (e.g. a wizard extra route):
            # nothing to verify a sectionId against -> empty set so the
            # marking is dropped with a warning rather than guessed.
            facit[route_id] = set()
            continue
        section_ids: set[str] = set()
        for key in ("requiredSections", "optionalSections"):
            values = declared.get(key)
            if isinstance(values, list):
                section_ids.update(
                    value for value in values if isinstance(value, str)
                )
        facit[route_id] = section_ids
    return facit


def validate_marked_sections(
    marked: list[dict[str, str]],
    *,
    base_run_dir: Path | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split markings into (applied, dropped) against the base run facit.

    Dropped entries carry a Swedish ``reason`` so the meta sidecar /
    build-result can explain the honest no-op to the operator. With no
    readable facit at all, EVERY marking is dropped — never guessed.
    """
    if not marked:
        return [], []
    facit: dict[str, set[str]] | None = None
    if base_run_dir is not None and base_run_dir.is_dir():
        facit = _emitted_sections_facit(base_run_dir)
        if facit is None:
            facit = _scaffold_sections_facit(base_run_dir)
    if facit is None:
        reason = (
            "Basversionens artefakter saknar sektionsfacit "
            "(emittedSections/site-plan) – markeringen kan inte verifieras."
        )
        return [], [
            {**entry, "reason": reason} for entry in marked
        ]
    applied: list[dict[str, str]] = []
    dropped: list[dict[str, str]] = []
    for entry in marked:
        route_id = entry["routeId"]
        section_id = entry["sectionId"]
        if route_id not in facit:
            dropped.append(
                {
                    **entry,
                    "reason": (
                        f"Routen '{route_id}' finns inte i basversionens "
                        "routePlan."
                    ),
                }
            )
            continue
        if section_id not in facit[route_id]:
            dropped.append(
                {
                    **entry,
                    "reason": (
                        f"Sektionen '{section_id}' renderades inte på routen "
                        f"'{route_id}' i basversionen."
                    ),
                }
            )
            continue
        applied.append(dict(entry))
    return applied, dropped


def focus_note_for_llm(marked: list[dict[str, str]]) -> str | None:
    """Render validated markings into a short Swedish LLM context note.

    The note is appended to planner/extractor context as a soft
    prioritisation signal. ``note`` (the section's heading text from the
    overlay) is included as untrusted context, never as an instruction.
    Returns ``None`` for an empty list so callers can skip cleanly.
    """
    if not marked:
        return None
    lines = ["Operatören har markerat följande sektioner i previewn:"]
    for entry in marked:
        line = f"- route '{entry['routeId']}', sektion '{entry['sectionId']}'"
        note = entry.get("note")
        if note:
            line += f" (rubrik: \"{note}\")"
        lines.append(line)
    lines.append(
        "Prioritera ändringar som gäller dessa sektioner när prompten är "
        "tvetydig."
    )
    return "\n".join(lines)


def route_sections_context(marked: list[dict[str, str]]) -> dict[str, list[str]]:
    """Markings as ``{routeId: [sectionId, ...]}`` for RouterContext.

    Matches the existing ``RouterContext.routeSections`` shape so the
    deterministic router can resolve section references without reading
    disk. Order-preserving, deduplicated per route.
    """
    grouped: dict[str, list[str]] = {}
    for entry in marked:
        sections = grouped.setdefault(entry["routeId"], [])
        if entry["sectionId"] not in sections:
            sections.append(entry["sectionId"])
    return grouped
