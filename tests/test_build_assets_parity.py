"""Content-parity lock for the asset/media pipeline before it moves modules.

``docs/refactor/megafiles-plan.md`` (Del 2, slice 2) requires a focused unit
test that freezes the favicon/Open-Graph derivation and the operator-upload
copy *before* the asset pipeline is extracted from ``scripts/build_site.py``
into ``packages/generation/build/assets.py``. Today these paths are mostly
covered indirectly via the builder smoke test, so this file closes that gap.

With the lock in place the extraction can be proven behavior-preserving: the
test passes against the pre-move code (it generated the goldens) and must keep
passing against the post-move re-export.

Why decoded pixels, not compressed bytes
----------------------------------------
The favicon ``.ico`` and Open-Graph ``.png`` are produced by Pillow. Their
*container* bytes are not stable across Pillow/zlib versions or OS (the ``.ico``
frames and the zlib ``optimize=True`` PNG stream re-compress differently on
Linux CI than on a developer's Windows box), so a raw ``produced == golden``
byte comparison is non-portable and fails on CI even when the move is a clean,
behavior-preserving re-export.

Both formats are *lossless* containers, so decoding the committed golden always
yields the same pixels regardless of which Pillow wrote it. We therefore lock
the **decoded** content instead:

* favicon ``.ico``: assert the exact set of frame sizes, assert the full-size
  ``64×64`` frame equals the deterministic source pixel-for-pixel (that frame is
  copied without resampling, so it is exact and portable), and compare every
  frame's decoded pixels against the golden within a tight tolerance that only
  absorbs cross-version resampling drift.
* og-image ``.png``: assert dimensions ``1200×630`` + mode, and compare decoded
  pixels against the golden within the same tight tolerance.
* ``copy_operator_uploads`` end-to-end: the raw uploads are copied *verbatim*
  (no re-encode) so those stay byte-comparisons; the derived ``favicon.ico`` /
  ``og-image.png`` go through the converters, so they use the decoded compare.

This still catches the regressions that matter (wrong size, wrong format, blank
or wrong-cropped image, a broken re-export) without locking unstable bytes.

The golden references live in ``tests/fixtures/assets/``. They were generated
from the unmodified builder via the same ``_gradient_png_bytes`` source helper
used below, so the inputs are fully reproducible:

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

# The four favicon frame sizes the converter is contracted to emit, and the
# Open-Graph output dimensions. Hard-coded on purpose: the test's job is to
# *lock* these, so they must not be read back from the code under test.
EXPECTED_ICO_SIZES: frozenset[tuple[int, int]] = frozenset(
    {(16, 16), (32, 32), (48, 48), (64, 64)}
)
EXPECTED_OG_SIZE = (1200, 630)

# Tolerance for the decoded-pixel comparison. Locally (and on a matching Pillow)
# the decoded pixels are identical (max diff 0); the slack only absorbs
# cross-version resampling drift while staying far below what a real regression
# (blank image, wrong crop, NEAREST-instead-of-LANCZOS on a non-smooth source)
# would produce on a 0-255 channel scale.
_MAX_CHANNEL_DIFF = 4
_MEAN_CHANNEL_DIFF = 1.0


def _gradient_png_bytes(width: int, height: int) -> bytes:
    """Return deterministic PNG bytes for a width×height RGB gradient.

    The pixel values are a pure function of (x, y) + the image size, so the
    decoded input the converters see is identical every run and on every
    machine. Used both to generate the committed goldens and to reproduce the
    same input here, so the content-lock is reproducible without shipping the
    raw source images.
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


def _assert_decoded_close(produced: Any, golden: Any, *, where: str) -> None:
    """Assert two PIL images have near-identical decoded pixels.

    Compares in RGBA so mode differences (e.g. RGB vs RGBA goldens) don't
    falsely trip the diff, then bounds both the per-channel max and the mean
    absolute difference. Portable across Pillow/zlib versions because it only
    looks at decoded pixels, never the compressed container bytes.
    """
    from PIL import ImageChops, ImageStat

    produced_rgba = produced.convert("RGBA")
    golden_rgba = golden.convert("RGBA")
    assert produced_rgba.size == golden_rgba.size, (
        f"{where}: size {produced_rgba.size} != golden {golden_rgba.size}"
    )
    diff = ImageChops.difference(produced_rgba, golden_rgba)
    max_diff = max(hi for _lo, hi in diff.getextrema())
    mean_diff = max(ImageStat.Stat(diff).mean)
    assert max_diff <= _MAX_CHANNEL_DIFF and mean_diff <= _MEAN_CHANNEL_DIFF, (
        f"{where}: decoded pixels drifted from the golden "
        f"(max channel diff {max_diff} > {_MAX_CHANNEL_DIFF} "
        f"or mean {mean_diff:.3f} > {_MEAN_CHANNEL_DIFF}). If this change is "
        "intentional, regenerate the golden under tests/fixtures/assets/; if "
        "you are mid-refactor (slice 2 asset extraction) this means the move "
        "was NOT behavior-preserving."
    )


def _assert_favicon_matches_golden(produced_bytes: bytes) -> None:
    """Lock the decoded structure + content of a produced favicon ``.ico``."""
    from PIL import Image, ImageChops, ImageStat

    source_rgba = Image.open(io.BytesIO(_favicon_source_bytes())).convert("RGBA")

    with (
        Image.open(io.BytesIO(produced_bytes)) as produced,
        Image.open(GOLDEN_FAVICON_ICO) as golden,
    ):
        assert produced.format == "ICO"
        produced_sizes = frozenset(produced.ico.sizes())
        assert produced_sizes == EXPECTED_ICO_SIZES, (
            f"favicon frame sizes {sorted(produced_sizes)} != "
            f"{sorted(EXPECTED_ICO_SIZES)}"
        )
        assert frozenset(golden.ico.sizes()) == EXPECTED_ICO_SIZES

        # The full-size frame is copied without resampling, so it must equal the
        # deterministic source pixel-for-pixel. This is exact and portable.
        full_frame = produced.ico.getimage((64, 64)).convert("RGBA")
        assert full_frame.size == (64, 64)
        assert ImageChops.difference(full_frame, source_rgba).getbbox() is None, (
            "favicon 64×64 frame is not a pixel-exact copy of the source upload"
        )

        for size in sorted(EXPECTED_ICO_SIZES):
            produced_frame = produced.ico.getimage(size).convert("RGBA")
            golden_frame = golden.ico.getimage(size).convert("RGBA")
            assert produced_frame.size == size
            # Guard against a blank/solid regression: the gradient source has
            # real per-channel variation in every downscaled frame.
            assert max(ImageStat.Stat(produced_frame).stddev[:3]) > 1.0, (
                f"favicon frame {size} looks blank (no colour variation)"
            )
            _assert_decoded_close(
                produced_frame, golden_frame, where=f"favicon frame {size}"
            )


def _assert_og_matches_golden(produced_bytes: bytes) -> None:
    """Lock the decoded dimensions + content of a produced og-image ``.png``."""
    from PIL import Image, ImageStat

    with (
        Image.open(io.BytesIO(produced_bytes)) as produced,
        Image.open(GOLDEN_OG_PNG) as golden,
    ):
        assert produced.format == "PNG"
        assert produced.size == EXPECTED_OG_SIZE, (
            f"og-image size {produced.size} != {EXPECTED_OG_SIZE}"
        )
        assert produced.mode == "RGB"
        # Guard against a blank/solid regression before the pixel compare.
        assert max(ImageStat.Stat(produced.convert("RGB")).stddev) > 1.0, (
            "og-image looks blank (no colour variation)"
        )
        _assert_decoded_close(produced, golden, where="og-image")


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
def test_convert_favicon_to_ico_is_content_locked(tmp_path: Path) -> None:
    """``_convert_favicon_to_ico`` output for the canonical 64×64 gradient must
    expose the four ``.ico`` frame sizes and decode to the locked pixels:
    a pixel-exact full-size frame plus per-frame matches against the golden.
    Locks the favicon derivation before the asset extraction without freezing
    non-portable compressed bytes.
    """
    from scripts.build_site import _convert_favicon_to_ico

    output_path = tmp_path / "favicon.ico"
    ok = _convert_favicon_to_ico(_favicon_source_bytes(), output_path)
    assert ok is True

    _assert_favicon_matches_golden(output_path.read_bytes())


@pytest.mark.tooling
def test_convert_og_image_to_1200x630_png_is_content_locked(tmp_path: Path) -> None:
    """``_convert_og_image_to_1200x630_png`` output for the canonical 300×150
    gradient must be a 1200×630 RGB PNG whose decoded pixels match the golden.
    Locks the Open-Graph center-crop + resize before the extraction without
    freezing non-portable compressed bytes.
    """
    from scripts.build_site import _convert_og_image_to_1200x630_png

    output_path = tmp_path / "og-image.png"
    ok = _convert_og_image_to_1200x630_png(_og_source_bytes(), output_path)
    assert ok is True

    _assert_og_matches_golden(output_path.read_bytes())


@pytest.mark.tooling
def test_copy_operator_uploads_end_to_end_is_content_locked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``copy_operator_uploads`` (logo + favicon + ogImage on disk) must copy
    the raw uploads verbatim AND emit the derived ``favicon.ico`` /
    ``og-image.png`` whose decoded content matches the same goldens the focused
    converter tests lock. This freezes the disk-first copy + derived-output
    wiring that today is only exercised indirectly via the builder smoke.

    The raw uploads are copied byte-for-byte (no re-encode), so those stay exact
    byte comparisons; only the converter-derived public outputs use the decoded
    compare, since their compressed bytes are not portable across Pillow/zlib.
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
    # Raw uploads are copied verbatim -> exact byte comparison is portable.
    assert (public / "uploads" / "brand-logo.png").read_bytes() == logo_bytes
    assert (public / "uploads" / "operator-favicon.png").read_bytes() == favicon_bytes
    assert (public / "uploads" / "operator-og.png").read_bytes() == og_bytes

    # Derived outputs are re-encoded by the converters -> decoded compare.
    _assert_favicon_matches_golden((public / "favicon.ico").read_bytes())
    _assert_og_matches_golden((public / "og-image.png").read_bytes())
