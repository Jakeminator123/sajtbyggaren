"""Deterministic Builder MVP for Sajtbyggaren.

Reads a Project Input, a Scaffold and a Variant from the repository, writes
canonical Engine Run artifacts under `data/runs/<runId>/`, and produces a
runnable Next.js project under an external preview root (default:
`../sajtbyggaren-output/.generated/<siteId>`) by copying the Starter
named in `site_plan["starterId"]` (resolved by `produce_site_plan` from the
`SCAFFOLD_TO_STARTER` mapping) and patching it with the project input's
content and the variant's tokens.

By default the builder also runs `npm install` (when `node_modules` is
missing) and `npm run build`. Pass `--skip-build` to skip those steps during
fast dev iteration.

This is the minimal happy path described in `docs/migration-plan.md` Sprint 2
and `docs/architecture/builder-mvp.md`.

LLM status (as of Sprint 2B):
    - Phase 1 Understand: calls `briefModel` via OpenAI when
      `OPENAI_API_KEY` is set, otherwise mock Site Brief.
    - Phase 2 Plan: delegates to
      `packages.generation.planning.produce_site_plan` - the SAME helper
      that `scripts/dev_generate.py` uses. The builder always passes a
      `pinned` payload (scaffoldId/variantId/starterId from the Project
      Input), which makes `planSource = 'pinned'` and skips the LLM
      because the operator's choice is authoritative. The capability
      filter still runs so requested capabilities without an
      implemented Dossier surface as `selectedDossiers.rejected[]`.
    - Phase 3 Build: deterministic codegen using the chosen
      Starter (`copy_starter(site_plan["starterId"], ...)`). Sprint 3A
      now wires real Quality Gate (typecheck + route-scan + build-status
      + policy-compliance) and a no-fix-applied Repair Pipeline through
      `packages.generation.{codegen, quality_gate, repair}`. Skeleton
      result writers are gone (ADR 0015).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
STARTERS_DIR = REPO_ROOT / "data" / "starters"
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
DEFAULT_GENERATED_DIR = REPO_ROOT.parent / "sajtbyggaren-output" / ".generated"
RUNS_DIR = REPO_ROOT / "data" / "runs"

# Files the builder must NEVER write under any siteId. Case-insensitive.
# `.env.example` is allowed (canonical placeholder).
_FORBIDDEN_ENV_PATTERN = re.compile(r"^\.env(\..+)?$", flags=re.IGNORECASE)
_ALLOWED_ENV_NAMES = {".env.example"}
_VERSIONED_PROMPT_INPUT_RE = re.compile(
    r"^(?P<site_id>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"
    r"\.v(?P<version>[1-9][0-9]*)\.project-input\.json$"
)
_CURRENT_PROMPT_INPUT_RE = re.compile(
    r"^(?P<site_id>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"
    r"\.project-input\.json$"
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def make_run_id(site_id: str) -> str:
    """Sortable, readable run id with millisecond precision and a uuid suffix.

    Example: ``20260507T143000.123Z-ab12cd34-painter-palma``. The uuid suffix
    eliminates the race window where two regenerations within the same
    millisecond could reuse a run directory and truncate each other's
    ``trace.ndjson``.
    """
    now = utc_now()
    stamp = now.strftime("%Y%m%dT%H%M%S")
    millis = f"{now.microsecond // 1000:03d}"
    short = uuid.uuid4().hex[:8]
    return f"{stamp}.{millis}Z-{short}-{site_id}"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def assert_not_env_secret(path: Path) -> None:
    """Refuse to touch real .env files (case-insensitive). .env.example is OK."""
    name = path.name
    if name in _ALLOWED_ENV_NAMES:
        return
    if _FORBIDDEN_ENV_PATTERN.match(name):
        raise AssertionError(
            f"Builder must not write secret env files (attempted: {path}). "
            "Hard Dossiers handle their own env contracts via env-contract.json."
        )


def write(path: Path, contents: str) -> None:
    """Write text to disk through the central guard. Use for ALL file writes.

    This is the single chokepoint that enforces the env-secret block.
    Helpers that previously called ``Path.write_text`` directly must go via
    this function instead so the guard cannot be bypassed.
    """
    assert_not_env_secret(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(contents)


def _to_repo_relative(path: Path) -> str:
    """Return ``path`` as POSIX-style string relative to REPO_ROOT when possible.

    Tests pass ``runs_dir=tmp_path`` outside the repo to keep ``data/runs/`` clean,
    in which case the absolute path is returned unchanged. Operators may also
    pass ``--dossier`` paths that live outside the repo (e.g. an ad-hoc fixture
    in ``$TEMP``); they hit the same fallback.
    """
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(REPO_ROOT)
    except ValueError:
        return str(resolved).replace("\\", "/")
    return str(relative).replace("\\", "/")


def resolve_generated_dir(override: str | Path | None = None) -> Path:
    """Resolve where dev-preview builds are written.

    Priority:
    1) explicit ``override`` (CLI/tests),
    2) ``SAJTBYGGAREN_GENERATED_DIR`` env var,
    3) ``DEFAULT_GENERATED_DIR`` (outside the repo root to reduce watcher load).
    """
    candidate = override
    if candidate is None:
        env_value = os.environ.get("SAJTBYGGAREN_GENERATED_DIR")
        if env_value:
            candidate = env_value
        else:
            candidate = DEFAULT_GENERATED_DIR

    resolved = Path(candidate).expanduser()
    if not resolved.is_absolute():
        resolved = (REPO_ROOT / resolved).resolve()
    return resolved


def _coerce_subprocess_text(stream: object) -> str:
    """Return a subprocess stdout/stderr capture as a string, regardless of
    whether the runtime gave us ``None``, ``bytes`` or ``str``.

    ``subprocess.TimeoutExpired`` and ``subprocess.run(...).{stdout,stderr}``
    are typed as ``str | bytes | None`` depending on whether ``text=True``
    was set and how far the process got before the timeout fired. Callers
    that want to surface the partial output to the operator must handle
    all three branches; this helper centralises that so each callsite
    cannot drop one stream silently.
    """
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode("utf-8", errors="replace")
    return str(stream)


def _member_initials(full_name: str) -> str:
    """Return up to two initials from a person's name.

    The earlier inline expression chained ``.split()[-1][:1]`` etc. inside
    an f-string in ``render_about``. After the JSX-escape rewrite (Sprint
    3B-next-cleanup) all interpolated values must be plain strings before
    they are wrapped by ``_jsx_safe_string``, so the initials logic moves
    here. Single-name people get just their first letter.
    """
    parts = full_name.split()
    if not parts:
        return ""
    first = parts[0][:1]
    if len(parts) == 1:
        return first
    return first + parts[-1][:1]


def _jsx_safe_string(text: str) -> str:
    """Wrap user-supplied text as a safe JSX expression.

    Returns the string in the form ``{"<json-encoded>"}``. Use as a drop-in
    replacement for raw f-string interpolation in JSX text content OR as the
    full attribute value (the part after ``=``):

        # Text content
        f"<h1>{_jsx_safe_string(name)}</h1>"

        # Attribute value
        f"<a href={_jsx_safe_string('tel:' + phone)}>"

    Routing the value through ``json.dumps`` ensures every JSX-special
    character (``<``, ``>``, ``{``, ``}``, ``&``, ``"``, ``\\``) becomes
    valid JS string-literal content. The earlier raw-interpolation approach
    let a customer name with ``<`` or ``{`` produce invalid TSX that
    ``next build`` would reject mid-pipeline.
    """
    return "{" + json.dumps(text, ensure_ascii=False) + "}"


def _js_string_literal(text: str) -> str:
    """Return user-supplied text as a JS string literal (with surrounding
    double quotes already included).

    Use in non-JSX positions where a JS string is expected, e.g. inside an
    object literal:

        export const metadata: Metadata = {
          title: <_js_string_literal>,
          description: <_js_string_literal>,
        };

    The earlier ``"{title}".replace('"', '\\\\"')`` approach only escaped
    double quotes; a backslash, newline or non-printing character in the
    source text could still produce an invalid string literal. Going
    through ``json.dumps`` covers every special character a JS string
    cannot contain raw.
    """
    return json.dumps(text, ensure_ascii=False)


def _validated_site_route_path(route_path: str) -> str:
    """Return a scaffold route path after fail-fast canonical validation."""
    if not isinstance(route_path, str) or not route_path.startswith("/"):
        raise SystemExit(
            "Builder failed: scaffold route path must be an absolute "
            f"site path starting with '/' (got {route_path!r})."
        )
    if route_path.startswith("//"):
        raise SystemExit(
            "Builder failed: scaffold route path must be a root-relative "
            f"site path, not a protocol-relative URL (got {route_path!r})."
        )
    if "\\" in route_path or "?" in route_path or "#" in route_path:
        raise SystemExit(
            "Builder failed: scaffold route path must be a canonical site "
            f"path without backslashes, query strings or fragments (got {route_path!r})."
        )
    if route_path != "/":
        segments = route_path.split("/")[1:]
        if any(segment in {"", ".", ".."} for segment in segments):
            raise SystemExit(
                "Builder failed: scaffold route path must not contain empty, "
                f"'.' or '..' path segments (got {route_path!r})."
            )
    return route_path


def _route_href(route_path: str) -> str:
    """Return a scaffold route path as a safe JSX href attribute value."""
    route_path = _validated_site_route_path(route_path)
    return _jsx_safe_string(route_path)


def write_json(path: Path, data: Any) -> None:
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _prompt_meta_path_for_dossier(dossier_path: Path) -> Path | None:
    """Return the adjacent prompt-input meta path for a Project Input file."""
    filename = dossier_path.name
    versioned = _VERSIONED_PROMPT_INPUT_RE.match(filename)
    if versioned:
        return dossier_path.with_name(
            f"{versioned.group('site_id')}.v{versioned.group('version')}.meta.json"
        )

    current = _CURRENT_PROMPT_INPUT_RE.match(filename)
    if current:
        return dossier_path.with_name(f"{current.group('site_id')}.meta.json")
    return None


def load_prompt_input_meta(
    dossier_path: Path,
    dossier: dict[str, Any],
) -> dict[str, Any]:
    """Load optional prompt metadata adjacent to data/prompt-inputs files.

    Curated examples do not have sidecar metadata and therefore keep the
    historical init-mode behaviour. Prompt-generated Project Inputs carry
    a sidecar with stable projectId/version so each Engine Run can record
    immutable version metadata instead of making Viewser read the mutable
    "latest" sidecar for every old run.
    """
    meta_path = _prompt_meta_path_for_dossier(dossier_path)
    if meta_path is None:
        # Dossier filename does not match either prompt-input pattern
        # (no `<siteId>.project-input.json` and no `<siteId>.vN.*`).
        # Nothing in the prompt-input contract applies; keep init-mode.
        return {"mode": "init"}
    if not meta_path.exists():
        # B60 fynd 4: a missing sidecar can mean either
        #   (a) corrupt prompt-input state (interrupted run, partial copy,
        #       manual delete on a `data/prompt-inputs/` snapshot or on a
        #       versioned `<siteId>.vN.project-input.json` file) - must
        #       fail loudly so the operator restores the meta instead of
        #       silently emitting a follow-up build labelled as init with
        #       no projectId/version, OR
        #   (b) a curated example under `examples/` whose filename happens
        #       to match `_CURRENT_PROMPT_INPUT_RE` but never had a
        #       sidecar by design.
        # A versioned filename (`.vN.project-input.json`) is unambiguously
        # written by `prompt_to_project_input.py` and therefore must have
        # a sidecar; the current-pointer pattern only carries the same
        # contract when the file lives under `data/prompt-inputs/`.
        is_versioned = (
            _VERSIONED_PROMPT_INPUT_RE.match(dossier_path.name) is not None
        )
        is_under_prompt_inputs = dossier_path.parent.name == "prompt-inputs"
        if is_versioned or is_under_prompt_inputs:
            raise SystemExit(
                f"Builder failed: prompt meta sidecar missing at {meta_path}. "
                "Restore the meta or remove the orphaned project-input file."
            )
        return {"mode": "init"}

    meta = load_json(meta_path)
    site_id = meta.get("siteId")
    if site_id != dossier.get("siteId"):
        raise SystemExit(
            "Builder failed: prompt meta siteId mismatch "
            f"({meta_path} has {site_id!r}, Project Input has "
            f"{dossier.get('siteId')!r})."
        )

    version = meta.get("version")
    if version is not None and (not isinstance(version, int) or version < 1):
        raise SystemExit(
            f"Builder failed: prompt meta has invalid version at {meta_path}."
        )

    mode = meta.get("mode")
    if mode not in {"init", "followup"}:
        mode = "followup" if isinstance(version, int) and version > 1 else "init"

    project_id = meta.get("projectId")
    if project_id is not None and (
        not isinstance(project_id, str) or not project_id.strip()
    ):
        raise SystemExit(
            f"Builder failed: prompt meta has invalid projectId at {meta_path}."
        )
    if mode == "followup" and not project_id:
        raise SystemExit(
            f"Builder failed: follow-up prompt meta requires projectId at {meta_path}."
        )

    normalized = dict(meta)
    normalized["mode"] = mode
    normalized["metaPath"] = _to_repo_relative(meta_path)
    return normalized


def _prompt_meta_mode(prompt_meta: dict[str, Any] | None) -> str:
    if not prompt_meta:
        return "init"
    mode = prompt_meta.get("mode")
    return mode if mode in {"init", "followup"} else "init"


def _prompt_meta_project_id(prompt_meta: dict[str, Any] | None) -> str | None:
    if not prompt_meta:
        return None
    project_id = prompt_meta.get("projectId")
    return project_id if isinstance(project_id, str) and project_id else None


def _prompt_meta_version(prompt_meta: dict[str, Any] | None) -> int | None:
    if not prompt_meta:
        return None
    version = prompt_meta.get("version")
    return version if isinstance(version, int) and version >= 1 else None


def _prompt_meta_raw_prompt(prompt_meta: dict[str, Any] | None) -> str | None:
    if not prompt_meta:
        return None
    mode = _prompt_meta_mode(prompt_meta)
    key = "followUpPrompt" if mode == "followup" else "originalPrompt"
    value = prompt_meta.get(key)
    return value if isinstance(value, str) else None


# ---------------------------------------------------------------------------
# Trace (append-only Engine Events)
# ---------------------------------------------------------------------------


class Trace:
    """Append-only Engine Event log per `engine-run.v1.json:trace`."""

    def __init__(self, run_id: str, run_dir: Path) -> None:
        self.run_id = run_id
        self.path = run_dir / "trace.ndjson"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Initialize empty file so the trace is canonical for this run.
        with self.path.open("w", encoding="utf-8", newline="\n"):
            pass

    def event(
        self,
        phase: str,
        event: str,
        status: str,
        message: str = "",
        payload_path: str | None = None,
    ) -> None:
        record = {
            "runId": self.run_id,
            "phase": phase,
            "event": event,
            "status": status,
            "message": message,
            "timestamp": utc_now().isoformat(),
            "payloadPath": payload_path,
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Starter copy and patch helpers
# ---------------------------------------------------------------------------


def _ignore_secret_envs(_dir: str, names: list[str]) -> list[str]:
    """shutil.copytree ignore-callback that drops any real .env file.

    `.env.example` is preserved (canonical placeholder). Combined with the
    pattern-based ignore list this guarantees that a starter that accidentally
    contains a real `.env` or `.env.local` cannot leak into a generated site.
    """
    drop: list[str] = []
    for name in names:
        if name in _ALLOWED_ENV_NAMES:
            continue
        if _FORBIDDEN_ENV_PATTERN.match(name):
            drop.append(name)
    return drop


def _ignore_combined(dir_path: str, names: list[str]) -> set[str]:
    base_ignore = shutil.ignore_patterns(
        "node_modules",
        ".next",
        "out",
        "*.tsbuildinfo",
        "next-env.d.ts",
    )(dir_path, names)
    secret_ignore = set(_ignore_secret_envs(dir_path, names))
    return set(base_ignore) | secret_ignore


_NPM_INSTALL_INPUT_KEYS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
    "overrides",
    "packageManager",
    "engines",
)


def _npm_install_inputs_changed(source: Path, target: Path) -> bool:
    source_pkg_path = source / "package.json"
    target_pkg_path = target / "package.json"
    if not source_pkg_path.exists() or not target_pkg_path.exists():
        return True

    source_pkg = load_json(source_pkg_path)
    try:
        target_pkg = load_json(target_pkg_path)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # An unreadable, malformed, or non-UTF-8 target package.json
        # cannot be diff:ad mot source. Force a clean reinstall instead
        # of letting the exception abort the whole build.
        return True
    return any(source_pkg.get(key) != target_pkg.get(key) for key in _NPM_INSTALL_INPUT_KEYS)


def copy_starter(starter_id: str, target: Path) -> None:
    source = STARTERS_DIR / starter_id
    if not source.exists():
        raise SystemExit(
            f"Starter '{starter_id}' missing at {source}. Run the starter setup before building."
        )
    # Preserve existing target's node_modules so we do not force a fresh
    # `npm install` on every unchanged regeneration, but never preserve `.next`.
    # Next's build cache is derived output, not source, and can carry stale
    # prerender state across starter/package changes. B41 reproduced as a
    # generated-site `/_global-error` prerender failure while a clean target
    # built successfully, so every regeneration now starts with a clean
    # framework build cache.
    preserved = {"node_modules"}
    if target.exists() and _npm_install_inputs_changed(source, target):
        preserved = set()
    if target.exists():
        for entry in target.iterdir():
            if entry.name in preserved:
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        shutil.copytree(source, target, ignore=_ignore_combined, dirs_exist_ok=True)
    else:
        shutil.copytree(source, target, ignore=_ignore_combined)


UPLOADS_ROOT_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"


def iter_asset_refs(project_input: dict) -> list[dict]:
    """Returnera alla AssetRef-objekt som finns i Project Input
    (`brand.logo`, `brand.heroImage`, varje item i `gallery`). Tar bara
    med refs där alla fält schemat kräver finns; trasiga refs hoppas
    över så build:en inte kraschar på en korrupt manifest.json."""
    refs: list[dict] = []
    brand = project_input.get("brand") or {}
    if isinstance(brand, dict):
        for key in ("logo", "heroImage"):
            ref = brand.get(key)
            if isinstance(ref, dict) and ref.get("assetId") and ref.get("filename"):
                refs.append(ref)
    gallery = project_input.get("gallery") or []
    if isinstance(gallery, list):
        for item in gallery:
            if isinstance(item, dict) and item.get("assetId") and item.get("filename"):
                refs.append(item)
    return refs


def copy_operator_uploads(site_id: str, target: Path, project_input: dict) -> int:
    """Kopiera operatör-uppladdade assets från data/uploads/<siteId>/
    (eller __draft för uppladdningar som gjordes innan siteId
    bestämdes) till genererad sajts public/uploads/. Returnerar antal
    filer som kopierats — 0 är giltigt (operatorn laddade inte upp
    något, generated site kör med starter-defaults).

    Vi föredrar `optimized.webp` (≤200 KB efter sharp-pipelinen) och
    faller tillbaka till `original.<ext>` om optimering inte gjordes
    (SVG passerar orörd). Filename i public/ är den som finns i
    AssetRef.filename så TSX-renderers kan referera den som
    /uploads/<filename>.
    """
    refs = iter_asset_refs(project_input)
    if not refs:
        return 0

    candidate_dirs = [UPLOADS_ROOT_DIR / site_id, UPLOADS_ROOT_DIR / "__draft"]
    public_uploads = target / "public" / "uploads"
    public_uploads.mkdir(parents=True, exist_ok=True)

    copied = 0
    for ref in refs:
        asset_id = ref["assetId"]
        filename = ref["filename"]
        source_dir: Path | None = None
        for candidate in candidate_dirs:
            if (candidate / asset_id).is_dir():
                source_dir = candidate / asset_id
                break
        if source_dir is None:
            print(
                f"copy_operator_uploads: asset {asset_id} saknas på disk "
                f"(letade i {candidate_dirs}). Hoppar över."
            )
            continue

        # Föredra webp; annars första matchande original.<ext>.
        candidates = [
            source_dir / "optimized.webp",
            source_dir / "original.svg",
            source_dir / "original.png",
            source_dir / "original.jpg",
            source_dir / "original.webp",
        ]
        source_file: Path | None = next((c for c in candidates if c.exists()), None)
        if source_file is None:
            print(
                f"copy_operator_uploads: asset {asset_id} saknar variant-fil "
                f"i {source_dir}. Hoppar över."
            )
            continue

        dest = public_uploads / filename
        shutil.copy2(source_file, dest)
        copied += 1

    return copied


def variant_css(variant: dict) -> str:
    tokens = variant["tokens"]
    color = tokens["color"]
    radius = tokens["radius"]
    spacing = tokens["spacing"]
    return (
        ":root {\n"
        f"  --background: {color['background']};\n"
        f"  --foreground: {color['foreground']};\n"
        f"  --muted: {color['muted']};\n"
        f"  --border: {color['border']};\n"
        f"  --primary: {color['primary']};\n"
        f"  --primary-foreground: {color['primaryForeground']};\n"
        f"  --accent: {color['accent']};\n"
        f"  --accent-foreground: {color['accentForeground']};\n"
        f"  --radius-sm: {radius['sm']};\n"
        f"  --radius-md: {radius['md']};\n"
        f"  --radius-lg: {radius['lg']};\n"
        f"  --section-spacing: {spacing['section']};\n"
        f"  --container-width: {spacing['container']};\n"
        "}\n"
    )


def patch_globals_css(target: Path, variant: dict) -> None:
    css = target / "app" / "globals.css"
    original = css.read_text(encoding="utf-8")
    block = variant_css(variant)
    marker = "/* sajtbyggaren-variant-tokens:start */"
    end = "/* sajtbyggaren-variant-tokens:end */"
    if marker in original:
        before, _, rest = original.partition(marker)
        _, _, after = rest.partition(end)
        new_contents = f"{before}{marker}\n{block}{end}{after}"
    else:
        new_contents = f"{marker}\n{block}{end}\n\n{original}"
    write(css, new_contents)


def patch_package_json(target: Path, dossier: dict) -> None:
    pkg_path = target / "package.json"
    pkg = load_json(pkg_path)
    pkg["name"] = dossier["siteId"]
    write(pkg_path, json.dumps(pkg, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Page renderers - JSX templates that compose lucide-react icons with the
# shadcn button primitive shipped by marketing-base. The renderers are kept
# generic so the same builder works for very different Project Inputs (a
# small painter firm and a video game arcade should both look polished).
# ---------------------------------------------------------------------------


SERVICE_ICONS: dict[str, str] = {
    "interior-painting": "Paintbrush",
    "exterior-painting": "House",
    "color-consultation": "Palette",
    "renovation-painting": "Hammer",
    "arcade-games": "Gamepad2",
    "retro-consoles": "Joystick",
    "tournaments": "Trophy",
    "tournaments-monthly": "Trophy",
    "birthday-parties": "Cake",
    "private-events": "PartyPopper",
    "food-drinks": "Coffee",
    "merch-shop": "ShoppingBag",
}
DEFAULT_SERVICE_ICON = "Sparkles"


def _icon_for_service(service_id: str) -> str:
    return SERVICE_ICONS.get(service_id, DEFAULT_SERVICE_ICON)


def _phone_href(phone: str) -> str:
    return phone.replace(" ", "").replace("(", "").replace(")", "")


# Default Swedish nav labels per scaffold route id. Unknown ids fall back
# to a slug-to-Title-Case form via _nav_label_for_route. Centralised so
# different scaffolds share the same vocabulary (e.g. "contact" -> "Kontakt"
# everywhere) without duplicating literals in each renderer.
_NAV_LABEL_BY_ROUTE_ID: dict[str, str] = {
    "home": "Hem",
    "services": "Tjänster",
    "products": "Produkter",
    "about": "Om oss",
    "contact": "Kontakt",
}


# Copy fragments per "listing" route id (services vs products). render_home
# renders the same overall hero/list/trust structure for both scaffolds but
# swaps eyebrow, heading and CTA copy so the cross-link sounds right.
_LISTING_COPY_BY_ROUTE_ID: dict[str, dict[str, str]] = {
    "services": {
        "eyebrow": "Tjänster",
        "heading": "Vad vi tar oss an",
        "cta": "Se alla tjänster",
    },
    "products": {
        "eyebrow": "Produkter",
        "heading": "Vårt sortiment",
        "cta": "Se alla produkter",
    },
}


# Demo-baseline-fix 1C (B96): hero CTA copy keyed on scaffold + conversion
# goals. ``ecommerce-lite`` (or any project whose conversionGoals signal
# purchase intent) gets a shopping verb; bokningsdrivna verksamheter
# (``booking_request`` i conversionGoals) får boka-verbet; resten faller
# tillbaka på "Begär offert" som var hardcoded före re-Verifierings-Scout
# 2026-05-15.
_HERO_CTA_VARIANT_LABELS: dict[str, dict[str, str]] = {
    "shop": {"sv": "Shoppa nu", "en": "Shop now"},
    "booking": {"sv": "Boka tid", "en": "Book a time"},
    "quote": {"sv": "Begär offert", "en": "Request a quote"},
}

_SHOP_CONVERSION_GOALS: frozenset[str] = frozenset(
    {"product_purchase", "shop_visit", "purchase"}
)
_BOOKING_CONVERSION_GOALS: frozenset[str] = frozenset(
    {"booking_request", "book_appointment"}
)
_SHOP_BUSINESS_TYPES: frozenset[str] = frozenset(
    {
        "e-commerce",
        "ecommerce",
        "ecommerce-shop",
        "ecommerce-store",
        "online-shop",
        "shop",
        "webshop",
        "webbshop",
    }
)
_BOOKING_BUSINESS_TYPES: frozenset[str] = frozenset(
    {
        "hair-salon",
        "hairdresser",
        "frisör",
        "barber",
        "barber-shop",
        "naprapat-clinic",
        "naprapath-clinic",
        "naprapat",
        "naprapath",
        "naprapatklinik",
        "chiropractor",
        "chiropractic-clinic",
        "massage",
        "massage-therapist",
        "physiotherapist",
        "physiotherapy-clinic",
        "dentist",
        "dental-clinic",
        "personal-training",
        "personal-trainer",
    }
)


def _normalize_business_type(value: object) -> str:
    """Normalize briefModel business type variants for CTA fallback lookup."""
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    compact = raw.replace("_", "-").replace(" ", "-")
    if compact.startswith("naprapat") or compact.startswith("naprapath"):
        return "naprapat-clinic"
    if compact in {"frisor", "frisör", "hairdresser"}:
        return "hair-salon"
    if compact in {"webshop", "webbshop", "online-shop"}:
        return "e-commerce"
    return compact


def _hero_cta_variant(dossier: dict) -> str:
    """Return the hero CTA variant key for this Project Input.

    Explicit conversion goals win first. Business type is then used as
    the B100 fallback for short prompts where briefModel leaves
    ``conversionGoals=[]``. The scaffold id remains the final defensive
    fallback because operators sometimes pin ``ecommerce-lite`` without
    filling conversionGoals.
    """
    scaffold_id = (dossier.get("scaffoldId") or "").strip().lower()
    company = dossier.get("company") or {}
    business_type = _normalize_business_type(company.get("businessType"))
    goals = {
        str(goal).strip().lower()
        for goal in (dossier.get("conversionGoals") or [])
        if isinstance(goal, str)
    }
    if goals & _SHOP_CONVERSION_GOALS:
        return "shop"
    if goals & _BOOKING_CONVERSION_GOALS:
        return "booking"
    if business_type in _SHOP_BUSINESS_TYPES:
        return "shop"
    if business_type in _BOOKING_BUSINESS_TYPES:
        return "booking"
    if scaffold_id == "ecommerce-lite":
        return "shop"
    return "quote"


def _hero_cta_label(dossier: dict) -> str:
    """Return the hero CTA label string for this Project Input.

    Reads ``dossier["language"]`` (defaults to ``sv``) and routes
    through ``_hero_cta_variant`` so render_home and render_services
    share the same wording. Values are drawn from the whitelist in
    ``_HERO_CTA_VARIANT_LABELS`` so the returned string is safe to
    interpolate into TSX without JSX-escaping (it never contains
    angle brackets, quotes or curlies).
    """
    language = (dossier.get("language") or "sv").strip().lower()
    if language not in ("sv", "en"):
        language = "sv"
    variant = _hero_cta_variant(dossier)
    return _HERO_CTA_VARIANT_LABELS[variant][language]


def _location_is_country_only(location: dict) -> bool:
    """Return True when ``location.city`` equals ``location.country``.

    Demo-baseline-fix 1C (B95): when the brief returns a country name
    as ``locationHint`` (or omits it entirely), ``_placeholder_location``
    falls back to ``city == country`` as a marker. ``render_home`` uses
    this helper to suppress the hero ortstag rather than rendering the
    country name as if it were a city.
    """
    city = (location.get("city") or "").strip().lower()
    country = (location.get("country") or "").strip().lower()
    return bool(city) and city == country


def _nav_label_for_route(route_id: str) -> str:
    """Return the Swedish nav label for a scaffold route id.

    Known ids use the centralised lookup. Unknown ids fall back to a
    human-readable form so an early-preview scaffold can still produce
    a sensible nav without first registering its labels here.
    """
    if route_id in _NAV_LABEL_BY_ROUTE_ID:
        return _NAV_LABEL_BY_ROUTE_ID[route_id]
    return route_id.replace("-", " ").replace("_", " ").title()


def _nav_items_from_scaffold(
    scaffold_default_routes: list[dict],
    dossier_routes: list[str],
) -> list[tuple[str, str]]:
    """Build the (href, label) nav items for header + footer.

    Driven by the scaffold's ``defaultRoutes`` (so different scaffolds
    can emit different nav structures) plus any Dossier-contributed
    routes that should appear in the nav. Currently the only such
    Dossier-route is ``/spel`` (interactive-game-loop); when more
    Dossiers add navigable pages this branch widens.

    Dossier-routes are deduped against the scaffold paths so a future
    scaffold that adopts ``/spel`` in ``defaultRoutes`` does not get
    the entry rendered twice (B52). Scaffold order is preserved; the
    Dossier-injected route lands at the end, after the scaffold's own
    nav structure.
    """
    items: list[tuple[str, str]] = [
        (route["path"], _nav_label_for_route(route["id"])) for route in scaffold_default_routes
    ]
    existing_paths = {href for href, _ in items}
    if "/spel" in dossier_routes and "/spel" not in existing_paths:
        items.append(("/spel", "Spel"))
    return items


def _pick_contact_route(
    scaffold_default_routes: list[dict],
) -> dict:
    """Return the scaffold's contact route.

    Renderers that link operators to the contact page route hrefs
    through this helper so a scaffold that ever moves the contact id
    to ``/kontakta-oss`` keeps its CTAs aligned with the nav. Missing
    contact routes fail fast: otherwise the builder could silently emit
    CTA links to ``/kontakt`` without writing the matching page.
    """
    for route in scaffold_default_routes:
        if route.get("id") == "contact":
            return route
    route_ids = [str(route.get("id", "<missing>")) for route in scaffold_default_routes]
    raise SystemExit(
        "Builder failed: scaffold routes.json defaultRoutes must include "
        "a route with id='contact' because generated navigation and CTAs "
        f"link to the contact page. Found route ids: {route_ids!r}."
    )


def _pick_listing_route(
    scaffold_default_routes: list[dict],
) -> dict | None:
    """Return the scaffold's primary listing route (services or products).

    Used by ``render_home`` to point the secondary CTA at the right
    place: ``/tjanster`` for local-service-business, ``/produkter``
    for ecommerce-lite. Returns ``None`` for scaffolds that declare
    neither (the home page then omits the listing cross-link entirely
    instead of inventing a path that has no matching route).
    """
    by_id = {r["id"]: r for r in scaffold_default_routes}
    for candidate in ("services", "products"):
        if candidate in by_id:
            return by_id[candidate]
    return None


def _collect_icons_for_pages(services: list[dict], dossier_routes: list[str]) -> list[str]:
    used: set[str] = {
        DEFAULT_SERVICE_ICON,
        "Phone",
        "Mail",
        "MapPin",
        "Clock",
        "ShieldCheck",
        "ArrowRight",
        "Quote",
    }
    for svc in services:
        used.add(_icon_for_service(svc["id"]))
    if "/spel" in dossier_routes:
        used.add("Gamepad2")
    return sorted(used)


def render_layout(
    dossier: dict,
    dossier_routes: list[str],
    *,
    scaffold_default_routes: list[dict] | None = None,
    contact_path: str | None = None,
) -> str:
    """Whole-file layout.tsx with sticky header and footer.

    Nav items are built from ``scaffold_default_routes`` so different
    scaffolds emit different navigation shells (e.g. ecommerce-lite
    points at ``/produkter`` instead of ``/tjanster``). When
    ``scaffold_default_routes`` is ``None`` the renderer falls back
    to the local-service-business defaults; this keeps the unit
    tests in tests/test_builder_audit_post_3b_next.py (which only
    check JSX escaping) functional without forcing every caller to
    pass the scaffold registry.
    """
    company = dossier["company"]
    contact = dossier["contact"]
    if scaffold_default_routes is None:
        scaffold_default_routes = [
            {"id": "home", "path": "/"},
            {"id": "services", "path": "/tjanster"},
            {"id": "about", "path": "/om-oss"},
            {"id": "contact", "path": "/kontakt"},
        ]
    nav_items = _nav_items_from_scaffold(scaffold_default_routes, dossier_routes)
    if contact_path is None:
        contact_path = str(_pick_contact_route(scaffold_default_routes)["path"])
    contact_href = _route_href(contact_path)
    # nav_items entries come from _nav_items_from_scaffold (canonical
    # paths + Swedish labels driven by scaffold_default_routes). Paths go
    # through _route_href which validates them as canonical site paths
    # (B50). Labels go through _jsx_safe_string so an unknown route id
    # that falls through to the ``.title()`` slug-to-Title-Case branch
    # (e.g. "look-book" -> "Look Book") cannot leak raw HTML/JSX into
    # the nav (B51). Customer-supplied values (company.name,
    # company.tagline, contact.*, addressLines) all go through
    # _jsx_safe_string for JSX positions or _js_string_literal for the
    # metadata object literal - see B30 in docs/known-issues.md.
    nav_links = "\n".join(
        f'            <a href={_route_href(href)} className="text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition-colors">{_jsx_safe_string(label)}</a>'
        for href, label in nav_items
    )
    address_line = ", ".join(contact["addressLines"])

    # Operatör-uppladdad logotyp (om finns) → renderas i header och
    # footer. Annars faller vi tillbaka till bokstavs-monogram-spannet
    # som starters har använt sedan B12. Filen finns redan på plats
    # under public/uploads/ via copy_operator_uploads ovan.
    brand_block = dossier.get("brand") if isinstance(dossier.get("brand"), dict) else {}
    operator_logo = brand_block.get("logo") if isinstance(brand_block, dict) else None
    if isinstance(operator_logo, dict) and operator_logo.get("filename"):
        logo_filename = operator_logo["filename"]
        logo_alt = operator_logo.get("alt") or f"{company['name']} logotyp"
        logo_width = operator_logo.get("width")
        logo_height = operator_logo.get("height")
        dims = ""
        if isinstance(logo_width, int) and isinstance(logo_height, int):
            dims = f' width={{{logo_width}}} height={{{logo_height}}}'
        # eslint-disable-next-line @next/next/no-img-element — vi använder
        # raw <img> för att slippa Next.js Image-loader inställningar i
        # alla starters; webp:erna är redan komprimerade av sharp.
        # VIKTIGT: `_jsx_safe_string("...")` returnerar `{"..."}` — det är
        # ett komplett JSX-uttryck för text/attribut, INTE en sträng som kan
        # smetas in mellan `"`-quotes. Tidigare kombinerade vi det med
        # `src="/uploads/{...}"`, vilket producerade `src="/uploads/{"x.webp"}"`
        # och bröt next build med "Expected '</', got '.'". Korrekt är att
        # låta hela attribut-värdet vara ett JS-uttryck (`src={...}`).
        header_logo_jsx = (
            f'              <img src={_jsx_safe_string("/uploads/" + logo_filename)}'
            f' alt={_js_string_literal(logo_alt)} className="h-9 w-auto object-contain"{dims} />'
        )
        footer_logo_jsx = (
            f'              <img src={_jsx_safe_string("/uploads/" + logo_filename)}'
            f' alt={_js_string_literal(logo_alt)} className="h-10 w-auto object-contain mb-1"{dims} />'
        )
    else:
        header_logo_jsx = (
            f'              <span className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-[color:var(--primary)] text-[color:var(--primary-foreground)] text-xs font-bold uppercase">{_jsx_safe_string(company["name"][:2])}</span>'
        )
        footer_logo_jsx = ""

    return (
        'import type { Metadata } from "next";\n'
        'import { Geist, Geist_Mono } from "next/font/google";\n'
        'import { Mail, MapPin, Phone } from "lucide-react";\n'
        'import "./globals.css";\n'
        "\n"
        "const geistSans = Geist({\n"
        '  variable: "--font-geist-sans",\n'
        '  subsets: ["latin"],\n'
        "});\n"
        "\n"
        "const geistMono = Geist_Mono({\n"
        '  variable: "--font-geist-mono",\n'
        '  subsets: ["latin"],\n'
        "});\n"
        "\n"
        "export const metadata: Metadata = {\n"
        f"  title: {_js_string_literal(company['name'])},\n"
        f"  description: {_js_string_literal(company['tagline'])},\n"
        "};\n"
        "\n"
        "export default function RootLayout({\n"
        "  children,\n"
        "}: Readonly<{\n"
        "  children: React.ReactNode;\n"
        "}>) {\n"
        "  return (\n"
        "    <html\n"
        '      lang="sv"\n'
        "      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}\n"
        "    >\n"
        '      <body className="min-h-full flex flex-col bg-[color:var(--background)] text-[color:var(--foreground)]">\n'
        '        <header className="sticky top-0 z-40 border-b border-[color:var(--border)] bg-[color:var(--background)]/80 backdrop-blur supports-[backdrop-filter]:bg-[color:var(--background)]/60">\n'
        '          <div className="mx-auto flex w-[var(--container-width)] items-center justify-between gap-6 py-4">\n'
        '            <a href="/" className="flex items-center gap-2 text-base font-semibold">\n'
        f"{header_logo_jsx}\n"
        f'              <span className="hidden sm:inline">{_jsx_safe_string(company["name"])}</span>\n'
        "            </a>\n"
        '            <nav className="flex items-center gap-5 text-sm font-medium">\n'
        f"{nav_links}\n"
        "            </nav>\n"
        f'            <a href={contact_href} className="hidden md:inline-flex items-center gap-1 rounded-md bg-[color:var(--primary)] px-4 py-2 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">Kontakta oss</a>\n'
        "          </div>\n"
        "        </header>\n"
        '        <div className="flex-1">{children}</div>\n'
        '        <footer className="border-t border-[color:var(--border)] bg-[color:var(--background)]">\n'
        '          <div className="mx-auto grid w-[var(--container-width)] gap-8 py-12 md:grid-cols-3">\n'
        '            <div className="flex flex-col gap-3">\n'
        + (f"{footer_logo_jsx}\n" if footer_logo_jsx else "")
        + f'              <p className="text-base font-semibold">{_jsx_safe_string(company["name"])}</p>\n'
        f'              <p className="text-sm text-[color:var(--muted)]">{_jsx_safe_string(company["tagline"])}</p>\n'
        "            </div>\n"
        '            <div className="flex flex-col gap-2 text-sm">\n'
        '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Kontakt</p>\n'
        f'              <a href={_jsx_safe_string("tel:" + _phone_href(contact["phone"]))} className="inline-flex items-center gap-2 hover:underline"><Phone className="size-4" />{_jsx_safe_string(contact["phone"])}</a>\n'
        f'              <a href={_jsx_safe_string("mailto:" + contact["email"])} className="inline-flex items-center gap-2 hover:underline"><Mail className="size-4" />{_jsx_safe_string(contact["email"])}</a>\n'
        f'              <p className="inline-flex items-start gap-2 text-[color:var(--muted)]"><MapPin className="size-4 mt-0.5" />{_jsx_safe_string(address_line)}</p>\n'
        "            </div>\n"
        '            <div className="flex flex-col gap-2 text-sm text-[color:var(--muted)]">\n'
        '              <p className="text-xs uppercase tracking-widest">Sajt</p>\n'
        + "\n".join(
            f'              <a href={_route_href(href)} className="hover:underline">{_jsx_safe_string(label)}</a>'
            for href, label in nav_items
        )
        + "\n"
        "            </div>\n"
        "          </div>\n"
        '          <div className="border-t border-[color:var(--border)] py-4">\n'
        f'            <p className="mx-auto w-[var(--container-width)] text-xs text-[color:var(--muted)]">© {{new Date().getFullYear()}} {_jsx_safe_string(company["name"])}. Alla rättigheter förbehållna.</p>\n'
        "          </div>\n"
        "        </footer>\n"
        "      </body>\n"
        "    </html>\n"
        "  );\n"
        "}\n"
    )


def render_home(
    dossier: dict,
    dossier_routes: list[str],
    *,
    listing_route: dict | None = None,
    contact_path: str = "/kontakt",
) -> str:
    """Home page renderer.

    ``listing_route`` is the scaffold's primary listing surface
    (``{"id": "services", "path": "/tjanster"}`` for
    local-service-business, ``{"id": "products", "path": "/produkter"}``
    for ecommerce-lite). When ``None`` the renderer keeps the listing
    section content but omits the cross-link rather than inventing a
    route that may not exist.

    The pre-B13 B30 unit tests in
    ``tests/test_builder_audit_post_3b_next.py`` call
    ``render_home(dossier, dossier_routes=...)`` directly to exercise
    JSX escaping and depend on the service/product grid being rendered.
    Keeping the section but dropping the CTA preserves those tests
    without creating a ghost route.
    """
    company = dossier["company"]
    location = dossier["location"]
    services = dossier["services"]
    trust = dossier["trustSignals"]
    contact = dossier["contact"]
    icons_used = _collect_icons_for_pages(services, dossier_routes)
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'
    services_grid = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--card,var(--background))] p-6 transition-all hover:border-[color:var(--primary)] hover:shadow-sm">\n'
        f'              <span className="mb-4 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><{_icon_for_service(svc["id"])} className="size-5" /></span>\n'
        f'              <h3 className="text-lg font-semibold">{_jsx_safe_string(svc["label"])}</h3>\n'
        f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </li>"
        for svc in services
    )
    trust_items = "\n".join(
        f'            <li key="trust-{i}" className="flex items-start gap-3">\n'
        f'              <ShieldCheck className="mt-0.5 size-5 shrink-0 text-[color:var(--primary)]" />\n'
        f'              <span className="text-base">{_jsx_safe_string(item)}</span>\n'
        "            </li>"
        for i, item in enumerate(trust)
    )
    trust_section = ""
    if trust:
        trust_section = (
            '      <section className="border-t border-[color:var(--border)] bg-[color:var(--accent)]/20">\n'
            '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[var(--section-spacing)]">\n'
            '          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Varför oss</h2>\n'
            '          <ul className="grid gap-4 md:grid-cols-2">\n'
            f"{trust_items}\n"
            "          </ul>\n"
            "        </div>\n"
            "      </section>\n"
            "\n"
        )
    spel_cta = (
        '          <a href="/spel" className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Gamepad2 className="size-4" />Spela direkt</a>\n'
        if "/spel" in dossier_routes
        else ""
    )
    contact_href = _route_href(contact_path)
    listing_copy = _LISTING_COPY_BY_ROUTE_ID["services"]
    listing_link = ""
    if listing_route is not None:
        listing_copy = _LISTING_COPY_BY_ROUTE_ID.get(
            listing_route["id"], _LISTING_COPY_BY_ROUTE_ID["services"]
        )
        listing_href = _route_href(listing_route["path"])
        listing_link = f'          <a href={listing_href} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">{listing_copy["cta"]}<ArrowRight className="size-4" /></a>\n'
    # Demo-baseline-fix 1C (B95): suppress the hero ortstag when the
    # location is country-only (no real city, see _placeholder_location).
    location_tag = ""
    if not _location_is_country_only(location):
        location_tag = (
            '          <div className="flex items-center gap-2 text-sm uppercase tracking-widest text-[color:var(--muted)]">\n'
            '            <MapPin className="size-4" />\n'
            f"            <span>{_jsx_safe_string(location['city'])}</span>\n"
            "          </div>\n"
        )
    # Demo-baseline-fix 1C (B96): hero CTA label is scaffold-aware
    # (shop / booking / quote) so e-commerce projects do not get a
    # service-business "Begär offert" verb in the hero.
    hero_cta_label = _hero_cta_label(dossier)

    # Operator-uploaded hero image (if present) renders as a banner
    # above the gradient section. The asset is placed in public/uploads/
    # by copy_operator_uploads. We render a raw <img> (not next/image)
    # because the webp files are pre-compressed by sharp and the
    # starters ship without a Next.js Image loader config.
    brand_block = dossier.get("brand") if isinstance(dossier.get("brand"), dict) else {}
    hero_asset = brand_block.get("heroImage") if isinstance(brand_block, dict) else None
    hero_section_jsx = ""
    if isinstance(hero_asset, dict) and hero_asset.get("filename"):
        hero_filename = hero_asset["filename"]
        hero_alt = hero_asset.get("alt") or company["tagline"]
        hero_section_jsx = (
            '      <section className="relative w-full overflow-hidden bg-[color:var(--background)]">\n'
            '        <div className="mx-auto w-[var(--container-width)] pt-[var(--section-spacing)]">\n'
            f'          <img src={_jsx_safe_string("/uploads/" + hero_filename)} alt={_js_string_literal(hero_alt)} className="aspect-[16/9] w-full rounded-2xl object-cover shadow-sm" />\n'
            "        </div>\n"
            "      </section>\n"
            "\n"
        )

    return (
        icon_import + "\n"
        "export default function Home() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        f"{hero_section_jsx}"
        '      <section className="relative overflow-hidden bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/30">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        f"{location_tag}"
        f'          <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">{_jsx_safe_string(company["name"])}</h1>\n'
        f'          <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed md:text-xl">{_jsx_safe_string(company["tagline"])}</p>\n'
        '          <div className="flex flex-wrap gap-3">\n'
        f'            <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{hero_cta_label}<ArrowRight className="size-4" /></a>\n'
        f'            <a href={_jsx_safe_string("tel:" + _phone_href(contact["phone"]))} className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />Ring {_jsx_safe_string(contact["phone"])}</a>\n'
        f"{spel_cta}"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{listing_copy["eyebrow"]}</p>\n'
        f'            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">{listing_copy["heading"]}</h2>\n'
        "          </div>\n"
        '          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{services_grid}\n"
        "          </ul>\n"
        f"{listing_link}"
        "        </div>\n"
        "      </section>\n"
        "\n"
        f"{trust_section}"
        '      <section className="border-t border-[color:var(--border)] bg-[color:var(--primary)] text-[color:var(--primary-foreground)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-[var(--section-spacing)]">\n'
        '          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Hör av dig idag</h2>\n'
        '          <p className="max-w-2xl text-base opacity-90 md:text-lg">Beskriv kort vad du behöver så återkommer vi inom en arbetsdag.</p>\n'
        f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary-foreground)] px-5 py-3 text-sm font-medium text-[color:var(--primary)] hover:opacity-90 transition-opacity">Kontakta oss<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_services(
    dossier: dict,
    *,
    contact_path: str = "/kontakt",
) -> str:
    services = dossier["services"]
    contact_href = _route_href(contact_path)
    icons_used = sorted({_icon_for_service(svc["id"]) for svc in services} | {"ArrowRight"})
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'
    items = "\n".join(
        f'          <article key={_jsx_safe_string(svc["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all hover:border-[color:var(--primary)] hover:shadow-sm">\n'
        f'            <span className="mb-4 inline-flex size-12 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><{_icon_for_service(svc["id"])} className="size-6" /></span>\n'
        f'            <h2 className="text-xl font-semibold">{_jsx_safe_string(svc["label"])}</h2>\n'
        f'            <p className="mt-3 text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "          </article>"
        for svc in services
    )
    # Demo-baseline-fix 1C (B96): keep the bottom-of-page CTA on
    # render_services aligned with the hero CTA verb so a booking-driven
    # service business (e.g. frisör) reads "Boka tid" everywhere.
    cta_label = _hero_cta_label(dossier)
    return (
        icon_import + "\n"
        "export default function ServicesPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Tjänster</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Vad vi gör</h1>\n'
        '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Allt vi erbjuder, samlat på ett ställe. Klicka på en tjänst eller hör av dig direkt.</p>\n'
        "          </header>\n"
        '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{items}\n"
        "          </div>\n"
        f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{cta_label}<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_about(dossier: dict) -> str:
    company = dossier["company"]
    team = company.get("team", [])
    location = dossier["location"]
    areas_html = ", ".join(location["serviceAreas"])
    location_section = ""
    if not _location_is_country_only(location):
        location_section = (
            '          <div className="flex flex-col gap-2">\n'
            '            <h2 className="inline-flex items-center gap-2 text-2xl font-semibold tracking-tight"><MapPin className="size-5" />Områden vi arbetar i</h2>\n'
            f'            <p className="text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(areas_html)}</p>\n'
            "          </div>\n"
        )
    # Demo-baseline-fix 1C (B94): skip the entire team section when no
    # team members are declared, mirroring B66's trustSignals fix.
    # Previously the renderer emitted "Teamet" + an empty <ul>, which
    # surfaced on every generated /om-oss page in the re-Verifierings-
    # Scout 2026-05-15 run because prompt_to_project_input.py never
    # populates team.
    team_section = ""
    if team:
        team_items = "\n".join(
            f'            <li key={_jsx_safe_string(member["name"])} className="rounded-xl border border-[color:var(--border)] p-6">\n'
            f'              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-full bg-[color:var(--accent)] text-[color:var(--accent-foreground)] text-sm font-semibold uppercase">{_jsx_safe_string(_member_initials(member["name"]))}</span>\n'
            f'              <p className="text-base font-semibold">{_jsx_safe_string(member["name"])}</p>\n'
            f'              <p className="mt-1 text-sm text-[color:var(--muted)]">{_jsx_safe_string(member["role"])}</p>\n'
            "            </li>"
            for member in team
        )
        team_section = (
            '          <div className="flex flex-col gap-4">\n'
            '            <h2 className="text-2xl font-semibold tracking-tight">Teamet</h2>\n'
            '            <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
            f"{team_items}\n"
            "            </ul>\n"
            "          </div>\n"
        )

    # Gallery images with placement="about" (or no placement, but we
    # restrict ourselves to about so we do not overload /om-oss).
    # The images come from operator upload via copy_operator_uploads.
    gallery_items = dossier.get("gallery") or []
    about_images = [
        item
        for item in gallery_items
        if isinstance(item, dict)
        and item.get("filename")
        and (item.get("placement") in (None, "about"))
    ]
    gallery_section_jsx = ""
    if about_images:
        gallery_cards = "\n".join(
            f'            <figure key={_jsx_safe_string(item["assetId"])} className="overflow-hidden rounded-xl border border-[color:var(--border)] bg-[color:var(--background)]">\n'
            f'              <img src={_jsx_safe_string("/uploads/" + item["filename"])} alt={_js_string_literal(item.get("alt") or company["name"])} className="aspect-[4/3] w-full object-cover" />\n'
            "            </figure>"
            for item in about_images
        )
        gallery_section_jsx = (
            '          <div className="flex flex-col gap-4">\n'
            '            <h2 className="text-2xl font-semibold tracking-tight">Galleri</h2>\n'
            '            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
            f"{gallery_cards}\n"
            "            </div>\n"
            "          </div>\n"
        )
    return (
        'import { MapPin, Quote } from "lucide-react";\n'
        "\n"
        "export default function AboutPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Om oss</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{_jsx_safe_string(company["name"])}</h1>\n'
        "          </header>\n"
        '          <div className="relative max-w-3xl rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 md:p-8">\n'
        '            <Quote className="absolute -top-3 -left-3 size-8 text-[color:var(--primary)]/20" />\n'
        f'            <p className="text-lg text-[color:var(--foreground)] leading-relaxed">{_jsx_safe_string(company["story"])}</p>\n'
        "          </div>\n"
        f"{team_section}"
        f"{gallery_section_jsx}"
        f"{location_section}"
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_contact(dossier: dict) -> str:
    contact = dossier["contact"]
    address_lines = "\n".join(
        f'                <span className="block">{_jsx_safe_string(line)}</span>'
        for line in contact["addressLines"]
    )
    return (
        'import { Clock, Mail, MapPin, Phone } from "lucide-react";\n'
        "\n"
        "export default function ContactPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Kontakt</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Hör av dig</h1>\n'
        '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Beskriv jobbet kort så återkommer vi inom en arbetsdag med tider och offert.</p>\n'
        "          </header>\n"
        '          <div className="grid gap-4 md:grid-cols-2">\n'
        '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
        '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><Phone className="size-5" /></span>\n'
        '              <h2 className="text-base font-semibold">Telefon</h2>\n'
        f'              <a href={_jsx_safe_string("tel:" + _phone_href(contact["phone"]))} className="mt-2 block text-lg font-medium hover:underline">{_jsx_safe_string(contact["phone"])}</a>\n'
        '              <p className="mt-2 inline-flex items-center gap-2 text-sm text-[color:var(--muted)]">\n'
        '                <Clock className="size-4" />\n'
        f"                <span>{_jsx_safe_string(contact['openingHours'])}</span>\n"
        "              </p>\n"
        "            </article>\n"
        '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
        '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><Mail className="size-5" /></span>\n'
        '              <h2 className="text-base font-semibold">E-post</h2>\n'
        f'              <a href={_jsx_safe_string("mailto:" + contact["email"])} className="mt-2 block text-lg font-medium hover:underline">{_jsx_safe_string(contact["email"])}</a>\n'
        "            </article>\n"
        '            <article className="rounded-xl border border-[color:var(--border)] p-6 md:col-span-2">\n'
        '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><MapPin className="size-5" /></span>\n'
        '              <h2 className="text-base font-semibold">Adress</h2>\n'
        '              <address className="mt-2 not-italic">\n'
        f"{address_lines}\n"
        "              </address>\n"
        "            </article>\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_products(
    dossier: dict,
    *,
    contact_path: str = "/kontakt",
) -> str:
    """Products-page renderer for ecommerce-lite (B13 route-emission).

    Reads the ``services`` array from the Project Input. The schema
    keeps the field named ``services`` because the renderer reads
    the same id/label/summary tuple regardless of scaffold; the
    rename to a dedicated ``products`` field is deliberately left
    for the next sprint that flips ``SCAFFOLD_TO_STARTER`` to
    ``commerce-base`` (current focus: B13 is route-emission only).

    ``contact_path`` defaults to ``/kontakt`` so direct unit tests
    still produce a valid href. write_pages threads the scaffold's
    actual contact route in so a scaffold that moves contact to
    ``/kontakta-oss`` keeps the CTA aligned with the nav (Bugbot PR
    #19 follow-up).
    """
    products = dossier["services"]
    contact_href = _route_href(contact_path)
    icons_used = sorted(
        {_icon_for_service(item["id"]) for item in products} | {"ArrowRight", "ShoppingBag"}
    )
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'
    items = "\n".join(
        f'          <article key={_jsx_safe_string(item["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all hover:border-[color:var(--primary)] hover:shadow-sm">\n'
        f'            <span className="mb-4 inline-flex size-12 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><{_icon_for_service(item["id"])} className="size-6" /></span>\n'
        f'            <h2 className="text-xl font-semibold">{_jsx_safe_string(item["label"])}</h2>\n'
        f'            <p className="mt-3 text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(item["summary"])}</p>\n'
        "          </article>"
        for item in products
    )
    return (
        icon_import + "\n"
        "export default function ProductsPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Produkter</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Vårt sortiment</h1>\n'
        '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Här är våra produkter. Hör av dig om du undrar något så hjälper vi dig hela vägen till beställning.</p>\n'
        "          </header>\n"
        '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{items}\n"
        "          </div>\n"
        f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity"><ShoppingBag className="size-4" />Fråga om en beställning<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def write_pages(
    target: Path,
    dossier: dict,
    scaffold_routes: dict,
    dossier_routes: list[str],
) -> list[str]:
    """Write every page declared in ``scaffold_routes["defaultRoutes"]``.

    The renderer for each route is selected by route id, not by
    path, so a future scaffold can keep the id ``"contact"`` while
    moving the path from ``/kontakt`` to ``/kontakta-oss`` without
    duplicating the renderer.

    Returns the list of paths written (one per default route) so
    the caller can mention them in the trace event without
    rebuilding the list.

    Raises ``SystemExit`` for scaffold route ids that have no
    registered renderer: silently skipping such routes would later
    surface as Quality Gate route-scan failures with no obvious
    owner. The error message names the route id so the operator
    can add a renderer or remove the route from the scaffold.
    """
    default_routes = scaffold_routes["defaultRoutes"]
    listing_route = _pick_listing_route(default_routes)
    contact_route = _pick_contact_route(default_routes)
    written: list[str] = []
    for route in default_routes:
        route_id = route["id"]
        path = route["path"]
        if route_id == "home":
            content = render_home(
                dossier,
                dossier_routes,
                listing_route=listing_route,
                contact_path=contact_route["path"],
            )
        elif route_id == "services":
            content = render_services(dossier, contact_path=contact_route["path"])
        elif route_id == "products":
            content = render_products(dossier, contact_path=contact_route["path"])
        elif route_id == "about":
            content = render_about(dossier)
        elif route_id == "contact":
            content = render_contact(dossier)
        else:
            raise SystemExit(
                "Builder failed: scaffold route id "
                f"{route_id!r} (path={path!r}) has no registered "
                "renderer in scripts/build_site.py. Add a "
                "render_<id>() function and register it in "
                "write_pages, or remove the route from the "
                "scaffold's routes.json."
            )
        write(route_to_page_path(target, path), content)
        written.append(path)
    write(
        target / "app" / "layout.tsx",
        render_layout(
            dossier,
            dossier_routes,
            scaffold_default_routes=default_routes,
            contact_path=contact_route["path"],
        ),
    )
    return written


def selected_required_dossiers(project_input: dict) -> list[str]:
    selected = project_input.get("selectedDossiers", {})
    required = selected.get("required", [])
    if not isinstance(required, list):
        return []
    return [item for item in required if isinstance(item, str) and item.strip()]


def resolve_dossier_dir(dossier_id: str) -> tuple[str, Path]:
    for dossier_class in ("soft", "hard"):
        path = DOSSIERS_DIR / dossier_class / dossier_id
        if path.exists():
            return dossier_class, path
    raise SystemExit(
        f"Selected dossier '{dossier_id}' not found under {DOSSIERS_DIR}/soft or /hard."
    )


def load_selected_dossier_manifests(project_input: dict) -> list[dict]:
    manifests: list[dict] = []
    for dossier_id in selected_required_dossiers(project_input):
        dossier_class, dossier_dir = resolve_dossier_dir(dossier_id)
        manifest_path = dossier_dir / "manifest.json"
        if not manifest_path.exists():
            raise SystemExit(f"Dossier '{dossier_id}' missing manifest.json at {manifest_path}")
        manifest = load_json(manifest_path)
        if manifest.get("id") != dossier_id:
            raise SystemExit(
                f"Dossier manifest id mismatch for {manifest_path}: expected '{dossier_id}', got '{manifest.get('id')}'"
            )
        if manifest.get("class") != dossier_class:
            raise SystemExit(
                f"Dossier manifest class mismatch for {manifest_path}: expected '{dossier_class}', got '{manifest.get('class')}'"
            )
        if manifest.get("enabled", True) is False:
            raise SystemExit(
                f"Selected dossier '{dossier_id}' is disabled in {manifest_path}."
            )
        manifests.append(
            {
                "id": dossier_id,
                "class": dossier_class,
                "dir": dossier_dir,
                "manifest": manifest,
            }
        )
    return manifests


def mount_dossier_components(target: Path, selected_dossiers: list[dict]) -> list[str]:
    """Copy each dossier's components into ``components/``.

    Filename collisions across dossiers are a hard build error: two dossiers
    cannot silently overwrite each other's components. Operators must rename or
    move the conflicting file before the build can proceed.

    Returns ``components/<filename>`` (path relative to the build target) for
    every copied file. The relative-path prefix is mandatory so downstream
    consumers - notably ``produce_codegen_artefakt`` in
    ``packages.generation.codegen`` - can record where the file actually
    lives. Returning bare filenames (which earlier Sprint 3A revisions did)
    made the codegen manifest claim files at the project root that were in
    fact under ``components/``.
    """
    copied: list[str] = []
    seen: dict[str, str] = {}
    components_target = target / "components"
    for info in selected_dossiers:
        components_dir = info["dir"] / "components"
        if not components_dir.exists():
            continue
        for source in sorted(components_dir.glob("*.tsx")):
            previous = seen.get(source.name)
            if previous is not None and previous != info["id"]:
                raise SystemExit(
                    "Builder failed: dossier component collision -> "
                    f"'{info['id']}' and '{previous}' both export "
                    f"components/{source.name}. Rename one of them or move it "
                    "into a dossier-specific subfolder before retrying."
                )
            seen[source.name] = info["id"]
            destination = components_target / source.name
            if destination.exists():
                raise SystemExit(
                    "Builder failed: dossier component would shadow an "
                    f"existing starter component at components/{source.name}. "
                    "Rename the dossier component before retrying."
                )
            write(destination, source.read_text(encoding="utf-8"))
            copied.append(f"components/{source.name}")
    return copied


def write_dossier_routes(target: Path, selected_dossiers: list[dict]) -> list[str]:
    routes: list[str] = []
    selected_ids = {info["id"] for info in selected_dossiers}

    if "interactive-game-loop" in selected_ids:
        write(
            target / "app" / "spel" / "page.tsx",
            (
                'import { PacmanGame } from "@/components/pacman-game";\n\n'
                "export default function Page() {\n"
                "  return (\n"
                '    <main className="mx-auto w-[min(100%,72rem)] px-4 py-10">\n'
                '      <h1 className="mb-3 text-3xl font-semibold">Pacman-spel</h1>\n'
                '      <p className="mb-6 text-sm text-[color:var(--muted)]">Tryck pilarna for att styra och R for att starta om.</p>\n'
                "      <PacmanGame />\n"
                "    </main>\n"
                "  );\n"
                "}\n"
            ),
        )
        routes.append("/spel")

    return routes


# ---------------------------------------------------------------------------
# Route guards
# ---------------------------------------------------------------------------


def required_routes(scaffold_routes: dict) -> list[str]:
    return [r["path"] for r in scaffold_routes["defaultRoutes"] if r.get("required")]


def all_default_routes(scaffold_routes: dict) -> list[str]:
    return [r["path"] for r in scaffold_routes["defaultRoutes"]]


def route_to_page_path(target: Path, route: str) -> Path:
    route = _validated_site_route_path(route)
    if route == "/":
        return target / "app" / "page.tsx"
    return target / "app" / route.lstrip("/") / "page.tsx"


# Detects "export default function|const|class ..." or "export { default }"
_DEFAULT_EXPORT_RE = re.compile(
    r"export\s+default\s+(?:async\s+)?(?:function|class|const|let|var|\w+)"
    r"|export\s*\{\s*default\b",
    flags=re.MULTILINE,
)


def assert_routes_present(target: Path, routes: list[str]) -> None:
    """Hard guard: every route must exist as a page.tsx with a default export.

    Checks both file existence AND that the file declares a default export so
    Next.js can mount the route. This catches the common error where a renderer
    template wrote an empty file or a file that was patched without exporting
    a component.
    """
    missing: list[str] = []
    no_export: list[str] = []
    for route in routes:
        path = route_to_page_path(target, route)
        if not path.exists():
            missing.append(f"{route} -> {path}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            missing.append(f"{route} -> unreadable ({exc})")
            continue
        if not _DEFAULT_EXPORT_RE.search(text):
            no_export.append(f"{route} -> {path} has no default export")

    problems: list[str] = []
    if missing:
        problems.append("missing route files:\n  " + "\n  ".join(missing))
    if no_export:
        problems.append("routes without default export:\n  " + "\n  ".join(no_export))
    if problems:
        raise SystemExit("Builder failed: " + "; ".join(problems))


# ---------------------------------------------------------------------------
# npm runner
# ---------------------------------------------------------------------------


NPM_INSTALL_TIMEOUT_SECONDS = 600
NPM_BUILD_TIMEOUT_SECONDS = 300


def _sanitized_npm_env() -> dict[str, str]:
    """Return a sanitized environment for child npm subprocesses.

    When ``apps/viewser`` runs ``next dev`` and spawns this builder via
    ``POST /api/sites``, the child inherits the viewser dev-server's
    environment. Next.js 16 enables Turbopack by default and exports
    ``TURBOPACK=1`` (plus ``__NEXT_*`` internals) to every descendant.
    Inside the generated site that env collides with the ``--webpack``
    flag in the starter scripts (added to side-step the Next 16
    ``/_global-error`` Turbopack prerender bug), and ``next build``
    aborts with "Multiple bundler flags set: TURBOPACK=1, --webpack".

    The viewser also propagates ``NODE_ENV=development`` to its
    children. That triggers Next.js' "non-standard NODE_ENV" warning
    inside ``next build`` and disables production optimisations.
    Stripping ``NODE_ENV`` lets the generated site's ``next build``
    pick the correct default ("production") for itself.
    """
    env = os.environ.copy()
    for key in list(env.keys()):
        if (
            key == "TURBOPACK"
            or key.startswith("TURBO_")
            or key == "NEXT_RUNTIME"
            or key.startswith("__NEXT_")
        ):
            env.pop(key, None)
    env.pop("NODE_ENV", None)
    return env


def run_npm(
    command: list[str],
    cwd: Path,
    *,
    timeout: float | None = None,
) -> tuple[bool, float, str]:
    """Run an npm command and return (ok, seconds, last_lines).

    Uses ``shutil.which`` to resolve ``npm`` (or ``npm.cmd`` on Windows) so the
    subprocess is invoked with ``shell=False``. ``shell=True`` with a list
    silently drops every argument after the first on POSIX, which made
    ``npm install`` collapse to a bare ``npm`` invocation in CI and exit 1
    after printing the help screen.

    A ``timeout`` (seconds) is required for long-running steps - without it
    a hung npm install/build would block the builder forever and leave the
    run directory half-written. ``subprocess.TimeoutExpired`` is caught so
    the caller still gets a deterministic ``(False, elapsed, message)``
    tuple instead of an uncaught exception.

    The subprocess environment is sanitized via ``_sanitized_npm_env`` to
    remove Next.js dev-server env vars (``TURBOPACK``, ``__NEXT_*``,
    ``NODE_ENV``) that would otherwise leak from the viewser dev server
    into the generated site's build and break it.
    """
    npm_path = shutil.which("npm")
    if npm_path is None:
        return False, 0.0, "npm executable not found on PATH"

    full_command = (
        [npm_path, *command[1:]] if command and command[0] == "npm" else [npm_path, *command]
    )
    child_env = _sanitized_npm_env()
    start = time.monotonic()
    try:
        proc = subprocess.run(
            full_command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout,
            env=child_env,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start
        # exc.stdout / exc.stderr are independently None | bytes | str. The
        # earlier implementation only built partial_text from one of them
        # and silently dropped the other when the type-check on stdout
        # mismatched - in particular stdout=None + stderr="<error log>"
        # would lose the only diagnostic the operator has. Decode each
        # stream individually and concatenate.
        partial_text = _coerce_subprocess_text(exc.stdout) + _coerce_subprocess_text(exc.stderr)
        last_lines = "\n".join(partial_text.splitlines()[-25:]) if partial_text else ""
        cmd_str = " ".join(command)
        message = f"timeout: '{cmd_str}' did not finish within {timeout:.0f}s"
        return False, elapsed, f"{message}\n{last_lines}".strip()
    elapsed = time.monotonic() - start
    output = (proc.stdout or "") + (proc.stderr or "")
    last_lines = "\n".join(output.splitlines()[-25:])
    return proc.returncode == 0, elapsed, last_lines


def _npm_step_result(name: str, ok: bool, seconds: float, log_excerpt: str) -> dict:
    step: dict[str, object] = {"name": name, "ok": ok, "seconds": round(seconds, 1)}
    if not ok and log_excerpt.strip():
        step["logExcerpt"] = log_excerpt.strip()
    return step


# ---------------------------------------------------------------------------
# Mock artefacts (no LLM yet)
# ---------------------------------------------------------------------------


def build_site_brief_mock(run_id: str, dossier: dict, scaffold: dict) -> dict:
    """Mock Site Brief derived from the dossier (no LLM).

    Returns the canonical Site Brief artefakt shape locked in
    ``governance/schemas/site-brief.schema.json`` (ADR 0013). Project Input
    fields are projected into the canonical fields rather than written
    alongside; the per-Project-Input data still lives in the source file
    under ``examples/`` for downstream phases that need the raw company /
    trust-signal payload.

    ``requestedCapabilities`` honours an explicit value from the Project
    Input, including an explicit empty list. Only when the field is absent
    does the builder fall back to the service-id stub.
    """
    requested = dossier.get("requestedCapabilities")
    if requested is None:
        requested = [svc["id"] for svc in dossier["services"]]
    company = dossier["company"]
    location = dossier.get("location") or {}
    tone_block = dossier.get("tone") or {}
    if isinstance(tone_block, dict):
        tone_words = [tone_block.get("primary")] + list(tone_block.get("secondary") or [])
        tone = [t for t in tone_words if t]
    else:
        tone = list(tone_block)
    location_parts = [
        location.get("city"),
        location.get("region"),
        location.get("country"),
    ]
    location_hint = ", ".join(p for p in location_parts if p) or None
    return {
        "runId": run_id,
        "language": dossier["language"],
        "rawPrompt": project_input_to_brief_prompt(dossier),
        "businessTypeGuess": company.get("businessType"),
        "pageCount": None,
        "tone": tone,
        "targetAudience": [],
        "requestedCapabilities": list(requested),
        "locationHint": location_hint,
        "conversionGoals": list(dossier.get("conversionGoals") or []),
        "servicesMentioned": [svc["id"] for svc in dossier.get("services", [])],
        "contentDepth": None,
        "notesForPlanner": (
            f"Mock brief for Project Input '{dossier.get('siteId')}' - planningModel "
            "wires in Sprint 2B."
        ),
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "briefSource": "mock-no-key",
        "briefError": None,
        "createdAt": utc_now().isoformat(timespec="seconds"),
        "scaffoldHint": scaffold["id"],
    }


def resolve_brief_model() -> str:
    """Resolve briefModel via the canonical helper in packages.generation.brief.

    Thin local wrapper kept only so the rest of this module can call it
    without importing through `packages.generation.brief.resolve_brief_model`
    everywhere.
    """
    from packages.generation.brief import resolve_brief_model as _resolve

    return _resolve()


def _join_values(values: list[Any]) -> str:
    return ", ".join(str(value) for value in values if value)


def project_input_to_brief_prompt(dossier: dict) -> str:
    """Create deterministic briefModel input from a Project Input.

    Builder examples already contain structured Project Input data, while
    briefModel expects a raw prompt. This adapter only restates existing facts
    so Phase 1 can run without inventing additional planning behavior.
    """
    company = dossier["company"]
    location = dossier["location"]
    tone = dossier.get("tone", {})
    selected = dossier.get("selectedDossiers", {})

    services = "\n".join(
        f"- {service['id']}: {service['label']} — {service['summary']}"
        for service in dossier.get("services", [])
    )
    trust = "\n".join(f"- {item}" for item in dossier.get("trustSignals", []))

    return (
        "Build a business website from this Project Input.\n\n"
        f"Company: {company.get('name')}\n"
        f"Business type: {company.get('businessType')}\n"
        f"Tagline: {company.get('tagline')}\n"
        f"Story: {company.get('story')}\n"
        f"Location: {location.get('city')}, {location.get('region')}, {location.get('country')}\n"
        f"Service areas: {_join_values(location.get('serviceAreas', []))}\n"
        f"Language: {dossier.get('language')}\n"
        f"Tone primary: {tone.get('primary')}\n"
        f"Tone secondary: {_join_values(tone.get('secondary', []))}\n"
        f"Tone avoid: {_join_values(tone.get('avoid', []))}\n"
        f"Conversion goals: {_join_values(dossier.get('conversionGoals', []))}\n"
        f"Requested capabilities: {_join_values(dossier.get('requestedCapabilities', []))}\n"
        f"Required dossiers: {_join_values(selected.get('required', []))}\n\n"
        "Services:\n"
        f"{services}\n\n"
        "Trust signals:\n"
        f"{trust}\n"
    )


def _mock_brief_after_llm_failure(
    run_id: str,
    dossier: dict,
    scaffold: dict,
    *,
    error: str,
    attempted_model: str | None,
) -> dict:
    brief = build_site_brief_mock(run_id, dossier, scaffold)
    brief.update(
        {
            "briefSource": "mock-llm-error",
            "briefError": error,
            "attemptedModel": attempted_model,
        }
    )
    return brief


def build_site_brief(run_id: str, dossier: dict, scaffold: dict) -> dict:
    """Build Site Brief with briefModel when available, otherwise mock fallback."""
    from packages.generation.brief import has_openai_api_key

    if not has_openai_api_key():
        print("No OPENAI_API_KEY - using mock Site Brief")
        return build_site_brief_mock(run_id, dossier, scaffold)

    model: str | None = None
    try:
        model = resolve_brief_model()
        prompt = project_input_to_brief_prompt(dossier)

        from packages.generation.brief import extract_site_brief, site_brief_to_artifact

        print(f"Calling briefModel ({model}) for Site Brief")
        result = extract_site_brief(
            prompt,
            model=model,
            language_hint=dossier.get("language"),
        )
        if result.source != "real":
            error = result.error or f"briefModel returned fallback source {result.source}"
            print(
                f"Warning: briefModel failed - using mock Site Brief fallback ({error})",
                file=sys.stderr,
            )
            return _mock_brief_after_llm_failure(
                run_id,
                dossier,
                scaffold,
                error=error,
                attempted_model=model,
            )

        brief = site_brief_to_artifact(result, run_id=run_id, model=model)
        brief["scaffoldHint"] = scaffold["id"]
        return brief
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        print(
            f"Warning: briefModel path failed - using mock Site Brief fallback ({error})",
            file=sys.stderr,
        )
        return _mock_brief_after_llm_failure(
            run_id,
            dossier,
            scaffold,
            error=error,
            attempted_model=model,
        )


def build_plan_artefakts(
    run_id: str,
    dossier: dict,
    scaffold: dict,
    variant: dict,
    site_brief: dict,
    prompt_meta: dict[str, Any] | None = None,
) -> tuple[dict, dict]:
    """Delegate Phase 2 Plan to the shared produce_site_plan helper.

    The builder pins scaffoldId/variantId from the Project Input (the
    operator already made that decision when authoring the Project
    Input), so this call always returns ``planSource = 'pinned'`` and
    does not touch planningModel. The capability filter still runs so
    requestedCapabilities without an implemented Dossier surface as
    ``selectedDossiers.rejected[]`` instead of being silently dropped.

    Both this builder and ``scripts/dev_generate.py`` go through the same
    helper. That is what closes ``docs/known-issues.md`` B19.
    """
    from packages.generation.artifacts import validate_site_plan
    from packages.generation.planning import (
        merge_operator_selected_with_helper,
        produce_site_plan,
    )

    pinned = {
        "scaffoldId": scaffold["id"],
        "variantId": variant["id"],
    }
    pinned_starter = dossier.get("starterId")
    if isinstance(pinned_starter, str) and pinned_starter:
        pinned["starterId"] = pinned_starter

    result = produce_site_plan(
        site_brief,
        run_id=run_id,
        pinned=pinned,
        engine_mode=_prompt_meta_mode(prompt_meta),
        project_id=_prompt_meta_project_id(prompt_meta),
        verification_policy="build-must-pass",
        preview_runtime="local",
    )

    site_plan = dict(result.site_plan)
    # Merge operator-selected dossiers with helper output so capability
    # gaps (selectedDossiers.rejected[]) are never silently dropped.
    operator_selected = dossier.get("selectedDossiers")
    site_plan["selectedDossiers"] = merge_operator_selected_with_helper(
        operator_selected, result.site_plan["selectedDossiers"]
    )
    # Revalidate after merge: helper validated before this function mutates
    # selectedDossiers, but the merged payload is a new object.
    validate_site_plan(site_plan)

    return site_plan, dict(result.generation_package)


# ---------------------------------------------------------------------------
# Engine Run artefakts
# ---------------------------------------------------------------------------


def write_phase1_understand(
    run_dir: Path,
    trace: Trace,
    dossier_path: Path,
    dossier: dict,
    scaffold: dict,
    prompt_meta: dict[str, Any] | None = None,
) -> dict:
    """Phase 1 understand: input.json + site-brief.json."""
    trace.event("understand", "phase.started", "started", "Phase 1 understand starts")

    # Dossier path may live outside the repo (operator pointed at an
    # ad-hoc fixture in $TEMP). _to_repo_relative falls back to the
    # absolute POSIX form so this never raises ValueError mid-build.
    rel_dossier = _to_repo_relative(dossier_path)
    input_data = {
        "runId": trace.run_id,
        "mode": _prompt_meta_mode(prompt_meta),
        "rawPrompt": _prompt_meta_raw_prompt(prompt_meta),
        "dossierPath": rel_dossier,
        "detectedLanguage": dossier["language"],
        "timestamp": utc_now().isoformat(),
    }
    project_id = _prompt_meta_project_id(prompt_meta)
    version = _prompt_meta_version(prompt_meta)
    if project_id is not None:
        input_data["projectId"] = project_id
    if version is not None:
        input_data["version"] = version
    if prompt_meta:
        for key in ("originalPrompt", "followUpPrompt", "previousVersion"):
            value = prompt_meta.get(key)
            if value is not None:
                input_data[key] = value
    write_json(run_dir / "input.json", input_data)
    trace.event(
        "understand",
        "input.written",
        "done",
        "Captured dossier path and runId",
        payload_path="input.json",
    )

    brief = build_site_brief(trace.run_id, dossier, scaffold)
    from packages.generation.artifacts import validate_site_brief

    validate_site_brief(brief)
    write_json(run_dir / "site-brief.json", brief)
    brief_source = brief.get("briefSource", "unknown")
    trace.event(
        "understand",
        "site_brief.written",
        "done",
        f"Site Brief written (briefSource={brief_source})",
        payload_path="site-brief.json",
    )
    trace.event("understand", "phase.completed", "done", "Phase 1 understand done")
    return brief


def write_phase2_plan(
    run_dir: Path,
    trace: Trace,
    dossier: dict,
    scaffold: dict,
    variant: dict,
    site_brief: dict,
    prompt_meta: dict[str, Any] | None = None,
) -> tuple[dict, dict]:
    """Phase 2 plan: site-plan.json + generation-package.json.

    Schema validation runs inside ``produce_site_plan``; the artefakts
    arriving here are already validated. Writing them is the only thing
    left for the builder to do.
    """
    trace.event("plan", "phase.started", "started", "Phase 2 plan starts")

    site_plan, package = build_plan_artefakts(
        trace.run_id,
        dossier,
        scaffold,
        variant,
        site_brief,
        prompt_meta,
    )

    write_json(run_dir / "site-plan.json", site_plan)
    trace.event(
        "plan",
        "site_plan.written",
        "done",
        f"Site Plan picked scaffold={scaffold['id']} variant={variant['id']} "
        f"starter={site_plan['starterId']} planSource={site_plan['planSource']}",
        payload_path="site-plan.json",
    )

    write_json(run_dir / "generation-package.json", package)
    trace.event(
        "plan",
        "generation_package.written",
        "done",
        "Generation Package composed via produce_site_plan helper",
        payload_path="generation-package.json",
    )
    trace.event("plan", "phase.completed", "done", "Phase 2 plan done")
    return site_plan, package


def snapshot_generated_files(target_dir: Path, run_dir: Path) -> Path:
    """Snapshot generated files into ``data/runs/<runId>/generated-files/``.

    The dev preview at ``.generated/<siteId>/`` keeps mutating across runs
    (regenerations, npm install, build cache). The Engine Run contract in
    ``engine-run.v1.json`` says the canonical Generated Files belong under
    the run directory. We snapshot the source-relevant files only and skip
    ``node_modules`` and build output for size reasons.
    """
    snap_dir = run_dir / "generated-files"
    if snap_dir.exists():
        shutil.rmtree(snap_dir)
    shutil.copytree(target_dir, snap_dir, ignore=_ignore_combined)
    return snap_dir


def run_phase3_quality_and_repair(
    run_dir: Path,
    target: Path,
    routes_required: list[str],
    npm_steps: list[dict],
    overall_status: str,
    do_typecheck: bool,
) -> tuple[dict, dict]:
    """Thin wiring around packages/generation/repair (which itself
    orchestrates quality_gate + repair).

    Sprint 3B routes the full sandwich loop through
    ``execute_phase3_quality_and_repair`` so this function stays at
    fewer than 60 lines and contains no Quality Gate or Repair logic.
    All product logic lives in the packages per ADR 0015 + 0016 +
    repo-boundaries.v1.json. ``quality-result.json`` records the FINAL
    (post-repair) Quality Gate output; pre-repair status is preserved
    on ``repair-result.json:qualityStatusBefore``.
    """
    from packages.generation.repair import execute_phase3_quality_and_repair

    final_quality, repair_result = execute_phase3_quality_and_repair(
        target_dir=target,
        required_routes=routes_required,
        npm_steps=npm_steps,
        build_status=overall_status,
        do_typecheck=do_typecheck,
    )

    quality_payload = final_quality.model_dump()
    # Schema-lock per Sprint 3C-lite (ADR 0017). Validation is strict:
    # if the QualityResult shape drifts from quality-result.schema.json
    # the build fails before write_json so a malformed artefakt never
    # reaches data/runs/.
    from packages.generation.artifacts import (
        validate_quality_result,
        validate_repair_result,
    )

    validate_quality_result(quality_payload)
    write_json(run_dir / "quality-result.json", quality_payload)

    repair_payload = repair_result.model_dump()
    validate_repair_result(repair_payload)
    write_json(run_dir / "repair-result.json", repair_payload)

    return quality_payload, repair_payload


def empty_model_usage(source: str = "mock-no-key") -> dict:
    """Backwards-compatible wrapper around the shared
    ``packages.generation.artifacts.compose_model_usage`` helper.

    Sprint 3C-lite extracted the composition logic into
    ``packages/generation/artifacts/model_usage.py`` so
    ``scripts/dev_generate.py`` can call it without importing a
    private helper across script boundaries (Sprint 3C-lite audit
    fynd 1). This wrapper preserves the historical name + signature
    for tests and any operator script that imported the symbol.
    """
    from packages.generation.artifacts import compose_model_usage

    return compose_model_usage(source, codegen_summary=None)


def write_build_result(
    run_dir: Path,
    trace: Trace,
    dossier: dict,
    site_brief: dict,
    scaffold: dict,
    variant: dict,
    starter_id: str,
    routes: list[str],
    npm_steps: list[dict],
    overall_status: str,
    target_dir: Path,
    duration_ms: int,
    codegen_summary: dict | None = None,
    prompt_meta: dict[str, Any] | None = None,
) -> dict:
    """Write build-result.json. ``generatedFilesDir`` points at the canonical
    snapshot under the run directory, not at the dev preview, so downstream
    consumers (Backoffice, eval batch) can trust it across regenerations.

    ``starter_id`` mirrors what ``site-plan.json`` chose - the builder no
    longer hardcodes ``marketing-base`` here so the build result reflects
    the planner's pick (Sprint 2B).

    ``codegen_summary`` carries the codegenModel v1 metadata (source,
    modelUsed, fileCount, rationale) that ADR 0015 reserves a slot for in
    build-result.json. The full ``files`` list is intentionally omitted -
    the manifest can grow large and the snapshot under generatedFilesDir
    is already the authoritative on-disk record.
    """
    from packages.generation.artifacts import compose_model_usage

    snap_dir = run_dir / "generated-files"
    rel_snapshot = _to_repo_relative(snap_dir)
    rel_preview = _to_repo_relative(target_dir)
    model_used = site_brief.get("modelUsed", "mock")
    brief_source = site_brief.get("briefSource", "mock-no-key")
    engine_mode = _prompt_meta_mode(prompt_meta)
    result = {
        "siteId": dossier["siteId"],
        "starterId": starter_id,
        "scaffoldId": scaffold["id"],
        "scaffoldVersion": scaffold["version"],
        "variantId": variant["id"],
        "language": dossier["language"],
        "engineMode": engine_mode,
        "buildSource": "scripts/build_site.py",
        "modelUsed": model_used,
        "briefSource": brief_source,
        "routes": routes,
        "generatedFilesDir": rel_snapshot,
        "devPreviewDir": rel_preview,
        "npmSteps": npm_steps,
        "modelUsage": compose_model_usage(brief_source, codegen_summary),
        "finalize": {
            "snapshotDir": rel_snapshot,
            "snapshotedAt": utc_now().isoformat(),
        },
        "status": overall_status,
        "runDurationMs": duration_ms,
    }
    project_id = _prompt_meta_project_id(prompt_meta)
    version = _prompt_meta_version(prompt_meta)
    if project_id is not None:
        result["projectId"] = project_id
    if version is not None:
        result["version"] = version
    if prompt_meta:
        prompt_summary: dict[str, Any] = {}
        for key in ("originalPrompt", "followUpPrompt", "previousVersion"):
            value = prompt_meta.get(key)
            if value is not None:
                prompt_summary[key] = value
        if prompt_summary:
            result["prompt"] = prompt_summary
    if codegen_summary is not None:
        result["codegen"] = codegen_summary
    write_json(run_dir / "build-result.json", result)
    trace.event(
        "build",
        "build.result.written",
        "done",
        f"Build result status={overall_status}",
        payload_path="build-result.json",
    )
    return result


# ---------------------------------------------------------------------------
# Main build orchestration
# ---------------------------------------------------------------------------


def build(
    dossier_path: Path,
    do_build: bool = True,
    runs_dir: Path | None = None,
    generated_dir: str | Path | None = None,
    auto_prune: bool = True,
) -> tuple[Path, Path]:
    """Generate a site and Engine Run artefakts. Returns (target, run_dir).

    ``runs_dir`` defaults to ``RUNS_DIR`` (``data/runs``); pass an isolated
    path (``tmp_path`` in tests) to keep the canonical history clean.
    ``generated_dir`` overrides where the dev-preview site is emitted.
    ``auto_prune`` runs the opt-in retention sweep from
    ``packages.generation.maintenance.auto_prune_all`` before Phase 0 so
    ``data/runs/``, ``data/prompt-inputs/`` and ``.generated/`` stay under
    the caps configured in ``.env``. Disabled automatically when ``runs_dir``
    is overridden (tests with ``tmp_path``).
    """
    started = time.monotonic()

    if auto_prune and runs_dir is None:
        from packages.generation.maintenance import auto_prune_all

        auto_prune_all(generated_dir=Path(generated_dir) if generated_dir else None)

    dossier = load_json(dossier_path)
    site_id = dossier["siteId"]
    scaffold_id = dossier["scaffoldId"]
    variant_id = dossier["variantId"]
    prompt_meta = load_prompt_input_meta(dossier_path, dossier)

    scaffold_dir = SCAFFOLDS_DIR / scaffold_id
    scaffold = load_json(scaffold_dir / "scaffold.json")
    scaffold_routes = load_json(scaffold_dir / "routes.json")
    variant = load_json(scaffold_dir / "variants" / f"{variant_id}.json")

    sections_path = scaffold_dir / "sections.json"
    if sections_path.exists():
        from packages.generation.artifacts import validate_sections

        validate_sections(load_json(sections_path))

    runs_root = runs_dir if runs_dir is not None else RUNS_DIR
    run_id = make_run_id(site_id)
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace(run_id, run_dir)

    print(f"runId: {run_id}")

    # Phase 1: understand
    site_brief = write_phase1_understand(
        run_dir,
        trace,
        dossier_path,
        dossier,
        scaffold,
        prompt_meta,
    )

    # Phase 2: plan (delegates to packages.generation.planning.produce_site_plan)
    site_plan, generation_package = write_phase2_plan(
        run_dir,
        trace,
        dossier,
        scaffold,
        variant,
        site_brief,
        prompt_meta,
    )

    generated_root = resolve_generated_dir(generated_dir)

    # Phase 3: build. The Starter to copy is whatever the plan picked - we
    # used to hardcode 'marketing-base' here, which made the planSource a
    # decoration rather than authoritative. Reading site_plan["starterId"]
    # also future-proofs the builder for the day commerce-base is harmonised.
    target = generated_root / site_id
    trace.event("build", "phase.started", "started", "Phase 3 build starts")

    starter_id = site_plan["starterId"]
    print(f"Copying starter {starter_id} -> {target}")
    copy_starter(starter_id, target)

    print("Copying operator uploads (logo, hero, gallery)")
    uploads_copied = copy_operator_uploads(site_id, target, dossier)
    print(f"  -> {uploads_copied} asset(s) copied to public/uploads/")

    print("Patching package.json")
    patch_package_json(target, dossier)

    print("Injecting variant tokens into app/globals.css")
    patch_globals_css(target, variant)

    selected_dossiers = load_selected_dossier_manifests(dossier)
    copied_components = mount_dossier_components(target, selected_dossiers)
    dossier_routes = write_dossier_routes(target, selected_dossiers)

    # Announce BEFORE the write so the operator can see which step
    # is in flight if write_pages raises (e.g. SystemExit for an
    # unknown scaffold route id). Bugbot caught this on PR #19: the
    # original post-write print left the operator with no
    # breadcrumbs when write_pages aborted mid-loop. We derive the
    # path list from scaffold_routes (already on hand) instead of
    # waiting for write_pages' return value, then verify the
    # return matches so a silent dispatch mismatch cannot drift
    # the announcement.
    routes_to_write = all_default_routes(scaffold_routes)
    print("Writing pages: " + ", ".join(routes_to_write) + " and layout")
    paths_written = write_pages(target, dossier, scaffold_routes, dossier_routes)
    if paths_written != routes_to_write:
        raise SystemExit(
            "Builder failed: write_pages returned "
            f"{paths_written!r} but scaffold declared "
            f"{routes_to_write!r}. The dispatch table and the "
            "scaffold registry have drifted; reconcile them "
            "before retrying."
        )

    routes_all = all_default_routes(scaffold_routes)
    routes_all_with_dossiers = sorted(set(routes_all + dossier_routes))
    # Sprint 3A note: the previous hard guard ``assert_routes_present`` ran
    # here and crashed the build via SystemExit on missing routes or absent
    # default exports. That made Quality Gate route-scan dead code in the
    # failure path - we always crashed before writing quality-result.json.
    # Quality Gate route-scan now owns the route check; failures flip
    # overall_status to "failed" and write structured findings to
    # quality-result.json. assert_routes_present remains as a utility
    # function (locked by tests/test_builder_hardening.py B8/B9 regression
    # tests) but no longer interrupts the canonical build flow.
    trace.event(
        "build",
        "files.written",
        "done",
        f"Wrote {len(routes_all_with_dossiers)} routes and copied {len(copied_components)} dossier components",
    )

    npm_steps: list[dict] = []
    overall_status = "ok"

    if do_build:
        if not (target / "node_modules").exists():
            print(f"Running npm install (timeout {NPM_INSTALL_TIMEOUT_SECONDS}s)...")
            ok, secs, last = run_npm(
                ["npm", "install"],
                target,
                timeout=NPM_INSTALL_TIMEOUT_SECONDS,
            )
            npm_steps.append(_npm_step_result("npm install", ok, secs, last))
            trace.event(
                "build",
                "npm.install",
                "done" if ok else "failed",
                f"npm install ok={ok} seconds={secs:.1f}",
            )
            if not ok:
                overall_status = "failed"
                print(last, file=sys.stderr)

        if overall_status == "ok":
            print(f"Running npm run build (timeout {NPM_BUILD_TIMEOUT_SECONDS}s)...")
            ok, secs, last = run_npm(
                ["npm", "run", "build"],
                target,
                timeout=NPM_BUILD_TIMEOUT_SECONDS,
            )
            npm_steps.append(_npm_step_result("npm run build", ok, secs, last))
            trace.event(
                "build",
                "npm.build",
                "done" if ok else "failed",
                f"next build ok={ok} seconds={secs:.1f}",
            )
            if not ok:
                overall_status = "failed"
                print(last, file=sys.stderr)
    else:
        overall_status = "skipped"
        trace.event(
            "build",
            "build.skipped",
            "degraded",
            "Build skipped via --skip-build",
        )

    # codegenModel v1 manifest (deterministic in Sprint 3A; LLM in 3B).
    from packages.generation.codegen import produce_codegen_artefakt

    codegen_result = produce_codegen_artefakt(
        generation_package,
        routes_written=routes_all_with_dossiers,
        dossier_components=copied_components,
        starter_id=starter_id,
    )
    trace.event(
        "build",
        "codegen.manifest.emitted",
        "done",
        f"codegenModel v1 manifest: {len(codegen_result.files)} files "
        f"(source={codegen_result.source})",
    )

    # Quality Gate + Repair Pipeline (real checks; ADR 0015 + 0016).
    # Repair may mutate target/, so we snapshot AFTER this call so
    # data/runs/<runId>/generated-files/ reflects the post-repair state
    # (Sprint 3B v1.1 fix - previously snapshotted pre-repair which
    # made the canonical artefact stale when a fix succeeded).
    do_typecheck = overall_status == "ok"
    quality_payload, repair_payload = run_phase3_quality_and_repair(
        run_dir,
        target,
        routes_all_with_dossiers,
        npm_steps,
        overall_status,
        do_typecheck,
    )
    trace.event(
        "build",
        "quality_result.written",
        "done",
        f"Quality Gate status={quality_payload['status']} "
        f"({len(quality_payload['checks'])} checks)",
        payload_path="quality-result.json",
    )
    trace.event(
        "build",
        "repair_result.written",
        "done",
        f"Repair Pipeline status={repair_payload['status']} "
        f"(remainingErrors={len(repair_payload['remainingErrors'])})",
        payload_path="repair-result.json",
    )

    # Snapshot generated files into the canonical run directory.
    # Must run AFTER Quality Gate + Repair so the snapshot captures
    # any mechanical fixes the Repair Pipeline applied to target/.
    print("Snapshotting generated files into run directory")
    snapshot_generated_files(target, run_dir)
    trace.event(
        "build",
        "generated_files.snapshotted",
        "done",
        "Snapshotted generated files into data/runs/<runId>/generated-files/",
        payload_path="generated-files/",
    )

    # Quality Gate status propagation (ADR 0015):
    #
    # - "failed" (typecheck or build-status failed) -> overall_status="failed",
    #   raise SystemExit(1) below. These are blocking checks.
    # - "degraded" (route-scan or policy-compliance failed but blocking
    #   checks ok/skipped) -> overall_status="degraded", exit code 0. The
    #   build is shippable but operator should investigate. Repair Pipeline
    #   already carries the structured remainingErrors[] for triage.
    # - "ok" -> no change.
    if quality_payload["status"] == "failed" and overall_status == "ok":
        overall_status = "failed"
    elif quality_payload["status"] == "degraded" and overall_status == "ok":
        overall_status = "degraded"

    codegen_summary = {
        "source": codegen_result.source,
        "modelUsed": codegen_result.modelUsed,
        "fileCount": len(codegen_result.files),
        "rationale": codegen_result.rationale,
        "riskNotes": list(codegen_result.riskNotes),
        "usage": codegen_result.usage.model_dump(),
    }
    if codegen_result.error is not None:
        codegen_summary["error"] = codegen_result.error

    duration_ms = int((time.monotonic() - started) * 1000)
    write_build_result(
        run_dir,
        trace,
        dossier,
        site_brief,
        scaffold,
        variant,
        starter_id,
        routes_all_with_dossiers,
        npm_steps,
        overall_status,
        target,
        duration_ms,
        codegen_summary=codegen_summary,
        prompt_meta=prompt_meta,
    )

    if overall_status == "failed":
        trace.event("build", "phase.completed", "failed", "Phase 3 build failed")
        raise SystemExit(1)

    trace.event("build", "phase.completed", "done", "Phase 3 build done")
    print(f"Generated site at {target}")
    print(f"Run artifacts at {run_dir}")
    return target, run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a generated site from a Project Input.")
    parser.add_argument(
        "--dossier",
        required=True,
        help="Path to the Project Input JSON file (examples/<siteId>.project-input.json).",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip npm install + npm run build (file generation only).",
    )
    parser.add_argument(
        "--runs-dir",
        default=None,
        help="Override canonical data/runs/ path (used by tests to isolate artefakts).",
    )
    parser.add_argument(
        "--generated-dir",
        default=None,
        help=(
            "Override dev-preview output root for generated sites. "
            "Defaults to SAJTBYGGAREN_GENERATED_DIR or "
            "the sibling folder ../sajtbyggaren-output/.generated."
        ),
    )
    args = parser.parse_args()

    dossier_path = Path(args.dossier).resolve()
    if not dossier_path.exists():
        print(f"Dossier not found: {dossier_path}", file=sys.stderr)
        return 1

    runs_dir = Path(args.runs_dir).resolve() if args.runs_dir else None
    build(
        dossier_path,
        do_build=not args.skip_build,
        runs_dir=runs_dir,
        generated_dir=args.generated_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
