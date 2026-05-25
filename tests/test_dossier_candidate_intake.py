"""Tests for read-only Dossier candidate source intake."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.dossier_candidate_intake import (
    DossierIntakeError,
    IntakeScanCaps,
    analyze_dossier_source,
    intake_report_hash,
    sanitize_intake_report_for_model,
)


def _analyse(source: Path, **kwargs: Any) -> dict[str, Any]:
    return analyze_dossier_source(
        source,
        allowed_roots=(source if source.is_file() else source.parent,),
        **kwargs,
    )


def test_intake_directory_with_manifest_and_instructions(tmp_path: Path) -> None:
    source = tmp_path / "faq-dossier"
    source.mkdir()
    (source / "manifest.json").write_text(
        json.dumps({"id": "faq-accordion", "capability": "faq-section", "class": "soft"}),
        encoding="utf-8",
    )
    (source / "instructions.md").write_text("# When to use\n\nReusable FAQ.\n", encoding="utf-8")

    report = _analyse(source)

    assert report["sourceKind"] == "directory"
    assert report["fileCount"] == 2
    assert report["candidateSignals"]["hasManifest"] is True
    assert report["candidateSignals"]["hasInstructions"] is True
    assert report["recommendedClass"] == "soft"
    assert report["suggestedDossierId"] == "faq-accordion"
    assert report["suggestedCapability"] == "faq-section"
    assert report["reportHash"].startswith("sha256:")


def test_intake_directory_with_tsx_and_asset_is_soft_candidate(tmp_path: Path) -> None:
    source = tmp_path / "before-after-slider"
    (source / "components").mkdir(parents=True)
    (source / "assets").mkdir()
    (source / "components" / "slider.tsx").write_text(
        "export function Slider() { return null; }\n",
        encoding="utf-8",
    )
    (source / "assets" / "handle.svg").write_text("<svg />\n", encoding="utf-8")

    report = _analyse(source)

    assert report["candidateSignals"]["hasComponents"] is True
    assert report["candidateSignals"]["hasAssets"] is True
    assert report["recommendedClass"] == "soft"
    assert {entry["extension"] for entry in report["includedFiles"]} >= {".tsx", ".svg"}


def test_intake_flags_env_as_forbidden_and_excludes_it(tmp_path: Path) -> None:
    source = tmp_path / "openai-chat"
    source.mkdir()
    (source / ".env").write_text("OPENAI_API_KEY=sk-secret\n", encoding="utf-8")
    (source / "instructions.md").write_text("# Chat\n", encoding="utf-8")

    report = _analyse(source)

    excluded = {entry["path"]: entry["reason"] for entry in report["excludedFiles"]}
    assert excluded[".env"] == "secret-like-path"
    assert all(entry["path"] != ".env" for entry in report["includedFiles"])


def test_secret_like_paths_are_not_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "secret-demo"
    source.mkdir()
    secret = source / "client-token.txt"
    secret.write_text("super secret token\n", encoding="utf-8")
    (source / "instructions.md").write_text("# Safe\n", encoding="utf-8")

    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == secret:
            raise AssertionError("secret-like file content must not be read")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = _analyse(source)

    excluded = {entry["path"]: entry["reason"] for entry in report["excludedFiles"]}
    assert excluded["client-token.txt"] == "secret-like-path"


def test_hard_candidate_signal_when_env_api_or_backend_is_present(tmp_path: Path) -> None:
    source = tmp_path / "stripe-checkout"
    source.mkdir()
    (source / "server-api.ts").write_text(
        "const key = process.env.STRIPE_SECRET_KEY;\n",
        encoding="utf-8",
    )

    report = _analyse(source)

    assert report["candidateSignals"]["hasHardSignals"] is True
    assert "hard-signal" in report["riskFlags"]
    assert report["recommendedClass"] == "hard"


def test_customer_specific_source_can_be_not_a_dossier(tmp_path: Path) -> None:
    source = tmp_path / "lineage-material"
    source.mkdir()
    (source / "logo.png").write_bytes(b"png")
    (source / "team.md").write_text(
        "Lineage vårt team kopplar upp sig med den här kundmanualen.\n",
        encoding="utf-8",
    )

    report = _analyse(source, operator_brief="Lineage team material")

    assert report["candidateSignals"]["hasCustomerSpecificSignals"] is True
    assert report["recommendedClass"] == "not-a-dossier"
    assert report["operatorQuestions"]


def test_symlink_escape_is_excluded(tmp_path: Path) -> None:
    source = tmp_path / "source"
    outside = tmp_path / "outside"
    source.mkdir()
    outside.mkdir()
    outside_file = outside / "external.md"
    outside_file.write_text("outside\n", encoding="utf-8")
    (source / "external.md").symlink_to(outside_file)

    report = analyze_dossier_source(source, allowed_roots=(source,))

    assert {entry["reason"] for entry in report["excludedFiles"]} == {"path-escape"}
    assert report["includedFiles"] == []


def test_source_path_outside_allowed_roots_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("hello\n", encoding="utf-8")
    allowed = tmp_path / "allowed"
    allowed.mkdir()

    with pytest.raises(DossierIntakeError, match="outside allowed roots"):
        analyze_dossier_source(source, allowed_roots=(allowed,))


def test_intake_report_hash_is_deterministic() -> None:
    report = {"reportVersion": 1, "sourcePath": "demo", "reportHash": "ignore"}

    assert intake_report_hash(report) == intake_report_hash(dict(report))


def test_sanitized_report_strips_content_like_keys() -> None:
    report = {
        "sourcePath": "demo",
        "rawContents": "remove",
        "includedFiles": [{"path": "a.md", "content": "remove", "sizeBytes": 1}],
        "excludedFiles": [{"path": ".env", "textPreview": "remove", "reason": "secret"}],
    }

    safe = sanitize_intake_report_for_model(report)

    assert "rawContents" not in safe
    assert "content" not in safe["includedFiles"][0]
    assert "textPreview" not in safe["excludedFiles"][0]


def test_scan_caps_mark_source_too_large(tmp_path: Path) -> None:
    source = tmp_path / "too-many-files"
    source.mkdir()
    for index in range(3):
        (source / f"file-{index}.md").write_text("x\n", encoding="utf-8")

    report = analyze_dossier_source(
        source,
        allowed_roots=(tmp_path,),
        scan_caps=IntakeScanCaps(max_files=1, max_total_bytes=100, max_readable_text_bytes_per_file=50),
    )

    assert report["recommendedClass"] == "needs-review"
    assert "source-too-large" in report["riskFlags"]


def test_repo_root_source_is_needs_review_without_scanning() -> None:
    from scripts.dossier_candidate_intake import REPO_ROOT

    report = analyze_dossier_source(REPO_ROOT, allowed_roots=(REPO_ROOT,))

    assert report["fileCount"] == 0
    assert report["recommendedClass"] == "needs-review"
    assert "source-too-broad" in report["riskFlags"]
    assert "source-too-large" in report["riskFlags"]
