"""Tests for scripts/prompt_to_project_input.py.

Locks the prompt-driven Project Input loop:

- Slugified siteId always satisfies apps/viewser/lib/project-inputs.ts'
  SITE_ID_PATTERN so the Viewser path-escape guards still hold when the
  siteId is generated server-side instead of operator-picked.
- Generated Project Input validates against
  governance/schemas/project-input.schema.json. A future schema bump
  must keep the helper passing or the prompt loop silently produces
  builds that crash inside build_site.py with a confusing KeyError.
- Scaffold heuristic flips to ecommerce-lite for shop-flavoured prompts
  and stays on local-service-business otherwise (default behaviour).
- Sidecar `<siteId>.meta.json` carries projectId + version + briefSource
  so the follow-up sprint can build "prompt -> ny version" on top of
  this sprint without a project-input schema migration.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"
SITE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from prompt_to_project_input import (  # noqa: E402
    generate,
    generate_followup,
    pick_scaffold,
    site_brief_to_project_input,
    slugify_site_id,
)


@pytest.fixture(scope="module")
def project_input_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.mark.tooling
def test_slugify_produces_valid_site_id() -> None:
    site_id = slugify_site_id("Skapa hemsida för en elektriker i Malmö")
    assert SITE_ID_PATTERN.match(site_id), site_id
    assert site_id.startswith("skapa-hemsida"), site_id


@pytest.mark.tooling
def test_slugify_handles_punctuation_only_prompt() -> None:
    """Falls back to `site-<tail>` so the schema-required siteId field
    cannot end up empty even for crafted prompts."""
    site_id = slugify_site_id("???")
    assert SITE_ID_PATTERN.match(site_id), site_id
    assert site_id.startswith("site-"), site_id


@pytest.mark.tooling
def test_slugify_handles_non_latin_script() -> None:
    """Cyrillic/CJK prompts still produce a valid siteId via the
    fallback. No silent crash inside build_site.py downstream."""
    site_id = slugify_site_id("漢字 のみ")
    assert SITE_ID_PATTERN.match(site_id), site_id


@pytest.mark.tooling
def test_pick_scaffold_defaults_to_local_service_business() -> None:
    scaffold_id, variant_id = pick_scaffold(
        "Skapa en hemsida för en målare", brief_business_type="painter"
    )
    assert scaffold_id == "local-service-business"
    assert variant_id == "nordic-trust"


@pytest.mark.tooling
def test_pick_scaffold_flips_to_ecommerce_for_shop_prompt() -> None:
    scaffold_id, variant_id = pick_scaffold(
        "Bygg en webshop med produkter och checkout",
        brief_business_type=None,
    )
    assert scaffold_id == "ecommerce-lite"
    assert variant_id == "clean-store"


@pytest.mark.tooling
def test_pick_scaffold_flips_via_business_type_signal() -> None:
    """When the prompt has no shop tokens but briefModel detected a
    shop-flavoured business type, still flip to ecommerce-lite."""
    scaffold_id, _ = pick_scaffold(
        "Skapa en sida som visar mitt varumärke",
        brief_business_type="online-shop",
    )
    assert scaffold_id == "ecommerce-lite"


@pytest.mark.tooling
def test_site_brief_to_project_input_validates_against_schema(
    project_input_schema: dict,
) -> None:
    """Empty mock-no-key brief must still produce a schema-valid
    Project Input - that is the path local dev hits without an OpenAI
    API key."""
    mock_brief = {
        "language": "sv",
        "businessTypeGuess": None,
        "rawPrompt": "Skapa en hemsida",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "locationHint": None,
        "notesForPlanner": None,
        "briefSource": "mock-no-key",
    }
    project_input = site_brief_to_project_input(
        mock_brief,
        site_id="example-site-abcdef",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Skapa en hemsida",
    )
    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["siteId"] == "example-site-abcdef"
    # Schema requires services minItems=1; the placeholder must satisfy it.
    assert len(project_input["services"]) >= 1


@pytest.mark.tooling
def test_site_brief_to_project_input_uses_real_brief_fields(
    project_input_schema: dict,
) -> None:
    rich_brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "rawPrompt": "Skapa hemsida för elektriker i Malmö",
        "tone": ["trustworthy", "local"],
        "conversionGoals": ["call", "quote-request"],
        "servicesMentioned": ["paneldragning", "laddbox-installation"],
        "requestedCapabilities": ["contact-form"],
        "locationHint": "Malmö",
        "notesForPlanner": "Lokal elektriker som söker offertförfrågningar.",
        "briefSource": "real",
    }
    project_input = site_brief_to_project_input(
        rich_brief,
        site_id="elektriker-malmo-abcdef",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Skapa hemsida för elektriker i Malmö",
    )
    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["language"] == "sv"
    assert project_input["company"]["businessType"] == "electrician"
    assert project_input["location"]["city"] == "Malmö"
    assert project_input["conversionGoals"] == ["call", "quote-request"]
    service_ids = {svc["id"] for svc in project_input["services"]}
    assert "paneldragning" in service_ids
    assert "laddbox-installation" in service_ids
    assert project_input["tone"]["primary"] == "trustworthy"


@pytest.mark.tooling
def test_generate_writes_project_input_and_meta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_input_schema: dict,
) -> None:
    """End-to-end: helper writes both files into the scratch dir.

    Uses tmp_path so the test never pollutes data/prompt-inputs/. Forces
    mock-no-key by deleting OPENAI_API_KEY so the test does not attempt
    a real network call.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    project_input, meta, project_input_path, meta_path = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)

    assert project_input_path.exists()
    assert meta_path.exists()
    assert project_input_path.parent == tmp_path

    # Meta sidecar contract: projectId + version are minimum what the
    # follow-up sprint reads to build "prompt -> ny version".
    assert "projectId" in meta and meta["projectId"]
    assert meta["version"] == 1
    assert meta["siteId"] == project_input["siteId"]
    assert meta["originalPrompt"].startswith("Skapa")
    # mock-no-key path must be honest about not calling the real LLM.
    assert meta["briefSource"] == "mock-no-key"


@pytest.mark.tooling
def test_generate_falls_back_when_extract_site_brief_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_input_schema: dict,
) -> None:
    """Unexpected exceptions from extract_site_brief must not crash the
    prompt-driven Viewser flow. The script should still write a
    schema-valid placeholder Project Input and record the failure in
    meta.briefError.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")

    def raise_llm_error(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("network timeout")

    monkeypatch.setattr(
        "prompt_to_project_input.extract_site_brief",
        raise_llm_error,
    )

    project_input, meta, project_input_path, meta_path = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input_path.exists()
    assert meta_path.exists()
    assert meta["briefSource"] == "mock-llm-error"
    assert "RuntimeError" in meta["briefError"]
    assert "network timeout" in meta["briefError"]


@pytest.mark.tooling
def test_generate_falls_back_when_site_brief_to_artifact_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_input_schema: dict,
) -> None:
    """The fallback must also cover exceptions after brief extraction,
    including serialization errors in site_brief_to_artifact.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def raise_serializer_error(*_args: object, **_kwargs: object) -> object:
        raise ValueError("bad artifact shape")

    monkeypatch.setattr(
        "prompt_to_project_input.site_brief_to_artifact",
        raise_serializer_error,
    )

    project_input, meta, project_input_path, meta_path = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input_path.exists()
    assert meta_path.exists()
    assert meta["briefSource"] == "mock-llm-error"
    assert "ValueError" in meta["briefError"]
    assert "bad artifact shape" in meta["briefError"]


@pytest.mark.tooling
def test_generate_respects_explicit_site_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input, meta, project_input_path, _ = generate(
        "valfri prompt",
        output_dir=tmp_path,
        site_id="custom-site-id-abc",
    )
    assert project_input["siteId"] == "custom-site-id-abc"
    assert meta["siteId"] == "custom-site-id-abc"
    assert project_input_path.name == "custom-site-id-abc.project-input.json"


@pytest.mark.tooling
def test_generate_rejects_unsafe_explicit_site_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An operator-supplied siteId that violates SITE_ID_PATTERN must
    fail loudly here, not silently land a Project Input that the
    Viewser file APIs (assertSafeSiteId) will then refuse to read."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        generate(
            "valfri prompt",
            output_dir=tmp_path,
            site_id="../escape",
        )


@pytest.mark.tooling
def test_generate_followup_bumps_version_and_reuses_project_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_input_schema: dict,
) -> None:
    """Follow-up prompts keep projectId stable while version increments."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _, initial_meta, _, meta_path = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="electrician-malmo",
        project_id="stable-project-id",
    )

    project_input, meta, project_input_path, next_meta_path = generate_followup(
        "Lägg till mer fokus på laddboxar och offertförfrågan.",
        output_dir=tmp_path,
        site_id="electrician-malmo",
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input_path.name == "electrician-malmo.project-input.json"
    assert next_meta_path == meta_path
    assert meta["projectId"] == initial_meta["projectId"] == "stable-project-id"
    assert meta["siteId"] == "electrician-malmo"
    assert meta["version"] == 2
    assert meta["previousVersion"] == 1
    assert meta["originalPrompt"] == initial_meta["originalPrompt"]
    assert meta["latestPrompt"].startswith("Lägg till mer fokus")


@pytest.mark.tooling
def test_generate_followup_supports_multiple_version_bumps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generate(
        "Skapa en hemsida för en målare",
        output_dir=tmp_path,
        site_id="malare-lund",
        project_id="stable-project-id",
    )

    _, meta_v2, _, _ = generate_followup(
        "Gör tonen varmare.",
        output_dir=tmp_path,
        site_id="malare-lund",
    )
    _, meta_v3, _, _ = generate_followup(
        "Lyft fram fasadmålning.",
        output_dir=tmp_path,
        site_id="malare-lund",
    )

    assert meta_v2["projectId"] == "stable-project-id"
    assert meta_v2["version"] == 2
    assert meta_v3["projectId"] == "stable-project-id"
    assert meta_v3["version"] == 3
    assert meta_v3["previousVersion"] == 2


@pytest.mark.tooling
def test_generate_followup_requires_existing_meta(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="meta sidecar saknas"):
        generate_followup(
            "Lägg till ny text.",
            output_dir=tmp_path,
            site_id="missing-site",
        )
