"""Coverage for the asset_set tool-intent consumer (task A, 2026-06-11).

AssetUploaderDialog sends a structured ``toolIntent`` next to the free-text
prompt. The free text is deliberately no-op:ed by the bildbyte-guard
(tests/test_followup_media_guard.py) — THIS seam is what actually lands the
swap: ``--tool-intent`` is parsed and re-validated by
``packages/generation/followup/asset_intent.py`` and the schema-valid
AssetRef is written to ``brand.logo`` / ``brand.heroImage`` / ``gallery[]``
on the merged Project Input.

Locked here:

- parse_tool_intent shape-validation (operator-readable errors),
- build_asset_ref field re-validation incl. path-traversal rejection,
- the local manifest.json fallback for missing mimeType/sizeBytes,
- apply per role (logo/hero/gallery incl. gallery upsert by assetId),
- the applied ref passes the Project Input schema end-to-end,
- rule 4 ("image-asset unapplied") is suppressed when the asset DID land.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from packages.generation.followup.asset_intent import (
    apply_asset_set_intent,
    build_asset_ref,
    parse_tool_intent,
)
from scripts.prompt_to_project_input import (
    _validate_against_schema,
    compute_unapplied_followup_intents,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

SITE_ID = "fotofirma-abc123"

FULL_PARAMS: dict[str, Any] = {
    "role": "hero",
    "assetId": "20260611T100000-AB12CD34EF56AB12",
    "filename": "20260611T100000-AB12CD34EF56AB12.webp",
    "mimeType": "image/webp",
    "sizeBytes": 123456,
    "width": 1600,
    "height": 900,
    "alt": "Studion i morgonljus",
}


def _previous_project_input() -> dict[str, Any]:
    """A schema-valid Project Input standing in for a previous version."""
    return {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": SITE_ID,
        "scaffoldId": "local-service-business",
        "variantId": "family-warmth",
        "language": "sv",
        "company": {
            "name": "Fotofirman",
            "businessType": "service",
            "tagline": "Vi fångar ögonblicken",
            "story": "En liten studio med stor passion.",
        },
        "location": {
            "city": "Malmö",
            "country": "Sverige",
            "serviceAreas": ["Malmö"],
        },
        "services": [
            {"id": "portratt", "label": "Porträtt", "summary": "Fina porträtt."}
        ],
        "tone": {"primary": "trustworthy", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46 8 000 00 00",
            "email": "kontakt@example.se",
            "addressLines": ["Adress lämnas på förfrågan"],
            "openingHours": "Mån-Fre 9-17",
        },
        "selectedDossiers": {"required": [], "recommended": []},
    }


def _params(**overrides: Any) -> dict[str, Any]:
    merged = dict(FULL_PARAMS)
    merged.update(overrides)
    return merged


# ---------------------------------------------------------------------------
# parse_tool_intent
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_parse_tool_intent_roundtrips_valid_payload() -> None:
    raw = json.dumps({"tool": "asset_set", "params": FULL_PARAMS})
    parsed = parse_tool_intent(raw)
    assert parsed["tool"] == "asset_set"
    assert parsed["params"]["assetId"] == FULL_PARAMS["assetId"]


@pytest.mark.tooling
@pytest.mark.parametrize(
    "raw",
    [
        "inte json",
        json.dumps(["asset_set"]),
        json.dumps({"params": {}}),
        json.dumps({"tool": "   ", "params": {}}),
        json.dumps({"tool": "asset_set"}),
        json.dumps({"tool": "asset_set", "params": "hero"}),
    ],
)
def test_parse_tool_intent_rejects_malformed_payloads(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_tool_intent(raw)


# ---------------------------------------------------------------------------
# build_asset_ref
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_build_asset_ref_keeps_complete_params(tmp_path: Path) -> None:
    ref = build_asset_ref(FULL_PARAMS, site_id=SITE_ID, uploads_dir=tmp_path)
    assert ref == {
        "assetId": FULL_PARAMS["assetId"],
        "filename": FULL_PARAMS["filename"],
        "mimeType": "image/webp",
        "sizeBytes": 123456,
        "role": "hero",
        "width": 1600,
        "height": 900,
        "alt": "Studion i morgonljus",
    }


@pytest.mark.tooling
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("role", "favicon"),  # saknar Project Input-säte — ärligt avvisad
        ("role", "ogImage"),
        ("role", None),
        ("assetId", "../escape"),
        ("assetId", ""),
        ("filename", "../../etc/passwd"),
        ("filename", "sub/dir.webp"),
        ("filename", ".hidden"),
        ("mimeType", "image/gif"),
        ("sourceUrl", "http://osäker.example/bild.webp"),
    ],
)
def test_build_asset_ref_rejects_invalid_fields(
    tmp_path: Path, field: str, value: Any
) -> None:
    with pytest.raises(ValueError):
        build_asset_ref(
            _params(**{field: value}), site_id=SITE_ID, uploads_dir=tmp_path
        )


@pytest.mark.tooling
def test_build_asset_ref_requires_mime_and_size_without_manifest(
    tmp_path: Path,
) -> None:
    # Äldre UI-versioner skickade bara role/assetId/filename. Utan lokal
    # manifest.json kan refen inte göras schema-komplett — ärligt fel,
    # aldrig en gissad mimeType/sizeBytes.
    minimal = {
        "role": "hero",
        "assetId": FULL_PARAMS["assetId"],
        "filename": FULL_PARAMS["filename"],
    }
    with pytest.raises(ValueError):
        build_asset_ref(minimal, site_id=SITE_ID, uploads_dir=tmp_path)


@pytest.mark.tooling
def test_build_asset_ref_completes_from_local_manifest(tmp_path: Path) -> None:
    asset_dir = tmp_path / SITE_ID / FULL_PARAMS["assetId"]
    asset_dir.mkdir(parents=True)
    (asset_dir / "manifest.json").write_text(
        json.dumps(
            {
                "assetId": FULL_PARAMS["assetId"],
                "filename": FULL_PARAMS["filename"],
                "mimeType": "image/webp",
                "sizeBytes": 99999,
                "width": 800,
                "height": 600,
                "alt": "Från manifestet",
                "role": "hero",
            }
        ),
        encoding="utf-8",
    )
    minimal = {
        "role": "hero",
        "assetId": FULL_PARAMS["assetId"],
        "filename": FULL_PARAMS["filename"],
    }
    ref = build_asset_ref(minimal, site_id=SITE_ID, uploads_dir=tmp_path)
    assert ref["mimeType"] == "image/webp"
    assert ref["sizeBytes"] == 99999
    assert ref["width"] == 800
    assert ref["alt"] == "Från manifestet"


# ---------------------------------------------------------------------------
# apply_asset_set_intent
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_apply_hero_lands_on_brand_and_passes_schema(tmp_path: Path) -> None:
    project_input = _previous_project_input()
    report = apply_asset_set_intent(
        project_input, FULL_PARAMS, uploads_dir=tmp_path
    )
    assert project_input["brand"]["heroImage"]["assetId"] == FULL_PARAMS["assetId"]
    assert report == {
        "tool": "asset_set",
        "role": "hero",
        "assetId": FULL_PARAMS["assetId"],
        "filename": FULL_PARAMS["filename"],
    }
    # Slutgiltig ärlighetsgrind: den applicerade refen måste vara giltig
    # mot project-input.schema.json — samma validering som generate() kör.
    _validate_against_schema(project_input)


@pytest.mark.tooling
def test_apply_logo_lands_on_brand_logo(tmp_path: Path) -> None:
    project_input = _previous_project_input()
    apply_asset_set_intent(
        project_input, _params(role="logo"), uploads_dir=tmp_path
    )
    assert project_input["brand"]["logo"]["role"] == "logo"
    assert "heroImage" not in project_input["brand"]
    _validate_against_schema(project_input)


@pytest.mark.tooling
def test_apply_gallery_appends_and_upserts_by_asset_id(tmp_path: Path) -> None:
    project_input = _previous_project_input()
    apply_asset_set_intent(
        project_input,
        _params(role="gallery", placement="home"),
        uploads_dir=tmp_path,
    )
    assert len(project_input["gallery"]) == 1
    assert project_input["gallery"][0]["placement"] == "home"

    # Samma assetId igen (ny placement) ersätter posten — ingen dubblett.
    apply_asset_set_intent(
        project_input,
        _params(role="gallery", placement="about"),
        uploads_dir=tmp_path,
    )
    assert len(project_input["gallery"]) == 1
    assert project_input["gallery"][0]["placement"] == "about"

    # Ett ANNAT assetId läggs till.
    apply_asset_set_intent(
        project_input,
        _params(
            role="gallery",
            assetId="20260611T110000-FFEEDDCCBBAA0011",
            filename="20260611T110000-FFEEDDCCBBAA0011.webp",
        ),
        uploads_dir=tmp_path,
    )
    assert len(project_input["gallery"]) == 2
    _validate_against_schema(project_input)


@pytest.mark.tooling
def test_apply_preserves_existing_brand_fields(tmp_path: Path) -> None:
    project_input = _previous_project_input()
    project_input["brand"] = {"primaryColorHex": "#aa3366", "logoText": "Fotofirman"}
    apply_asset_set_intent(project_input, FULL_PARAMS, uploads_dir=tmp_path)
    assert project_input["brand"]["primaryColorHex"] == "#aa3366"
    assert project_input["brand"]["logoText"] == "Fotofirman"
    assert project_input["brand"]["heroImage"]["role"] == "hero"


@pytest.mark.tooling
def test_apply_requires_site_id(tmp_path: Path) -> None:
    project_input = _previous_project_input()
    project_input.pop("siteId")
    with pytest.raises(ValueError):
        apply_asset_set_intent(project_input, FULL_PARAMS, uploads_dir=tmp_path)


# ---------------------------------------------------------------------------
# Rule 4-suppression (ärlig rapportering när asseten FAKTISKT landade)
# ---------------------------------------------------------------------------

MEDIA_PROMPT = "Byt ut hero-bilden till den uppladdade bilden"


@pytest.mark.tooling
def test_rule4_posts_image_asset_when_nothing_landed() -> None:
    previous = _previous_project_input()
    merged = copy.deepcopy(previous)
    posts = compute_unapplied_followup_intents(
        previous, merged, follow_up_prompt=MEDIA_PROMPT
    )
    assert any(post["target"] == "image-asset" for post in posts)


@pytest.mark.tooling
def test_rule4_suppressed_when_asset_set_intent_landed(tmp_path: Path) -> None:
    previous = _previous_project_input()
    merged = copy.deepcopy(previous)
    apply_asset_set_intent(merged, FULL_PARAMS, uploads_dir=tmp_path)
    posts = compute_unapplied_followup_intents(
        previous, merged, follow_up_prompt=MEDIA_PROMPT
    )
    assert not any(post["target"] == "image-asset" for post in posts)


@pytest.mark.tooling
def test_rule4_suppressed_when_gallery_changed(tmp_path: Path) -> None:
    previous = _previous_project_input()
    merged = copy.deepcopy(previous)
    apply_asset_set_intent(
        merged, _params(role="gallery"), uploads_dir=tmp_path
    )
    posts = compute_unapplied_followup_intents(
        previous, merged, follow_up_prompt=MEDIA_PROMPT
    )
    assert not any(post["target"] == "image-asset" for post in posts)
