"""Structured asset_set tool intent (specialist-dispatch steg 2, task A).

AssetUploaderDialog skickar ett strukturerat ``toolIntent`` bredvid
fritextprompten när operatören applicerar en uppladdad bild:

    {"tool": "asset_set", "params": {"role": "hero", "assetId": ...,
     "filename": ..., "mimeType"?: ..., "sizeBytes"?: ..., "alt"?: ...,
     "sourceUrl"?: ..., "hint"?: ...}}

Fritextprompten ("Använd den uppladdade bilden som ny huvudbild ...")
no-op:as medvetet av bildbyte-guarden i ``copy_directives`` — den FÅR
aldrig tolkas som copy-edit. Detta är den strukturerade sömmen som
faktiskt landar bilden: params re-valideras fält för fält (samma
defense-in-depth som hex-checken i theme-sömmen) och skrivs som en
schema-giltig AssetRef till ``brand.logo`` / ``brand.heroImage`` /
``gallery[]`` på det mergeade Project Input:et, så ``build_site.py``:s
``copy_operator_uploads`` plockar upp bytes:en precis som för
wizard-uppladdningar.

Saknade obligatoriska AssetRef-fält (``mimeType``/``sizeBytes`` skickas
inte av äldre UI-versioner) kompletteras från asset-storens lokala
``data/uploads/<siteId>/<assetId>/manifest.json``. Kan refen inte
göras schema-komplett hoppas intentet över med ett operatörsläsbart
``ValueError`` — aldrig en gissad ref som fäller schema-valideringen.

Conventions: code identifiers in English, operator-facing strings in
Swedish (governance/rules/code-in-english.md).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_UPLOADS_DIR = _REPO_ROOT / "data" / "uploads"

# Roller som har en deterministisk Project Input-destination idag.
# favicon/ogImage/backgroundVideo saknar konsument-säte i schemat
# (brand har bara logo/heroImage) och avvisas ärligt tills vidare.
SUPPORTED_ASSET_ROLES: tuple[str, ...] = ("logo", "hero", "gallery")

# Speglar assetRef-enumen i governance/schemas/project-input.schema.json.
_ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/svg+xml",
        "video/mp4",
        "video/webm",
    }
)
_ALLOWED_PLACEMENTS: frozenset[str] = frozenset(
    {"home", "about", "services", "projects", "products", "gallery"}
)

# assetId genereras av asset-storen (tidsprefix + 16 hex ur randomUUID),
# men vi tillåter samma konservativa token-grammatik som SITE_ID_PATTERN
# i upload-routen så historiska id:n inte avvisas. Inga path-tecken.
_ASSET_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
# filename refereras som /uploads/<filename> i den genererade sajten —
# inga separatorer eller ledande punkt (path traversal-defense; spawn()
# quotar inte och manifest-fallbacken läser disk baserat på värdet).
_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,199}$")
_ALT_MAX_LENGTH = 300
_HINT_MAX_LENGTH = 500


def parse_tool_intent(raw: str) -> dict[str, Any]:
    """Parse + shape-validate the ``--tool-intent`` JSON payload.

    Returns ``{"tool": <str>, "params": <dict>}``. Raises ``ValueError``
    with an operator-readable Swedish message on malformed payloads —
    the CLI converts that into a clean exit instead of a stack trace.
    Unknown tool names are NOT an error here: the caller decides whether
    to dispatch or honestly ignore them (forward-compat with the other
    verktygs-sömmar som konsumeras på TS-sidan idag).
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--tool-intent är inte giltig JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("--tool-intent måste vara ett JSON-objekt.")
    tool = payload.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError("--tool-intent saknar fältet 'tool'.")
    params = payload.get("params")
    if not isinstance(params, dict):
        raise ValueError("--tool-intent saknar objektet 'params'.")
    return {"tool": tool.strip(), "params": params}


def _clean_string(value: Any, *, max_length: int | None = None) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if max_length is not None:
        trimmed = trimmed[:max_length]
    return trimmed


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


def _load_local_manifest(
    uploads_dir: Path, site_id: str, asset_id: str
) -> dict[str, Any] | None:
    """Read the asset store's manifest.json for missing AssetRef fields.

    Both ids are pattern-validated by the caller before this runs, so the
    joined path cannot escape ``uploads_dir``. Returns None on any read
    or parse failure — the caller decides whether the ref is complete
    enough without it.
    """
    manifest_path = uploads_dir / site_id / asset_id / "manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def build_asset_ref(
    params: dict[str, Any],
    *,
    site_id: str,
    uploads_dir: Path = DEFAULT_UPLOADS_DIR,
) -> dict[str, Any]:
    """Re-validate asset_set params into a schema-valid AssetRef.

    Raises ``ValueError`` (Swedish, operator-readable) when the ref
    cannot be made schema-complete. Never guesses: a missing
    ``mimeType``/``sizeBytes`` is only filled from the local asset
    store manifest, never invented.
    """
    role = _clean_string(params.get("role"))
    if role not in SUPPORTED_ASSET_ROLES:
        raise ValueError(
            f"rollen {role!r} stöds inte (förväntar logo, hero eller gallery)."
        )
    asset_id = _clean_string(params.get("assetId"))
    if not asset_id or not _ASSET_ID_PATTERN.match(asset_id):
        raise ValueError(f"ogiltigt assetId {params.get('assetId')!r}.")
    filename = _clean_string(params.get("filename"))
    if not filename or not _FILENAME_PATTERN.match(filename):
        raise ValueError(f"ogiltigt filename {params.get('filename')!r}.")

    mime_type = _clean_string(params.get("mimeType"))
    size_bytes = _positive_int(params.get("sizeBytes"))
    width = _positive_int(params.get("width"))
    height = _positive_int(params.get("height"))
    alt = _clean_string(params.get("alt"), max_length=_ALT_MAX_LENGTH)
    placement = _clean_string(params.get("placement"))
    source_url = _clean_string(params.get("sourceUrl"))

    # Komplettera saknade fält från asset-storens manifest (LocalAssetStore
    # skriver hela AssetRef:en till manifest.json vid uppladdning). Blob-
    # drivern saknar lokal disk — där MÅSTE UI:t skicka kompletta params.
    if mime_type is None or size_bytes is None:
        manifest = _load_local_manifest(uploads_dir, site_id, asset_id)
        if manifest is not None:
            if mime_type is None:
                mime_type = _clean_string(manifest.get("mimeType"))
            if size_bytes is None:
                size_bytes = _positive_int(manifest.get("sizeBytes"))
            if width is None:
                width = _positive_int(manifest.get("width"))
            if height is None:
                height = _positive_int(manifest.get("height"))
            if alt is None:
                alt = _clean_string(manifest.get("alt"), max_length=_ALT_MAX_LENGTH)
            if placement is None:
                placement = _clean_string(manifest.get("placement"))
            if source_url is None:
                source_url = _clean_string(manifest.get("sourceUrl"))

    if mime_type not in _ALLOWED_MIME_TYPES:
        raise ValueError(
            f"mimeType {mime_type!r} saknas eller stöds inte — skicka med "
            "hela AssetRef:en från /api/upload-asset i toolIntent.params."
        )
    if size_bytes is None:
        raise ValueError(
            "sizeBytes saknas — skicka med hela AssetRef:en från "
            "/api/upload-asset i toolIntent.params."
        )
    if source_url is not None and not source_url.startswith("https://"):
        raise ValueError(f"sourceUrl måste vara en https-URL, fick {source_url!r}.")

    ref: dict[str, Any] = {
        "assetId": asset_id,
        "filename": filename,
        "mimeType": mime_type,
        "sizeBytes": size_bytes,
        "role": role,
    }
    if width is not None:
        ref["width"] = width
    if height is not None:
        ref["height"] = height
    if alt is not None:
        ref["alt"] = alt
    if placement in _ALLOWED_PLACEMENTS:
        ref["placement"] = placement
    if source_url is not None:
        ref["sourceUrl"] = source_url
    return ref


def apply_asset_set_intent(
    project_input: dict[str, Any],
    params: dict[str, Any],
    *,
    uploads_dir: Path = DEFAULT_UPLOADS_DIR,
) -> dict[str, Any]:
    """Write a validated AssetRef into the merged Project Input.

    Mutates ``project_input`` in place (samma mönster som
    ``apply_theme_directive``):

    - role ``logo``    → ``brand.logo``
    - role ``hero``    → ``brand.heroImage``
    - role ``gallery`` → upsert på ``assetId`` i ``gallery[]``

    Returns an applied-report dict for meta-sidecar traceability.
    Raises ``ValueError`` when the ref cannot be validated — the caller
    logs and skips, never fails the build over a bad intent.
    """
    site_id = project_input.get("siteId")
    if not isinstance(site_id, str) or not site_id.strip():
        raise ValueError("project input saknar siteId.")
    ref = build_asset_ref(params, site_id=site_id, uploads_dir=uploads_dir)
    role = ref["role"]

    if role in ("logo", "hero"):
        brand = project_input.get("brand")
        if not isinstance(brand, dict):
            brand = {}
            project_input["brand"] = brand
        brand["logo" if role == "logo" else "heroImage"] = ref
    else:
        gallery = project_input.get("gallery")
        if not isinstance(gallery, list):
            gallery = []
            project_input["gallery"] = gallery
        for index, item in enumerate(gallery):
            if isinstance(item, dict) and item.get("assetId") == ref["assetId"]:
                gallery[index] = ref
                break
        else:
            gallery.append(ref)

    return {
        "tool": "asset_set",
        "role": role,
        "assetId": ref["assetId"],
        "filename": ref["filename"],
    }
