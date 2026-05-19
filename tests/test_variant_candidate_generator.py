"""Tests for Scaffold Variant schema and candidate generation tooling."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
VARIANT_SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "variant.schema.json"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_variant_candidate import (  # noqa: E402
    VariantModelResolutionError,
    build_variant_prompt_payload,
    generate_variant_candidates,
    load_variant_context,
    resolve_variant_model,
    slugify_variant_id,
)

from packages.generation.artifacts import ArtifactSchemaError, validate_variant  # noqa: E402
from packages.generation.brief.models import OPENAI_API_KEY_ENV  # noqa: E402


def _variant_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "test-variant",
        "enabled": False,
        "label": "Test Variant",
        "description": "A focused test Variant.",
        "tokens": {
            "color": {
                "background": "#f7f8f5",
                "foreground": "#18201b",
                "muted": "#68706a",
                "border": "#dde3dc",
                "primary": "#245c45",
                "primaryForeground": "#f7f8f5",
                "accent": "#b98f45",
                "accentForeground": "#18201b",
            },
            "typography": {
                "fontFamilyDisplay": "var(--font-geist-sans)",
                "fontFamilyBody": "var(--font-geist-sans)",
                "fontFamilyMono": "var(--font-geist-mono)",
                "scaleRatio": 1.22,
            },
            "radius": {"sm": "0.25rem", "md": "0.5rem", "lg": "0.75rem"},
            "spacing": {"section": "5.5rem", "container": "min(74rem, 92vw)"},
            "motion": {"level": "subtle"},
        },
        "tone": {"vibe": ["calm", "credible"]},
    }
    payload.update(overrides)
    return payload


@pytest.mark.tooling
def test_variant_schema_is_valid_json_schema_2020_12() -> None:
    schema = json.loads(VARIANT_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.tooling
@pytest.mark.parametrize(
    "variant_path",
    sorted(SCAFFOLDS_DIR.glob("*/variants/*.json")),
    ids=lambda path: f"{path.parent.parent.name}/{path.stem}",
)
def test_committed_variants_validate(variant_path: Path) -> None:
    payload = json.loads(variant_path.read_text(encoding="utf-8"))
    validate_variant(payload)


@pytest.mark.tooling
def test_variant_schema_rejects_route_fields() -> None:
    payload = _variant_payload(routes={"defaultRoutes": []})
    with pytest.raises(ArtifactSchemaError, match="routes"):
        validate_variant(payload)


@pytest.mark.tooling
def test_slugify_variant_id_is_ascii_and_alpha_prefixed() -> None:
    assert slugify_variant_id("3 varma Malmö-färger!") == "variant-3-varma-malmo-farger"


@pytest.mark.tooling
def test_resolves_variant_model_from_real_policy() -> None:
    model = resolve_variant_model()
    assert isinstance(model, str)
    assert model
    assert model.strip() == model


@pytest.mark.tooling
def test_resolve_variant_model_raises_when_role_missing(tmp_path: Path) -> None:
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
    with pytest.raises(VariantModelResolutionError, match="variantModel role missing"):
        resolve_variant_model(policy_path=policy)


def _variant_ids_on_disk(scaffold_id: str) -> set[str]:
    variants_dir = SCAFFOLDS_DIR / scaffold_id / "variants"
    return {path.stem for path in variants_dir.glob("*.json")}


@pytest.mark.tooling
def test_load_variant_context_reads_exact_scaffold_files() -> None:
    context = load_variant_context("local-service-business")
    assert set(context.required_files) == {
        "scaffold.json",
        "routes.json",
        "sections.json",
        "quality-contract.json",
        "compatible-dossiers.json",
        "selection-profile.json",
    }
    assert context.existing_variant_ids == _variant_ids_on_disk("local-service-business")
    assert "nordic-trust" in context.existing_variant_ids

    ecommerce = load_variant_context("ecommerce-lite")
    assert ecommerce.existing_variant_ids == _variant_ids_on_disk("ecommerce-lite")
    assert "clean-store" in ecommerce.existing_variant_ids

    prompt_payload = build_variant_prompt_payload(
        context=context,
        brief="Warm and human local service expression.",
        requested_variant_id="warm-human",
        enabled=False,
    )
    assert prompt_payload["context"]["variantOutputSchema"]["$id"] == "variant.schema.json"
    assert prompt_payload["context"]["requiredScaffoldFiles"]["scaffold.json"]["id"] == (
        "local-service-business"
    )


@pytest.mark.tooling
def test_generate_candidate_without_key_writes_disabled_variant(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    [result] = generate_variant_candidates(
        scaffold_id="local-service-business",
        brief="Warm, human and crafted visual direction.",
        variant_id="warm-human",
        output_dir=tmp_path,
        use_llm=True,
    )

    assert result.source == "mock-no-key"
    assert result.model_used == "mock"
    assert result.path == tmp_path / "local-service-business" / "warm-human.json"
    assert result.payload["id"] == "warm-human"
    assert result.payload["enabled"] is False
    validate_variant(result.payload)

    written = json.loads(result.path.read_text(encoding="utf-8"))
    assert written == result.payload


@pytest.mark.tooling
def test_generate_candidate_uses_variant_model_when_key_is_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import generate_variant_candidate as generator

    captured: dict[str, Any] = {}

    def fake_call_variant_model(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return _variant_payload(id="model-picked-id", enabled=True)

    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-fake")
    monkeypatch.setattr(generator, "resolve_variant_model", lambda: "gpt-variant-test")
    monkeypatch.setattr(generator, "_call_variant_model", fake_call_variant_model)

    [result] = generate_variant_candidates(
        scaffold_id="local-service-business",
        brief="A crisp clinic-like expression.",
        variant_id="crisp-clinic",
        output_dir=tmp_path,
        enabled=False,
    )

    assert result.source == "real"
    assert result.model_used == "gpt-variant-test"
    assert result.payload["id"] == "crisp-clinic"
    assert result.payload["enabled"] is False
    assert captured["model"] == "gpt-variant-test"
    assert captured["requested_variant_id"] == "crisp-clinic"


@pytest.mark.tooling
def test_generate_multiple_candidates_get_unique_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    results = generate_variant_candidates(
        scaffold_id="local-service-business",
        brief="Warm local trust",
        count=2,
        output_dir=tmp_path,
        use_llm=False,
    )

    assert [result.payload["id"] for result in results] == [
        "warm-local-trust-1",
        "warm-local-trust-2",
    ]
    assert {result.source for result in results} == {"deterministic-v1"}
    assert all(result.path.exists() for result in results)
