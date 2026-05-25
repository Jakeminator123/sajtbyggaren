"""Regression tests for the shared candidate-generation helpers.

These tests pin the contract that ``scripts/generate_variant_candidate.py``
and ``scripts/generate_dossier_candidate.py`` rely on after the helpers
were de-duplicated into ``scripts/candidate_generation_metadata``. The
goal is to ensure both generators get identical behaviour for sidecar
paths, brief fingerprints, ISO timestamps and the canonical
orchestration output-dir guard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.candidate_generation_metadata import (
    brief_fingerprint,
    created_at,
    guard_candidate_output_dir,
    repo_or_output_relative,
)


@pytest.mark.tooling
def test_repo_or_output_relative_prefers_repo_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    output_dir = tmp_path / "out"
    target = repo_root / "data" / "candidate.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")

    assert (
        repo_or_output_relative(target, repo_root=repo_root, output_dir=output_dir)
        == "data/candidate.json"
    )


@pytest.mark.tooling
def test_repo_or_output_relative_falls_back_to_output_dir(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    output_dir = tmp_path / "out"
    target = output_dir / "candidate.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")

    assert (
        repo_or_output_relative(target, repo_root=repo_root, output_dir=output_dir)
        == "candidate.json"
    )


@pytest.mark.tooling
def test_repo_or_output_relative_falls_back_to_filename(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    output_dir = tmp_path / "out"
    target = tmp_path / "elsewhere" / "candidate.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")

    assert (
        repo_or_output_relative(target, repo_root=repo_root, output_dir=output_dir)
        == "candidate.json"
    )


@pytest.mark.tooling
def test_brief_fingerprint_is_deterministic_and_trims_input() -> None:
    fingerprint_a = brief_fingerprint("  Hello brief.\n")
    fingerprint_b = brief_fingerprint("Hello brief.")

    assert fingerprint_a == fingerprint_b
    assert fingerprint_a.startswith("sha256:")
    assert len(fingerprint_a) == len("sha256:") + 64


@pytest.mark.tooling
def test_created_at_returns_iso8601_with_z_suffix() -> None:
    stamp = created_at()

    assert stamp.endswith("Z")
    assert "T" in stamp


@pytest.mark.tooling
def test_guard_candidate_output_dir_allows_clean_path(tmp_path: Path) -> None:
    output_dir = tmp_path / "candidates"
    output_dir.mkdir()
    forbidden = tmp_path / "forbidden"
    forbidden.mkdir()

    guard_candidate_output_dir(
        output_dir,
        forbidden_roots=(forbidden,),
        error_cls=RuntimeError,
        kind="Test",
    )


@pytest.mark.tooling
def test_guard_candidate_output_dir_rejects_path_under_forbidden_root(
    tmp_path: Path,
) -> None:
    forbidden = tmp_path / "forbidden"
    forbidden.mkdir()
    nested = forbidden / "nested" / "candidate"

    with pytest.raises(RuntimeError, match="Refusing to write Test candidate"):
        guard_candidate_output_dir(
            nested,
            forbidden_roots=(forbidden,),
            error_cls=RuntimeError,
            kind="Test",
        )


@pytest.mark.tooling
def test_guard_candidate_output_dir_rejects_path_equal_to_forbidden_root(
    tmp_path: Path,
) -> None:
    forbidden = tmp_path / "forbidden"
    forbidden.mkdir()

    with pytest.raises(RuntimeError, match="Refusing to write Test candidate"):
        guard_candidate_output_dir(
            forbidden,
            forbidden_roots=(forbidden,),
            error_cls=RuntimeError,
            kind="Test",
        )


@pytest.mark.tooling
def test_guard_candidate_output_dir_raises_caller_supplied_exception(
    tmp_path: Path,
) -> None:
    """Helper must surface the exception class the caller passes in.

    Using :class:`KeyError` (a Python builtin already accepted by the
    term-coverage check) keeps the test focused on the contract
    "whatever ``error_cls`` you pass is what bubbles up" without
    introducing a new domain-looking class name.
    """
    forbidden = tmp_path / "forbidden"
    forbidden.mkdir()

    with pytest.raises(KeyError):
        guard_candidate_output_dir(
            forbidden,
            forbidden_roots=(forbidden,),
            error_cls=KeyError,
            kind="caller-supplied",
        )
