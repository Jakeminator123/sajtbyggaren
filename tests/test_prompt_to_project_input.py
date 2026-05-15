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
    _derive_company_name,
    _derive_story,
    _slugify_label,
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
    assert project_input_path.name.endswith(".v1.project-input.json")
    assert meta_path.name.endswith(".v1.meta.json")
    assert (tmp_path / f"{project_input['siteId']}.project-input.json").exists()
    assert (tmp_path / f"{project_input['siteId']}.meta.json").exists()

    # Meta sidecar contract: projectId + version are minimum what the
    # follow-up sprint reads to build "prompt -> ny version".
    assert "projectId" in meta and meta["projectId"]
    assert meta["version"] == 1
    assert meta["mode"] == "init"
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
    assert project_input_path.name == "custom-site-id-abc.v1.project-input.json"
    assert (tmp_path / "custom-site-id-abc.project-input.json").exists()


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
    initial_project_input, initial_meta, initial_path, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="electrician-malmo",
        project_id="stable-project-id",
    )
    initial_snapshot = initial_path.read_text(encoding="utf-8")

    project_input, meta, project_input_path, next_meta_path = generate_followup(
        "Lägg till mer fokus på laddboxar och offertförfrågan.",
        output_dir=tmp_path,
        site_id="electrician-malmo",
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input_path.name == "electrician-malmo.v2.project-input.json"
    assert next_meta_path.name == "electrician-malmo.v2.meta.json"
    assert initial_path.read_text(encoding="utf-8") == initial_snapshot
    assert meta["projectId"] == initial_meta["projectId"] == "stable-project-id"
    assert meta["siteId"] == "electrician-malmo"
    assert meta["version"] == 2
    assert meta["mode"] == "followup"
    assert meta["previousVersion"] == 1
    assert meta["originalPrompt"] == initial_meta["originalPrompt"]
    assert meta["followUpPrompt"].startswith("Lägg till mer fokus")
    assert "latestPrompt" not in meta
    assert project_input["company"]["name"] == initial_project_input["company"]["name"]
    assert project_input["contact"] == initial_project_input["contact"]
    assert project_input["scaffoldId"] == initial_project_input["scaffoldId"]
    # B60 fynd 2: follow-up prompt MUST NOT leak into customer-facing
    # company.story. The operator's prompt lives in meta.followUpPrompt
    # only; render_about in build_site.py renders company.story directly
    # on /om-oss, so any English workflow suffix would surface as public
    # copy. Lock the absence of the pre-B60 leakage and lock that
    # company.story matches v1 byte-for-byte (no merge-time mutation).
    assert "Follow-up request" not in project_input["company"]["story"]
    assert "Lägg till mer fokus" not in project_input["company"]["story"]
    assert (
        project_input["company"]["story"]
        == initial_project_input["company"]["story"]
    )

    current_meta = json.loads(
        (tmp_path / "electrician-malmo.meta.json").read_text(encoding="utf-8")
    )
    assert current_meta["version"] == 2
    assert current_meta["followUpPrompt"] == meta["followUpPrompt"]


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

    _, meta_v2, path_v2, meta_path_v2 = generate_followup(
        "Gör tonen varmare.",
        output_dir=tmp_path,
        site_id="malare-lund",
    )
    _, meta_v3, path_v3, meta_path_v3 = generate_followup(
        "Lyft fram fasadmålning.",
        output_dir=tmp_path,
        site_id="malare-lund",
    )

    assert meta_v2["projectId"] == "stable-project-id"
    assert meta_v2["version"] == 2
    assert meta_v3["projectId"] == "stable-project-id"
    assert meta_v3["version"] == 3
    assert meta_v3["previousVersion"] == 2
    assert path_v2.name == "malare-lund.v2.project-input.json"
    assert path_v3.name == "malare-lund.v3.project-input.json"
    assert meta_path_v2.name == "malare-lund.v2.meta.json"
    assert meta_path_v3.name == "malare-lund.v3.meta.json"

    current_meta = json.loads(
        (tmp_path / "malare-lund.meta.json").read_text(encoding="utf-8")
    )
    assert current_meta["version"] == 3
    assert current_meta["followUpPrompt"] == "Lyft fram fasadmålning."


@pytest.mark.tooling
def test_generate_followup_requires_existing_meta(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="meta sidecar saknas"):
        generate_followup(
            "Lägg till ny text.",
            output_dir=tmp_path,
            site_id="missing-site",
        )


@pytest.mark.tooling
def test_versioned_snapshot_refuses_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B60 fynd 1: `.vN.project-input.json` and `.vN.meta.json` snapshots
    must be immutable. A second `generate(...)` call that targets the
    same explicit `(site_id, project_id, version)` tuple would otherwise
    silently overwrite the previous snapshot and break PR #27's "older
    versions stay byte-stable" promise. Lock the SystemExit so future
    refactors of `write_project_input` cannot drop the FileExistsError
    guard in `_write_immutable_snapshot`.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generate(
        "Skapa en hemsida för en målare",
        output_dir=tmp_path,
        site_id="painter-immut",
        project_id="stable-project-id",
    )
    with pytest.raises(SystemExit, match="Versioned snapshot already exists"):
        generate(
            "Försök skriva över v1 med samma siteId/projectId/version.",
            output_dir=tmp_path,
            site_id="painter-immut",
            project_id="stable-project-id",
        )


@pytest.mark.tooling
def test_followup_does_not_inject_workflow_text_into_company_story(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B60 fynd 2: cover the merge helper directly so the contract is
    locked even if a future caller bypasses `generate_followup`. The
    follow-up prompt must not be appended to `company.story`; it lives
    in `meta.followUpPrompt` only.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    initial_project_input, _, _, _ = generate(
        "Skapa en hemsida för en målare",
        output_dir=tmp_path,
        site_id="painter-story",
        project_id="stable-project-id",
    )
    expected_story = initial_project_input["company"]["story"]

    followup_project_input, followup_meta, _, _ = generate_followup(
        "Lägg till ett tydligt prisavsnitt och varmare ton.",
        output_dir=tmp_path,
        site_id="painter-story",
    )

    assert followup_project_input["company"]["story"] == expected_story
    assert "Follow-up request" not in followup_project_input["company"]["story"]
    assert (
        "prisavsnitt" not in followup_project_input["company"]["story"]
    ), "Follow-up prompt content leaked into customer-facing copy."
    # Operator visibility is preserved via meta.followUpPrompt.
    assert followup_meta["followUpPrompt"].startswith("Lägg till ett tydligt")


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1A (T2): raw prompt must never become customer-facing
# company.name or company.story copy. The previous helper used
# `prompt[:60]` as H1 and `prompt[:600]` as /om-oss story, which leaked
# operator typos and meta-instructions onto the public site.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_company_name_uses_swedish_business_type_mapping() -> None:
    """`electrician` + `Malmö` -> "Elektriker i Malmö", not the raw prompt."""
    name = _derive_company_name(
        business_type="electrician",
        location_hint="Malmö",
        language="sv",
    )
    assert name == "Elektriker i Malmö"


@pytest.mark.tooling
def test_company_name_falls_back_when_brief_has_no_signals() -> None:
    """Empty brief -> safe placeholder; never the raw prompt."""
    name = _derive_company_name(
        business_type=None,
        location_hint=None,
        language="sv",
    )
    assert name == "Ny sajt"


@pytest.mark.tooling
def test_company_name_handles_location_only() -> None:
    name = _derive_company_name(
        business_type=None,
        location_hint="Stockholm",
        language="sv",
    )
    assert name == "Sajt i Stockholm"


@pytest.mark.tooling
def test_company_name_falls_back_for_unknown_business_type_slug() -> None:
    """Unknown English slug surfaces as an obvious placeholder, never raw."""
    name = _derive_company_name(
        business_type="thinly-niche-business",
        location_hint="Lund",
        language="sv",
    )
    assert name.startswith("Sajt för thinly niche business")
    assert "Lund" in name


@pytest.mark.tooling
def test_story_prefers_notes_for_planner() -> None:
    notes = "2-sidig svensk företagswebb för elektriker i Malmö."
    story = _derive_story(
        business_type="electrician",
        location_hint="Malmö",
        notes_for_planner=notes,
        language="sv",
    )
    assert story == notes


@pytest.mark.tooling
def test_story_constructs_placeholder_when_notes_missing() -> None:
    story = _derive_story(
        business_type="electrician",
        location_hint="Malmö",
        notes_for_planner=None,
        language="sv",
    )
    assert "elektriker" in story
    assert "Malmö" in story
    assert "Justera Project Input" in story


@pytest.mark.tooling
def test_company_name_and_story_never_contain_raw_prompt(
    project_input_schema: dict,
) -> None:
    """The exact regression observed on the real prompt-run
    `enehmsida-som-s-ljer-b-t-661e23`: prompt typos and meta-instructions
    must not surface on the rendered H1 or `/om-oss` copy.
    """
    raw_prompt = "Enehmsida som säljer båtari skövde. 2 sidor"
    brief = {
        "language": "sv",
        "businessTypeGuess": "boat-dealer",
        "locationHint": "Skövde",
        "notesForPlanner": (
            "2-sidig svensk företagswebb för båtverksamhet i Skövde "
            "med fokus på köpkonvertering."
        ),
        "rawPrompt": raw_prompt,
        "tone": ["trustworthy"],
        "conversionGoals": ["purchase"],
        "servicesMentioned": ["båtförsäljning"],
        "requestedCapabilities": [],
        "briefSource": "real",
    }
    project_input = site_brief_to_project_input(
        brief,
        site_id="boat-skovde-abcdef",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt=raw_prompt,
    )
    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)

    name = project_input["company"]["name"]
    story = project_input["company"]["story"]
    for forbidden in ("Enehmsida", "båtari", "2 sidor"):
        assert forbidden not in name, (
            f"Raw prompt token {forbidden!r} leaked into company.name: {name!r}"
        )
        assert forbidden not in story, (
            f"Raw prompt token {forbidden!r} leaked into company.story: "
            f"{story!r}"
        )


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1A (T3): service labels must preserve Swedish
# characters (å/ä/ö) so the rendered service grid reads naturally. The
# previous `_SLUG_CLEAN` substitution stripped Swedish letters from
# both slug and label, turning "färska ägg direkt från gården" into
# the unreadable label "F Rska Gg Direkt Fr N G Rden".
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_slugify_label_ascii_folds_swedish_chars() -> None:
    assert _slugify_label("färska ägg direkt från gården") == (
        "farska-agg-direkt-fran-garden"
    )
    assert _slugify_label("paneldragning") == "paneldragning"
    assert _slugify_label("Akut elservice!") == "akut-elservice"


@pytest.mark.tooling
def test_swedish_service_labels_preserve_case() -> None:
    brief = {
        "language": "sv",
        "businessTypeGuess": "egg-farm",
        "locationHint": "Småland",
        "rawPrompt": "Skapa en hemsida för en äggfarm",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [
            "färska ägg direkt från gården",
            "gårdsbutik",
            "lokal produktion",
        ],
        "requestedCapabilities": [],
        "briefSource": "real",
    }
    project_input = site_brief_to_project_input(
        brief,
        site_id="egg-farm-abcdef",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Skapa en hemsida för en äggfarm",
    )

    labels = {svc["label"] for svc in project_input["services"]}
    assert "Färska ägg direkt från gården" in labels
    assert "Gårdsbutik" in labels
    assert "Lokal produktion" in labels

    slugs = {svc["id"] for svc in project_input["services"]}
    for slug in slugs:
        assert all(ord(c) < 128 for c in slug), (
            f"Slug {slug!r} contains non-ASCII; must ASCII-fold for safe "
            "use as React key / route segment."
        )
    assert "farska-agg-direkt-fran-garden" in slugs
    assert "gardsbutik" in slugs
    assert "lokal-produktion" in slugs


@pytest.mark.tooling
def test_slugify_site_id_ascii_folds_swedish_chars() -> None:
    """The siteId is operator-facing in URLs/paths. NFKD-folding before
    `_SLUG_CLEAN` means "elektriker i Malmö" reads as
    `elektriker-i-malmo-<tail>` instead of the pre-T3
    `elektriker-i-malm-<tail>` (with `ö` collapsed to a dash).
    """
    site_id = slugify_site_id("elektriker i Malmö", suffix="abcdef")
    assert site_id == "elektriker-i-malmo-abcdef"


@pytest.mark.tooling
def test_pointer_writes_use_atomic_replace(tmp_path: Path) -> None:
    """B60 fynd 3: pointer files must be written via tempfile + replace,
    never `Path.write_text` directly. Source-lock the helper names so a
    refactor cannot regress to non-atomic writes that leave readers
    observing half-written JSON.
    """
    helper_path = REPO_ROOT / "scripts" / "prompt_to_project_input.py"
    text = helper_path.read_text(encoding="utf-8")
    assert "_atomic_write_text" in text, (
        "scripts/prompt_to_project_input.py måste exponera "
        "_atomic_write_text-helpern (tempfile + os.replace) som används "
        "för pointer-filerna."
    )
    assert "os.replace(tmp_name, path)" in text, (
        "Pointer-uppdateringen måste gå via os.replace för att vara "
        "atomic; en framtida refactor får inte regressera till en "
        "vanlig Path.write_text på pointer-pathen."
    )
    assert "_atomic_write_text(current_project_input_path" in text, (
        "write_project_input måste använda _atomic_write_text för "
        "current pointer Project Input."
    )
    assert "_atomic_write_text(current_meta_path" in text, (
        "write_project_input måste använda _atomic_write_text för "
        "current pointer meta."
    )
    # Tempfile is empty after a successful write (the actual scratch dir
    # used by tests is `tmp_path`; functional verification happens via
    # test_generate_writes_project_input_and_meta which reads the
    # final pointer payload).
    assert tmp_path.is_dir()
