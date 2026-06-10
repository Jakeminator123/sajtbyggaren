"""Builder Phase-1 brief generation (extracted from scripts/build_site.py).

Slice 4 of the behavior-preserving megafile refactor
(``docs/refactor/megafiles-plan.md`` Del 2): the deterministic builder's
Phase-1 brief builders used to live inline in ``scripts/build_site.py``. They
now live here, beside the canonical brief extractor (``extract.py``) and the
model resolver (``models.py``).

Public surface (re-exported by ``scripts/build_site.py`` so existing spellings
keep resolving):
    build_site_brief(run_id, dossier, scaffold) -> dict
        Build a Site Brief via ``briefModel`` when ``OPENAI_API_KEY`` is set,
        otherwise the deterministic mock fallback.
    build_site_brief_mock(run_id, dossier, scaffold) -> dict
        Deterministic mock Site Brief derived from the Project Input.
    resolve_brief_model() -> str
        Thin wrapper around ``packages.generation.brief.resolve_brief_model``.
    project_input_to_brief_prompt(dossier) -> str
        Deterministic briefModel input restated from a Project Input.
    reuse_previous_site_brief(run_id, dossier, previous_run_dir) -> dict | None
        B180 carry-forward: reuse the previous run's Site Brief on a follow-up
        build whose brief input is unchanged (masked comparison), so a pure
        restyle/section/capability follow-up never re-rolls the creative copy.

``utc_now`` stays in ``scripts/build_site.py`` (the io-helpers slice has not
landed yet), so ``build_site_brief_mock`` bridges it via a lazy
``from scripts.build_site import utc_now`` inside its body (same pattern slice 3
used for ``load_json`` / ``_to_repo_relative``).
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

from packages.generation.build.assets import _iter_mood_refs

_OPERATOR_DIRECTIVE_NOTE_PREFIX = "Operator: "
_MOOD_VISUAL_NOTE_PREFIX = "Visual mood: "


def _mood_visual_note_blocks(dossier: dict) -> list[str]:
    """Return planner notes from existing mood-image Vision metadata."""
    blocks: list[str] = []
    for ref in _iter_mood_refs(dossier):
        subject = ref.get("visionSubject")
        confidence = ref.get("visionConfidence")
        has_subject = isinstance(subject, str) and bool(subject.strip())
        has_confidence = isinstance(confidence, str) and bool(confidence.strip())
        if not has_subject and not has_confidence:
            continue

        parts: list[str] = []
        alt = ref.get("alt")
        if isinstance(alt, str) and alt.strip():
            parts.append(alt.strip())
        if has_subject:
            parts.append(f"subject: {subject.strip()}")
        if has_confidence:
            parts.append(f"confidence: {confidence.strip()}")
        if parts:
            blocks.append(f"{_MOOD_VISUAL_NOTE_PREFIX}{'; '.join(parts)}")
    return blocks


def _apply_operator_directive_note(brief: dict, dossier: dict) -> None:
    """Prepend deterministic operator and mood context to Site Brief notes.

    Gap 5 adds ``directives.notesForPlanner`` with prefix ``"Operator: "``.
    Gap 9 adds existing Vision metadata from ``moodImages`` with prefix
    ``"Visual mood: "`` when those fields are already present on the
    AssetRef. Missing/empty inputs leave the brief untouched.
    """
    blocks: list[str] = []
    directives = dossier.get("directives")
    if isinstance(directives, dict):
        raw_note = directives.get("notesForPlanner")
        if isinstance(raw_note, str):
            note = raw_note.strip()
            if note:
                blocks.append(f"{_OPERATOR_DIRECTIVE_NOTE_PREFIX}{note}")

    blocks.extend(_mood_visual_note_blocks(dossier))
    if not blocks:
        return

    existing = brief.get("notesForPlanner")
    if isinstance(existing, str) and existing.strip():
        blocks.append(existing.strip())
    brief["notesForPlanner"] = "\n\n".join(blocks)


def build_site_brief_mock(run_id: str, dossier: dict, scaffold: dict) -> dict:
    """Mock Site Brief derived from the dossier (no LLM).

    Returns the canonical Site Brief artefakt shape locked in
    ``governance/schemas/site-brief.schema.json`` (ADR 0013). Project Input
    fields are projected into the canonical fields rather than written
    alongside; the per-Project-Input data still lives in the source file
    under ``examples/`` for downstream phases that need the raw company /
    trust-signal payload.

    ``requestedCapabilities`` honours an explicit value from the Project
    Input, including an explicit empty list. Only when the field is absent
    does the builder fall back to the service-id stub.
    """
    from scripts.build_site import utc_now

    requested = dossier.get("requestedCapabilities")
    if requested is None:
        requested = [svc["id"] for svc in dossier["services"]]
    company = dossier["company"]
    location = dossier.get("location") or {}
    tone_block = dossier.get("tone") or {}
    if isinstance(tone_block, dict):
        tone_words = [tone_block.get("primary")] + list(tone_block.get("secondary") or [])
        tone = [t for t in tone_words if t]
    else:
        tone = list(tone_block)
    location_parts = [
        location.get("city"),
        location.get("region"),
        location.get("country"),
    ]
    location_hint = ", ".join(p for p in location_parts if p) or None
    brief = {
        "runId": run_id,
        "language": dossier["language"],
        "rawPrompt": project_input_to_brief_prompt(dossier),
        "businessTypeGuess": company.get("businessType"),
        "pageCount": None,
        "tone": tone,
        "targetAudience": [],
        "requestedCapabilities": list(requested),
        "locationHint": location_hint,
        "conversionGoals": list(dossier.get("conversionGoals") or []),
        "servicesMentioned": [svc["id"] for svc in dossier.get("services", [])],
        "contentDepth": None,
        "notesForPlanner": (
            f"Mock brief for Project Input '{dossier.get('siteId')}' - planningModel "
            "wires in Sprint 2B."
        ),
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "briefSource": "mock-no-key",
        "briefError": None,
        "createdAt": utc_now().isoformat(timespec="seconds"),
        "scaffoldHint": scaffold["id"],
    }
    _apply_operator_directive_note(brief, dossier)
    return brief


def resolve_brief_model() -> str:
    """Resolve briefModel via the canonical helper in packages.generation.brief.

    Thin local wrapper kept only so the rest of this module can call it
    without importing through `packages.generation.brief.resolve_brief_model`
    everywhere.
    """
    from packages.generation.brief import resolve_brief_model as _resolve

    return _resolve()


def _join_values(values: list[Any]) -> str:
    return ", ".join(str(value) for value in values if value)


def project_input_to_brief_prompt(dossier: dict) -> str:
    """Create deterministic briefModel input from a Project Input.

    Builder examples already contain structured Project Input data, while
    briefModel expects a raw prompt. This adapter only restates existing facts
    so Phase 1 can run without inventing additional planning behavior.
    """
    company = dossier["company"]
    location = dossier["location"]
    tone = dossier.get("tone", {})
    selected = dossier.get("selectedDossiers", {})

    services = "\n".join(
        f"- {service['id']}: {service['label']} — {service['summary']}"
        for service in dossier.get("services", [])
    )
    trust = "\n".join(f"- {item}" for item in dossier.get("trustSignals", []))

    return (
        "Build a business website from this Project Input.\n\n"
        f"Company: {company.get('name')}\n"
        f"Business type: {company.get('businessType')}\n"
        f"Tagline: {company.get('tagline')}\n"
        f"Story: {company.get('story')}\n"
        f"Location: {location.get('city')}, {location.get('region')}, {location.get('country')}\n"
        f"Service areas: {_join_values(location.get('serviceAreas', []))}\n"
        f"Language: {dossier.get('language')}\n"
        f"Tone primary: {tone.get('primary')}\n"
        f"Tone secondary: {_join_values(tone.get('secondary', []))}\n"
        f"Tone avoid: {_join_values(tone.get('avoid', []))}\n"
        f"Conversion goals: {_join_values(dossier.get('conversionGoals', []))}\n"
        f"Requested capabilities: {_join_values(dossier.get('requestedCapabilities', []))}\n"
        f"Required dossiers: {_join_values(selected.get('required', []))}\n\n"
        "Services:\n"
        f"{services}\n\n"
        "Trust signals:\n"
        f"{trust}\n"
    )


# --- B180: Site Brief carry-forward on follow-up builds ---------------------
#
# Every build (init AND follow-up) used to call briefModel anew, so all
# brief-derived copy (about-story, hero subheadline, "quick facts", ...)
# drifted on EVERY follow-up even when the prompt was a pure restyle ("gör
# sajten mörkblå"). B173 pinned only the hero H1; this is the root-cause fix
# for the rest: when the brief INPUT is unchanged, the previous run's brief is
# reused byte-stably, with a deterministic refresh of exactly the fields
# planning consumes from the new Project Input.

# Prompt lines masked in the reuse comparison. These drive structure/typography
# deterministically through the Project Input itself (planning reads
# requestedCapabilities from the refreshed brief, tone/dossiers from the PI),
# not creative copy - so a capability/tone-only follow-up still reuses the
# creative brief instead of re-rolling all copy.
_MASKED_BRIEF_PROMPT_LINE_PREFIXES = (
    "Tone primary:",
    "Tone secondary:",
    "Tone avoid:",
    "Requested capabilities:",
    "Required dossiers:",
)

# The exact preamble extract_site_brief prepends to the model's user message
# ("[language hint: sv]\n\n..."); the model echoes it back in rawPrompt.
_LANGUAGE_HINT_PREFIX_RE = re.compile(r"^\[language hint: [^\]\n]*\]\n\n")


def _masked_brief_input(prompt: str) -> str:
    """Project a brief prompt onto the lines that drive CREATIVE copy.

    Strips the optional ``[language hint: ...]`` preamble and drops the masked
    lines above, so two brief inputs compare equal exactly when the creative
    content (company facts, story, services, trust signals, ...) is unchanged.
    """
    body = _LANGUAGE_HINT_PREFIX_RE.sub("", prompt or "")
    kept = [
        line
        for line in body.splitlines()
        if not line.startswith(_MASKED_BRIEF_PROMPT_LINE_PREFIXES)
    ]
    return "\n".join(kept)


def _deterministic_note_blocks(dossier: dict) -> list[str]:
    """The note blocks ``_apply_operator_directive_note`` derives from a PI."""
    blocks: list[str] = []
    directives = dossier.get("directives")
    if isinstance(directives, dict):
        raw_note = directives.get("notesForPlanner")
        if isinstance(raw_note, str) and raw_note.strip():
            blocks.append(f"{_OPERATOR_DIRECTIVE_NOTE_PREFIX}{raw_note.strip()}")
    blocks.extend(_mood_visual_note_blocks(dossier))
    return blocks


def reuse_previous_site_brief(
    run_id: str,
    dossier: dict,
    previous_run_dir: Path,
) -> dict | None:
    """Carry the previous run's Site Brief forward when its input is unchanged.

    Returns the carried brief (deepcopy, schema-stable) or ``None`` when the
    brief must be regenerated. Read-only: only the previous run's
    ``site-brief.json`` is read, nothing is written.

    Reuse requires ALL of:

    - The previous brief exists and parses.
    - Source parity: previous ``briefSource == "real"`` while a key is set, or
      ``"mock-no-key"`` while no key is set. An error fallback
      (mock-llm-error / mock-import-error) or a no-key -> key upgrade always
      regenerates.
    - The masked brief input (``project_input_to_brief_prompt`` minus the
      language-hint preamble and the masked capability/tone/dossier lines)
      is byte-identical to the previous run's ``rawPrompt``.
    - Every deterministic note block the new PI would inject (operator
      directive + mood-vision notes) is already present in the previous
      brief's ``notesForPlanner`` - a new directive must reach the planner,
      so it regenerates.

    The carried brief refreshes ONLY deterministic fields: ``runId``,
    ``createdAt``, ``rawPrompt`` (the new prompt, same preamble form) and the
    fields planning consumes from the new PI - ``requestedCapabilities`` (so a
    capability/section follow-up still mounts, plan.py reads it from the
    brief) and ``tone`` (PI tone block, mirroring the mock derivation). All
    creative fields (positioning/contentStrategy/businessFacts/conversion/
    notesForPlanner/...) stay byte-stable. ``briefSource`` is carried
    unchanged: the schema enum is locked, and the reuse is reported as a
    trace event by the caller, not as a new artefakt field.
    """
    from packages.generation.brief import has_openai_api_key

    try:
        previous = json.loads(
            (previous_run_dir / "site-brief.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(previous, dict):
        return None

    expected_source = "real" if has_openai_api_key() else "mock-no-key"
    if previous.get("briefSource") != expected_source:
        return None

    previous_raw = previous.get("rawPrompt")
    if not isinstance(previous_raw, str) or not previous_raw.strip():
        return None
    new_prompt = project_input_to_brief_prompt(dossier)
    if _masked_brief_input(new_prompt) != _masked_brief_input(previous_raw):
        return None

    previous_notes = previous.get("notesForPlanner")
    notes_text = previous_notes if isinstance(previous_notes, str) else ""
    new_blocks = _deterministic_note_blocks(dossier)
    # Forward: every deterministic block the NEW PI injects must already be in
    # the previous brief - an ADDED or CHANGED directive/mood note must reach
    # the planner, so it regenerates.
    for block in new_blocks:
        if block not in notes_text:
            return None
    # Reverse (removed-notes guard): if the previous brief carries an operator-
    # directive or mood-vision block but the NEW PI injects none of that kind,
    # the operator REMOVED that directive. The previous brief's creative copy
    # was shaped by it, so a byte-stable reuse would silently keep the dropped
    # instruction's influence - regenerate instead.
    new_has_operator = any(
        block.startswith(_OPERATOR_DIRECTIVE_NOTE_PREFIX) for block in new_blocks
    )
    new_has_mood = any(
        block.startswith(_MOOD_VISUAL_NOTE_PREFIX) for block in new_blocks
    )
    if _OPERATOR_DIRECTIVE_NOTE_PREFIX in notes_text and not new_has_operator:
        return None
    if _MOOD_VISUAL_NOTE_PREFIX in notes_text and not new_has_mood:
        return None

    from scripts.build_site import utc_now

    carried = copy.deepcopy(previous)
    carried["runId"] = run_id
    carried["createdAt"] = utc_now().isoformat(timespec="seconds")
    if _LANGUAGE_HINT_PREFIX_RE.match(previous_raw):
        carried["rawPrompt"] = (
            f"[language hint: {dossier.get('language')}]\n\n{new_prompt}"
        )
    else:
        carried["rawPrompt"] = new_prompt
    requested = dossier.get("requestedCapabilities")
    if requested is None:
        requested = [svc["id"] for svc in dossier.get("services", [])]
    carried["requestedCapabilities"] = list(requested)
    tone_block = dossier.get("tone") or {}
    if isinstance(tone_block, dict):
        tone_words = [tone_block.get("primary")] + list(tone_block.get("secondary") or [])
        carried["tone"] = [t for t in tone_words if t]
    else:
        carried["tone"] = list(tone_block)
    return carried


def _mock_brief_after_llm_failure(
    run_id: str,
    dossier: dict,
    scaffold: dict,
    *,
    error: str,
    attempted_model: str | None,
) -> dict:
    brief = build_site_brief_mock(run_id, dossier, scaffold)
    brief.update(
        {
            "briefSource": "mock-llm-error",
            "briefError": error,
            "attemptedModel": attempted_model,
        }
    )
    return brief


def build_site_brief(run_id: str, dossier: dict, scaffold: dict) -> dict:
    """Build Site Brief with briefModel when available, otherwise mock fallback."""
    from packages.generation.brief import has_openai_api_key

    if not has_openai_api_key():
        print("No OPENAI_API_KEY - using mock Site Brief")
        return build_site_brief_mock(run_id, dossier, scaffold)

    model: str | None = None
    try:
        model = resolve_brief_model()
        prompt = project_input_to_brief_prompt(dossier)

        from packages.generation.brief import extract_site_brief, site_brief_to_artifact

        print(f"Calling briefModel ({model}) for Site Brief")
        result = extract_site_brief(
            prompt,
            model=model,
            language_hint=dossier.get("language"),
        )
        if result.source != "real":
            error = result.error or f"briefModel returned fallback source {result.source}"
            print(
                f"Warning: briefModel failed - using mock Site Brief fallback ({error})",
                file=sys.stderr,
            )
            return _mock_brief_after_llm_failure(
                run_id,
                dossier,
                scaffold,
                error=error,
                attempted_model=model,
            )

        brief = site_brief_to_artifact(result, run_id=run_id, model=model)
        brief["scaffoldHint"] = scaffold["id"]
        _apply_operator_directive_note(brief, dossier)
        return brief
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        print(
            f"Warning: briefModel path failed - using mock Site Brief fallback ({error})",
            file=sys.stderr,
        )
        return _mock_brief_after_llm_failure(
            run_id,
            dossier,
            scaffold,
            error=error,
            attempted_model=model,
        )
