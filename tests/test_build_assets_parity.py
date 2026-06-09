"""Byte-parity lock for the asset/media pipeline before it moves modules.

``docs/refactor/megafiles-plan.md`` (Del 2, slice 2) requires a focused unit
test that freezes the favicon/Open-Graph derivation and the operator-upload
copy *before* the asset pipeline is extracted from ``scripts/build_site.py``
into ``packages/generation/build/assets.py``. Today these paths are mostly
covered indirectly via the builder smoke test, so this file closes that gap.

With the lock in place the extraction can be proven behavior-preserving: the
test passes against the pre-move code (it generated the goldens) and must keep
passing against the post-move re-export.

The golden bytes live in ``tests/fixtures/assets/``. They were generated from
the unmodified builder via the same ``_gradient_png_bytes`` source helper used
below, so the inputs are fully reproducible:

    favicon-from-64px-gradient.ico   <- _convert_favicon_to_ico(64x64 gradient)
    og-image-from-300x150-gradient.png <- _convert_og_image_to_1200x630_png(...)

All symbols are imported via ``scripts.build_site`` on purpose: that spelling
must keep resolving through the re-export façade after the move, so the test
doubles as a guard that the façade stays intact (``copy_operator_uploads``
stays defined in scripts; the pure converters move to the package).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "assets"
GOLDEN_FAVICON_ICO = FIXTURES_DIR / "favicon-from-64px-gradient.ico"
GOLDEN_OG_PNG = FIXTURES_DIR / "og-image-from-300x150-gradient.png"


def _gradient_png_bytes(width: int, height: int) -> bytes:
    """Return deterministic PNG bytes for a width×height RGB gradient.

    The pixel values are a pure function of (x, y) + the image size, so the
    decoded input the converters see is identical every run and on every
    machine. Used both to generate the committed goldens and to reproduce the
    same input here, so the byte-lock is reproducible without shipping the raw
    source images.
    """
    from PIL import Image

    pixels = [
        (
            (x * 255) // max(width - 1, 1),
            (y * 255) // max(height - 1, 1),
            ((x + y) * 255) // max(width + height - 2, 1),
        )
        for y in range(height)
        for x in range(width)
    ]
    image = Image.new("RGB", (width, height))
    image.putdata(pixels)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _favicon_source_bytes() -> bytes:
    return _gradient_png_bytes(64, 64)


def _og_source_bytes() -> bytes:
    return _gradient_png_bytes(300, 150)


def _asset_ref(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "assetId": "01HASSETPARITY0000000000001",
        "filename": "asset.png",
        "mimeType": "image/png",
        "sizeBytes": 1024,
        "role": "logo",
    }
    base.update(overrides)
    return base


@pytest.mark.tooling
def test_convert_favicon_to_ico_is_byte_locked(tmp_path: Path) -> None:
    """``_convert_favicon_to_ico`` output for the canonical 64×64 gradient must
    equal the committed golden byte-for-byte, and expose the four .ico frame
    sizes. Locks the favicon derivation before the asset extraction.
    """
    from scripts.build_site import _convert_favicon_to_ico

    output_path = tmp_path / "favicon.ico"
    ok = _convert_favicon_to_ico(_favicon_source_bytes(), output_path)
    assert ok is True

    produced = output_path.read_bytes()
    golden = GOLDEN_FAVICON_ICO.read_bytes()
    assert produced == golden, (
        "_convert_favicon_to_ico output drifted from the golden lock. If this "
        "change is intentional, regenerate "
        "tests/fixtures/assets/favicon-from-64px-gradient.ico; if you are "
        "mid-refactor (slice 2 asset extraction) this means the move was NOT "
        "behavior-preserving."
    )

    from PIL import Image

    with Image.open(io.BytesIO(produced)) as icon:
        assert icon.format == "ICO"
        assert icon.ico.sizes() == {(16, 16), (32, 32), (48, 48), (64, 64)}


@pytest.mark.tooling
def test_convert_og_image_to_1200x630_png_is_byte_locked(tmp_path: Path) -> None:
    """``_convert_og_image_to_1200x630_png`` output for the canonical 300×150
    gradient must equal the committed golden byte-for-byte and be a 1200×630
    PNG. Locks the Open-Graph center-crop + resize before the extraction.
    """
    from scripts.build_site import _convert_og_image_to_1200x630_png

    output_path = tmp_path / "og-image.png"
    ok = _convert_og_image_to_1200x630_png(_og_source_bytes(), output_path)
    assert ok is True

    produced = output_path.read_bytes()
    golden = GOLDEN_OG_PNG.read_bytes()
    assert produced == golden, (
        "_convert_og_image_to_1200x630_png output drifted from the golden "
        "lock. If this change is intentional, regenerate "
        "tests/fixtures/assets/og-image-from-300x150-gradient.png; if you are "
        "mid-refactor (slice 2 asset extraction) this means the move was NOT "
        "behavior-preserving."
    )

    from PIL import Image

    with Image.open(io.BytesIO(produced)) as image:
        assert image.format == "PNG"
        assert image.size == (1200, 630)


@pytest.mark.tooling
def test_copy_operator_uploads_end_to_end_is_byte_locked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``copy_operator_uploads`` (logo + favicon + ogImage on disk) must copy
    the raw uploads verbatim AND emit the derived ``favicon.ico`` /
    ``og-image.png`` whose bytes equal the same goldens the focused converter
    tests lock. This freezes the disk-first copy + derived-output wiring that
    today is only exercised indirectly via the builder smoke.
    """
    from scripts import build_site

    uploads_root = tmp_path / "uploads"
    site_id = "asset-parity-site"

    favicon_bytes = _favicon_source_bytes()
    og_bytes = _og_source_bytes()
    logo_bytes = _gradient_png_bytes(48, 48)

    specs = {
        "01HLOGO00000000000000000001": logo_bytes,
        "01HFAVICON0000000000000001": favicon_bytes,
        "01HOGIMAGE0000000000000001": og_bytes,
    }
    for asset_id, data in specs.items():
        asset_dir = uploads_root / "__draft" / asset_id
        asset_dir.mkdir(parents=True)
        (asset_dir / "original.png").write_bytes(data)

    monkeypatch.setattr(build_site, "UPLOADS_ROOT_DIR", uploads_root)

    project_input = {
        "brand": {
            "logo": _asset_ref(
                assetId="01HLOGO00000000000000000001",
                filename="brand-logo.png",
                role="logo",
            ),
        },
        "media": {
            "favicon": _asset_ref(
                assetId="01HFAVICON0000000000000001",
                filename="operator-favicon.png",
                role="favicon",
            ),
            "ogImage": _asset_ref(
                assetId="01HOGIMAGE0000000000000001",
                filename="operator-og.png",
                role="ogImage",
            ),
        },
    }

    target = tmp_path / "generated-site"
    target.mkdir()

    copied = build_site.copy_operator_uploads(site_id, target, project_input)

    assert copied == 3

    public = target / "public"
    assert (public / "uploads" / "brand-logo.png").read_bytes() == logo_bytes
    assert (public / "uploads" / "operator-favicon.png").read_bytes() == favicon_bytes
    assert (public / "uploads" / "operator-og.png").read_bytes() == og_bytes

    assert (public / "favicon.ico").read_bytes() == GOLDEN_FAVICON_ICO.read_bytes()
    assert (public / "og-image.png").read_bytes() == GOLDEN_OG_PNG.read_bytes()
