"""Regression tests for build-pipeline favicon and Open Graph image derivation."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_site  # noqa: E402


def _asset_ref(
    *,
    asset_id: str,
    filename: str,
    role: str,
    mime_type: str,
    **overrides: Any,
) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "assetId": asset_id,
        "filename": filename,
        "mimeType": mime_type,
        "sizeBytes": 1024,
        "role": role,
    }
    ref.update(overrides)
    return ref


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "generated-site"
    target.mkdir()
    return target


def _write_source_image(path: Path, *, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


def _minimal_dossier(media: dict[str, Any]) -> dict[str, Any]:
    return {
        "siteId": "favicon-og-test",
        "company": {
            "name": "Brief Company AB",
            "businessType": "painter",
            "tagline": "Hantverk på vita väggar",
            "story": "",
        },
        "location": {
            "city": "Stockholm",
            "country": "Sverige",
            "serviceAreas": ["Stockholm"],
        },
        "services": [
            {"id": "maleri", "label": "Måleri", "summary": "Måleri inomhus."},
        ],
        "tone": {"primary": "warm", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46 8 000 00 00",
            "email": "hej@example.se",
            "addressLines": ["Exempelgatan 1"],
            "openingHours": "Mån-Fre 09:00-17:00",
        },
        "gallery": [],
        "brand": {"primaryColorHex": "#1d4ed8"},
        "media": media,
    }


@pytest.mark.tooling
def test_copy_operator_uploads_converts_og_image_to_exact_png(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploads_root = tmp_path / "uploads"
    site_id = "og-site"
    asset_id = "01JOGIMAGE0000000000000000"
    source = uploads_root / site_id / asset_id / "original.png"
    _write_source_image(source, size=(2000, 900), color=(20, 80, 140))
    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    ref = _asset_ref(
        asset_id=asset_id,
        filename="operator-og.png",
        role="ogImage",
        mime_type="image/png",
        alt="Delningsbild",
    )
    target = _target(tmp_path)

    copied = build_site.copy_operator_uploads(site_id, target, {"media": {"ogImage": ref}})

    assert copied == 1
    derived = target / "public" / "og-image.png"
    assert derived.exists()
    with Image.open(derived) as image:
        assert image.size == (1200, 630)
        assert image.format == "PNG"
    assert (target / "public" / "uploads" / "operator-og.png").read_bytes() == source.read_bytes()


@pytest.mark.tooling
def test_copy_operator_uploads_writes_multisize_favicon_ico(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploads_root = tmp_path / "uploads"
    site_id = "favicon-site"
    asset_id = "01JFAVICON000000000000000"
    source = uploads_root / site_id / asset_id / "original.png"
    _write_source_image(source, size=(256, 256), color=(180, 40, 80))
    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    ref = _asset_ref(
        asset_id=asset_id,
        filename="operator-favicon.png",
        role="favicon",
        mime_type="image/png",
    )
    target = _target(tmp_path)

    copied = build_site.copy_operator_uploads(site_id, target, {"media": {"favicon": ref}})

    assert copied == 1
    derived = target / "public" / "favicon.ico"
    assert derived.exists()
    with Image.open(derived) as icon:
        assert getattr(icon, "n_frames", 1) >= 1
        assert icon.ico.sizes() == {(16, 16), (32, 32), (48, 48), (64, 64)}
    assert (target / "public" / "uploads" / "operator-favicon.png").read_bytes() == source.read_bytes()


@pytest.mark.tooling
def test_copy_operator_uploads_svg_favicon_writes_public_svg_not_ico(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    uploads_root = tmp_path / "uploads"
    site_id = "svg-favicon-site"
    asset_id = "01JSVGFAVICON00000000000"
    source = uploads_root / site_id / asset_id / "original.svg"
    svg_bytes = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
        b'<rect width="64" height="64" fill="#123456"/></svg>'
    )
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(svg_bytes)
    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    ref = _asset_ref(
        asset_id=asset_id,
        filename="operator-favicon.svg",
        role="favicon",
        mime_type="image/svg+xml",
    )
    target = _target(tmp_path)

    copied = build_site.copy_operator_uploads(site_id, target, {"media": {"favicon": ref}})

    captured = capsys.readouterr()
    assert copied == 1
    assert (target / "public" / "favicon.svg").read_bytes() == svg_bytes
    assert not (target / "public" / "favicon.ico").exists()
    assert (target / "public" / "uploads" / "operator-favicon.svg").read_bytes() == svg_bytes
    assert (
        "favicon är SVG, hoppar över .ico-konvertering — "
        "Next.js Metadata API rendrar SVG direkt"
    ) in captured.err


@pytest.mark.tooling
def test_layout_adds_og_image_png_before_uploaded_fallback() -> None:
    ref = _asset_ref(
        asset_id="01JLAYOUTOG00000000000000",
        filename="social-card.webp",
        role="ogImage",
        mime_type="image/webp",
        alt="Social preview",
    )

    layout = build_site.render_layout(
        _minimal_dossier({"ogImage": ref}),
        dossier_routes=["/"],
    )

    derived_index = layout.index('url: "/og-image.png"')
    fallback_index = layout.index('url: "/uploads/social-card.webp"')
    assert derived_index < fallback_index
    assert 'type: "image/png"' in layout
    assert 'url: "/uploads/social-card.webp"' in layout


@pytest.mark.tooling
def test_copy_operator_uploads_preserves_corrupt_original_and_warns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    uploads_root = tmp_path / "uploads"
    site_id = "corrupt-og-site"
    asset_id = "01JCORRUPTOG000000000000"
    source = uploads_root / site_id / asset_id / "original.png"
    corrupt_bytes = b"not actually an image"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(corrupt_bytes)
    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    ref = _asset_ref(
        asset_id=asset_id,
        filename="corrupt-og.png",
        role="ogImage",
        mime_type="image/png",
    )
    target = _target(tmp_path)

    copied = build_site.copy_operator_uploads(site_id, target, {"media": {"ogImage": ref}})

    captured = capsys.readouterr()
    assert copied == 1
    assert not (target / "public" / "og-image.png").exists()
    assert (target / "public" / "uploads" / "corrupt-og.png").read_bytes() == corrupt_bytes
    assert "Warning: failed to convert Open Graph image to public/og-image.png" in captured.err
