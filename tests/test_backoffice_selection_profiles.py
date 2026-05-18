"""Tests for Backoffice Selection Profile helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backoffice import selection_profiles


def _profile(**overrides) -> dict:
    payload = {
        "id": "demo",
        "embeddingText": "A local service business.",
        "semanticSignals": ["local service", "quote request", "service area"],
        "negativeSignals": ["online shop", "saas dashboard", "restaurant menu"],
        "llmClassificationHints": ["Choose for local service companies."],
        "minConfidence": 0.72,
        "requiresTieBreakWhenWithin": 0.08,
    }
    payload.update(overrides)
    return payload


def test_validate_profile_reports_missing_required_fields() -> None:
    payload = _profile()
    payload.pop("embeddingText")

    errors = selection_profiles.validate_profile(payload)

    assert "Missing required field: embeddingText" in errors


def test_signal_findings_report_overlap_and_duplicates() -> None:
    payload = _profile(
        semanticSignals=["local", "local", "shared"],
        negativeSignals=["shared", "other", "third"],
    )

    findings = selection_profiles.signal_findings(payload)

    assert any("overlap" in finding for finding in findings)
    assert any("duplicates" in finding for finding in findings)


def test_write_profile_validates_and_writes_atomically(tmp_path: Path) -> None:
    scaffolds_dir = tmp_path / "scaffolds"
    (scaffolds_dir / "demo").mkdir(parents=True)

    selection_profiles.write_profile(
        "demo",
        _profile(),
        scaffolds_dir=scaffolds_dir,
    )

    written = json.loads(
        (scaffolds_dir / "demo" / "selection-profile.json").read_text(
            encoding="utf-8"
        )
    )
    assert written["id"] == "demo"


def test_write_profile_rejects_invalid_payload(tmp_path: Path) -> None:
    scaffolds_dir = tmp_path / "scaffolds"
    (scaffolds_dir / "demo").mkdir(parents=True)

    with pytest.raises(ValueError, match="semanticSignals must be a list"):
        selection_profiles.write_profile(
            "demo",
            _profile(semanticSignals="local"),
            scaffolds_dir=scaffolds_dir,
        )
