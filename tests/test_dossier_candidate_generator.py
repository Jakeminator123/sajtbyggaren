"""Tests for soft Dossier candidate generation tooling."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_dossier_candidate import (  # noqa: E402
    DossierGenerationError,
    DossierModelResolutionError,
    generate_dossier_candidate,
    resolve_dossier_model,
    slugify_dossier_id,
)

from packages.generation.artifacts import validate_dossier  # noqa: E402
from packages.generation.brief.models import OPENAI_API_KEY_ENV  # noqa: E402


def test_slugify_dossier_id_is_ascii_and_alpha_prefixed() -> None:
    assert slugify_dossier_id("3 mjuka Malmö-effekter!") == "dossier-3-mjuka-malmo-effekter"


def test_resolves_dossier_model_from_real_policy() -> None:
    model = resolve_dossier_model()

    assert isinstance(model, str)
    assert model
    assert model.strip() == model


def test_resolve_dossier_model_raises_when_role_missing(tmp_path: Path) -> None:
    policy = tmp_path / "models.json"
    policy.write_text(
        json.dumps(
            {
                "roles": [
                    {"id": "briefModel", "provider": "openai", "model": "gpt-test"}
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(DossierModelResolutionError, match="dossierModel role missing"):
        resolve_dossier_model(policy_path=policy)


def test_generate_soft_candidate_without_key_writes_disabled_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    # Tidigare användes ``faq-accordion`` som exempel-candidate här,
    # men Week 1 batch 3 av "fantastic sites"-roadmappen (2026-05-24)
    # implementerade faq-accordion på riktigt under packages/.../soft/.
    # Generatorns kollisionsdetektion hittade då dossier:n och la till
    # ``-2``-suffix vilket bröt id-assertionen. Byter till
    # ``carousel-embla`` (MIN_IDE-planerad slug för carousel-capability-
    # gapet i capability-map.v1.json) som inte är implementerad än.
    result = generate_dossier_candidate(
        brief="Reusable embla-based carousel for product hero strips.",
        candidate_id="carousel-embla",
        capability="carousel",
        output_dir=tmp_path,
        use_llm=True,
    )

    assert result.source == "mock-no-key"
    assert result.model_used == "mock"
    assert result.candidate_dir == tmp_path / "soft" / "carousel-embla"
    assert result.manifest["id"] == "carousel-embla"
    assert result.manifest["class"] == "soft"
    assert result.manifest["enabled"] is False
    assert result.manifest["envVars"] == []
    assert result.manifest["dependencies"] == []
    validate_dossier(result.manifest)
    assert (result.candidate_dir / "components").is_dir()
    assert result.instructions_path.read_text(encoding="utf-8") == result.instructions
    metadata = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert metadata == result.metadata
    assert metadata["schemaVersion"] == 1
    assert metadata["candidateType"] == "dossier"
    assert metadata["candidateId"] == "carousel-embla"
    assert metadata["capability"] == "carousel"
    assert metadata["source"] == "mock-no-key"
    assert metadata["modelUsed"] == "mock"
    assert metadata["modelRole"] == "dossierModel"
    assert metadata["generator"] == "scripts.generate_dossier_candidate"
    assert metadata["enabled"] is False
    assert metadata["outputPath"] == "soft/carousel-embla/manifest.json"
    assert metadata["instructionsPath"] == "soft/carousel-embla/instructions.md"
    assert not Path(metadata["outputPath"]).is_absolute()
    assert not Path(metadata["instructionsPath"]).is_absolute()
    assert metadata["operatorBriefHash"].startswith("sha256:")
    assert "Reusable embla" not in json.dumps(metadata)


def test_generate_candidate_uses_dossier_model_when_key_is_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import generate_dossier_candidate as generator

    captured: dict[str, Any] = {}

    def fake_call_dossier_model(**kwargs: Any) -> tuple[dict[str, Any], str]:
        captured.update(kwargs)
        manifest = {
            "$schema": "../../../../../../governance/schemas/dossier.schema.json",
            "id": "model-picked-id",
            "enabled": True,
            "label": "Model Picked",
            "capability": "model-capability",
            "class": "soft",
            "codeFidelity": "instructions-only",
            "complexity": "low",
            "defaultForCapability": False,
            "summary": "Model-generated candidate.",
            "envVars": ["SHOULD_BE_REMOVED"],
            "dependencies": ["SHOULD_BE_REMOVED"],
            "files": [],
            "exposes": [],
            "lastVerified": "2026-05-18",
        }
        return manifest, "# When to use\n\nUse when needed.\n"

    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-fake")
    monkeypatch.setattr(generator, "resolve_dossier_model", lambda: "gpt-dossier-test")
    monkeypatch.setattr(generator, "_call_dossier_model", fake_call_dossier_model)

    result = generate_dossier_candidate(
        brief="A small comparison table.",
        candidate_id="comparison-table",
        capability="comparison-table",
        output_dir=tmp_path,
    )

    assert result.source == "real"
    assert result.model_used == "gpt-dossier-test"
    assert result.manifest["id"] == "comparison-table"
    assert result.manifest["capability"] == "comparison-table"
    assert result.manifest["enabled"] is False
    assert result.manifest["envVars"] == []
    assert result.manifest["dependencies"] == []
    assert captured["model"] == "gpt-dossier-test"
    assert result.metadata["source"] == "real"
    assert result.metadata["modelUsed"] == "gpt-dossier-test"


def test_generate_candidate_with_intake_report_writes_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    intake_report = {
        "recommendedClass": "soft",
        "sourcePath": "legacy-dossiers/carousel",
        "fileCount": 3,
        "suggestedDossierId": "carousel-embla",
        "suggestedCapability": "carousel",
        "reportHash": "sha256:intake",
    }

    result = generate_dossier_candidate(
        brief="Reusable carousel behaviour.",
        output_dir=tmp_path,
        use_llm=False,
        intake_report=intake_report,
    )

    assert result.candidate_dir == tmp_path / "soft" / "carousel-embla"
    metadata = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert metadata["generatedBy"] == "dossier-candidate-intake-v1"
    assert metadata["sourcePath"] == "legacy-dossiers/carousel"
    assert metadata["sourceFileCount"] == 3
    assert metadata["intakeReportHash"] == "sha256:intake"
    assert metadata["intakeRecommendedClass"] == "soft"


def test_generate_candidate_refuses_not_a_dossier_intake(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    with pytest.raises(DossierGenerationError, match="not-a-dossier"):
        generate_dossier_candidate(
            brief="Lineage team assets.",
            output_dir=tmp_path,
            use_llm=False,
            intake_report={
                "recommendedClass": "not-a-dossier",
                "sourcePath": "lineage",
                "fileCount": 2,
            },
        )

    assert not list(tmp_path.rglob("*"))


def test_generate_hard_candidate_from_intake_writes_only_candidate_contract_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    intake_report = {
        "recommendedClass": "hard",
        "sourcePath": "legacy-dossiers/openai-chat",
        "fileCount": 4,
        "suggestedDossierId": "openai-chat",
        "suggestedCapability": "ai-chat",
        "reportHash": "sha256:hard",
    }

    result = generate_dossier_candidate(
        brief="OpenAI chat widget with future backend integration.",
        output_dir=tmp_path,
        use_llm=False,
        intake_report=intake_report,
    )

    assert result.candidate_dir == tmp_path / "hard" / "openai-chat"
    assert result.manifest["class"] == "hard"
    assert result.manifest["enabled"] is False
    assert result.manifest["envVars"] == []
    assert result.manifest["dependencies"] == []
    assert {path.name for path in result.candidate_dir.iterdir()} == {
        "manifest.json",
        "instructions.md",
        "meta.json",
        "components",
    }
    assert (result.candidate_dir / "components").is_dir()
    assert not list((result.candidate_dir / "components").iterdir())
    assert {path.name for path in result.candidate_dir.iterdir() if path.is_file()} == {
        "manifest.json",
        "instructions.md",
        "meta.json",
    }
    assert not (result.candidate_dir / "env-contract.json").exists()
    assert not (result.candidate_dir / "integration-contract.json").exists()
    validate_dossier(result.manifest)
    contract = json.loads(
        (REPO_ROOT / "governance" / "policies" / "dossier-contract.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["dossierDirectoryLayout"]["requiredFilesAllClasses"] == [
        "manifest.json",
        "instructions.md",
    ]
    assert contract["dossierDirectoryLayout"]["additionalRequiredFilesByClass"]["hard"] == []


def test_hard_candidate_id_avoids_existing_soft_candidate_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    (tmp_path / "soft" / "shared-id").mkdir(parents=True)

    result = generate_dossier_candidate(
        brief="Future API backed capability.",
        candidate_id="shared-id",
        capability="ai-chat",
        output_dir=tmp_path,
        use_llm=False,
        intake_report={"recommendedClass": "hard"},
    )

    assert result.candidate_dir == tmp_path / "hard" / "shared-id-2"
    assert result.manifest["id"] == "shared-id-2"


def test_generate_candidate_passes_sanitized_intake_report_to_dossier_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import generate_dossier_candidate as generator

    captured: dict[str, Any] = {}

    def fake_call_dossier_model(**kwargs: Any) -> tuple[dict[str, Any], str]:
        captured.update(kwargs)
        return (
            {
                "$schema": "../../../../../../governance/schemas/dossier.schema.json",
                "id": "model-picked-id",
                "enabled": False,
                "label": "Model Picked",
                "capability": "carousel",
                "class": "soft",
                "codeFidelity": "instructions-only",
                "complexity": "low",
                "defaultForCapability": False,
                "summary": "Model-generated candidate.",
                "envVars": [],
                "dependencies": [],
                "files": [],
                "exposes": [],
                "lastVerified": "2026-05-18",
            },
            "# When to use\n\nUse when needed.\n",
        )

    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-fake")
    monkeypatch.setattr(generator, "resolve_dossier_model", lambda: "gpt-dossier-test")
    monkeypatch.setattr(generator, "_call_dossier_model", fake_call_dossier_model)

    generate_dossier_candidate(
        brief="Carousel from intake.",
        candidate_id="carousel-intake",
        capability="carousel",
        output_dir=tmp_path,
        intake_report={
            "recommendedClass": "soft",
            "sourcePath": "legacy",
            "fileCount": 1,
            "rawContents": "must be stripped",
            "includedFiles": [{"path": "component.tsx", "content": "strip me"}],
            "excludedFiles": [{"path": ".env", "textPreview": "strip me"}],
        },
    )

    assert captured["model"] == "gpt-dossier-test"
    assert captured["candidate_class"] == "soft"
    sent_report = captured["intake_report"]
    assert "rawContents" not in sent_report
    assert "content" not in sent_report["includedFiles"][0]
    assert "textPreview" not in sent_report["excludedFiles"][0]


def test_candidate_id_avoids_existing_candidate_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    (tmp_path / "soft" / "faq-accordion").mkdir(parents=True)

    result = generate_dossier_candidate(
        brief="Reusable FAQ accordion.",
        candidate_id="faq-accordion",
        output_dir=tmp_path,
        use_llm=False,
    )

    assert result.manifest["id"] == "faq-accordion-2"


def test_generate_dossier_rejects_canonical_output_dir() -> None:
    with pytest.raises(DossierGenerationError, match="canonical orchestration path"):
        generate_dossier_candidate(
            brief="Reusable FAQ accordion.",
            candidate_id="faq-accordion",
            output_dir=REPO_ROOT / "packages" / "generation" / "orchestration",
            use_llm=False,
        )
