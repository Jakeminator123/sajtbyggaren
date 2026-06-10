"""Site Brief carry-forward across follow-up rebuilds (B180).

Repro (volt-watt, 2026-06-10, real briefModel key): a pure colour restyle
("gör sajten mörkblå") changed the about-story, the hero subheadline and the
"quick facts" lines — every follow-up re-called briefModel, so ALL
brief-derived copy drifted. B173 pinned only the hero H1; this locks the
root-cause fix: ``reuse_previous_site_brief`` carries the previous run's
brief forward byte-stably when the brief INPUT is unchanged, with a
deterministic refresh of exactly the fields planning consumes from the new
Project Input (``requestedCapabilities``, ``tone``).

Locked here:

1. Reuse decision: identical input -> reuse; changed company name/story ->
   regenerate; changed capabilities/tone -> reuse with refreshed fields;
   source parity (real needs a key, mock-no-key needs no key, error
   fallbacks always regenerate); a NEW operator directive regenerates.
2. Schema: a carried brief still passes ``validate_site_brief``.
3. Integration (mock-no-key, tmp_path, real chain): a restyle/section-add
   follow-up reuses the previous brief (sentinel survives) while
   ``requestedCapabilities`` follows the NEW Project Input; a company-name
   change regenerates.

Everything runs without OPENAI_API_KEY and is fully deterministic.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from packages.generation.artifacts import validate_site_brief
from packages.generation.brief.site_brief import (
    build_site_brief_mock,
    project_input_to_brief_prompt,
    reuse_previous_site_brief,
)

pytestmark = [pytest.mark.tooling, pytest.mark.core]

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "painter-palma.project-input.json"
SITE_ID = "painter-palma"
SCAFFOLD = {"id": "local-service-business"}
SENTINEL = "SENTINEL-POSITIONING-B180-skall-overleva-carry-forward"


def _dossier() -> dict[str, Any]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _write_previous_run(
    tmp_path: Path,
    brief: dict[str, Any],
    *,
    run_id: str = "run-prev",
) -> Path:
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "site-brief.json").write_text(
        json.dumps(brief, ensure_ascii=False), encoding="utf-8"
    )
    return run_dir


def _previous_mock_brief(
    dossier: dict[str, Any], **overrides: Any
) -> dict[str, Any]:
    """A schema-valid previous brief (mock derivation) with a sentinel."""
    brief = build_site_brief_mock("run-prev", dossier, SCAFFOLD)
    brief["positioning"] = {"oneLiner": SENTINEL}
    brief.update(overrides)
    return brief


def _previous_real_brief(dossier: dict[str, Any]) -> dict[str, Any]:
    """A schema-valid previous brief shaped like the REAL briefModel path:
    briefSource=real and a rawPrompt that echoes the language-hint preamble."""
    brief = _previous_mock_brief(dossier)
    brief["briefSource"] = "real"
    brief["modelUsed"] = "gpt-test"
    brief["rawPrompt"] = (
        f"[language hint: {dossier['language']}]\n\n"
        + project_input_to_brief_prompt(dossier)
    )
    return brief


# ---------------------------------------------------------------------------
# 1. Reuse decision (unit, no key unless stated)
# ---------------------------------------------------------------------------


def test_identical_input_reuses_previous_brief(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dossier = _dossier()
    previous = _previous_mock_brief(dossier)
    run_dir = _write_previous_run(tmp_path, previous)

    carried = reuse_previous_site_brief("run-new", dossier, run_dir)
    assert carried is not None
    assert carried["runId"] == "run-new"
    assert carried["positioning"]["oneLiner"] == SENTINEL
    # Everything creative is byte-stable: only the deterministic refresh
    # fields may differ from the previous artefakt.
    refreshed = {"runId", "createdAt", "rawPrompt", "requestedCapabilities", "tone"}
    for key in set(previous) - refreshed:
        assert carried[key] == previous[key], f"creative field {key} drifted"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["company"].__setitem__("name", "Palma Proffsmålarna"),
        lambda d: d["company"].__setitem__("story", "En helt ny historia."),
        lambda d: d["services"][0].__setitem__("summary", "Nytt tjänsteinnehåll."),
        lambda d: d["trustSignals"].append("Ny trust-signal"),
    ],
    ids=["company-name", "story", "service-summary", "trust-signal"],
)
def test_changed_creative_input_regenerates(monkeypatch, tmp_path, mutate):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    base = _dossier()
    run_dir = _write_previous_run(tmp_path, _previous_mock_brief(base))

    changed = copy.deepcopy(base)
    mutate(changed)
    assert reuse_previous_site_brief("run-new", changed, run_dir) is None


def test_changed_capabilities_reuse_with_refreshed_field(monkeypatch, tmp_path):
    """A capability-only change (the section_add family) still reuses the
    creative brief, but requestedCapabilities follows the NEW Project Input -
    plan.py reads brief.requestedCapabilities, so the new capability mounts."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    base = _dossier()
    run_dir = _write_previous_run(tmp_path, _previous_mock_brief(base))

    changed = copy.deepcopy(base)
    changed["requestedCapabilities"] = ["interactive-game", "faq-section"]
    changed["selectedDossiers"]["required"] = [
        "interactive-game-loop",
        "faq-section",
    ]
    carried = reuse_previous_site_brief("run-new", changed, run_dir)
    assert carried is not None
    assert carried["requestedCapabilities"] == ["interactive-game", "faq-section"]
    assert carried["positioning"]["oneLiner"] == SENTINEL


def test_changed_tone_reuse_with_refreshed_field(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    base = _dossier()
    run_dir = _write_previous_run(tmp_path, _previous_mock_brief(base))

    changed = copy.deepcopy(base)
    changed["tone"]["primary"] = "energisk"
    carried = reuse_previous_site_brief("run-new", changed, run_dir)
    assert carried is not None
    assert carried["tone"][0] == "energisk"
    assert carried["positioning"]["oneLiner"] == SENTINEL


def test_no_key_to_key_upgrade_regenerates(monkeypatch, tmp_path):
    """A mock-no-key brief is never carried once a key exists - the upgrade
    must run the real briefModel."""
    dossier = _dossier()
    run_dir = _write_previous_run(tmp_path, _previous_mock_brief(dossier))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    assert reuse_previous_site_brief("run-new", dossier, run_dir) is None


def test_real_brief_is_not_carried_without_key(monkeypatch, tmp_path):
    """Key removed -> the honest mock path runs; a stale real brief is never
    presented as the product of the current (key-less) configuration."""
    dossier = _dossier()
    run_dir = _write_previous_run(tmp_path, _previous_real_brief(dossier))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert reuse_previous_site_brief("run-new", dossier, run_dir) is None


@pytest.mark.parametrize("source", ["mock-llm-error", "mock-import-error"])
def test_error_fallback_always_regenerates(monkeypatch, tmp_path, source):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dossier = _dossier()
    previous = _previous_mock_brief(dossier, briefSource=source)
    run_dir = _write_previous_run(tmp_path, previous)
    assert reuse_previous_site_brief("run-new", dossier, run_dir) is None


def test_real_brief_reuse_keeps_language_hint_preamble_form(monkeypatch, tmp_path):
    """A real brief (rawPrompt echoes '[language hint: ...]') is reused with a
    refreshed rawPrompt in the SAME preamble form."""
    dossier = _dossier()
    run_dir = _write_previous_run(tmp_path, _previous_real_brief(dossier))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")

    carried = reuse_previous_site_brief("run-new", dossier, run_dir)
    assert carried is not None
    assert carried["briefSource"] == "real"
    assert carried["rawPrompt"].startswith("[language hint: sv]\n\n")
    assert carried["positioning"]["oneLiner"] == SENTINEL


def test_new_operator_directive_regenerates(monkeypatch, tmp_path):
    """A directive block the previous brief never saw must reach the planner -
    the brief regenerates instead of carrying stale notes."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    base = _dossier()
    run_dir = _write_previous_run(tmp_path, _previous_mock_brief(base))

    changed = copy.deepcopy(base)
    changed["directives"] = {"notesForPlanner": "Lyft fram fasadmålning."}
    assert reuse_previous_site_brief("run-new", changed, run_dir) is None


def test_known_operator_directive_still_reuses(monkeypatch, tmp_path):
    """The SAME directive the previous brief already carries does not block
    reuse (it is already in notesForPlanner via the deterministic injector)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    base = _dossier()
    base["directives"] = {"notesForPlanner": "Lyft fram fasadmålning."}
    previous = _previous_mock_brief(base)
    assert "Operator: Lyft fram fasadmålning." in previous["notesForPlanner"]
    run_dir = _write_previous_run(tmp_path, previous)

    carried = reuse_previous_site_brief("run-new", base, run_dir)
    assert carried is not None
    assert carried["positioning"]["oneLiner"] == SENTINEL


def test_removed_operator_directive_regenerates(monkeypatch, tmp_path):
    """A directive the PREVIOUS brief carried but the new Project Input dropped
    must regenerate: the previous brief's creative copy was shaped by that
    directive, so a byte-stable reuse would silently keep the removed
    instruction's influence (the operator deleted it on purpose)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    base = _dossier()
    base["directives"] = {"notesForPlanner": "Lyft fram fasadmålning."}
    previous = _previous_mock_brief(base)
    assert "Operator: Lyft fram fasadmålning." in previous["notesForPlanner"]
    run_dir = _write_previous_run(tmp_path, previous)

    # The new version removes the operator directive entirely.
    without_directive = copy.deepcopy(base)
    without_directive.pop("directives", None)
    assert reuse_previous_site_brief("run-new", without_directive, run_dir) is None


def test_missing_or_malformed_previous_brief_regenerates(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dossier = _dossier()
    empty_run = tmp_path / "run-empty"
    empty_run.mkdir()
    assert reuse_previous_site_brief("run-new", dossier, empty_run) is None

    broken_run = tmp_path / "run-broken"
    broken_run.mkdir()
    (broken_run / "site-brief.json").write_text("{not json", encoding="utf-8")
    assert reuse_previous_site_brief("run-new", dossier, broken_run) is None


# ---------------------------------------------------------------------------
# 2. Schema: a carried brief is still a valid Site Brief artefakt
# ---------------------------------------------------------------------------


def test_carried_brief_passes_site_brief_schema(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dossier = _dossier()
    run_dir = _write_previous_run(tmp_path, _previous_mock_brief(dossier))
    carried = reuse_previous_site_brief("run-new", dossier, run_dir)
    assert carried is not None
    validate_site_brief(carried)


def test_carried_real_brief_passes_site_brief_schema(monkeypatch, tmp_path):
    dossier = _dossier()
    run_dir = _write_previous_run(tmp_path, _previous_real_brief(dossier))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    carried = reuse_previous_site_brief("run-new", dossier, run_dir)
    assert carried is not None
    validate_site_brief(carried)


# ---------------------------------------------------------------------------
# 3. Integration: the REAL follow-up chain reuses/regenerates correctly
# ---------------------------------------------------------------------------


def _init_build(monkeypatch, tmp_path):
    """Init-build painter-palma into tmp storage (mock-no-key, no npm)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import build

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"
    _target, v1_run_dir = build(
        EXAMPLE,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs_dir=prompt_inputs,
    )
    return prompt_inputs, runs_dir, generated_dir, v1_run_dir


def _inject_sentinel(run_dir: Path) -> None:
    """Mark the run's brief so a reused brief is distinguishable from a
    deterministically regenerated mock (which would be byte-identical)."""
    brief_path = run_dir / "site-brief.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["positioning"] = {"oneLiner": SENTINEL}
    brief_path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")


def _run_brief(runs_dir: Path, run_id: str) -> dict[str, Any]:
    return json.loads(
        (runs_dir / run_id / "site-brief.json").read_text(encoding="utf-8")
    )


def _trace_events(runs_dir: Path, run_id: str) -> list[str]:
    lines = (runs_dir / run_id / "trace.ndjson").read_text(encoding="utf-8")
    return [json.loads(line)["event"] for line in lines.splitlines() if line.strip()]


def test_followup_chain_restyle_reuses_brief_end_to_end(monkeypatch, tmp_path):
    """Mock-no-key integration over the REAL chain: a pure restyle carries the
    previous brief (sentinel survives) and emits the site_brief.reused trace
    event - exactly the volt-watt repro, byte-stable this time."""
    prompt_inputs, runs_dir, generated_dir, v1_run_dir = _init_build(
        monkeypatch, tmp_path
    )
    _inject_sentinel(v1_run_dir)
    from scripts.build_site import run_followup_chain

    result = run_followup_chain(
        SITE_ID,
        "gör sajten mörkblå",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert result["applied"] is True, result
    v2_brief = _run_brief(runs_dir, result["runId"])
    assert v2_brief.get("positioning", {}).get("oneLiner") == SENTINEL, (
        "the restyle follow-up must carry the previous brief forward"
    )
    assert v2_brief["runId"] == result["runId"]
    assert "site_brief.reused" in _trace_events(runs_dir, result["runId"])


def test_followup_chain_section_add_reuses_brief_and_mounts_capability(
    monkeypatch, tmp_path
):
    """A section_add follow-up reuses the creative brief AND the refreshed
    requestedCapabilities follow the new Project Input, so the new capability
    still mounts (plan.py reads brief.requestedCapabilities)."""
    prompt_inputs, runs_dir, generated_dir, v1_run_dir = _init_build(
        monkeypatch, tmp_path
    )
    _inject_sentinel(v1_run_dir)
    from scripts.build_site import run_followup_chain

    result = run_followup_chain(
        SITE_ID,
        "lägg till en faq-sektion",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert result["applied"] is True, result
    v2_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.project-input.json").read_text(
            encoding="utf-8"
        )
    )
    assert "faq-section" in (v2_pi.get("requestedCapabilities") or [])
    v2_brief = _run_brief(runs_dir, result["runId"])
    assert v2_brief.get("positioning", {}).get("oneLiner") == SENTINEL
    assert v2_brief["requestedCapabilities"] == v2_pi["requestedCapabilities"]


def test_followup_with_changed_company_name_regenerates_brief(
    monkeypatch, tmp_path
):
    """A text-changing follow-up (new company name) must regenerate the brief
    - carrying the old creative copy would bury the operator's edit."""
    prompt_inputs, runs_dir, generated_dir, v1_run_dir = _init_build(
        monkeypatch, tmp_path
    )
    _inject_sentinel(v1_run_dir)

    # Fabricate the v2 Project Input the copy path would write: same site,
    # bumped version, changed company name.
    v1_meta = json.loads(
        (prompt_inputs / f"{SITE_ID}.v1.meta.json").read_text(encoding="utf-8")
    )
    v2_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.v1.project-input.json").read_text(
            encoding="utf-8"
        )
    )
    v2_pi["company"]["name"] = "Palma Proffsmålarna"
    v2_pi_path = prompt_inputs / f"{SITE_ID}.v2.project-input.json"
    v2_pi_path.write_text(json.dumps(v2_pi, ensure_ascii=False), encoding="utf-8")
    v2_meta = {
        "projectId": v1_meta["projectId"],
        "version": 2,
        "previousVersion": 1,
        "mode": "followup",
        "siteId": SITE_ID,
        "scaffoldId": v2_pi["scaffoldId"],
        "variantId": v2_pi["variantId"],
        "followUpPrompt": "byt namnet till Palma Proffsmålarna",
    }
    (prompt_inputs / f"{SITE_ID}.v2.meta.json").write_text(
        json.dumps(v2_meta, ensure_ascii=False), encoding="utf-8"
    )

    from scripts.build_site import build

    _target, v2_run_dir = build(
        v2_pi_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )
    v2_brief = _run_brief(runs_dir, v2_run_dir.name)
    assert v2_brief.get("positioning", {}).get("oneLiner") != SENTINEL, (
        "a changed company name must regenerate the brief, not carry it"
    )
    assert "site_brief.reused" not in _trace_events(runs_dir, v2_run_dir.name)
    assert "Palma Proffsmålarna" in v2_brief["rawPrompt"]
