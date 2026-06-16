"""E2E proof: an "add a page" follow-up is an HONEST no-op, never a silent
company-name change (route_add, ADR 0062 §4).

The confident-wrong 2026-06-16 bug: "Lägg till en sida ... som heter 'Jakobs
sida'" classified as route_add, but route_add had no executor, so the bridge
fell through to the legacy copy path - which stole the quoted "...som heter X"
page name as a company rename (v2->v3) and reported "Klart!". route_add now
surfaces the reserved ``route_add_unsupported`` terminal stage (already in
route.ts's TERMINAL_EDIT_NOOP_STAGES), so the bridge stops with a build-free
honest no-op: no new version, no new run, and no company-name mutation.

Via the REAL user path (``run_followup_chain``) on painter-palma, mock-safe
(no OPENAI_API_KEY, do_build=False) like the route_remove/nav_hide E2Es. Full
route_add page-adding (a new page renderer + nav wiring) remains a follow-up;
this proves only the honesty contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _seed_painter_palma(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Init-build the painter-palma example (no npm), isolated dirs."""
    from scripts.build_site import build

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"
    build(
        REPO_ROOT / "examples" / "painter-palma.project-input.json",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs_dir=prompt_inputs,
    )
    return prompt_inputs, runs_dir, generated_dir


def test_add_page_som_heter_is_honest_no_op_not_company_rename(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """"Lägg till en sida ... som heter 'Jakobs sida'" -> route_add_unsupported:
    no new version, no new run, and the company name is left untouched (never
    silently renamed to "Jakobs sida")."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)
    base_pi = json.loads(
        (prompt_inputs / f"{site_id}.project-input.json").read_text(encoding="utf-8")
    )
    base_name = base_pi["company"]["name"]
    runs_before = {d.name for d in runs_dir.iterdir() if d.is_dir()}

    result = run_followup_chain(
        site_id,
        'Lägg till en sida och en navigationslänk som heter "Jakobs sida"',
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    # Honest terminal no-op: route_add is recognised but refused (unsupported).
    assert result["applied"] is False, result
    assert result["stage"] == "route_add_unsupported", result
    assert result["editKind"] == "route_add", result

    # No version bumped and no new run created (the bridge stops build-free).
    assert not (prompt_inputs / f"{site_id}.v2.project-input.json").exists()
    assert {d.name for d in runs_dir.iterdir() if d.is_dir()} == runs_before

    # The whole point of the fix: the company name was NOT silently changed to
    # the new page's name. The current pointer PI still holds the base name.
    after_pi = json.loads(
        (prompt_inputs / f"{site_id}.project-input.json").read_text(encoding="utf-8")
    )
    assert after_pi["company"]["name"] == base_name
    assert after_pi["company"]["name"] != "Jakobs sida"
