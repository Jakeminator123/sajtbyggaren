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
    build_safe_intake_evidence,
    intake_report_hash,
    review_dossier_intake_with_model,
    sanitize_intake_report_for_model,
    suggest_capability_from_source_path,
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


def test_real_soft_dossier_with_no_api_language_stays_soft() -> None:
    from scripts.dossier_candidate_intake import REPO_ROOT

    source = REPO_ROOT / "packages/generation/orchestration/dossiers/soft/faq-accordion"

    report = analyze_dossier_source(source, allowed_roots=(REPO_ROOT,))

    assert report["candidateSignals"]["hasManifest"] is True
    assert report["candidateSignals"]["hasInstructions"] is True
    assert report["recommendedClass"] == "soft"
    assert "hard-signal" not in report["riskFlags"]


def test_generic_vendor_words_do_not_force_hard_without_secret_context(tmp_path: Path) -> None:
    source = tmp_path / "pricing-notes"
    source.mkdir()
    (source / "instructions.md").write_text(
        "Mention Stripe, OpenAI, webhook and database words as examples only.\n",
        encoding="utf-8",
    )

    report = _analyse(source)

    assert report["recommendedClass"] == "soft"
    assert "hard-signal" not in report["riskFlags"]


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


def test_secret_like_paths_are_not_stat_touched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "secret-stat-demo"
    source.mkdir()
    secret = source / "client-token.txt"
    secret.write_text("super secret token\n", encoding="utf-8")
    (source / "instructions.md").write_text("# Safe\n", encoding="utf-8")

    original_stat = Path.stat

    def guarded_stat(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == secret:
            raise AssertionError("secret-like file metadata must not be touched")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", guarded_stat)

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


def test_payments_stripe_checkout_path_suggests_capability_not_operator_question(
    tmp_path: Path,
) -> None:
    source = tmp_path / "payments-stripe-checkout"
    source.mkdir()
    (source / "instructions.md").write_text(
        "# Stripe Checkout\n\nUse process.env.STRIPE_SECRET_KEY later.\n",
        encoding="utf-8",
    )

    report = _analyse(
        source,
        operator_brief="Hur skulle du göra för att få denna inputkälla till en bra dossier som passar mitt repo?",
    )

    assert report["recommendedClass"] == "hard"
    assert report["suggestedDossierId"] == "payments-stripe-checkout"
    assert report["suggestedCapability"] == "stripe-checkout"
    assert "hur-skulle" not in report["suggestedCapability"]
    assert suggest_capability_from_source_path("payments-stripe-checkout") == "stripe-checkout"


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


def test_safe_intake_evidence_includes_safe_fields_and_excludes_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "payments-stripe-checkout"
    source.mkdir()
    secret = source / ".env"
    secret.write_text("STRIPE_SECRET_KEY=sk_live_secret\n", encoding="utf-8")
    (source / "manifest.json").write_text(
        json.dumps({"id": "stripe-checkout", "capability": "stripe-checkout", "class": "hard"}),
        encoding="utf-8",
    )
    (source / "instructions.md").write_text(
        "# Stripe Checkout\n\nUse checkout sessions.\n",
        encoding="utf-8",
    )
    (source / "package.json").write_text(
        json.dumps({"name": "stripe-demo", "dependencies": {"stripe": "^1.0.0"}}),
        encoding="utf-8",
    )
    (source / "checkout.tsx").write_text(
        "import Stripe from 'stripe';\nexport function CheckoutButton() { return null; }\n",
        encoding="utf-8",
    )
    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == secret:
            raise AssertionError("secret-like content must not enter safe evidence")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    report = _analyse(source)

    evidence = build_safe_intake_evidence(report, source)

    assert evidence["manifest"]["id"] == "stripe-checkout"
    assert "Stripe Checkout" in evidence["markdown"]["instructions.md"]["headings"]
    assert evidence["package"]["dependencies"] == ["stripe"]
    assert evidence["components"][0]["exports"] == ["CheckoutButton"]
    assert ".env" not in json.dumps(evidence)
    assert "sk_live_secret" not in json.dumps(evidence)


def test_review_no_key_fallback_uses_safe_evidence_and_path_capability(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "payments-stripe-checkout"
    source.mkdir()
    (source / "instructions.md").write_text(
        "# Stripe Checkout\n\nUse process.env.STRIPE_SECRET_KEY later.\n",
        encoding="utf-8",
    )
    report = _analyse(source, operator_brief="Hur skulle du göra för att få denna inputkälla?")
    evidence = build_safe_intake_evidence(report, source)

    review = review_dossier_intake_with_model(
        operator_brief="Hur skulle du göra för att få denna inputkälla?",
        intake_report=report,
        safe_evidence=evidence,
        use_llm=True,
    )

    assert review["source"] == "mock-no-key"
    assert review["modelRole"] == "dossierModel"
    assert review["recommendedClass"] == "hard"
    assert review["suggestedCapability"] == "stripe-checkout"
    assert review["operatorQuestions"]


def test_llm_review_payload_contains_safe_evidence_not_secret_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.dossier_candidate_intake as intake

    captured: dict[str, Any] = {}

    def fake_call_intake_review_model(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "decision": "can-be-dossier",
            "recommendedClass": "hard",
            "suggestedDossierId": "payments-stripe-checkout",
            "suggestedCapability": "stripe-checkout",
            "summary": "Review",
            "proposedContents": [],
            "risks": [],
            "operatorQuestions": [],
            "testPlan": [],
            "promotionBlockedReason": "",
        }

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(intake, "resolve_dossier_model", lambda: "gpt-dossier-test")
    monkeypatch.setattr(intake, "_call_intake_review_model", fake_call_intake_review_model)

    review = review_dossier_intake_with_model(
        operator_brief="Review this",
        intake_report={"rawContents": "must not be sent", "includedFiles": []},
        safe_evidence={"includedFilePaths": ["instructions.md"], "markdown": {"instructions.md": {"excerpt": "safe"}}},
        use_llm=True,
    )

    assert review["source"] == "real"
    assert captured["safe_evidence"]["includedFilePaths"] == ["instructions.md"]
    assert "rawContents" not in captured["intake_report"]
    assert "must not be sent" not in json.dumps(captured)


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


def test_broad_repo_subtree_source_is_needs_review_without_scanning() -> None:
    from scripts.dossier_candidate_intake import REPO_ROOT

    report = analyze_dossier_source(REPO_ROOT / "data", allowed_roots=(REPO_ROOT,))

    assert report["fileCount"] == 0
    assert report["recommendedClass"] == "needs-review"
    assert "source-too-broad" in report["riskFlags"]
    assert "source-too-large" in report["riskFlags"]
