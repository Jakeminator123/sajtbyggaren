"""Regression coverage for products[].productImage end-to-end."""

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


def _valid_product_image_ref(**overrides) -> dict:
    base = {
        "assetId": "01HPRODUCTIMAGE000000000001",
        "filename": "sourdough-upload.webp",
        "mimeType": "image/webp",
        "sizeBytes": 12000,
        "width": 800,
        "height": 600,
        "alt": "Rustik limpa",
        "role": "gallery",
        "placement": "products",
    }
    base.update(overrides)
    return base


def _project_input_with_product(ref: dict | None = None) -> dict:
    product: dict = {
        "id": "sourdough-bread",
        "label": "Surdegsbröd",
        "summary": "Långjäst bröd med krispig skorpa.",
        "price": "95 kr",
    }
    if ref is not None:
        product["productImage"] = ref
    return {"products": [product]}


@pytest.mark.governance
def test_schema_accepts_products_with_product_image(
    schema: dict, base_project_input: dict
) -> None:
    payload = copy.deepcopy(base_project_input)
    payload["products"] = [
        {
            "id": "sourdough-bread",
            "label": "Surdegsbröd",
            "summary": "Långjäst bröd med krispig skorpa.",
            "price": "95 kr",
            "productImage": _valid_product_image_ref(),
        }
    ]

    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))

    assert not errors, [error.message for error in errors]


@pytest.mark.tooling
def test_iter_asset_refs_collects_product_images() -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from build_site import iter_asset_refs  # noqa: E402

    ref = _valid_product_image_ref()
    refs = iter_asset_refs(_project_input_with_product(ref))

    assert [item["assetId"] for item in refs] == [ref["assetId"]]


@pytest.mark.tooling
def test_copy_product_images_writes_public_product_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_site  # noqa: E402

    uploads_root = tmp_path / "uploads"
    asset_dir = uploads_root / "demo-shop" / "01HPRODUCTIMAGE000000000001"
    asset_dir.mkdir(parents=True)
    image_bytes = b"product-image-bytes"
    (asset_dir / "optimized.webp").write_bytes(image_bytes)
    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    project_input = _project_input_with_product(_valid_product_image_ref())
    target = tmp_path / "generated-site"
    target.mkdir()

    copied = build_site._copy_product_images("demo-shop", target, project_input)

    assert copied == 1
    dest = target / "public" / "products" / "sourdough-bread.webp"
    assert dest.read_bytes() == image_bytes
    assert project_input["products"][0]["imageUrl"] == "/products/sourdough-bread.webp"


@pytest.mark.tooling
def test_copy_operator_uploads_product_image_overrides_text_image_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_site  # noqa: E402

    uploads_root = tmp_path / "uploads"
    asset_dir = uploads_root / "__draft" / "01HPRODUCTIMAGE000000000001"
    asset_dir.mkdir(parents=True)
    (asset_dir / "optimized.webp").write_bytes(b"draft-product-image")
    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    project_input = _project_input_with_product(_valid_product_image_ref())
    project_input["products"][0]["imageUrl"] = "https://example.com/manual.webp"
    target = tmp_path / "generated-site"
    target.mkdir()

    copied = build_site.copy_operator_uploads("demo-shop", target, project_input)

    assert copied == 1
    assert not (target / "public" / "uploads" / "sourdough-upload.webp").exists()
    assert (target / "public" / "products" / "sourdough-bread.webp").exists()
    assert project_input["products"][0]["imageUrl"] == "/products/sourdough-bread.webp"


@pytest.mark.tooling
def test_discovery_products_preserve_product_image() -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from prompt_to_project_input import _apply_discovery_overrides  # noqa: E402

    ref = _valid_product_image_ref()
    out = _apply_discovery_overrides(
        {"services": [{"id": "fallback", "label": "Fallback", "summary": "Fallback"}]},
        {
            "answers": {
                "products": [
                    {
                        "id": "sourdough-bread",
                        "name": "Surdegsbröd",
                        "description": "Långjäst bröd med krispig skorpa.",
                        "price": "95 kr",
                        "productImage": ref,
                    }
                ]
            }
        },
    )

    assert out["products"][0]["productImage"]["assetId"] == ref["assetId"]
    assert out["products"][0]["label"] == "Surdegsbröd"


@pytest.mark.tooling
def test_discovery_products_do_not_silently_truncate_after_eight_items() -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from prompt_to_project_input import _apply_discovery_overrides  # noqa: E402

    products = [
        {
            "id": f"product-{index}",
            "name": f"Produkt {index}",
            "description": f"Beskrivning {index}",
        }
        for index in range(1, 11)
    ]

    out = _apply_discovery_overrides(
        {"services": [{"id": "fallback", "label": "Fallback", "summary": "Fallback"}]},
        {"answers": {"products": products}},
    )

    assert len(out["products"]) == 10
    assert out["products"][8]["id"] == "product-9"
    assert out["products"][9]["id"] == "product-10"


@pytest.mark.tooling
def test_product_grid_renderer_uses_product_image_url() -> None:
    from packages.generation.build.renderers import render_section_product_grid

    html = render_section_product_grid(
        {
            "products": [
                {
                    "id": "sourdough-bread",
                    "label": "Surdegsbröd",
                    "summary": "Långjäst bröd med krispig skorpa.",
                    "imageUrl": "/products/sourdough-bread.webp",
                    "productImage": {
                        "alt": "Rustik limpa",
                    },
                }
            ],
            "services": [
                {
                    "id": "fallback",
                    "label": "Fallback",
                    "summary": "Fallback",
                }
            ],
        }
    )

    assert '<img src={"/products/sourdough-bread.webp"}' in html
    assert 'alt={"Rustik limpa"}' in html
    assert 'width={640}' in html
    assert "Fallback" not in html
