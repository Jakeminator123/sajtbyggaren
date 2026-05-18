"""Operator-upload-pipelinen.

Guards:

1. ``governance/schemas/project-input.schema.json`` accepterar ``brand``
   och ``gallery`` med AssetRef-form, men kräver dem inte
   (bakåtkompatibilitet med befintliga examples utan bilder).
2. ``$defs/assetRef`` failar closed på unkown enum-värden för
   ``role``/``placement``/``mimeType``.
3. ``iter_asset_refs`` plockar både brand.logo, brand.heroImage och
   gallery-items från en Project Input.
4. ``copy_operator_uploads`` returnerar 0 utan att krascha när
   uppladdningsmappen saknas.
5. ``_apply_discovery_overrides`` mappar discovery.assets → brand.logo /
   brand.heroImage / gallery i Project Input.

Ingen extern I/O — vi mockar disk genom temporära mappar.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"
EXAMPLE_PROJECT_INPUT = REPO_ROOT / "examples" / next(
    (
        p.name
        for p in (REPO_ROOT / "examples").glob("*.project-input.json")
    ),
    "",
)


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def base_project_input() -> dict:
    assert EXAMPLE_PROJECT_INPUT.exists(), (
        "Hittade inget committat project-input-example att basera testerna på."
    )
    return json.loads(EXAMPLE_PROJECT_INPUT.read_text(encoding="utf-8"))


def _valid_asset_ref(**overrides) -> dict:
    base = {
        "assetId": "01HXYZ7Q3KEXABCDEFG1234567",
        "filename": "logo-01hxyz7q.webp",
        "mimeType": "image/webp",
        "sizeBytes": 18342,
        "width": 512,
        "height": 512,
        "alt": "Företagets logotyp",
        "role": "logo",
    }
    base.update(overrides)
    return base


@pytest.mark.governance
def test_schema_accepts_brand_logo_hero_and_gallery(
    schema: dict, base_project_input: dict
) -> None:
    payload = copy.deepcopy(base_project_input)
    payload["brand"] = {
        "logo": _valid_asset_ref(),
        "heroImage": _valid_asset_ref(
            assetId="01HXYZ8R0XYZ0PQRSTUV9876543",
            filename="hero-01hxyz8r.webp",
            role="hero",
            alt="Bild av lokalen",
        ),
        "primaryColorHex": "#1A2B3C",
    }
    payload["gallery"] = [
        _valid_asset_ref(
            assetId="01HXYZ9S0AAAA1234567890ABCD",
            filename="gallery-01hxyz9s.webp",
            role="gallery",
            placement="about",
        )
    ]
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    assert not errors, [error.message for error in errors]


@pytest.mark.governance
def test_schema_still_validates_existing_examples_without_brand(
    schema: dict,
) -> None:
    """Bakåtkompat: alla committade examples måste validera mot det
    utökade schemat trots att de saknar brand/gallery-fälten."""
    validator = jsonschema.Draft202012Validator(schema)
    for path in (REPO_ROOT / "examples").glob("*.project-input.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors = list(validator.iter_errors(payload))
        assert not errors, f"{path.name}: {[e.message for e in errors]}"


@pytest.mark.governance
@pytest.mark.parametrize(
    "field,value",
    [
        ("role", "footer"),
        ("placement", "everywhere"),
        ("mimeType", "image/gif"),
    ],
)
def test_asset_ref_rejects_unknown_enum_values(
    schema: dict, base_project_input: dict, field: str, value: str
) -> None:
    payload = copy.deepcopy(base_project_input)
    bad_ref = _valid_asset_ref()
    bad_ref[field] = value
    payload["brand"] = {"logo": bad_ref}
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    assert errors, f"Expected schema error when {field}={value!r}"


@pytest.mark.tooling
def test_iter_asset_refs_collects_brand_and_gallery() -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from build_site import iter_asset_refs  # noqa: E402

    logo = _valid_asset_ref(role="logo")
    hero = _valid_asset_ref(
        assetId="01HXYZ8R0XYZ0PQRSTUV9876543",
        filename="hero.webp",
        role="hero",
    )
    gallery_item = _valid_asset_ref(
        assetId="01HXYZ9S0AAAA1234567890ABCD",
        filename="g.webp",
        role="gallery",
        placement="about",
    )
    pi = {
        "brand": {"logo": logo, "heroImage": hero},
        "gallery": [gallery_item],
    }
    refs = iter_asset_refs(pi)
    asset_ids = {ref["assetId"] for ref in refs}
    assert asset_ids == {
        logo["assetId"],
        hero["assetId"],
        gallery_item["assetId"],
    }


@pytest.mark.tooling
def test_copy_operator_uploads_returns_zero_when_uploads_missing(
    tmp_path: Path,
) -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from build_site import copy_operator_uploads  # noqa: E402

    pi = {"brand": {"logo": _valid_asset_ref()}}
    target = tmp_path / "generated-site"
    target.mkdir()
    # Ingen data/uploads/<siteId>/ existerar → ska returnera 0 utan
    # att kasta. public/uploads/ skapas ändå (idempotent).
    copied = copy_operator_uploads("doesnotexist", target, pi)
    assert copied == 0


@pytest.mark.tooling
def test_apply_discovery_overrides_maps_assets_to_brand_and_gallery() -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from prompt_to_project_input import _apply_discovery_overrides  # noqa: E402

    base_pi: dict = {}
    discovery = {
        "answers": {
            "assets": {
                "logo": _valid_asset_ref(),
                "heroImage": _valid_asset_ref(
                    assetId="01HXYZ8R0XYZ0PQRSTUV9876543",
                    filename="hero.webp",
                    role="hero",
                ),
                "gallery": [
                    _valid_asset_ref(
                        assetId="01HXYZ9S0AAAA1234567890ABCD",
                        filename="g.webp",
                        role="gallery",
                        placement="about",
                    )
                ],
            }
        }
    }
    out = _apply_discovery_overrides(base_pi, discovery)
    assert out["brand"]["logo"]["assetId"] == discovery["answers"]["assets"]["logo"]["assetId"]
    assert out["brand"]["heroImage"]["role"] == "hero"
    assert len(out["gallery"]) == 1
    assert out["gallery"][0]["placement"] == "about"
