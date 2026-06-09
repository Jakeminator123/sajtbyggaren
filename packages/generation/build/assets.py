"""Asset-/media-pipelinens rena logik för den deterministiska byggaren.

Extraherat ordagrant ur ``scripts/build_site.py`` enligt
``docs/refactor/megafiles-plan.md`` (Del 2, slice 2), beteendebevarande.

Modulen rymmer den DEL av asset-pipelinen som inte beror på byggarens
io-/path-tillstånd: AssetRef-validering + iteration, favicon-/og-
konvertering (Pillow), extension/stem-härledning och SVG-detektion. De
io-skrivande funktionerna som anropar buildern via ``UPLOADS_ROOT_DIR`` /
``_REMOTE_ASSET_MAX_BYTES`` (``_fetch_asset_bytes_from_url``,
``_operator_asset_candidate_dirs``, ``_resolve_operator_asset_source``,
``_copy_product_images``, ``copy_operator_uploads``, ``copy_mood_assets``)
ligger MEDVETET kvar i ``scripts/build_site.py`` denna slice: de befintliga
testerna patchar ``build_site.UPLOADS_ROOT_DIR`` /
``build_site._REMOTE_ASSET_MAX_BYTES`` på modulnivå, så en flytt skulle
antingen kräva en package→scripts-shim (förbjuden) eller ändrade tester
(förbjudet). Pillow importeras lat i konverterarna precis som tidigare.
"""

from __future__ import annotations

import io
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any


def _is_valid_asset_ref(value: Any) -> bool:
    """True if ``value`` har de minst fält builder:n behöver för att
    rendera + kopiera asset:n.

    Bug-fix: tidigare checkade vi bara ``bool(value.get(...))`` vilket
    accepterade fel typer (``filename: 123`` passerade) och sedan
    kraschade nedströms när vi gjorde ``"/uploads/" + str(...)``.
    Vi kräver nu explicit ``str``-typ + non-empty efter strip på
    båda kritiska fälten.
    """
    if not isinstance(value, dict):
        return False
    asset_id = value.get("assetId")
    filename = value.get("filename")
    if not isinstance(asset_id, str) or not asset_id.strip():
        return False
    if not isinstance(filename, str) or not filename.strip():
        return False
    return True


def resolve_media_asset(project_input: dict, role: str) -> dict | None:
    """Hitta en `media.<role>` AssetRef i Project Input.

    Kanonisk källa: `project_input["media"][role]`. Resolvern i
    `packages/generation/discovery/resolve.py::_apply_directives_fields`
    persisterar dit deterministiskt från wizardens v2-payload
    (`directives.media`) sedan commit 502b5c0.

    En sista fallback mot `project_input["directives"]["media"]` behålls
    för callers som anropar `build_site.py` direkt med en rå wizard-
    payload utan att gå genom discovery-resolvern (t.ex. test-fixtures
    eller framtida JIT-rendering). Detta fält strippas normalt av
    `_apply_directives_fields` så fallback:en är defensiv, inte
    primär. Den dagen alla callers garanterat går genom resolvern kan
    fallback:en tas bort utan att förlora funktionalitet.
    """
    media = project_input.get("media")
    if isinstance(media, dict):
        candidate = media.get(role)
        if _is_valid_asset_ref(candidate):
            return candidate
    directives = project_input.get("directives")
    if isinstance(directives, dict):
        directives_media = directives.get("media")
        if isinstance(directives_media, dict):
            candidate = directives_media.get(role)
            if _is_valid_asset_ref(candidate):
                return candidate
    return None


def iter_asset_refs(project_input: dict) -> list[dict]:
    """Returnera publika AssetRef-objekt som finns i Project Input
    (`brand.logo`, `brand.heroImage`, varje item i `gallery`, samt
    `products[].productImage`, `media.favicon` / `media.ogImage` /
    `media.backgroundVideo`). Tar bara med refs där alla fält schemat
    kräver finns; trasiga refs hoppas över så build:en inte kraschar
    på en korrupt manifest.json.

    `moodImages` ingår inte här: de är interna inspirationsbilder och ska
    isoleras via `copy_mood_assets`, inte publiceras till sajten.
    """
    refs: list[dict] = []
    brand = project_input.get("brand") or {}
    if isinstance(brand, dict):
        for key in ("logo", "heroImage"):
            ref = brand.get(key)
            if _is_valid_asset_ref(ref):
                refs.append(ref)
    gallery = project_input.get("gallery") or []
    if isinstance(gallery, list):
        for item in gallery:
            if _is_valid_asset_ref(item):
                refs.append(item)
    products = project_input.get("products") or []
    if isinstance(products, list):
        for product in products:
            if not isinstance(product, dict):
                continue
            ref = product.get("productImage")
            if _is_valid_asset_ref(ref):
                refs.append(ref)
    for role in ("favicon", "ogImage", "backgroundVideo"):
        ref = resolve_media_asset(project_input, role)
        if ref is not None:
            refs.append(ref)
    return refs


def _iter_public_upload_refs(project_input: dict) -> list[dict]:
    """Return asset refs that should be published under public/uploads/.

    Product images are deliberately excluded here. They are public assets,
    but their stable generated URL is ``/products/<productId>.<ext>`` and
    `_copy_product_images` owns both that copy and the imageUrl mutation.
    """
    refs: list[dict] = []
    brand = project_input.get("brand") or {}
    if isinstance(brand, dict):
        for key in ("logo", "heroImage"):
            ref = brand.get(key)
            if _is_valid_asset_ref(ref):
                refs.append(ref)
    gallery = project_input.get("gallery") or []
    if isinstance(gallery, list):
        for item in gallery:
            if _is_valid_asset_ref(item):
                refs.append(item)
    for role in ("favicon", "ogImage", "backgroundVideo"):
        ref = resolve_media_asset(project_input, role)
        if ref is not None:
            refs.append(ref)
    return refs


def _iter_mood_refs(project_input: dict) -> list[dict]:
    """Return mood-reference asset refs that must stay outside public/uploads."""
    mood_images = project_input.get("moodImages") or []
    if not isinstance(mood_images, list):
        return []
    refs: list[dict] = []
    for item in mood_images:
        if _is_valid_asset_ref(item):
            refs.append(item)
    return refs


# Hosts allowed when fetching bytes from ``ref.sourceUrl``. The builder
# must not turn arbitrary Project Input data into an SSRF primitive; only
# the public Vercel Blob host shape emitted by VercelBlobAssetStore is
# valid here. If another remote AssetStore driver is added, add its public
# read host explicitly instead of widening this check.
_ALLOWED_ASSET_FETCH_HOSTS: tuple[str, ...] = (
    "public.blob.vercel-storage.com",
)


def _is_allowed_asset_source_url(url: str) -> bool:
    """Return True only for HTTPS URLs on an explicitly allowed asset host."""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = parsed.hostname or ""
    if not host:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if port not in (None, 443):
        return False
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in _ALLOWED_ASSET_FETCH_HOSTS)


_FAVICON_ICO_SIZES: tuple[tuple[int, int], ...] = (
    (16, 16),
    (32, 32),
    (48, 48),
    (64, 64),
)
_OG_IMAGE_SIZE = (1200, 630)


def _asset_requires_derived_public_output(ref: dict) -> bool:
    return ref.get("role") in {"favicon", "ogImage"}


def _is_svg_favicon(ref: dict, image_bytes: bytes, source_file: Path | None = None) -> bool:
    mime_type = ref.get("mimeType")
    if isinstance(mime_type, str) and mime_type.strip().lower() == "image/svg+xml":
        return True
    filename = ref.get("filename")
    if isinstance(filename, str) and filename.strip().lower().endswith(".svg"):
        return True
    if source_file is not None and source_file.suffix.lower() == ".svg":
        return True
    prefix = image_bytes.lstrip()[:512].lower()
    return b"<svg" in prefix


def _convert_favicon_to_ico(image_bytes: bytes, output_path: Path) -> bool:
    """Write a deterministic multi-size favicon.ico from uploaded image bytes."""
    try:
        from PIL import Image
    except ImportError as exc:
        print(
            "Warning: Pillow is not installed; skipping favicon.ico conversion "
            f"({exc}). Original upload will still be copied.",
            file=sys.stderr,
        )
        return False

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(image_bytes)) as image:
            converted = image.convert("RGBA")
            converted.save(output_path, format="ICO", sizes=list(_FAVICON_ICO_SIZES))
        return True
    except Exception as exc:
        print(
            "Warning: failed to convert favicon to public/favicon.ico "
            f"({type(exc).__name__}: {exc}). Original upload will still be copied.",
            file=sys.stderr,
        )
        return False


def _convert_og_image_to_1200x630_png(image_bytes: bytes, output_path: Path) -> bool:
    """Write a center-cropped 1200×630 PNG from uploaded Open Graph bytes."""
    try:
        from PIL import Image
    except ImportError as exc:
        print(
            "Warning: Pillow is not installed; skipping og-image.png conversion "
            f"({exc}). Original upload will still be copied.",
            file=sys.stderr,
        )
        return False

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            source = image.convert("RGBA" if image.mode in {"LA", "P", "RGBA"} else "RGB")
            width, height = source.size
            target_width, target_height = _OG_IMAGE_SIZE
            target_ratio = target_width / target_height
            source_ratio = width / height

            if source_ratio > target_ratio:
                crop_width = int(height * target_ratio)
                left = (width - crop_width) // 2
                crop_box = (left, 0, left + crop_width, height)
            else:
                crop_height = int(width / target_ratio)
                top = (height - crop_height) // 2
                crop_box = (0, top, width, top + crop_height)

            resampling = getattr(Image, "Resampling", Image).LANCZOS
            cropped = source.crop(crop_box)
            resized = cropped.resize(_OG_IMAGE_SIZE, resampling)
            resized.save(output_path, format="PNG", optimize=True)
        return True
    except Exception as exc:
        print(
            "Warning: failed to convert Open Graph image to public/og-image.png "
            f"({type(exc).__name__}: {exc}). Original upload will still be copied.",
            file=sys.stderr,
        )
        return False


def _write_derived_media_asset(
    ref: dict,
    image_bytes: bytes,
    target: Path,
    *,
    source_file: Path | None = None,
) -> None:
    """Write derived public root assets for favicon/OG uploads without aborting builds."""
    public_dir = target / "public"
    role = ref.get("role")
    if role == "favicon":
        if _is_svg_favicon(ref, image_bytes, source_file):
            print(
                "favicon är SVG, hoppar över .ico-konvertering — "
                "Next.js Metadata API rendrar SVG direkt",
                file=sys.stderr,
            )
            favicon_svg = public_dir / "favicon.svg"
            favicon_svg.parent.mkdir(parents=True, exist_ok=True)
            favicon_svg.write_bytes(image_bytes)
            return
        _convert_favicon_to_ico(image_bytes, public_dir / "favicon.ico")
        return
    if role == "ogImage":
        _convert_og_image_to_1200x630_png(image_bytes, public_dir / "og-image.png")


def _operator_asset_variant_candidates(source_dir: Path) -> list[Path]:
    return [
        source_dir / "optimized.webp",
        source_dir / "original.svg",
        source_dir / "original.png",
        source_dir / "original.jpg",
        source_dir / "original.jpeg",
        source_dir / "original.webp",
        source_dir / "original.mp4",
        source_dir / "original.webm",
    ]


def _private_mood_asset_extension(ref: dict, source_file: Path | None) -> str:
    if source_file is not None and source_file.suffix:
        return source_file.suffix.lower().lstrip(".")
    filename = ref.get("filename")
    if isinstance(filename, str):
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix:
            return suffix
    mime_type = str(ref.get("mimeType") or "").strip().lower()
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/svg+xml": "svg",
        "video/mp4": "mp4",
        "video/webm": "webm",
    }.get(mime_type, "bin")


def _private_mood_asset_stem(asset_id: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", asset_id).strip(".-")
    return stem or "asset"


def _public_product_asset_extension(ref: dict, source_file: Path | None) -> str:
    if source_file is not None and source_file.suffix:
        return source_file.suffix.lower().lstrip(".")
    filename = ref.get("filename")
    if isinstance(filename, str):
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix:
            return suffix
    mime_type = str(ref.get("mimeType") or "").strip().lower()
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/svg+xml": "svg",
    }.get(mime_type, "webp")


def _public_product_asset_stem(product: dict, index: int) -> str:
    for key in ("id", "slug"):
        raw = product.get(key)
        if isinstance(raw, str) and raw.strip():
            stem = re.sub(r"[^A-Za-z0-9._-]+", "-", raw.strip().lower()).strip(".-")
            if stem:
                return stem
    return f"product-{index + 1}"
