"""Regression coverage for B155 follow-up no-op honesty.

The tests exercise the builder-side contract only: follow-up builds get an
``appliedVisibleEffect`` boolean in build-result.json, and no-op follow-ups
also emit a structured trace event. UI presentation is intentionally out of
scope for this backend slice.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.build_site import (
    _detect_followup_applied_visible_effect,
    _find_previous_page_snapshot,
    _prompt_meta_applied_followup_directive_kinds,
    _prompt_meta_unapplied_followup_intents,
    build,
)
from scripts.prompt_to_project_input import (
    compute_applied_followup_directive_kinds,
    compute_unapplied_followup_intents,
    generate,
    generate_followup,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

INIT_PROMPT = "Skapa en hemsida för Surdegsbagaren i Malmö."
NO_OP_FOLLOWUP_PROMPT = "Lägg till mycket mer info om surdegsbröd"
SITE_ID = "surdegsbagaren-malmo"
PROJECT_ID = "b155-honest-no-op"
NO_OP_REASONS = {"intent_no_semantic_change", "visible_files_unchanged"}


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_trace_events(run_dir: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in (run_dir / "trace.ndjson").read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


@pytest.mark.tooling
def test_init_build_omits_applied_visible_effect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_path, _ = generate(
        INIT_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )

    _, run_dir = build(
        init_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    build_result = _read_json(run_dir / "build-result.json")
    assert build_result["engineMode"] == "init"
    assert "appliedVisibleEffect" not in build_result
    assert "appliedVisibleEffectReason" not in build_result


@pytest.mark.tooling
def test_sourdough_followup_no_op_writes_build_result_and_trace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Jakob's "more info about sourdough bread" case must be honest.

    The reason assertion deliberately accepts both supported no-op paths:
    if the classifier stays conservative we expect intent-based detection;
    if it later learns a semantic intent, the unchanged page snapshot still
    proves that no visible home-page effect was applied.
    """

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_path, _ = generate(
        INIT_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    build(init_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir)

    _, followup_meta, followup_path, _ = generate_followup(
        NO_OP_FOLLOWUP_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
    )
    _, run_dir_v2 = build(
        followup_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    build_result = _read_json(run_dir_v2 / "build-result.json")
    assert build_result["engineMode"] == "followup"
    assert build_result["appliedVisibleEffect"] is False
    assert build_result["appliedVisibleEffectReason"] in NO_OP_REASONS

    actual_intent = followup_meta["projectDna"]["followUpIntent"]["id"]
    assert isinstance(actual_intent, str)

    events = _read_trace_events(run_dir_v2)
    event_names = [event["event"] for event in events]
    no_op_index = event_names.index("followup.no_op_detected")
    build_result_index = event_names.index("build.result.written")
    assert no_op_index < build_result_index
    no_op_event = events[no_op_index]
    assert no_op_event["status"] == "warning"
    assert no_op_event["reason"] in NO_OP_REASONS


@pytest.mark.tooling
def test_snapshot_diff_marks_semantic_followup_false_when_visible_files_are_unchanged(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    previous_run = runs_root / "previous-run"
    current_run = runs_root / "current-run"
    previous_page = previous_run / "generated-files" / "app" / "page.tsx"
    current_page = current_run / "generated-files" / "app" / "page.tsx"
    previous_page.parent.mkdir(parents=True)
    current_page.parent.mkdir(parents=True)
    previous_page.write_bytes(b"export default function Page() { return null }\n")
    current_page.write_bytes(b"export default function Page() { return null }\n")
    (previous_run / "input.json").write_text(
        json.dumps({"projectId": PROJECT_ID, "version": 1}),
        encoding="utf-8",
    )
    prompt_meta = {
        "mode": "followup",
        "projectId": PROJECT_ID,
        "version": 2,
        "previousVersion": 1,
        "projectDna": {"followUpIntent": {"id": "tone-shift"}},
    }

    effect = _detect_followup_applied_visible_effect(
        runs_root,
        current_run,
        prompt_meta,
        {},
    )

    assert effect == {"applied": False, "reason": "visible_files_unchanged"}


@pytest.mark.tooling
def test_snapshot_diff_marks_semantic_followup_true_when_visible_files_changed(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    previous_run = runs_root / "previous-run"
    current_run = runs_root / "current-run"
    previous_page = previous_run / "generated-files" / "app" / "page.tsx"
    current_page = current_run / "generated-files" / "app" / "page.tsx"
    previous_page.parent.mkdir(parents=True)
    current_page.parent.mkdir(parents=True)
    previous_page.write_bytes(b"previous page\n")
    current_page.write_bytes(b"changed page\n")
    (previous_run / "input.json").write_text(
        json.dumps({"projectId": PROJECT_ID, "version": 1}),
        encoding="utf-8",
    )
    prompt_meta = {
        "mode": "followup",
        "projectId": PROJECT_ID,
        "version": 2,
        "previousVersion": 1,
        "projectDna": {"followUpIntent": {"id": "tone-shift"}},
    }

    effect = _detect_followup_applied_visible_effect(
        runs_root,
        current_run,
        prompt_meta,
        {},
    )

    assert effect == {"applied": True, "reason": "visible_files_changed"}


@pytest.mark.tooling
def test_snapshot_diff_marks_tone_shift_true_when_only_css_changed(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    previous_run = runs_root / "previous-run"
    current_run = runs_root / "current-run"
    for run_dir, css in (
        (previous_run, b":root { --primary: #111111; }\n"),
        (current_run, b":root { --primary: #eeeeee; }\n"),
    ):
        page = run_dir / "generated-files" / "app" / "page.tsx"
        globals_css = run_dir / "generated-files" / "app" / "globals.css"
        page.parent.mkdir(parents=True)
        page.write_bytes(b"export default function Page() { return null }\n")
        globals_css.write_bytes(css)
    (previous_run / "input.json").write_text(
        json.dumps({"projectId": PROJECT_ID, "version": 1}),
        encoding="utf-8",
    )
    prompt_meta = {
        "mode": "followup",
        "projectId": PROJECT_ID,
        "version": 2,
        "previousVersion": 1,
        "projectDna": {"followUpIntent": {"id": "tone-shift"}},
    }

    effect = _detect_followup_applied_visible_effect(
        runs_root,
        current_run,
        prompt_meta,
        {},
    )

    assert effect == {"applied": True, "reason": "visible_files_changed"}


@pytest.mark.tooling
def test_previous_snapshot_lookup_derives_previous_version_from_current_version(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    previous_run = runs_root / "previous-run"
    previous_page = previous_run / "generated-files" / "app" / "page.tsx"
    previous_page.parent.mkdir(parents=True)
    previous_page.write_text("previous\n", encoding="utf-8")
    (previous_run / "input.json").write_text(
        json.dumps({"projectId": PROJECT_ID, "version": 1}),
        encoding="utf-8",
    )
    prompt_meta_without_previous_version = {
        "mode": "followup",
        "projectId": PROJECT_ID,
        "version": 2,
    }

    assert (
        _find_previous_page_snapshot(
            runs_root,
            runs_root / "current-run",
            prompt_meta_without_previous_version,
        )
        == previous_page
    )


# ---------------------------------------------------------------------------
# B155 honest-level-1: per-intent unappliedFollowupIntents signal
# ---------------------------------------------------------------------------
#
# Reproduces data/runs/20260602T151424.516Z-44580d9a-bryggans-bageri-823775
# (v2): a multi-part follow-up where the two new products landed but the hero
# heading rewrite + the reviews section were silently dropped while
# appliedVisibleEffect stayed true.
V2_FOLLOWUP_PROMPT = (
    "Lagg till tva nya produkter: lunchmackor och glutenfritt surdegsbrod. "
    "Skriv om hjaltesektionens rubriktext sa att den varmt valkomnar besokaren "
    "till bageriet i Kalmar, och lagg till en kort sektion med kundomdomen."
)


def _bryggans_v1_project_input() -> dict[str, object]:
    """Shape mirrors the real v1 Project Input snapshot for this site."""
    return {
        "company": {
            "name": "Bryggans Bageri",
            "tagline": "Hjälp med ekologiskt surdegsbröd",
        },
        "requestedCapabilities": ["map"],
        "selectedDossiers": {"required": [], "recommended": []},
        "services": [
            {
                "id": "ekologiskt-surdegsbrod",
                "label": "Ekologiskt surdegsbröd",
                "summary": "Tydlig hjälp med ekologiskt surdegsbröd.",
            }
        ],
    }


def _bryggans_v2_project_input() -> dict[str, object]:
    """v2: two products added (services), reviews capability requested, hero
    heading + tagline byte-stable (the real merge kept them unchanged)."""
    data = copy.deepcopy(_bryggans_v1_project_input())
    data["requestedCapabilities"] = ["map", "reviews"]
    data["services"].extend(
        [
            {
                "id": "lunchmackor",
                "label": "Lunchmackor",
                "summary": "Tydlig hjälp med lunchmackor.",
            },
            {
                "id": "glutenfritt-surdegsbrod",
                "label": "Glutenfritt surdegsbröd",
                "summary": "Tydlig hjälp med glutenfritt surdegsbröd.",
            },
        ]
    )
    return data


@pytest.mark.tooling
def test_compute_unapplied_flags_reviews_and_hero_not_products() -> None:
    """The exact v2 intent must flag hero-rubrik + reviews, never the products."""
    posts = compute_unapplied_followup_intents(
        _bryggans_v1_project_input(),
        _bryggans_v2_project_input(),
        follow_up_prompt=V2_FOLLOWUP_PROMPT,
    )
    targets = {post["target"] for post in posts}

    # Hero rewrite + reviews section recognised-but-not-applied.
    assert targets == {"hero", "reviews"}
    # The two products landed as services - they must never be flagged.
    assert not (targets & {"lunchmackor", "glutenfritt-surdegsbrod", "products"})
    # `map` was a v1 capability (not this follow-up's ask) and is not even a
    # capability-map slug - it must not be flagged either.
    assert "map" not in targets
    for post in posts:
        assert isinstance(post["target"], str) and post["target"].strip()
        assert isinstance(post["reason"], str) and post["reason"].strip()


@pytest.mark.tooling
def test_compute_unapplied_products_only_is_empty() -> None:
    """An additive products-only follow-up has nothing unapplied."""
    previous = _bryggans_v1_project_input()
    merged = copy.deepcopy(previous)
    merged["services"].append(
        {
            "id": "lunchmackor",
            "label": "Lunchmackor",
            "summary": "Tydlig hjälp med lunchmackor.",
        }
    )
    posts = compute_unapplied_followup_intents(
        previous,
        merged,
        follow_up_prompt="Lagg till tva nya produkter: lunchmackor och glutenfritt surdegsbrod.",
    )
    assert posts == []


@pytest.mark.tooling
def test_compute_unapplied_skips_capability_that_is_mounted() -> None:
    """A reviews dossier in selectedDossiers.required means reviews IS rendered."""
    previous = _bryggans_v1_project_input()
    merged = _bryggans_v2_project_input()
    merged["selectedDossiers"] = {"required": ["reviews-display"], "recommended": []}

    posts = compute_unapplied_followup_intents(
        previous, merged, follow_up_prompt=V2_FOLLOWUP_PROMPT
    )
    targets = {post["target"] for post in posts}
    # reviews is mounted now -> not flagged; hero still unapplied.
    assert "reviews" not in targets
    assert "hero" in targets


@pytest.mark.tooling
def test_compute_unapplied_flags_newly_added_unknown_capability_slug() -> None:
    """1b (site-3e7d71ad): a NEWLY requested slug absent from capability-map is
    an honest miss - briefModel can invent a slug ("responsive-badges") that
    codegen v1 cannot mount and Phase 2 rejects, so it must be named in
    unappliedFollowupIntents instead of silently dropped."""
    previous = _bryggans_v1_project_input()
    merged = copy.deepcopy(previous)
    merged["requestedCapabilities"] = ["map", "responsive-badges"]

    posts = compute_unapplied_followup_intents(
        previous,
        merged,
        follow_up_prompt="Gor badges responsiva.",
    )
    targets = {post["target"] for post in posts}
    assert "responsive-badges" in targets
    # ``map`` was a v1 capability (not this follow-up's delta) and stays silent.
    assert "map" not in targets
    for post in posts:
        assert isinstance(post["target"], str) and post["target"].strip()
        assert isinstance(post["reason"], str) and post["reason"].strip()


@pytest.mark.tooling
def test_compute_unapplied_ignores_unknown_slug_already_in_previous() -> None:
    """An unknown slug that was ALREADY requested in the previous version is not
    this follow-up's delta, so it must not be re-flagged on every later build."""
    previous = _bryggans_v1_project_input()
    previous["requestedCapabilities"] = ["map", "responsive-badges"]
    merged = copy.deepcopy(previous)

    posts = compute_unapplied_followup_intents(
        previous,
        merged,
        follow_up_prompt="Lagg till mer info om brod.",
    )
    targets = {post["target"] for post in posts}
    assert "responsive-badges" not in targets


@pytest.mark.tooling
def test_compute_unapplied_hero_suppressed_when_heading_changed() -> None:
    """An explicit heading rewrite that DID change company.name is not flagged."""
    previous = _bryggans_v1_project_input()
    merged = copy.deepcopy(previous)
    merged["company"]["name"] = "Bryggans Surdegsbageri"

    posts = compute_unapplied_followup_intents(
        previous,
        merged,
        follow_up_prompt="Skriv om hjaltesektionens rubrik till Bryggans Surdegsbageri",
    )
    targets = {post["target"] for post in posts}
    assert "hero" not in targets


@pytest.mark.tooling
def test_compute_unapplied_hero_requires_rewrite_verb() -> None:
    """No rewrite verb -> the hero rule stays silent (avoids false positives)."""
    previous = _bryggans_v1_project_input()
    merged = copy.deepcopy(previous)

    posts = compute_unapplied_followup_intents(
        previous,
        merged,
        follow_up_prompt="Berätta mer om hjältesektionen för mig.",
    )
    assert posts == []


@pytest.mark.tooling
def test_prompt_meta_reader_validates_dedupes_and_caps() -> None:
    """The build_site reader rejects malformed entries and bounds strings."""
    meta = {
        "unappliedFollowupIntents": [
            {"target": "reviews", "reason": "ok"},
            {"target": "reviews", "reason": "duplicate target dropped"},
            {"target": "  ", "reason": "blank target dropped"},
            {"target": "hero"},  # missing reason -> dropped
            "not-a-dict",  # dropped
            {"target": "x" * 200, "reason": "y" * 1000},
        ]
    }
    posts = _prompt_meta_unapplied_followup_intents(meta)
    targets = [post["target"] for post in posts]

    assert targets.count("reviews") == 1
    assert "hero" not in targets  # reason was missing
    long_post = next(post for post in posts if post["target"].startswith("x"))
    assert len(long_post["target"]) <= 80
    assert len(long_post["reason"]) <= 400


@pytest.mark.tooling
def test_prompt_meta_reader_handles_missing_or_malformed_field() -> None:
    assert _prompt_meta_unapplied_followup_intents(None) == []
    assert _prompt_meta_unapplied_followup_intents({}) == []
    assert _prompt_meta_unapplied_followup_intents(
        {"unappliedFollowupIntents": "nope"}
    ) == []


@pytest.mark.tooling
def test_hero_rewrite_followup_surfaces_signal_in_build_result_and_trace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-to-end: a no-op + hero-rewrite follow-up writes the honest signal.

    Uses the deterministic mock path (no OPENAI_API_KEY). "Lägg till ..."
    classifies as no-semantic-change so the hero heading/tagline stay
    byte-stable; the hero rewrite then has no copyDirective target and is
    reported via unappliedFollowupIntents + a trace event, while
    appliedVisibleEffect remains the unchanged global boolean.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_path, _ = generate(
        INIT_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    build(init_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir)

    # The real v2 prompt: "Lägg till ..." keeps the intent no-semantic-change
    # (hero heading/tagline byte-stable) and "rubriktext" does not word-match
    # the deterministic name keyword "rubrik", so no copyDirective is applied -
    # exactly the silent hero drop the signal must surface.
    _, followup_meta, followup_path, _ = generate_followup(
        V2_FOLLOWUP_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
    )
    # The sidecar carries the honest signal (deterministic for the hero rule).
    meta_posts = followup_meta.get("unappliedFollowupIntents")
    assert isinstance(meta_posts, list)
    assert any(post["target"] == "hero" for post in meta_posts)

    _, run_dir_v2 = build(
        followup_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    build_result = _read_json(run_dir_v2 / "build-result.json")
    posts = build_result["unappliedFollowupIntents"]
    assert any(post["target"] == "hero" for post in posts)
    # The complement does not replace the global boolean - both coexist.
    assert "appliedVisibleEffect" in build_result

    events = _read_trace_events(run_dir_v2)
    event_names = [event["event"] for event in events]
    assert "followup.unapplied_intents_detected" in event_names
    assert event_names.index("followup.unapplied_intents_detected") < event_names.index(
        "build.result.written"
    )
    unapplied_event = events[event_names.index("followup.unapplied_intents_detected")]
    assert unapplied_event["status"] == "warning"
    assert "hero" in str(unapplied_event["reason"])


# --- ROW 3 (copy-passthrough fix 2026-06-09): intent-applied honesty --------
#
# appliedVisibleEffect answers "did your intent land?", not just "did bytes
# change?". When the operator explicitly asked to replace a quoted copy string
# but no copyDirective applied, a regenerated paraphrase that changes bytes must
# NOT be reported as a successful edit (the lask-ab trust bug).

_COPY_REPLACE_PROMPT = 'ändra denna text "Den gamla hjälten" till "Den nya hjälten"'


def _force_visible_change(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Force the ``visible_files_changed`` branch of the effect detector."""
    import scripts.build_site as bs

    monkeypatch.setattr(
        bs,
        "_find_previous_generated_files_snapshot",
        lambda *a, **k: tmp_path / "prev-snapshot",
    )
    monkeypatch.setattr(bs, "_visible_snapshots_changed", lambda *a, **k: True)


@pytest.mark.tooling
def test_copy_replace_no_op_is_honest_even_when_bytes_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ROW 3: an explicit quoted copy-replace request that produced NO
    copyDirective reports applied=False even when an unrelated rebuild changed
    visible bytes - a regenerated paraphrase must not look like a success."""
    _force_visible_change(monkeypatch, tmp_path)
    run_dir = tmp_path / "runs" / "v2"
    run_dir.mkdir(parents=True)
    prompt_meta = {"mode": "followup", "followUpPrompt": _COPY_REPLACE_PROMPT}
    dossier = {"company": {"name": "X"}}  # no directives.copyDirectives

    effect = _detect_followup_applied_visible_effect(
        tmp_path / "runs", run_dir, prompt_meta, dossier
    )
    assert effect == {"applied": False, "reason": "copy_directive_not_applied"}


@pytest.mark.tooling
def test_copy_replace_no_op_is_honest_under_mangled_verb(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B204 encoding-robustness: the operator's stored followUpPrompt arrives
    with the leading "Ä" mangled to "*" ("Ändra" -> "*ndra"). The honest-effect
    gate keys on the quoted OLD/NEW pair, not the verb keyword, so a quoted
    copy-replace that produced NO copyDirective is still reported as an honest
    no-op (copy_directive_not_applied) instead of letting an unrelated rebuild
    byte-diff pose as a successful edit (#313 contract holds under mangling)."""
    _force_visible_change(monkeypatch, tmp_path)
    run_dir = tmp_path / "runs" / "v2"
    run_dir.mkdir(parents=True)
    mangled_prompt = '*ndra denna text "Den gamla hjälten" till "Den nya hjälten"'
    prompt_meta = {"mode": "followup", "followUpPrompt": mangled_prompt}
    dossier = {"company": {"name": "X"}}  # no directives.copyDirectives

    effect = _detect_followup_applied_visible_effect(
        tmp_path / "runs", run_dir, prompt_meta, dossier
    )
    assert effect == {"applied": False, "reason": "copy_directive_not_applied"}


@pytest.mark.tooling
def test_copy_replace_applied_reports_visible_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ROW 3 guard: when the copyDirective DID apply, a visible byte change is
    honestly reported as applied."""
    _force_visible_change(monkeypatch, tmp_path)
    run_dir = tmp_path / "runs" / "v2"
    run_dir.mkdir(parents=True)
    prompt_meta = {"mode": "followup", "followUpPrompt": _COPY_REPLACE_PROMPT}
    dossier = {
        "company": {"name": "X"},
        "directives": {
            "copyDirectives": [
                {
                    "target": "tagline",
                    "operation": "replace-text",
                    "payload": "Den nya hjälten",
                    "source": "prompt-rule",
                }
            ]
        },
    }
    effect = _detect_followup_applied_visible_effect(
        tmp_path / "runs", run_dir, prompt_meta, dossier
    )
    assert effect == {"applied": True, "reason": "visible_files_changed"}


@pytest.mark.tooling
def test_non_copy_followup_visible_change_unaffected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ROW 3 guard: a NON-copy-replace follow-up (tone/section change) keeps
    reporting visible_files_changed - the honesty tightening only touches
    explicit quoted copy-replace requests, so section_add stays unaffected."""
    _force_visible_change(monkeypatch, tmp_path)
    run_dir = tmp_path / "runs" / "v2"
    run_dir.mkdir(parents=True)
    prompt_meta = {
        "mode": "followup",
        "followUpPrompt": "gör tonen mörkare och mer premium",
    }
    dossier = {"company": {"name": "X"}}
    effect = _detect_followup_applied_visible_effect(
        tmp_path / "runs", run_dir, prompt_meta, dossier
    )
    assert effect == {"applied": True, "reason": "visible_files_changed"}


@pytest.mark.tooling
def test_additive_section_add_with_quote_reports_visible_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """#224 P2: an additive 'lägg till en FAQ-sektion med texten "..."' that
    added a visible section (bytes changed) must report applied=True, NOT a
    phantom copy_directive_not_applied no-op. The quoted text is the NEW
    section's copy, not an OLD string the operator asked to swap - so a
    successful visible add is never reported as a failed copy no-op."""
    _force_visible_change(monkeypatch, tmp_path)
    run_dir = tmp_path / "runs" / "v2"
    run_dir.mkdir(parents=True)
    prompt_meta = {
        "mode": "followup",
        "followUpPrompt": 'lägg till en FAQ-sektion med texten "Vanliga frågor"',
    }
    # A section_add records no copyDirectives - exactly the state that used to
    # trip the copy_directive_not_applied branch.
    dossier = {"company": {"name": "X"}}
    effect = _detect_followup_applied_visible_effect(
        tmp_path / "runs", run_dir, prompt_meta, dossier
    )
    assert effect == {"applied": True, "reason": "visible_files_changed"}


# --- 1a (site-3e7d71ad, 2026-06-12): intent_not_executable honesty -----------
#
# A follow-up whose intent no executor owns ("ta bort sidan Kontakt",
# "gör badges responsiva") still produced a byte diff (brief paraphrase) and
# reported applied=true. The legacy resolver now records exactly which
# executor-owned edits it applied in appliedFollowupDirectiveKinds; an empty
# list over a byte diff is an honest intent_not_executable no-op.


def _bryggans_v1_with_theme() -> dict[str, object]:
    data = _bryggans_v1_project_input()
    data["brand"] = {"primaryColorHex": "#111111"}
    data["tone"] = {"primary": "trustworthy"}
    return data


@pytest.mark.tooling
def test_compute_applied_kinds_copy_directive() -> None:
    previous = _bryggans_v1_project_input()
    merged = copy.deepcopy(previous)
    merged["directives"] = {
        "copyDirectives": [
            {"target": "tagline", "operation": "replace-text", "payload": "Ny tagline"}
        ]
    }
    assert "copy" in compute_applied_followup_directive_kinds(previous, merged)


@pytest.mark.tooling
def test_compute_applied_kinds_theme_change() -> None:
    previous = _bryggans_v1_with_theme()
    merged = copy.deepcopy(previous)
    merged["brand"]["primaryColorHex"] = "#ff4488"
    assert "theme" in compute_applied_followup_directive_kinds(previous, merged)


@pytest.mark.tooling
def test_compute_applied_kinds_products_add() -> None:
    previous = _bryggans_v1_project_input()
    merged = _bryggans_v2_project_input()  # adds two services (new ids)
    assert "services" in compute_applied_followup_directive_kinds(previous, merged)


@pytest.mark.tooling
def test_compute_applied_kinds_service_summary_paraphrase_is_not_a_change() -> None:
    """A brief-regenerated summary on the SAME service (id+label stable) is not
    an executor-owned edit - it must not flip the honesty signal to applied."""
    previous = _bryggans_v1_project_input()
    merged = copy.deepcopy(previous)
    merged["services"][0]["summary"] = "En helt omformulerad sammanfattning."
    assert compute_applied_followup_directive_kinds(previous, merged) == []


@pytest.mark.tooling
def test_compute_applied_kinds_section_style() -> None:
    previous = _bryggans_v1_project_input()
    merged = copy.deepcopy(previous)
    merged["directives"] = {
        "sectionStyleOverrides": [
            {"routeId": "home", "sectionId": "hero", "backgroundColorHex": "#eeeeee"}
        ]
    }
    assert "section-style" in compute_applied_followup_directive_kinds(previous, merged)


@pytest.mark.tooling
def test_compute_applied_kinds_no_op_is_empty() -> None:
    """The prod no-op shape: an invented unmounted slug + paraphrase only - no
    executor-owned edit, so the honest signal is an EMPTY list."""
    previous = _bryggans_v1_project_input()
    merged = copy.deepcopy(previous)
    merged["requestedCapabilities"] = ["map", "responsive-badges"]
    assert compute_applied_followup_directive_kinds(previous, merged) == []


@pytest.mark.tooling
def test_detect_flip_to_intent_not_executable_when_kinds_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An empty appliedFollowupDirectiveKinds over a byte diff is an honest
    intent_not_executable no-op (the route-removal / restyle trust bug)."""
    _force_visible_change(monkeypatch, tmp_path)
    run_dir = tmp_path / "runs" / "v2"
    run_dir.mkdir(parents=True)
    prompt_meta = {
        "mode": "followup",
        "followUpPrompt": "ta bort sidan Kontakt",
        "appliedFollowupDirectiveKinds": [],
    }
    effect = _detect_followup_applied_visible_effect(
        tmp_path / "runs", run_dir, prompt_meta, {"company": {"name": "X"}}
    )
    assert effect == {"applied": False, "reason": "intent_not_executable"}


@pytest.mark.tooling
def test_detect_keeps_visible_change_when_kinds_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A genuine theme follow-up (kinds=["theme"]) keeps the honest
    visible_files_changed applied=True even though no copyDirective applied."""
    _force_visible_change(monkeypatch, tmp_path)
    run_dir = tmp_path / "runs" / "v2"
    run_dir.mkdir(parents=True)
    prompt_meta = {
        "mode": "followup",
        "followUpPrompt": "gör tonen mörkare och mer premium",
        "appliedFollowupDirectiveKinds": ["theme"],
    }
    effect = _detect_followup_applied_visible_effect(
        tmp_path / "runs", run_dir, prompt_meta, {"company": {"name": "X"}}
    )
    assert effect == {"applied": True, "reason": "visible_files_changed"}


@pytest.mark.tooling
def test_detect_absent_kinds_key_preserves_legacy_behaviour(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """No appliedFollowupDirectiveKinds key (targeted path / pre-signal meta) ->
    the pre-signal visible_files_changed behaviour is preserved."""
    _force_visible_change(monkeypatch, tmp_path)
    run_dir = tmp_path / "runs" / "v2"
    run_dir.mkdir(parents=True)
    prompt_meta = {"mode": "followup", "followUpPrompt": "gör tonen mörkare"}
    effect = _detect_followup_applied_visible_effect(
        tmp_path / "runs", run_dir, prompt_meta, {"company": {"name": "X"}}
    )
    assert effect == {"applied": True, "reason": "visible_files_changed"}


@pytest.mark.tooling
def test_applied_directive_kinds_reader_none_when_absent_and_bounded() -> None:
    assert _prompt_meta_applied_followup_directive_kinds(None) is None
    assert _prompt_meta_applied_followup_directive_kinds({}) is None
    assert _prompt_meta_applied_followup_directive_kinds(
        {"appliedFollowupDirectiveKinds": "nope"}
    ) is None
    # Present-but-empty stays an empty list (the honest no-op signal).
    assert _prompt_meta_applied_followup_directive_kinds(
        {"appliedFollowupDirectiveKinds": []}
    ) == []
    # Malformed entries dropped, duplicates deduped, strings bounded.
    kinds = _prompt_meta_applied_followup_directive_kinds(
        {
            "appliedFollowupDirectiveKinds": [
                "theme",
                "theme",
                "  ",
                123,
                "x" * 100,
            ]
        }
    )
    assert kinds.count("theme") == 1
    assert all(len(kind) <= 40 for kind in kinds)
