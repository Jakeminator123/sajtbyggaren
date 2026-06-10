"""Tests for the deterministic loop-proof helper behind the Loop-bevis view.

Runs the real generate -> build(do_build=False) chain into an isolated tmp dir
with no OPENAI_API_KEY and no npm. This proves the loop builds a real site
deterministically (it is not a mocked view).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backoffice.loop_proof import (
    baseline_prompt_choices,
    prune_playground_runs,
    run_loop_proof,
    slugify,
)


@pytest.mark.tooling
def test_baseline_prompt_choices_are_the_four_golden_path_prompts():
    choices = baseline_prompt_choices()
    assert len(choices) == 4
    case_ids = {case_id for case_id, _ in choices}
    assert case_ids == {
        "electrician-malmo",
        "salon-goteborg",
        "naprapat-stockholm",
        "ceramics-shop",
    }
    for _case_id, prompt in choices:
        assert prompt and isinstance(prompt, str)


@pytest.mark.tooling
def test_slugify_exact_cases():
    assert slugify("ABC!!!123") == "abc-123"
    assert slugify("   ") == "fri-prompt"
    assert slugify("", fallback="x") == "x"


@pytest.mark.tooling
def test_slugify_is_filesystem_safe():
    slug = slugify("Skapa en hemsida för en elektriker i Malmö.")
    assert slug
    assert len(slug) <= 40
    assert re.fullmatch(r"[a-z0-9-]+", slug)
    assert not slug.startswith("-") and not slug.endswith("-")


@pytest.mark.tooling
def test_prune_playground_runs_keeps_newest(tmp_path: Path):
    import os

    root = tmp_path / "playground"
    root.mkdir()
    for i in range(5):
        d = root / f"run-{i}"
        d.mkdir()
        os.utime(d, (1_000_000 + i, 1_000_000 + i))
    removed = prune_playground_runs(root, keep_last=2)
    remaining = sorted(p.name for p in root.iterdir())
    assert remaining == ["run-3", "run-4"]
    assert set(removed) == {"run-0", "run-1", "run-2"}


@pytest.mark.tooling
def test_run_loop_proof_builds_a_real_site_deterministically(tmp_path: Path, monkeypatch):
    """End-to-end deterministic build for one golden-path prompt, no key/npm."""
    # Ensure deterministic mode even if the test host has a key configured.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    artifacts_root = tmp_path / "playground"

    result = run_loop_proof(
        "Skapa en hemsida för en elektriker i Malmö.",
        site_id="electrician-malmo",
        artifacts_root=artifacts_root,
        keep_last=5,
    )

    # Real selection happened.
    assert result["scaffoldId"] == "local-service-business"
    assert result["variantId"]
    assert result["starterId"]
    # Routes were planned and generated.
    assert result["plannedRoutes"], "expected planned routes"
    assert result["generatedRoutes"], "expected generated routes on disk"
    assert "/" in result["generatedRoutes"]
    # Deterministic mock provenance (no key present).
    assert result["briefSource"]
    assert result["planSource"]
    # Quality gate ran and produced per-check results.
    assert result["qualityChecks"], "expected quality checks"
    assert {c["name"] for c in result["qualityChecks"]}
    # A real app/page.tsx snippet was produced.
    assert result["pageSnippet"].strip()
    # Work tree is isolated under the provided artifacts root.
    assert str(artifacts_root) in result["runDir"]


@pytest.mark.tooling
def test_run_loop_proof_retains_only_keep_last(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    artifacts_root = tmp_path / "playground"
    for _ in range(2):
        run_loop_proof(
            "Skapa en hemsida för en frisörsalong i Göteborg.",
            site_id="salon-goteborg",
            artifacts_root=artifacts_root,
            keep_last=1,
        )
    # keep_last=1 means at most one work dir remains after the second run.
    remaining = [p for p in artifacts_root.iterdir() if p.is_dir()]
    assert len(remaining) == 1
