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

``utc_now`` stays in ``scripts/build_site.py`` (the io-helpers slice has not
landed yet), so ``build_site_brief_mock`` bridges it via a lazy
``from scripts.build_site import utc_now`` inside its body (same pattern slice 3
used for ``load_json`` / ``_to_repo_relative``).
"""

from __future__ import annotations

import sys
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
