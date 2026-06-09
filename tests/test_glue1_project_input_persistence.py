"""Glue 1 regression: a fresh build persists a discoverable Project Input.

The core loop is ``create -> preview -> follow-up -> new version``. A follow-up
resolves the Project Input from ``data/prompt-inputs/<siteId>.*``
(``read_existing_meta`` / ``read_base_run_snapshot``). The Viewser prompt path
writes that sidecar via ``prompt_to_project_input.generate`` before the build, but
a build driven straight from a curated example or any ad-hoc dossier (the builder
MVP path ``build_site.py --dossier examples/<slug>.project-input.json``) used to
leave ``data/prompt-inputs/`` empty - so the very next follow-up died with
"Follow-up meta sidecar saknas" and the loop felt broken on a freshly built site.

These tests pin the fix (``build`` persists a v1 sidecar for such builds) and its
behaviour-preserving guards. Mock-safe: ``OPENAI_API_KEY`` is removed so brief/plan
fall back to the deterministic mock; ``do_build=False`` keeps the suite Node-free.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXAMPLE_SITE_ID = "painter-palma"
EXAMPLE_DOSSIER = REPO_ROOT / "examples" / f"{EXAMPLE_SITE_ID}.project-input.json"


def test_build_from_example_persists_discoverable_project_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A fresh build from a curated example writes the prompt-inputs sidecar."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import build

    prompt_inputs = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"

    _target, run_dir = build(
        EXAMPLE_DOSSIER,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs_dir=prompt_inputs,
    )

    # The current pointers + immutable v1 snapshots are persisted.
    current_pi = prompt_inputs / f"{EXAMPLE_SITE_ID}.project-input.json"
    current_meta = prompt_inputs / f"{EXAMPLE_SITE_ID}.meta.json"
    v1_pi = prompt_inputs / f"{EXAMPLE_SITE_ID}.v1.project-input.json"
    v1_meta = prompt_inputs / f"{EXAMPLE_SITE_ID}.v1.meta.json"
    assert current_pi.is_file()
    assert current_meta.is_file()
    assert v1_pi.is_file()
    assert v1_meta.is_file()

    meta = json.loads(current_meta.read_text(encoding="utf-8"))
    assert meta["siteId"] == EXAMPLE_SITE_ID
    assert meta["version"] == 1
    assert meta["mode"] == "init"
    assert isinstance(meta["projectId"], str) and meta["projectId"]

    pi = json.loads(current_pi.read_text(encoding="utf-8"))
    assert pi["siteId"] == EXAMPLE_SITE_ID

    # The run records the SAME identity so read_base_run_snapshot stays consistent
    # with the persisted v1 snapshot (input.json version + projectId).
    run_input = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    assert run_input["version"] == 1
    assert run_input["projectId"] == meta["projectId"]


def test_followup_on_example_built_site_discovers_project_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end Glue 1: build from an example, then a section_add follow-up runs
    the whole chain instead of failing 'Follow-up meta sidecar saknas'."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import build, run_followup_chain

    prompt_inputs = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"

    build(
        EXAMPLE_DOSSIER,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs_dir=prompt_inputs,
    )

    result = run_followup_chain(
        EXAMPLE_SITE_ID,
        "lägg till en sektion om garantier",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["applied"] is True
    assert result["editKind"] == "section_add"
    assert result["version"] == 2
    assert (prompt_inputs / f"{EXAMPLE_SITE_ID}.v2.project-input.json").is_file()
    # Honest signal: mount-only section_add with do_build=False never claims a
    # visible effect or a preview refresh.
    assert result["appliedVisibleEffect"] is False
    assert result["previewShouldRefresh"] is False


def test_isolated_build_without_prompt_inputs_dir_does_not_persist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Behaviour-preserving: an isolated build (runs_dir set, no prompt_inputs_dir)
    never writes to the canonical prompt-inputs dir."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import scripts.build_site as build_site

    canonical_pi = tmp_path / "canonical-prompt-inputs"
    canonical_pi.mkdir()
    monkeypatch.setattr(build_site, "PROMPT_INPUTS_DIR", canonical_pi)

    build_site.build(
        EXAMPLE_DOSSIER,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "gen",
    )

    assert list(canonical_pi.iterdir()) == [], (
        "an isolated build (runs_dir set, no explicit prompt_inputs_dir) must not "
        "persist a sidecar to the canonical data/prompt-inputs/"
    )


def test_prompt_inputs_backed_build_is_left_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A build already backed by a sidecar (the prompt path) is not re-persisted:
    the generate-written projectId/version stay authoritative."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import build
    from scripts.prompt_to_project_input import generate

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()

    _pi, meta, v1_path, _meta_path = generate(
        "Skapa en hemsida för en florist i Lund",
        output_dir=prompt_inputs,
        site_id="florist-test",
        project_id="florist-stable-id",
    )

    _target, run_dir = build(
        v1_path,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "gen",
        prompt_inputs_dir=prompt_inputs,
    )

    persisted_meta = json.loads(
        (prompt_inputs / "florist-test.meta.json").read_text(encoding="utf-8")
    )
    assert persisted_meta["projectId"] == "florist-stable-id"
    assert persisted_meta["projectId"] == meta["projectId"]
    # No spurious v2 snapshot from a re-persist.
    assert not (prompt_inputs / "florist-test.v2.project-input.json").exists()


def test_rebuild_from_example_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Re-building the same example does not clobber or crash on the immutable v1
    snapshot; the existing sidecar (projectId/version) is preserved."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import build

    prompt_inputs = tmp_path / "prompt-inputs"

    build(
        EXAMPLE_DOSSIER,
        do_build=False,
        runs_dir=tmp_path / "runs1",
        generated_dir=tmp_path / "gen1",
        prompt_inputs_dir=prompt_inputs,
    )
    meta_first = json.loads(
        (prompt_inputs / f"{EXAMPLE_SITE_ID}.meta.json").read_text(encoding="utf-8")
    )

    # Second build must not raise (the existing v1 snapshot is left intact).
    build(
        EXAMPLE_DOSSIER,
        do_build=False,
        runs_dir=tmp_path / "runs2",
        generated_dir=tmp_path / "gen2",
        prompt_inputs_dir=prompt_inputs,
    )
    meta_second = json.loads(
        (prompt_inputs / f"{EXAMPLE_SITE_ID}.meta.json").read_text(encoding="utf-8")
    )

    assert meta_first["projectId"] == meta_second["projectId"]
    assert meta_second["version"] == 1
