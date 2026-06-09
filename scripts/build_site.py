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
import importlib
import json
import os
import re
import shutil
import sys
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_subprocess_exports = importlib.import_module("packages.generation.build.subprocesses")
_renderer_exports = importlib.import_module("packages.generation.build.renderers")
_static_asset_exports = importlib.import_module("packages.generation.build.static_assets")
_dispatcher_exports = importlib.import_module("packages.generation.build.dispatcher")

NPM_BUILD_TIMEOUT_SECONDS = _subprocess_exports.NPM_BUILD_TIMEOUT_SECONDS
NPM_INSTALL_TIMEOUT_SECONDS = _subprocess_exports.NPM_INSTALL_TIMEOUT_SECONDS
_coerce_subprocess_text = _subprocess_exports._coerce_subprocess_text
_npm_step_result = _subprocess_exports._npm_step_result
_sanitized_npm_env = _subprocess_exports._sanitized_npm_env
run_npm = _subprocess_exports.run_npm
subprocess = _subprocess_exports.subprocess

# Eager re-exports of the most commonly imported names — kept so IDE/static
# analysis can see them. Everything else (including the 30+ section renderers
# Christopher added in PR #105 + the Phase 3 operator-pin helpers from PR
# #108) is re-exported lazily via ``__getattr__`` further down, so callers
# can still do ``from scripts.build_site import render_section_hero`` after
# the B146 port without us listing every renderer name twice.

# Page renderers + write_pages (from renderers module).
_WIZARD_ROUTE_RENDERERS = _renderer_exports._WIZARD_ROUTE_RENDERERS
_hero_style_for = _renderer_exports._hero_style_for
render_about = _renderer_exports.render_about
render_booking = _renderer_exports.render_booking
render_contact = _renderer_exports.render_contact
render_faq = _renderer_exports.render_faq
render_gallery = _renderer_exports.render_gallery
render_home = _renderer_exports.render_home
render_layout = _renderer_exports.render_layout
render_map = _renderer_exports.render_map
render_menu = _renderer_exports.render_menu
render_portfolio = _renderer_exports.render_portfolio
render_pricing = _renderer_exports.render_pricing
render_products = _renderer_exports.render_products
render_services = _renderer_exports.render_services
render_team = _renderer_exports.render_team
render_treatments = _renderer_exports.render_treatments
render_expertise = _renderer_exports.render_expertise
render_work = _renderer_exports.render_work
write_pages = _renderer_exports.write_pages

# Static asset renderers.
_render_structured_data_jsonld = _static_asset_exports._render_structured_data_jsonld
render_global_error = _static_asset_exports.render_global_error
render_not_found = _static_asset_exports.render_not_found
render_og_fallback_svg = _static_asset_exports.render_og_fallback_svg
render_robots_txt = _static_asset_exports.render_robots_txt
render_sitemap_xml = _static_asset_exports.render_sitemap_xml

# Dispatcher (B146 port, 2026-05-25): section-id registry, scaffold
# sections cache, treatment-resolution helpers and the generic route
# composer. These are re-exported so tests and external callers can keep
# using the ``scripts.build_site`` spelling (e.g.
# ``bs._SECTION_RENDERERS``, ``bs.render_route_generic``) without
# learning the new layout. ADR 0032 covers the Phase 3 operator-pin
# tier; ADR pointers in the dispatcher module itself explain the
# resolve-order math.
_SECTION_RENDERERS = _dispatcher_exports._SECTION_RENDERERS
_SECTION_TREATMENTS_BY_VARIANT = _dispatcher_exports._SECTION_TREATMENTS_BY_VARIANT
_SCAFFOLD_SECTIONS_CACHE = _dispatcher_exports._SCAFFOLD_SECTIONS_CACHE
_call_section_renderer = _dispatcher_exports._call_section_renderer
_load_scaffold_sections = _dispatcher_exports._load_scaffold_sections
_operator_pin_for_section = _dispatcher_exports._operator_pin_for_section
_section_renderer_kwargs = _dispatcher_exports._section_renderer_kwargs
_treatment_for_section = _dispatcher_exports._treatment_for_section
render_route_generic = _dispatcher_exports.render_route_generic

# Color/token system (slice 1, behavior-preserving extraction per
# docs/refactor/megafiles-plan.md Del 2): the color scale + typography + motion
# helpers and ``variant_css`` now live in
# ``packages.generation.build.tokens``. They are re-exported here via attribute
# binds (same pattern as the renderer re-exports above) so every existing
# spelling keeps resolving: the local ``patch_globals_css``/
# ``patch_package_json`` below call them as bare names, tests do
# ``from scripts.build_site import variant_css``, and the renderers/
# static-assets lazy shim resolves ``getattr(build_site, "_normalise_hex_color")``
# / ``"_normalize_tone_key"``. ``patch_globals_css``/``patch_package_json`` stay
# defined locally (they use write/load_json, which move in the io-helpers slice).
_tokens_exports = importlib.import_module("packages.generation.build.tokens")
_HEX_COLOR_RE = _tokens_exports._HEX_COLOR_RE
_TONE_COLOR_TOKENS = _tokens_exports._TONE_COLOR_TOKENS
_BRAND_SCALE_LIGHTNESS = _tokens_exports._BRAND_SCALE_LIGHTNESS
_BRAND_SCALE_MAX_SATURATION = _tokens_exports._BRAND_SCALE_MAX_SATURATION
_VARIANT_TYPOGRAPHY = _tokens_exports._VARIANT_TYPOGRAPHY
_TYPOGRAPHY_FALLBACK = _tokens_exports._TYPOGRAPHY_FALLBACK
_TONE_KEY_ALIASES = _tokens_exports._TONE_KEY_ALIASES
_TONE_TYPOGRAPHY = _tokens_exports._TONE_TYPOGRAPHY
_normalise_hex_color = _tokens_exports._normalise_hex_color
_foreground_for_background = _tokens_exports._foreground_for_background
_hex_to_hsl = _tokens_exports._hex_to_hsl
_hsl_to_hex = _tokens_exports._hsl_to_hex
_build_color_scale = _tokens_exports._build_color_scale
_token_overrides_from_project_input = _tokens_exports._token_overrides_from_project_input
_typography_for_variant = _tokens_exports._typography_for_variant
_normalize_tone_key = _tokens_exports._normalize_tone_key
_typography_overlay_for_tone = _tokens_exports._typography_overlay_for_tone
_motion_css_block = _tokens_exports._motion_css_block
variant_css = _tokens_exports.variant_css

# Asset/media pipeline (slice 2, behavior-preserving extraction per
# docs/refactor/megafiles-plan.md Del 2): the PURE asset logic (AssetRef
# validation + iteration, favicon/og conversion, extension/stem derivation,
# SVG detection) now lives in ``packages.generation.build.assets``. It is
# re-exported here via attribute binds (same pattern as the renderer/token
# re-exports above) so every existing spelling keeps resolving: the local
# io-writing copy helpers below call these as bare names, tests do
# ``from scripts.build_site import iter_asset_refs`` / ``_is_allowed_asset_source_url``,
# and the renderer lazy shim resolves ``getattr(build_site, "resolve_media_asset")``.
# The io-writing functions that read the test-monkeypatched module globals
# ``UPLOADS_ROOT_DIR`` / ``_REMOTE_ASSET_MAX_BYTES``
# (``_fetch_asset_bytes_from_url``, ``_operator_asset_candidate_dirs``,
# ``_resolve_operator_asset_source``, ``_copy_product_images``,
# ``copy_operator_uploads``, ``copy_mood_assets``) stay defined locally below:
# moving them would need a package->scripts shim (forbidden) or test edits
# (forbidden), so they keep the cleanest zero-coupling seam.
_assets_exports = importlib.import_module("packages.generation.build.assets")
_ALLOWED_ASSET_FETCH_HOSTS = _assets_exports._ALLOWED_ASSET_FETCH_HOSTS
_FAVICON_ICO_SIZES = _assets_exports._FAVICON_ICO_SIZES
_OG_IMAGE_SIZE = _assets_exports._OG_IMAGE_SIZE
_is_valid_asset_ref = _assets_exports._is_valid_asset_ref
resolve_media_asset = _assets_exports.resolve_media_asset
iter_asset_refs = _assets_exports.iter_asset_refs
_iter_public_upload_refs = _assets_exports._iter_public_upload_refs
_iter_mood_refs = _assets_exports._iter_mood_refs
_is_allowed_asset_source_url = _assets_exports._is_allowed_asset_source_url
_asset_requires_derived_public_output = _assets_exports._asset_requires_derived_public_output
_is_svg_favicon = _assets_exports._is_svg_favicon
_convert_favicon_to_ico = _assets_exports._convert_favicon_to_ico
_convert_og_image_to_1200x630_png = _assets_exports._convert_og_image_to_1200x630_png
_write_derived_media_asset = _assets_exports._write_derived_media_asset
_operator_asset_variant_candidates = _assets_exports._operator_asset_variant_candidates
_private_mood_asset_extension = _assets_exports._private_mood_asset_extension
_private_mood_asset_stem = _assets_exports._private_mood_asset_stem
_public_product_asset_extension = _assets_exports._public_product_asset_extension
_public_product_asset_stem = _assets_exports._public_product_asset_stem

# Prompt-input-meta readers (slice 3, behavior-preserving extraction per
# docs/refactor/megafiles-plan.md Del 2): the prompt-meta reader family + the
# prompt-input filename patterns and the placeholder-contact field set now live
# in ``packages.generation.build.prompt_meta``. They are re-exported here via
# eager attribute binds (same pattern as the tokens block above) so every
# existing spelling keeps resolving: build(), build_targeted_version(),
# build_plan_artefakts(), write_phase1/2 and _detect_followup_applied_visible_effect
# call them as bare names, and tests do ``from scripts.build_site import
# load_prompt_input_meta``. The readers that need io-helpers (``load_json``/
# ``_to_repo_relative``, which move in a later io-helpers slice) do a lazy
# ``from scripts.build_site import ...`` inside their bodies, so this eager import
# stays cycle-free. ``_prompt_meta_unapplied_followup_intents`` stays defined
# locally below (separate region near write_build_result).
_prompt_meta_exports = importlib.import_module("packages.generation.build.prompt_meta")
_VERSIONED_PROMPT_INPUT_RE = _prompt_meta_exports._VERSIONED_PROMPT_INPUT_RE
_CURRENT_PROMPT_INPUT_RE = _prompt_meta_exports._CURRENT_PROMPT_INPUT_RE
_PLACEHOLDER_CONTACT_VALID_FIELDS = _prompt_meta_exports._PLACEHOLDER_CONTACT_VALID_FIELDS
_prompt_meta_path_for_dossier = _prompt_meta_exports._prompt_meta_path_for_dossier
load_prompt_input_meta = _prompt_meta_exports.load_prompt_input_meta
_prompt_meta_mode = _prompt_meta_exports._prompt_meta_mode
_prompt_meta_project_id = _prompt_meta_exports._prompt_meta_project_id
_prompt_meta_version = _prompt_meta_exports._prompt_meta_version
_prompt_meta_previous_version = _prompt_meta_exports._prompt_meta_previous_version
_prompt_meta_raw_prompt = _prompt_meta_exports._prompt_meta_raw_prompt
_persist_init_project_input_sidecar = _prompt_meta_exports._persist_init_project_input_sidecar
_prompt_meta_placeholder_contact_fields = (
    _prompt_meta_exports._prompt_meta_placeholder_contact_fields
)
_prompt_meta_followup_intent_id = _prompt_meta_exports._prompt_meta_followup_intent_id
_has_copy_directives = _prompt_meta_exports._has_copy_directives
_placeholder_contact_warning_message = _prompt_meta_exports._placeholder_contact_warning_message
_prompt_meta_wizard_must_have = _prompt_meta_exports._prompt_meta_wizard_must_have


def __getattr__(name: str) -> Any:
    """Lazy re-export from the build subpackage modules.

    Pre-B146 the entire renderer territory lived in this file
    (6313+ rader). After the port, source-of-truth moved into
    ``packages.generation.build.{renderers,static_assets,dispatcher}``
    and ``scripts.build_site`` is mostly a slim coordinator + a
    re-export façade. This hook lets callers keep the existing
    ``from scripts.build_site import render_section_X`` spelling
    without us having to enumerate every section renderer (Christopher
    added ~30 in PR #105 alone). Look-ups for names this module
    defines locally always win over the fallback; only unknown names
    fall through here.
    """
    for _mod in (_renderer_exports, _dispatcher_exports, _static_asset_exports):
        try:
            return getattr(_mod, name)
        except AttributeError:
            continue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

STARTERS_DIR = REPO_ROOT / "data" / "starters"
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
DEFAULT_GENERATED_DIR = REPO_ROOT.parent / "sajtbyggaren-output" / ".generated"
RUNS_DIR = REPO_ROOT / "data" / "runs"
PROMPT_INPUTS_DIR = REPO_ROOT / "data" / "prompt-inputs"

# Files the builder must NEVER write under any siteId. Case-insensitive.
# `.env.example` is allowed (canonical placeholder).
_FORBIDDEN_ENV_PATTERN = re.compile(r"^\.env(\..+)?$", flags=re.IGNORECASE)
_ALLOWED_ENV_NAMES = {".env.example"}


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


_ENV_QUOTED_RE = re.compile(r"""^(['"])((?:[^\\]|\\.)*?)\1\s*(?:#.*)?$""")


def load_repo_root_env() -> list[str]:
    """Load ``REPO_ROOT/.env`` into ``os.environ`` as a single source of truth.

    Dependency-free (no python-dotenv): a minimal parser for the common dotenv
    forms (``KEY=value``, optional ``export `` prefix, quoted values, trailing
    `` # comment``). Mirrors the inline parser in
    ``apps/viewser/scripts/dev.mjs`` and the Node resolver in
    ``apps/viewser/lib/generated-dir.ts`` so the Viewser dev flow and the
    builder read the same file the same way.

    ``os.environ`` ALWAYS wins: a key already present (shell export, Cloud-
    injected secret, or a value the Viewser spawn already passed through) is
    never overridden. Missing file = no-op, so CI and the test suite (no
    committed ``.env``) are unaffected. Returns the list of keys it set, for
    tracing/tests.
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return []
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return []
    applied: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        quoted = _ENV_QUOTED_RE.match(value)
        if quoted:
            value = quoted.group(2)
        else:
            comment = re.search(r"\s+#.*$", value)
            if comment:
                value = value[: comment.start()].rstrip()
        os.environ[key] = value
        applied.append(key)
    return applied


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
        *,
        reason: str | None = None,
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
        if reason is not None:
            record["reason"] = reason
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
    if any(source_pkg.get(key) != target_pkg.get(key) for key in _NPM_INSTALL_INPUT_KEYS):
        return True

    # B154 root cause: starter's package-lock.json drifted relative to its
    # own package.json (Next/eslint-config-next/PostCSS pinned to an older
    # baseline). Comparing lockfile contents catches that class of bug so
    # an existing .generated/<siteId> with stale node_modules forcibly
    # reinstalls when the starter ships an updated lockfile, even if
    # package.json fields look identical.
    source_lock = source / "package-lock.json"
    target_lock = target / "package-lock.json"
    if source_lock.exists() != target_lock.exists():
        return True
    if source_lock.exists() and target_lock.exists():
        try:
            if source_lock.read_bytes() != target_lock.read_bytes():
                return True
        except OSError:
            return True
    return False


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


def cleanup_flat_layout(site_dir: Path, *, keep: set[str]) -> list[str]:
    """Remove legacy flat-layout artefacts that sit directly under ``site_dir``.

    B157 level 4, flat-layout cleanup (the remaining non-blocking item in
    ``docs/gaps/GAP-windows-safe-rebuild-pipeline.md``): before immutable builds
    the Builder wrote straight into ``<generated>/<siteId>/`` (``.next``,
    ``node_modules``, ``app``, ``package.json`` ...). After the migration the
    active site lives under ``builds/<buildId>/`` and is pointed at by
    ``current.json``; the old flat-layout files in the site root are dead weight
    that only eat disk and can confuse the preview resolver's flat-``.next``
    fallback (``apps/viewser/lib/local-preview-server.ts:resolveActivePreviewDir``).

    Call this ONLY after ``current.json`` has been swapped to the new immutable
    build, so a running preview never loses its fallback before the pointer is
    live. Best-effort: a locked flat artefact (e.g. a not-yet-stopped preview
    still holding the old ``.next``/``node_modules`` open on Windows) is skipped
    and reported, never raised - cleanup must not fail an otherwise green build.

    ``keep`` is the set of site-root entries to leave in place (the immutable
    ``builds/`` directory and the ``current.json`` pointer). Returns the list of
    removed entry names so the caller can record the cleanup in the trace.
    """
    removed: list[str] = []
    if not site_dir.is_dir():
        return removed
    for entry in site_dir.iterdir():
        if entry.name in keep:
            continue
        try:
            if entry.is_symlink() or entry.is_file():
                entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            removed.append(entry.name)
        except OSError:
            # Locked or unreadable flat artefact: skip it. The next build (or a
            # manual sweep) retries; leaking one stale dir beats failing a build.
            continue
    return removed


UPLOADS_ROOT_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"


# Remote sourceUrl bytes cap. 8 MB is well above the optimized.webp
# budget, but prevents a build from reading an accidentally huge asset.
_REMOTE_ASSET_MAX_BYTES = 8 * 1024 * 1024

# Per-request timeout. A dead blob URL should skip one asset, not block
# the whole build.
_REMOTE_ASSET_TIMEOUT_SEC = 15
_REMOTE_ASSET_CHUNK_BYTES = 64 * 1024


def _fetch_asset_bytes_from_url(url: str) -> bytes | None:
    """Fetch bytes from an already-allowlisted remote asset URL.

    Redirects are deliberately disabled: a public blob URL must not be
    allowed to hop to loopback, link-local metadata endpoints, or any
    other non-allowlisted host after the initial validation.
    """
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "sajtbyggaren-build/1.0",
                "Accept": "*/*",
            },
            timeout=_REMOTE_ASSET_TIMEOUT_SEC,
            stream=True,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        print(f"copy_operator_uploads: fetch failed for {url}: {exc}")
        return None

    try:
        status_code = response.status_code
        if 300 <= status_code < 400:
            print(
                f"copy_operator_uploads: sourceUrl redirect blocked for {url}. "
                "Skipping asset.",
            )
            return None
        if status_code >= 400:
            print(
                f"copy_operator_uploads: sourceUrl returned HTTP {status_code} "
                f"for {url}. Skipping asset.",
            )
            return None

        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = None
            if declared_size is not None and declared_size > _REMOTE_ASSET_MAX_BYTES:
                print(
                    f"copy_operator_uploads: payload larger than {_REMOTE_ASSET_MAX_BYTES} "
                    f"bytes for {url}. Skipping asset.",
                )
                return None

        # Streaming-fel (ChunkedEncodingError, ConnectionError, Timeout
        # mid-read) bubblar inte ut till copy_operator_uploads. Reviewer-
        # fynd: utan denna inre except kraschade hela bygget vid en bruten
        # blob-stream trots att funktionen lovar att tysta hoppa över ett
        # trasigt asset. requests.RequestException täcker både stream- och
        # decoding-fel som kan uppstå efter att headers redan tagits emot.
        try:
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=_REMOTE_ASSET_CHUNK_BYTES):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _REMOTE_ASSET_MAX_BYTES:
                    print(
                        f"copy_operator_uploads: payload larger than {_REMOTE_ASSET_MAX_BYTES} "
                        f"bytes for {url}. Skipping asset.",
                    )
                    return None
                chunks.append(chunk)
            return b"".join(chunks)
        except requests.RequestException as exc:
            print(
                f"copy_operator_uploads: stream interrupted for {url}: {exc}. "
                "Skipping asset.",
            )
            return None
    finally:
        response.close()


def _operator_asset_candidate_dirs(site_id: str) -> list[Path]:
    return [UPLOADS_ROOT_DIR / site_id, UPLOADS_ROOT_DIR / "__draft"]


def _resolve_operator_asset_source(
    site_id: str,
    ref: dict,
    *,
    log_prefix: str,
) -> tuple[bytes, Path | None] | None:
    """Resolve operator-uploaded bytes via disk-first/sourceUrl-fallback."""
    asset_id = ref["assetId"]
    candidate_dirs = _operator_asset_candidate_dirs(site_id)

    # 1. Disk-lookup först — Local disk har företräde när bytes finns.
    source_dir: Path | None = None
    for candidate in candidate_dirs:
        if (candidate / asset_id).is_dir():
            source_dir = candidate / asset_id
            break

    if source_dir is not None:
        source_file = next(
            (candidate for candidate in _operator_asset_variant_candidates(source_dir) if candidate.exists()),
            None,
        )
        if source_file is not None:
            return source_file.read_bytes(), source_file
        # Source-dir finns men ingen variant-fil — fortsätt till
        # sourceUrl-fallback istället för att skippa direkt.
        print(
            f"{log_prefix}: asset {asset_id} saknar variant-fil "
            f"i {source_dir}. Försöker sourceUrl-fallback.",
        )

    # 2. Remote-fallback från sourceUrl när disk saknas.
    source_url = ref.get("sourceUrl")
    if isinstance(source_url, str) and source_url.strip():
        cleaned_source_url = source_url.strip()
        if not _is_allowed_asset_source_url(cleaned_source_url):
            print(
                f"{log_prefix}: sourceUrl for asset {asset_id} "
                f"is not an allowed HTTPS Vercel Blob URL ({cleaned_source_url!r}). "
                "Skipping asset.",
            )
            return None
        data = _fetch_asset_bytes_from_url(cleaned_source_url)
        if data is None:
            return None
        return data, None

    # 3. Båda saknas — logga och hoppa över.
    print(
        f"{log_prefix}: asset {asset_id} saknas både på disk "
        f"(letade i {candidate_dirs}) och saknar sourceUrl. Hoppar över.",
    )
    return None


def _copy_product_images(site_id: str, target: Path, project_input: dict) -> int:
    """Copy products[].productImage to public/products/ and set imageUrl."""
    products = project_input.get("products") or []
    if not isinstance(products, list):
        return 0

    public_products = target / "public" / "products"
    copied = 0
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            continue
        ref = product.get("productImage")
        if not _is_valid_asset_ref(ref):
            continue
        resolved = _resolve_operator_asset_source(
            site_id,
            ref,
            log_prefix="copy_product_images",
        )
        if resolved is None:
            continue
        data, source_file = resolved
        extension = _public_product_asset_extension(ref, source_file)
        filename = f"{_public_product_asset_stem(product, index)}.{extension}"
        public_products.mkdir(parents=True, exist_ok=True)
        (public_products / filename).write_bytes(data)
        product["imageUrl"] = f"/products/{filename}"
        copied += 1
    return copied


def copy_operator_uploads(site_id: str, target: Path, project_input: dict) -> int:
    """Copy operator-uploaded assets to the generated site's public/uploads/.

    Disk-first med remote-fallback. För varje ``AssetRef``:

    1. **Disk-lookup först.** Letar i ``data/uploads/<siteId>/<assetId>/``
       och ``data/uploads/__draft/<assetId>/``. Föredrar ``optimized.webp``
       och faller tillbaka till ``original.<ext>`` (SVG/video). Om bytes
       finns på disk kopieras de — buildern behöver inte fråga remote.

    2. **Remote-fallback från ``ref.sourceUrl``.** Om disk-lookup
       misslyckas och ``sourceUrl`` finns + pekar på en allowlist:ad
       HTTPS-host, HTTP-fetchas bytes och skrivs till
       ``public/uploads/<filename>``. Vid fetch-fel (URL/status/size/
       stream interrupt) skippas assetet — render faller tillbaka till
       alt-text.

    3. **Båda saknas → skippa med log.**

    Reviewer-fynd (Medium, 2026-05-24): Tidigare ``remote-authoritative``-
    semantik (sourceUrl vann ALLTID när present) gjorde en transient
    blob-outage till saknade bilder även om bra lokala bytes fanns på
    disk. Disk-first är robustare och matchar Christophers ursprungliga
    ``706a88a``-implementation samt naming-dictionary-definitionen.
    Stale-state-risken (disk har gamla bytes men blob har nyare) är
    acceptabel i operator-prototype: alla uppdateringar går via samma
    AssetStore-driver, så disk och blob är inte i divergens normalt.

    Returns the number of files written. A single bad asset never aborts
    the build; the renderer can still fall back to alt text / defaults.
    """
    refs = _iter_public_upload_refs(project_input)
    copied = 0
    if refs:
        public_uploads = target / "public" / "uploads"
        public_uploads.mkdir(parents=True, exist_ok=True)

        for ref in refs:
            filename = ref["filename"]
            resolved = _resolve_operator_asset_source(
                site_id,
                ref,
                log_prefix="copy_operator_uploads",
            )
            if resolved is None:
                continue
            data, source_file = resolved
            dest = public_uploads / filename
            if _asset_requires_derived_public_output(ref):
                _write_derived_media_asset(ref, data, target, source_file=source_file)
            dest.write_bytes(data)
            copied += 1

    copied += _copy_product_images(site_id, target, project_input)
    return copied


def copy_mood_assets(site_id: str, project_input: dict) -> int:
    """Isolate mood-reference assets under data/uploads/<siteId>/__mood/."""
    refs = _iter_mood_refs(project_input)
    if not refs:
        return 0

    mood_dir = UPLOADS_ROOT_DIR / site_id / "__mood"
    mood_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for ref in refs:
        resolved = _resolve_operator_asset_source(
            site_id,
            ref,
            log_prefix="copy_mood_assets",
        )
        if resolved is None:
            continue
        data, source_file = resolved
        asset_id = ref["assetId"]
        extension = _private_mood_asset_extension(ref, source_file)
        dest = mood_dir / f"{_private_mood_asset_stem(asset_id)}.{extension}"
        dest.write_bytes(data)
        copied += 1

    return copied


def patch_globals_css(
    target: Path,
    variant: dict,
    project_input: dict[str, Any] | None = None,
) -> list[str]:
    css = target / "app" / "globals.css"
    original = css.read_text(encoding="utf-8")
    token_overrides, warnings = _token_overrides_from_project_input(project_input)
    typography_overlay = _typography_overlay_for_tone(project_input)
    block = variant_css(
        variant,
        token_overrides,
        typography_overlay=typography_overlay,
    )
    font_marker = "/* sajtbyggaren-font-import:start */"
    font_end = "/* sajtbyggaren-font-import:end */"
    marker = "/* sajtbyggaren-variant-tokens:start */"
    end = "/* sajtbyggaren-variant-tokens:end */"

    # Strip any previously emitted regions so re-patching (follow-up
    # rebuilds) stays idempotent: the hoisted font @import block at the
    # top AND the variant-tokens block further down.
    base_contents = original
    if font_marker in base_contents:
        before, _, rest = base_contents.partition(font_marker)
        _, _, after = rest.partition(font_end)
        base_contents = f"{before}{after}"
    if marker in base_contents:
        before, _, rest = base_contents.partition(marker)
        _, _, after = rest.partition(end)
        base_contents = f"{before}{after}"
    base_contents = base_contents.strip()

    # Hoist the Google Fonts @import line(s) out of the variant block to
    # the absolute top of the file. CSS requires every @import rule to
    # precede all other rules; appending the variant block verbatim put
    # the font @import after the starter's :root/@layer rules, which
    # triggers the build/browser warning "@import rules must precede all
    # rules" on every build. (Longer-term fix: load the webfont via
    # next/font/google or a <link> in the Next layout instead of a CSS
    # @import — the layout already preconnects to fonts.googleapis.com.)
    import_lines: list[str] = []
    body_lines: list[str] = []
    for line in block.splitlines():
        if line.lstrip().startswith("@import"):
            import_lines.append(line)
        else:
            body_lines.append(line)
    block_body = "\n".join(body_lines)

    font_region = ""
    if import_lines:
        font_region = f"{font_marker}\n" + "\n".join(import_lines) + f"\n{font_end}\n\n"

    # Variant tokens appended last so starter defaults earlier in
    # globals.css cannot win the cascade.
    new_contents = (
        f"{font_region}{base_contents}\n\n{marker}\n{block_body}\n{end}\n"
    )
    write(css, new_contents)
    return warnings


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
    # B132 follow-up sprint 2026-05-21: wizardMustHave-driven extras
    # land as real routes for local-service-business via the new
    # _wizard_extra_routes helper in packages/generation/planning/plan.py.
    # Labels here keep the nav copy operator-facing in Swedish without
    # forcing each renderer to repeat the same string.
    "faq": "Vanliga frågor",
    "gallery": "Galleri",
    "map": "Hitta hit",
    "team": "Team",
    "pricing": "Priser",
    "portfolio": "Portfolio",
    # restaurant-hospitality scaffold routes — Issue #90. The scaffold's
    # routes.json declares Swedish slugs ``/meny`` and ``/bokning``; the
    # nav must use restaurant-flavoured labels rather than fall through
    # to ``_nav_label_for_route``'s slug-to-title-case fallback. We also
    # override the "contact" label for restaurants by relying on the
    # generic "Kontakt" entry above — the scaffold uses route id
    # ``contact`` so it picks up the same label as LSB/commerce.
    "menu": "Meny",
    "booking": "Boka bord",
    # Runtime-active Path B scaffolds (clinic-healthcare,
    # professional-services, agency-studio) use these route ids.
    "treatments": "Behandlingar",
    "expertise": "Expertis",
    "work": "Arbeten",
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
    "treatments": {
        "eyebrow": "Behandlingar",
        "heading": "Det vi hjälper med",
        "cta": "Se alla behandlingar",
    },
    "expertise": {
        "eyebrow": "Expertis",
        "heading": "Våra expertisområden",
        "cta": "Se all expertis",
    },
    "work": {
        "eyebrow": "Arbeten",
        "heading": "Utvalda arbeten",
        "cta": "Se våra arbeten",
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
    """Normalize briefModel business type variants for CTA fallback lookup.

    B150: briefModel sometimes emits multi-word business types
    ("massage studio", "yoga studio", "personal trainer studio"). The
    compact slug ("massage-studio") does not appear in
    ``_BOOKING_BUSINESS_TYPES`` or ``_SHOP_BUSINESS_TYPES``, which made
    ``_hero_cta_variant`` fall through to the generic "Begär offert" CTA
    instead of firing "Boka tid" / "Handla nu" for these branscher. We
    therefore try progressively shorter dash-prefixes and return the
    longest prefix that is itself a registered slug. The function never
    invents new slugs — it can only return strings that the CTA-resolver
    already knows about, or the unchanged compact form.
    """
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
    if compact in _BOOKING_BUSINESS_TYPES or compact in _SHOP_BUSINESS_TYPES:
        return compact
    if "-" in compact:
        parts = compact.split("-")
        for n in range(len(parts) - 1, 0, -1):
            prefix = "-".join(parts[:n])
            if prefix in _BOOKING_BUSINESS_TYPES or prefix in _SHOP_BUSINESS_TYPES:
                return prefix
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


# B102 (re-Verifierings-Scout 3 2026-05-18): commerce-CTA på /produkter
# var hardcoded till "Fråga om en beställning" / "ShoppingBag"-glyfen, vilket
# läste som en offerttjänst snarare än shop-flöde. Vi behåller länken mot
# kontakt-routen (ingen checkout finns ännu i builder MVP) men byter
# verbet så tonen följer hero-CTA "Shoppa nu". Whitelist-baserade
# strängar håller TSX-interpolationen säker utan JSX-escape.
_COMMERCE_BOTTOM_CTA_LABELS: dict[str, str] = {
    "sv": "Hör av dig för att beställa",
    "en": "Get in touch to order",
}


def _commerce_bottom_cta_label(dossier: dict) -> str:
    """Return the /produkter bottom-CTA label string.

    B102: "Fråga om en beställning" lät som en offert/förfrågan-tjänst
    på e-handel-cases där hero redan stod "Shoppa nu". Den nya copyn
    håller fortfarande den verbala dörren öppen mot kontakt-routen (ingen
    checkout finns i builder MVP) men landar i shop-tonalitet via verbet
    "beställa" / "order". Returvärdet är hämtat från en whitelist så
    interpolationen i TSX är säker utan JSX-escape.
    """
    language = (dossier.get("language") or "sv").strip().lower()
    if language not in _COMMERCE_BOTTOM_CTA_LABELS:
        language = "sv"
    return _COMMERCE_BOTTOM_CTA_LABELS[language]


def _hero_cta_target_path(
    dossier: dict,
    listing_route: dict | None,
    contact_path: str,
) -> str:
    """Return the route the hero CTA should link to.

    B101 (re-Verifierings-Scout 3 2026-05-18): a hero CTA labelled
    "Shoppa nu" / "Shop now" used to point at the scaffold contact
    route even when the build emitted a real ``/produkter`` listing,
    so the operator-visible button promised one thing and the click
    landed somewhere else. The new rule: when the CTA variant is
    ``shop`` and the scaffold actually emits a products listing, the
    hero CTA jumps to that listing route. Booking and quote variants
    keep contact as the primary target because there is no equivalent
    "list of bookable slots" surface in the current scaffolds. Shop
    variants fall back to contact when the scaffold has no products
    route - the label still reads "Shoppa nu" but at least the click
    lands on a real page instead of inventing ``/produkter`` for
    scaffolds that never declared it.
    """
    variant = _hero_cta_variant(dossier)
    if (
        variant == "shop"
        and listing_route is not None
        and listing_route.get("id") == "products"
        and listing_route.get("path")
    ):
        return listing_route["path"]
    return contact_path


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
    extra_routes: list[dict] | None = None,
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

    ``extra_routes`` carries wizard-driven routes (B132 follow-up
    sprint 2026-05-21): they land after scaffold defaults but before
    the contact CTA in the nav order. Same dedupe rule as for
    dossier routes — a path already declared by the scaffold or by a
    dossier wins, so emitting a wizard extra cannot duplicate the
    visible nav item.
    """
    items: list[tuple[str, str]] = [
        (route["path"], _nav_label_for_route(route["id"])) for route in scaffold_default_routes
    ]
    existing_paths = {href for href, _ in items}
    if extra_routes:
        # B148: look up the contact route's actual path from the scaffold
        # rather than hardcoding "/kontakt". restaurant-hospitality uses
        # "/hitta-hit" and future scaffolds may pick other ids — the
        # insert-before-contact heuristic must follow the scaffold, not
        # the most common path. Mirrors the lookup pattern in
        # ``_pick_contact_route`` (no SystemExit here — nav-building must
        # stay defensive even if a scaffold lacks a contact route, in
        # which case wizard-extras simply append to the end).
        contact_path = next(
            (
                route.get("path")
                for route in scaffold_default_routes
                if route.get("id") == "contact"
            ),
            None,
        )
        contact_idx: int | None = None
        if isinstance(contact_path, str) and contact_path:
            contact_idx = next(
                (i for i, (href, _label) in enumerate(items) if href == contact_path),
                None,
            )
        for route in extra_routes:
            if not isinstance(route, dict):
                continue
            path = route.get("path")
            route_id = route.get("id") or ""
            if not isinstance(path, str) or not path or path in existing_paths:
                continue
            entry = (path, _nav_label_for_route(route_id))
            if contact_idx is not None:
                items.insert(contact_idx, entry)
                contact_idx += 1
            else:
                items.append(entry)
            existing_paths.add(path)
    if "/spel" in dossier_routes and "/spel" not in existing_paths:
        items.append(("/spel", "Spel"))
        existing_paths.add("/spel")
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
    for candidate in ("services", "products", "treatments", "expertise", "work"):
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


# Sprint 5 — postMessage-lyssnare som Sajtbyggarens Site Inspector
# (TokensTab) skickar till för att uppdatera CSS-tokens i preview-
# iframen utan en ny build. Se kommentaren vid <script>-injektionen
# i render_layout för säkerhetsmodellen. Hålls som modulkonstant så
# tester kan asserta exakt innehåll utan att duplicera strängen.
_RUNTIME_TOKEN_LISTENER_JS = (
    "(function(){"
    "var ALLOWED={primary:1,accent:1,background:1,foreground:1};"
    "var HEX=/^#[0-9a-fA-F]{6}$/;"
    # Hjälpare som postar ett ack-meddelande till parent-fönstret (Site
    # Inspectorn) så TokensTab vet att listenern faktiskt lever och
    # accepterar set-token. target-origin "*" eftersom parent-origin
    # kan vara antingen ``http://localhost:3000`` (viewser:s dev-server)
    # eller en framtida tunnel-URL — vi skickar bara ett token-namn,
    # ingen sensitiv data. Ack är harmless: parent ignorerar typen om
    # den inte känner igen den.
    "function ack(token,value,applied){"
    "if(!window.parent||window.parent===window)return;"
    "try{window.parent.postMessage({type:'sajtbyggaren:token-applied',token:token,value:value,applied:applied},'*');}"
    "catch(_){}"
    "}"
    "window.addEventListener('message',function(e){"
    "var d=e&&e.data;"
    "if(!d||typeof d!=='object'||d.type!=='sajtbyggaren:set-token')return;"
    "if(!ALLOWED[d.token]){ack(d.token,d.value,false);return;}"
    "var root=document.documentElement;"
    "var prop='--'+d.token;"
    "if(d.value==='reset'){root.style.removeProperty(prop);ack(d.token,'reset',true);return;}"
    "if(typeof d.value==='string'&&HEX.test(d.value)){"
    "root.style.setProperty(prop,d.value);"
    "ack(d.token,d.value,true);"
    "return;"
    "}"
    "ack(d.token,d.value,false);"
    "});"
    "})();"
)




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


# ---------------------------------------------------------------------------
# Mock artefacts (no LLM yet)
# ---------------------------------------------------------------------------


_OPERATOR_DIRECTIVE_NOTE_PREFIX = "Operator: "
_MOOD_VISUAL_NOTE_PREFIX = "Visual mood: "


def _mood_visual_note_blocks(dossier: dict) -> list[str]:
    """Return planner notes from existing mood-image Vision metadata."""
    blocks: list[str] = []
    for ref in _iter_mood_refs(dossier):
        subject = ref.get("visionSubject")
        confidence = ref.get("visionConfidence")
        has_subject = isinstance(subject, str) and bool(subject.strip())
        has_confidence = isinstance(confidence, str) and bool(confidence.strip())
        if not has_subject and not has_confidence:
            continue

        parts: list[str] = []
        alt = ref.get("alt")
        if isinstance(alt, str) and alt.strip():
            parts.append(alt.strip())
        if has_subject:
            parts.append(f"subject: {subject.strip()}")
        if has_confidence:
            parts.append(f"confidence: {confidence.strip()}")
        if parts:
            blocks.append(f"{_MOOD_VISUAL_NOTE_PREFIX}{'; '.join(parts)}")
    return blocks


def _apply_operator_directive_note(brief: dict, dossier: dict) -> None:
    """Prepend deterministic operator and mood context to Site Brief notes.

    Gap 5 adds ``directives.notesForPlanner`` with prefix ``"Operator: "``.
    Gap 9 adds existing Vision metadata from ``moodImages`` with prefix
    ``"Visual mood: "`` when those fields are already present on the
    AssetRef. Missing/empty inputs leave the brief untouched.
    """
    blocks: list[str] = []
    directives = dossier.get("directives")
    if isinstance(directives, dict):
        raw_note = directives.get("notesForPlanner")
        if isinstance(raw_note, str):
            note = raw_note.strip()
            if note:
                blocks.append(f"{_OPERATOR_DIRECTIVE_NOTE_PREFIX}{note}")

    blocks.extend(_mood_visual_note_blocks(dossier))
    if not blocks:
        return

    existing = brief.get("notesForPlanner")
    if isinstance(existing, str) and existing.strip():
        blocks.append(existing.strip())
    brief["notesForPlanner"] = "\n\n".join(blocks)


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
    brief = {
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
    _apply_operator_directive_note(brief, dossier)
    return brief


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
        _apply_operator_directive_note(brief, dossier)
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


# ---------------------------------------------------------------------------
# Intent Guard light (warning-only) — B137-/B138-sprint 2026-05-21
# ---------------------------------------------------------------------------
#
# Wizardens kategori (``discoveryDecision.categoryIds``) och briefens
# ``businessTypeGuess`` / ``servicesMentioned`` kan motsäga varandra när
# operatören blandar fri prompt och wizardval. Scout case 4 (sköldpaddssoppa)
# visade exemplet: operatören valde fitness i wizardens overlay men beskrev
# mat-/restaurang-verksamhet i fri prompten — builden gick igenom utan att
# någonstans flagga konflikten. Helpern emitterar warnings men stoppar
# INTE generationen. Konflikt-tabellen är medvetet minimal i v1; utbyggnad
# sker i separat sprint om Scout visar fler false-negative-case.

_INTENT_GUARD_CONFLICTS: dict[str, tuple[str, ...]] = {
    "fitness": (
        "mat", "restaurang", "café", "cafe", "bageri",
        "restaurant", "bakery", "catering", "food-truck", "pizzeria", "bar",
    ),
    "construction": (
        "mat", "hår", "naglar", "salong",
        "hairdresser", "hair-salon", "barber", "nail-salon", "beauty-salon",
        "spa", "massage", "skincare",
        "restaurant", "bakery", "café", "cafe",
    ),
    "beauty": (
        "elektriker", "vvs", "tak", "bygg",
        "electrician", "plumber", "roofer", "carpenter", "hvac",
        "locksmith", "flooring", "renovation", "builder",
    ),
}


def _intent_guard_warnings(
    site_brief: dict[str, Any],
    prompt_meta: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Detect wizard-vs-brief category mismatches (warning-only).

    Returns a list of warning dicts shaped per
    ``governance/schemas/site-plan.schema.json``'s ``intentGuardWarnings``
    items. Empty list when no conflict exists or required signals are
    missing. Builder never blocks on this; the warning surfaces in
    ``site-plan.json`` for Backoffice/Run Details to display.
    """
    if not prompt_meta:
        return []
    decision = prompt_meta.get("discoveryDecision")
    if not isinstance(decision, dict):
        return []
    category_ids_raw = decision.get("categoryIds")
    if not isinstance(category_ids_raw, list):
        return []
    category_ids = [
        cat for cat in category_ids_raw if isinstance(cat, str) and cat
    ]
    if not category_ids:
        return []

    business_raw = site_brief.get("businessTypeGuess")
    business_type = (
        business_raw.strip().lower() if isinstance(business_raw, str) else ""
    )
    services_raw = site_brief.get("servicesMentioned") or []
    service_terms = [
        s.strip().lower()
        for s in services_raw
        if isinstance(s, str) and s.strip()
    ]
    candidate_terms = ([business_type] if business_type else []) + service_terms

    # B149: tokenise candidate terms so we can exact-token-match against the
    # conflict tokens instead of substring-matching. The original
    # ``blocked in term`` check produced false positives for short tokens
    # ("bar" in "barber", "spa" in "spaghetti", "mat" in "automation",
    # "tak" in "kontakt"). Each candidate term contributes itself plus any
    # sub-tokens split on whitespace and dashes — so slug entries in the
    # conflict tables ("hair-salon", "food-truck") still match against
    # slug-form business_type values, and bare tokens ("hair", "salon")
    # match individual words inside Swedish servicesMentioned strings.
    candidate_tokens: set[str] = set()
    for term in candidate_terms:
        if not term:
            continue
        candidate_tokens.add(term)
        for sub in term.replace("-", " ").split():
            if sub:
                candidate_tokens.add(sub)

    warnings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for category_id in category_ids:
        forbidden = _INTENT_GUARD_CONFLICTS.get(category_id)
        if not forbidden:
            continue
        for blocked in forbidden:
            if blocked not in candidate_tokens:
                continue
            key = (category_id, blocked)
            if key in seen:
                continue
            seen.add(key)
            warning: dict[str, str] = {
                "categoryId": category_id,
                "conflictingTerm": blocked,
                "reason": "category-vs-business-mismatch",
            }
            if business_type:
                warning["businessTypeGuess"] = business_type
            warnings.append(warning)
    return warnings


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

    intent_warnings = _intent_guard_warnings(site_brief, prompt_meta)

    result = produce_site_plan(
        site_brief,
        run_id=run_id,
        pinned=pinned,
        wizard_must_have=_prompt_meta_wizard_must_have(prompt_meta),
        engine_mode=_prompt_meta_mode(prompt_meta),
        project_id=_prompt_meta_project_id(prompt_meta),
        verification_policy="build-must-pass",
        preview_runtime="local",
        intent_guard_warnings=intent_warnings,
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


def _find_previous_generated_files_snapshot(
    runs_root: Path,
    current_run_dir: Path,
    prompt_meta: dict[str, Any] | None,
) -> Path | None:
    """Locate v(n-1)'s generated-files snapshot for a follow-up run."""
    project_id = _prompt_meta_project_id(prompt_meta)
    previous_version = _prompt_meta_previous_version(prompt_meta)
    if not project_id or previous_version is None:
        return None
    if not runs_root.exists():
        return None

    candidates = [
        run_dir
        for run_dir in runs_root.iterdir()
        if run_dir.is_dir() and run_dir != current_run_dir
    ]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for run_dir in candidates:
        input_path = run_dir / "input.json"
        try:
            input_payload = json.loads(input_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if input_payload.get("projectId") != project_id:
            continue
        if input_payload.get("version") != previous_version:
            continue
        snapshot = run_dir / "generated-files"
        if snapshot.is_dir():
            return snapshot
    return None


def _find_previous_page_snapshot(
    runs_root: Path,
    current_run_dir: Path,
    prompt_meta: dict[str, Any] | None,
) -> Path | None:
    """Locate v(n-1)'s generated home-page snapshot for a follow-up run."""
    snapshot = _find_previous_generated_files_snapshot(
        runs_root,
        current_run_dir,
        prompt_meta,
    )
    if snapshot is None:
        return None
    page_snapshot = snapshot / "app" / "page.tsx"
    return page_snapshot if page_snapshot.is_file() else None


_VISIBLE_EFFECT_SUFFIXES = frozenset(
    {
        ".css",
        ".gif",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".jsx",
        ".png",
        ".svg",
        ".ts",
        ".tsx",
        ".webp",
    }
)
_VISIBLE_EFFECT_ROOTS = ("app", "public")


def _visible_snapshot_bytes(snapshot_dir: Path) -> dict[str, bytes] | None:
    """Return visible source bytes from a generated-files snapshot.

    The home page alone is not enough: style-only follow-ups can change
    ``app/globals.css`` without changing ``app/page.tsx``. Comparing app/
    and public/ source assets keeps the no-op signal honest without reading
    node_modules, build cache, or other non-rendered metadata.
    """
    if not snapshot_dir.is_dir():
        return None
    visible_files: dict[str, bytes] = {}
    try:
        for root_name in _VISIBLE_EFFECT_ROOTS:
            root = snapshot_dir / root_name
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in _VISIBLE_EFFECT_SUFFIXES:
                    continue
                visible_files[path.relative_to(snapshot_dir).as_posix()] = path.read_bytes()
    except OSError:
        return None
    return visible_files


def _visible_snapshots_changed(previous_snapshot: Path, current_snapshot: Path) -> bool | None:
    """Return whether visible generated output changed, or None if unreadable."""
    previous_files = _visible_snapshot_bytes(previous_snapshot)
    current_files = _visible_snapshot_bytes(current_snapshot)
    if previous_files is None or current_files is None:
        return None
    return previous_files != current_files


def _detect_followup_applied_visible_effect(
    runs_root: Path,
    current_run_dir: Path,
    prompt_meta: dict[str, Any] | None,
    dossier: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the honest applied-effect signal for follow-up builds.

    ``None`` means the current build is not a follow-up. Follow-up builds
    always return a boolean so downstream UI can distinguish "not relevant"
    from "evaluated and not visible".
    """
    if _prompt_meta_mode(prompt_meta) != "followup":
        return None

    current_snapshot = current_run_dir / "generated-files"
    previous_snapshot = _find_previous_generated_files_snapshot(
        runs_root,
        current_run_dir,
        prompt_meta,
    )
    if previous_snapshot is not None:
        visible_changed = _visible_snapshots_changed(previous_snapshot, current_snapshot)
        if visible_changed is True:
            # A visible byte diff is NOT proof the operator's edit landed: a
            # copy follow-up can no-op while an unrelated rebuild regenerates
            # copy from stale facts, changing bytes anyway. When the operator
            # explicitly asked to replace a specific QUOTED copy string but no
            # copyDirective applied, report an honest no-op so a regenerated
            # paraphrase never masquerades as a successful edit (the
            # 2026-06-09 lask-ab trust bug). The signal answers "did your
            # intent land?", not just "did bytes change?". ROW 3.
            from packages.generation.followup.copy_directives import (
                _followup_requested_copy_replace,
            )

            raw_prompt = _prompt_meta_raw_prompt(prompt_meta)
            if (
                raw_prompt
                and _followup_requested_copy_replace(raw_prompt)
                and not _has_copy_directives(dossier)
            ):
                return {
                    "applied": False,
                    "reason": "copy_directive_not_applied",
                }
            return {
                "applied": True,
                "reason": "visible_files_changed",
            }
        if visible_changed is False:
            intent_id = _prompt_meta_followup_intent_id(prompt_meta)
            has_copy_directives = _has_copy_directives(prompt_meta) or _has_copy_directives(
                dossier
            )
            reason = (
                "intent_no_semantic_change"
                if intent_id == "no-semantic-change" and not has_copy_directives
                else "visible_files_unchanged"
            )
            return {
                "applied": False,
                "reason": reason,
            }

    intent_id = _prompt_meta_followup_intent_id(prompt_meta)
    has_copy_directives = _has_copy_directives(prompt_meta) or _has_copy_directives(
        dossier
    )
    if intent_id == "no-semantic-change" and not has_copy_directives:
        return {
            "applied": False,
            "reason": "intent_no_semantic_change",
        }

    return {
        "applied": True,
        "reason": "semantic_intent_without_previous_snapshot",
    }


def run_phase3_quality_and_repair(
    run_dir: Path,
    target: Path,
    routes_required: list[str],
    npm_steps: list[dict],
    overall_status: str,
    do_typecheck: bool,
    generation_package: dict[str, Any] | None = None,
    site_brief: dict[str, Any] | None = None,
    rerender: Callable[[dict[str, Any], dict[str, Any] | None], None] | None = None,
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
        generation_package=generation_package,
        site_brief=site_brief,
        run_dir=run_dir,
        run_id=run_dir.name,
        rerender=rerender,
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


# B155 honest-level-1: bounds for the unappliedFollowupIntents list so a
# malformed sidecar cannot smuggle arbitrary/oversized strings into
# build-result.json (Viewser reads the list verbatim).
_UNAPPLIED_FOLLOWUP_TARGET_MAX_LENGTH = 80
_UNAPPLIED_FOLLOWUP_REASON_MAX_LENGTH = 400
_UNAPPLIED_FOLLOWUP_MAX_ITEMS = 20


def _prompt_meta_unapplied_followup_intents(
    prompt_meta: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Return validated B155 unappliedFollowupIntents from the prompt sidecar.

    Each entry is ``{"target": <str>, "reason": <str>}`` - the honest-level-1
    complement to ``appliedVisibleEffect`` (a global file-diff boolean). It
    names the follow-up asks the deterministic v1 pipeline recognised but could
    not apply (an unmounted capability or a hero/section rewrite with no
    copyDirective target). Defensive parsing mirrors
    ``_prompt_meta_placeholder_contact_fields``: skip malformed entries, dedupe
    on target, cap string lengths and item count.
    """
    if not prompt_meta:
        return []
    raw = prompt_meta.get("unappliedFollowupIntents")
    if not isinstance(raw, list):
        return []
    posts: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        target = item.get("target")
        reason = item.get("reason")
        if not isinstance(target, str) or not isinstance(reason, str):
            continue
        target = target.strip()
        reason = reason.strip()
        if not target or not reason or target in seen:
            continue
        seen.add(target)
        posts.append(
            {
                "target": target[:_UNAPPLIED_FOLLOWUP_TARGET_MAX_LENGTH],
                "reason": reason[:_UNAPPLIED_FOLLOWUP_REASON_MAX_LENGTH],
            }
        )
        if len(posts) >= _UNAPPLIED_FOLLOWUP_MAX_ITEMS:
            break
    return posts


def write_build_result(
    run_dir: Path,
    trace: Trace,
    dossier: dict,
    site_brief: dict,
    scaffold: dict,
    variant: dict,
    starter_id: str,
    routes: list[str],
    page_intent_warnings: list[dict[str, Any]] | None,
    npm_steps: list[dict],
    overall_status: str,
    target_dir: Path,
    duration_ms: int,
    codegen_summary: dict | None = None,
    prompt_meta: dict[str, Any] | None = None,
    followup_effect: dict[str, Any] | None = None,
    blueprint_effect: dict[str, Any] | None = None,
    active_build_id: str | None = None,
) -> dict:
    """Write build-result.json. ``generatedFilesDir`` points at the canonical
    snapshot under the run directory, not at the dev preview, so downstream
    consumers (Backoffice, eval batch) can trust it across regenerations.

    ``devPreviewDir`` points at the immutable build directory this run wrote
    to (``<generated>/<siteId>/builds/<buildId>/`` since B157 level 4 Stage A).
    ``active_build_id`` is the build id when the current.json pointer was
    swapped to this run (status ok|degraded); it is ``None`` for failed/
    skipped runs, where the pointer is intentionally left on the previous
    build and ``activeBuildId`` is omitted from build-result.json.

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
        "pageIntentWarnings": list(page_intent_warnings or []),
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
    if followup_effect is not None:
        result["appliedVisibleEffect"] = bool(followup_effect["applied"])
        result["appliedVisibleEffectReason"] = followup_effect["reason"]
    elif blueprint_effect is not None:
        # kor-2: on init builds (no follow-up file-diff) the honest applied-
        # effect signal reports whether the Generation Package blueprint
        # actually changed the rendered output vs the template defaults. Only
        # emitted when a blueprint was present, so a legacy non-blueprint build
        # never grows the field (zero regression). Follow-up builds keep the
        # file-diff signal above; this branch never overrides it.
        result["appliedVisibleEffect"] = bool(blueprint_effect["applied"])
        result["appliedVisibleEffectReason"] = blueprint_effect["reason"]
    # B133 (2026-05-19): surface placeholder contact fields so Viewser
    # Run Details can warn the operator that the published site shows
    # dummy contact info ("+46 8 000 00 00", "kontakt@example.se",
    # "Adress lämnas på förfrågan") until those fields are filled in
    # Project Input. Emitted only when the list is non-empty.
    placeholder_contact_fields = _prompt_meta_placeholder_contact_fields(
        prompt_meta
    )
    if placeholder_contact_fields:
        result["placeholderContactFields"] = list(placeholder_contact_fields)
        result["placeholderContactMessage"] = _placeholder_contact_warning_message(
            placeholder_contact_fields
        )
    # B155 honest-level-1: surface the follow-up asks the deterministic v1
    # pipeline recognised but could not apply (computed in
    # prompt_to_project_input and carried on the meta sidecar). Complements the
    # global appliedVisibleEffect boolean; emitted only when non-empty.
    unapplied_followup_intents = _prompt_meta_unapplied_followup_intents(prompt_meta)
    if unapplied_followup_intents:
        result["unappliedFollowupIntents"] = unapplied_followup_intents
    if codegen_summary is not None:
        result["codegen"] = codegen_summary
    if active_build_id is not None:
        result["activeBuildId"] = active_build_id
    write_json(run_dir / "build-result.json", result)
    if unapplied_followup_intents:
        trace.event(
            "build",
            "followup.unapplied_intents_detected",
            "warning",
            "Follow-up contained intents the deterministic v1 pipeline could not apply",
            reason=", ".join(post["target"] for post in unapplied_followup_intents),
        )
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


def _extract_wizard_extra_routes(
    site_plan: dict,
    scaffold_routes: dict,
) -> list[dict[str, str]]:
    """Return wizard-driven extras present on site_plan.routePlan.

    The Plan helper (``packages.generation.planning.plan``) appends
    wizard mustHave routes after the scaffold defaults so the routePlan
    is the single source of truth. This helper extracts the subset whose
    paths are NOT in the scaffold's ``routes.json`` so write_pages knows
    which renderers to dispatch via ``_WIZARD_ROUTE_RENDERERS``. The
    list preserves the routePlan order so nav and on-disk paths stay
    consistent.
    """
    default_paths = {
        route["path"]
        for route in scaffold_routes.get("defaultRoutes") or []
        if isinstance(route, dict) and isinstance(route.get("path"), str)
    }
    extras: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for route in site_plan.get("routePlan") or []:
        if not isinstance(route, dict):
            continue
        route_id = route.get("id")
        path = route.get("path")
        if not isinstance(route_id, str) or not isinstance(path, str):
            continue
        if path in default_paths or path in seen_paths:
            continue
        if route_id not in _WIZARD_ROUTE_RENDERERS:
            continue
        extras.append({"id": route_id, "path": path})
        seen_paths.add(path)
    return extras


def build(
    dossier_path: Path,
    do_build: bool = True,
    runs_dir: Path | None = None,
    generated_dir: str | Path | None = None,
    auto_prune: bool = True,
    prompt_inputs_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Generate a site and Engine Run artefakts. Returns (target, run_dir).

    ``runs_dir`` defaults to ``RUNS_DIR`` (``data/runs``); pass an isolated
    path (``tmp_path`` in tests) to keep the canonical history clean.
    ``generated_dir`` overrides where the dev-preview site is emitted.
    ``auto_prune`` runs the retention sweep from
    ``packages.generation.maintenance.auto_prune_all`` before Phase 0 so
    ``data/runs/``, ``data/prompt-inputs/`` and ``.generated/`` stay under
    the caps configured in ``.env``. Disabled automatically when ``runs_dir``
    is overridden (tests with ``tmp_path``). The ``build_site.py`` CLI now
    leaves this OFF unless ``--allow-prune`` is passed, so a manual or smoke
    ``--dossier`` build can NEVER silently delete existing prompt-input
    sidecars / runs / previews just because ``SAJTBYGGAREN_MAX_*`` caps are
    set (the data-loss trap a smoke build would otherwise hit when there are
    more sites on disk than the cap). The Viewser product flow opts in
    explicitly via ``--allow-prune`` (apps/viewser/lib/build-runner.ts), and
    the prompt-driven create path keeps its own sweep in
    ``scripts/prompt_to_project_input.py``, so retention behaviour there is
    unchanged.

    ``prompt_inputs_dir`` (Glue 1): where to persist a discoverable Project
    Input sidecar for a fresh init build that did not come through
    ``prompt_to_project_input.generate`` (see
    ``_persist_init_project_input_sidecar``). A canonical build (``runs_dir``
    unset) persists to ``data/prompt-inputs/``; an isolated build (``runs_dir``
    overridden, e.g. tests/evals) only persists when this is given explicitly,
    so the canonical history stays clean.
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

    # Glue 1 (core loop): make sure a fresh init build leaves a discoverable
    # Project Input sidecar so the next follow-up can find it on disk. Canonical
    # builds (runs_dir unset) persist to data/prompt-inputs/; an isolated build
    # only persists when an explicit prompt_inputs_dir is given, so tests/evals
    # never write to the canonical history. A build already backed by a sidecar
    # (the Viewser prompt path / any follow-up version) is left untouched.
    if prompt_inputs_dir is not None:
        persist_dir: Path | None = prompt_inputs_dir
    elif runs_dir is None:
        persist_dir = PROMPT_INPUTS_DIR
    else:
        persist_dir = None
    if persist_dir is not None:
        enriched_prompt_meta = _persist_init_project_input_sidecar(
            dossier, prompt_meta, persist_dir
        )
        if enriched_prompt_meta is not None:
            prompt_meta = enriched_prompt_meta

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

    # B157 level 4, Stage A (docs/gaps/GAP-windows-safe-rebuild-pipeline.md):
    # build into an immutable builds/<buildId>/ directory instead of in place
    # at <generated>/<siteId>/. The Builder never deletes or overwrites a
    # directory a live preview holds open, so the WinError 5 .node file-lock
    # class is removed at the architecture level (not patched). The active
    # build is published via an atomic current.json pointer swap further down,
    # once overall_status is final and shippable. All pointer/build-id logic
    # lives in packages/generation/build/immutable_builds.py; this is wiring.
    from packages.generation.build.immutable_builds import (
        build_dir_for,
        new_build_id,
        write_active_pointer,
    )

    site_dir = generated_root / site_id
    build_id = new_build_id(
        exists=lambda candidate: build_dir_for(generated_root, site_id, candidate).exists()
    )

    # Phase 3: build. The Starter to copy is whatever the plan picked - we
    # used to hardcode 'marketing-base' here, which made the planSource a
    # decoration rather than authoritative. Reading site_plan["starterId"]
    # also future-proofs the builder for the day commerce-base is harmonised.
    target = build_dir_for(generated_root, site_id, build_id)
    trace.event("build", "phase.started", "started", "Phase 3 build starts")

    starter_id = site_plan["starterId"]
    print(f"Copying starter {starter_id} -> {target}")
    copy_starter(starter_id, target)

    print("Copying operator uploads (logo, hero, gallery)")
    uploads_copied = copy_operator_uploads(site_id, target, dossier)
    print(f"  -> {uploads_copied} asset(s) copied to public/uploads/")

    print("Isolating mood reference uploads")
    mood_assets_copied = copy_mood_assets(site_id, dossier)
    print(f"  -> {mood_assets_copied} mood asset(s) copied to data/uploads/{site_id}/__mood/")

    print("Patching package.json")
    patch_package_json(target, dossier)

    print("Injecting variant tokens into app/globals.css")
    token_warnings = patch_globals_css(target, variant, dossier)
    for warning in token_warnings:
        trace.event("build", "variant_tokens.warning", "warning", warning)

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
    #
    # B132 follow-up sprint 2026-05-21: wizardMustHave-driven routes
    # land via plan.py's ``_wizard_extra_routes`` and arrive on
    # ``site_plan["routePlan"]``. They are not in the scaffold's
    # routes.json, so we extract them here and thread them through
    # write_pages. The dispatch announcement covers both lists so
    # operators still see exactly which paths are about to be
    # written if the next step raises.
    wizard_extra_routes = _extract_wizard_extra_routes(site_plan, scaffold_routes)
    routes_to_write = all_default_routes(scaffold_routes) + [
        route["path"] for route in wizard_extra_routes
    ]
    # kor-2: the deterministic renderer now reads the Generation Package
    # blueprint (contentBlocks/visualDirection) + Site Brief honesty fields
    # (businessFacts/conversion/qualityRisks) as its content source, with
    # graceful per-field fallback to the template. The blueprint object also
    # records which addresses actually changed the render so the build can
    # report an honest appliedVisibleEffect on init builds (see below).
    from packages.generation.build.blueprint_render import RenderBlueprint

    blueprint = RenderBlueprint.from_artifacts(generation_package, site_brief)
    print("Writing pages: " + ", ".join(routes_to_write) + " and layout")
    paths_written = write_pages(
        target,
        dossier,
        scaffold_routes,
        dossier_routes,
        extra_routes=wizard_extra_routes or None,
        variant_id=variant.get("id") if isinstance(variant, dict) else None,
        blueprint=blueprint,
    )
    if paths_written != routes_to_write:
        raise SystemExit(
            "Builder failed: write_pages returned "
            f"{paths_written!r} but scaffold + wizard declared "
            f"{routes_to_write!r}. The dispatch table and the "
            "scaffold registry have drifted; reconcile them "
            "before retrying."
        )

    routes_all = list(routes_to_write)
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
            # Prefer ``npm ci`` for strict, reproducible installs when a
            # lockfile is present: it installs exactly the pinned tree and
            # fails fast on package.json/lockfile drift instead of silently
            # mutating the lockfile the way ``npm install`` can. Each
            # immutable ``builds/<buildId>/`` is a fresh copy of the starter
            # (which ships a committed, in-sync lockfile), so ``npm ci`` is
            # the right tool. Fall back to ``npm install`` only when no
            # lockfile was copied (e.g. minimal test starters) so those
            # builds still work. ``patch_package_json`` only rewrites the
            # root ``name`` (not the dependency set), which ``npm ci`` does
            # not treat as drift.
            if (target / "package-lock.json").is_file():
                install_cmd = ["npm", "ci"]
            else:
                install_cmd = ["npm", "install"]
            install_label = " ".join(install_cmd)
            print(f"Running {install_label} (timeout {NPM_INSTALL_TIMEOUT_SECONDS}s)...")
            ok, secs, last = run_npm(
                install_cmd,
                target,
                timeout=NPM_INSTALL_TIMEOUT_SECONDS,
            )
            npm_steps.append(_npm_step_result(install_label, ok, secs, last))
            trace.event(
                "build",
                "npm.install",
                "done" if ok else "failed",
                f"{install_label} ok={ok} seconds={secs:.1f}",
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

    # kor-5 skiva 1c: give the Repair Pipeline a rerender callback so a
    # blueprint-repair patch is materialised by the SAME deterministic
    # renderer as the initial build before the critic re-runs. Without it
    # the pass stays dormant and never claims a copy improvement the
    # rendered site lacks. No npm rebuild here - write_pages rewrites
    # app/*.tsx in place; the critic re-reads the patched blueprint + tree
    # (ADR 0015/0016: render logic stays in scripts/, called via the seam).
    def _rerender_after_repair(
        patched_generation_package: dict[str, Any],
        patched_site_brief: dict[str, Any] | None,
    ) -> None:
        patched_blueprint = RenderBlueprint.from_artifacts(
            patched_generation_package, patched_site_brief
        )
        write_pages(
            target,
            dossier,
            scaffold_routes,
            dossier_routes,
            extra_routes=wizard_extra_routes or None,
            variant_id=variant.get("id") if isinstance(variant, dict) else None,
            blueprint=patched_blueprint,
        )

    quality_payload, repair_payload = run_phase3_quality_and_repair(
        run_dir,
        target,
        routes_all_with_dossiers,
        npm_steps,
        overall_status,
        do_typecheck,
        generation_package=generation_package,
        site_brief=site_brief,
        rerender=_rerender_after_repair,
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
    followup_effect = _detect_followup_applied_visible_effect(
        runs_root,
        run_dir,
        prompt_meta,
        dossier,
    )
    if followup_effect is not None and followup_effect["applied"] is False:
        trace.event(
            "build",
            "followup.no_op_detected",
            "warning",
            "Follow-up produced no visible effect",
            reason=followup_effect["reason"],
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

    # B157 level 4, Stage A: publish the immutable build by swapping the
    # current.json pointer atomically, gated on the final status. "ok" and
    # "degraded" are shippable (ADR 0015: "degraded" means a route-scan or
    # policy soft-failure while typecheck/build passed), so the operator's
    # preview should move to this build. "failed" and "skipped" leave the
    # pointer untouched so a broken or file-only run never becomes the active
    # preview - the previous good build keeps serving until a new one lands.
    active_build_id: str | None = None
    if overall_status in ("ok", "degraded"):
        build_path = target.relative_to(site_dir).as_posix()
        write_active_pointer(site_dir, build_id, build_path)
        active_build_id = build_id
        trace.event(
            "build",
            "active_pointer.swapped",
            "done",
            f"current.json -> {build_path} (status={overall_status})",
        )
        # B157 level 4, flat-layout cleanup (GAP-windows-safe-rebuild-pipeline.md
        # remaining non-blocking item): now that current.json points at the new
        # immutable build, reclaim any legacy flat-layout artefacts left in the
        # site root from the pre-immutable era (.next, node_modules, app, ...).
        # Gated on the swap above so the preview's flat-.next fallback is only
        # removed AFTER the pointer makes it redundant. Best-effort: a still
        # locked artefact is skipped, never fatal.
        from packages.generation.build.immutable_builds import (
            BUILDS_DIRNAME,
            POINTER_FILENAME,
        )

        removed_flat = cleanup_flat_layout(
            site_dir, keep={BUILDS_DIRNAME, POINTER_FILENAME}
        )
        if removed_flat:
            trace.event(
                "build",
                "flat_layout.cleaned",
                "done",
                f"Removed {len(removed_flat)} legacy flat-layout artefact(s): "
                + ", ".join(sorted(removed_flat)),
            )

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

    # kor-2: honest applied-effect signal for init builds — did the blueprint
    # actually change the rendered output vs the template defaults? Follow-up
    # builds keep owning appliedVisibleEffect via the file-diff path above; this
    # is None on non-blueprint builds so the field is never added there.
    from packages.generation.build.blueprint_render import blueprint_applied_effect

    blueprint_effect = blueprint_applied_effect(blueprint)
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
        site_plan.get("pageIntentWarnings"),
        npm_steps,
        overall_status,
        target,
        duration_ms,
        codegen_summary=codegen_summary,
        prompt_meta=prompt_meta,
        followup_effect=followup_effect,
        blueprint_effect=blueprint_effect,
        active_build_id=active_build_id,
    )

    if overall_status == "failed":
        trace.event("build", "phase.completed", "failed", "Phase 3 build failed")
        raise SystemExit(1)

    trace.event("build", "phase.completed", "done", "Phase 3 build done")
    print(f"Generated site at {target}")
    print(f"Run artifacts at {run_dir}")
    return target, run_dir


def _append_targeted_render_event(
    run_dir: Path,
    run_id: str,
    result: Any,
) -> None:
    """Append the kor-7d targeted-render outcome to the run's trace.ndjson.

    Append-only (mirrors ``Trace.event`` and the router/apply trace helpers): it
    never truncates the build's trace, it only adds one honest summary event so
    every targeted build - applied, no-op or skipped - leaves a trace (FYND1).
    """
    status = {
        "applied": "done",
        "no-op": "warning",
        "skipped": "skipped",
        "failed": "failed",
    }.get(result.outcome, "done")
    record = {
        "runId": run_id,
        "phase": "build",
        "event": "targeted_render.outcome",
        "status": status,
        "message": (
            f"targeted render {result.outcome}: "
            f"previewShouldRefresh={result.previewShouldRefresh} "
            f"affected={result.affectedRoutes} changed={result.changedRoutes}"
        ),
        "timestamp": utc_now().isoformat(),
        "payloadPath": None,
    }
    trace_path = run_dir / "trace.ndjson"
    with trace_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _route_segment_to_id_map(run_dir: Path) -> dict[str, str]:
    """Map generated route-directory segments to scaffold route ids (KÖR-7-STAB #176).

    The targeted-render diff attributes a changed file to a route by its URL
    path segment (``app/kontakt/page.tsx``), but affected routes are derived from
    the kor-1a logical route id (``contentBlocks.contact``). The site plan's
    ``routePlan`` carries the authoritative scaffold path<->id map, so we read it
    from the just-built run and translate file segments back to route ids before
    comparing. Returns ``{}`` (raw-segment fallback) when the plan is missing or
    unreadable.
    """
    try:
        plan = load_json(run_dir / "site-plan.json")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    route_plan = plan.get("routePlan") if isinstance(plan, dict) else None
    if not isinstance(route_plan, list):
        return {}
    mapping: dict[str, str] = {}
    for entry in route_plan:
        if not isinstance(entry, dict):
            continue
        route_id = entry.get("id")
        path = entry.get("path")
        if not isinstance(route_id, str) or not route_id:
            continue
        if not isinstance(path, str):
            continue
        mapping[path.strip("/")] = route_id
    return mapping


def _find_active_build_generated_files_snapshot(
    runs_root: Path,
    generated_root: Path,
    site_id: str | None,
) -> Path | None:
    """Return the generated-files snapshot of the operator's ACTIVE build.

    KÖR-7-STAB #176: ``previewShouldRefresh``/changed-routes must compare against
    what the preview actually serves - the build ``current.json`` points at - not
    an arbitrary historical previousVersion run that may not be active. Reads the
    active build id from the immutable-build pointer (read-only; the current.json
    contract stays off-limits) and finds the run whose ``build-result.json``
    published that build id, returning its ``generated-files`` snapshot. Returns
    ``None`` when there is no active pointer yet or no matching run, so the caller
    falls back to the historical previous-version snapshot.
    """
    if not site_id:
        return None
    from packages.generation.build.immutable_builds import read_active_build_dir

    active_build_dir = read_active_build_dir(generated_root / site_id)
    if active_build_dir is None:
        return None
    active_build_id = active_build_dir.name
    if not runs_root.exists():
        return None
    candidates = [run_dir for run_dir in runs_root.iterdir() if run_dir.is_dir()]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for run_dir in candidates:
        try:
            payload = json.loads(
                (run_dir / "build-result.json").read_text(encoding="utf-8")
            )
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if payload.get("activeBuildId") != active_build_id:
            continue
        snapshot = run_dir / "generated-files"
        if snapshot.is_dir():
            return snapshot
    return None


def _find_new_run_dir(runs_root: Path, before_names: set[str]) -> Path | None:
    """Return the run directory created during this call (newest not in ``before_names``)."""
    if not runs_root.exists():
        return None
    new_dirs = [
        run_dir
        for run_dir in runs_root.iterdir()
        if run_dir.is_dir() and run_dir.name not in before_names
    ]
    if not new_dirs:
        return None
    new_dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return new_dirs[0]


def _apply_result_mismatch(
    apply_result: Any,
    dossier_path: Path,
    dossier: dict[str, Any],
    prompt_meta: dict[str, Any] | None,
) -> str | None:
    """Return a mismatch reason, or ``None`` when the apply_result fits the build.

    KÖR-7-STAB #176: a supplied ``apply_result`` must describe the SAME version
    ``dossier_path`` points at; otherwise affected-route derivation and the build
    would silently operate on the wrong site/version. Checks ``siteId``,
    ``version`` and (when present) ``projectInputPath`` against the dossier being
    built. Only fields that are populated on both sides are compared, so a sparse
    apply_result is not rejected on absent data.
    """
    apply_site = getattr(apply_result, "siteId", None)
    dossier_site = dossier.get("siteId")
    if apply_site and dossier_site and apply_site != dossier_site:
        return (
            f"apply_result.siteId {apply_site!r} matchar inte dossier.siteId "
            f"{dossier_site!r}."
        )
    apply_version = getattr(apply_result, "version", None)
    meta_version = _prompt_meta_version(prompt_meta)
    if (
        isinstance(apply_version, int)
        and isinstance(meta_version, int)
        and apply_version != meta_version
    ):
        return (
            f"apply_result.version {apply_version} matchar inte versionen som "
            f"byggs ({meta_version})."
        )
    apply_path = getattr(apply_result, "projectInputPath", None)
    if isinstance(apply_path, str) and apply_path:
        try:
            same = Path(apply_path).resolve() == dossier_path.resolve()
        except OSError:
            same = False
        if not same:
            return (
                f"apply_result.projectInputPath {apply_path!r} pekar inte på "
                f"dossier_path {str(dossier_path)!r}."
            )
    return None


def build_targeted_version(
    dossier_path: Path,
    *,
    apply_result: Any = None,
    affected_routes: list[str] | None = None,
    do_build: bool = True,
    runs_dir: Path | None = None,
    generated_dir: str | Path | None = None,
    require_internal_chain: bool = True,
    build_fn: Any = build,
) -> Any:
    """KÖR-7d: targeted render + version-build for a kor-7c-applied version.

    Builds a NEW immutable version of a Project Input produced by the internal
    kor-7b(plan) -> kor-7c(apply) chain, reusing the existing project-wide
    ``build()`` unchanged: immutable build dir, atomic ``current.json`` swap on
    ``ok``/``degraded`` only, honest follow-up ``appliedVisibleEffect``, a fresh
    runId, and previous runs left untouched. On top it adds the *targeted* layer:
    derive the affected route(s), verify which routes actually changed, and
    decide whether the operator preview should refresh (only on a shippable build
    with a real visible change - a no-op never restarts the preview).

    Targeted = render of the affected route files, NOT a partial Next build (see
    kor-7d "Targeted = render/filgenerering, inte partiell Next build"): the
    deterministic builder re-renders the whole site, but because the render is
    deterministic only the affected route changes vs the previous build, which is
    verified here via a per-route snapshot diff. ``npm run build`` / typecheck /
    Quality Gate stay project-wide (v1).

    FYND2 (revalidation assumption): this entry point is intended to build ONLY a
    version produced by the internal apply chain. ``require_internal_chain``
    (default True) refuses - with :class:`TargetedRenderError` (STOP and report)
    - a version that carries no kor-7c apply provenance
    (``meta.appliedPatchPlan.source == "kor-7c-artifact-apply"``) and no
    ``apply_result``, so an external/hand-built Project Input never silently
    reaches the build path through this entry. When a caller explicitly opts out
    (``require_internal_chain=False``) the fallback is still safe because
    ``build()`` re-runs ``produce_site_plan``, which re-applies the SAME planning
    rails (capability-map + scaffold sections) to the version before anything is
    rendered: a capability/section/dossier not on the rails is rejected at plan
    time, before render/build. Either way, un-revalidated input is never
    rendered. ``build_fn`` is injectable for tests; it defaults to ``build``.

    KÖR-7-STAB #176 stabilisations: (1) a skipped/unmapped ``apply_result``
    (``applied=False``) never triggers build/promote; (2) a supplied
    ``apply_result`` is matched (siteId/version/projectInputPath) against the
    version being built before anything runs; (3) ``previewShouldRefresh`` and
    changed-routes diff against the operator's ACTIVE build snapshot
    (``current.json``, captured before the pointer swap), falling back to the
    historical previous-version snapshot only when no active pointer exists yet;
    (4) generated route files are attributed to routes via the scaffold's
    routePlan path<->id map (so ``app/kontakt`` is reported as route ``contact``,
    not ``kontakt``); (5) a FAILED build still trace-logs a targeted-render
    outcome before the SystemExit propagates; all run snapshots are read/written
    under the same ``runs_root``.
    """
    from packages.generation.build.targeted_render import (
        ROOT_ROUTE_ID,
        TargetedRenderError,
        TargetedRenderResult,
        affected_routes_from_apply,
        changed_routes_between_snapshots,
        decide_preview_refresh,
        route_id_from_patch_field,
    )

    # KÖR-7-STAB #176: a skipped/unmapped apply never wrote a new version.
    # Building it would re-render unchanged input and risk promoting a stale
    # build, so refuse to build/promote. The apply step already traced its
    # skipped/unmapped outcome under its own run (FYND1), so this stays honest.
    if apply_result is not None and not getattr(apply_result, "applied", True):
        return TargetedRenderResult(
            siteId=getattr(apply_result, "siteId", None),
            version=getattr(apply_result, "version", None),
            previousVersion=getattr(apply_result, "previousVersion", None),
            outcome="skipped",
            previewShouldRefresh=False,
            notes=[
                "apply_result.applied=False (skipped/unmapped apply): ingen "
                "targeted build, ingen promote. Apply-steget loggade redan "
                "utfallet i sin egen run.",
            ],
        )

    dossier = load_json(dossier_path)
    site_id = dossier.get("siteId")
    prompt_meta = load_prompt_input_meta(dossier_path, dossier)

    # FYND2: internal-chain guard. Refuse to build a version that did not come
    # from the kor-7c apply chain unless the caller explicitly opts in to the
    # planner-rails re-validation fallback documented above.
    provenance = prompt_meta.get("appliedPatchPlan") if prompt_meta else None
    has_internal_provenance = (
        isinstance(provenance, dict)
        and provenance.get("source") == "kor-7c-artifact-apply"
    )
    is_followup = _prompt_meta_mode(prompt_meta) == "followup"
    internal = apply_result is not None or (is_followup and has_internal_provenance)
    if require_internal_chain and not internal:
        raise TargetedRenderError(
            "kor-7d bygger bara en version producerad av den interna kedjan "
            "kor-7b(plan) -> kor-7c(apply). Project Input saknar apply-proveniens "
            "(meta.appliedPatchPlan.source != 'kor-7c-artifact-apply') och inget "
            "apply_result gavs. STOPP: kör via den interna kedjan, eller sätt "
            "require_internal_chain=False (build() re-validerar då versionen mot "
            "planeringens rails via produce_site_plan innan render)."
        )

    # KÖR-7-STAB #176: an explicit apply_result must describe the SAME version
    # dossier_path points at, or affected-route derivation and the build would
    # silently operate on the wrong site/version.
    if apply_result is not None:
        mismatch = _apply_result_mismatch(
            apply_result, dossier_path, dossier, prompt_meta
        )
        if mismatch:
            raise TargetedRenderError(
                "kor-7d: apply_result matchar inte versionen som ska byggas. "
                + mismatch
            )

    # Affected routes: UNION the patch-derived routes (from the apply) with the
    # surfaced section routes (passed explicitly via ``affected_routes``), then
    # fall back to the meta provenance's patch fields and finally the root route.
    # When a follow-up combines a normal patch (e.g. "home") with a visible
    # section_add (e.g. ["faq"]), letting the patch route override the surfaced
    # route dropped "faq" - so it reported only "home" though /faq changed and
    # warned about an unexpected route (#221 P2). Order-preserving + deduped:
    # patch route(s) first, then surfaced section route(s); neither overrides the
    # other.
    affected: list[str] = []
    patch_routes = (
        affected_routes_from_apply(apply_result) if apply_result is not None else []
    )
    explicit_routes = [
        route for route in (affected_routes or []) if isinstance(route, str)
    ]
    for route_id in (*patch_routes, *explicit_routes):
        if route_id and route_id not in affected:
            affected.append(route_id)
    if not affected and isinstance(provenance, dict):
        for entry in provenance.get("appliedCapabilities") or []:
            field = entry.get("patchField") if isinstance(entry, dict) else None
            route_id = route_id_from_patch_field(field)
            if route_id and route_id not in affected:
                affected.append(route_id)
    if not affected:
        affected = [ROOT_ROUTE_ID]

    runs_root = runs_dir if runs_dir is not None else RUNS_DIR

    # KÖR-7-STAB #176: capture the operator's ACTIVE build snapshot (current.json)
    # BEFORE this build swaps the pointer, so previewShouldRefresh/changed-routes
    # compare against what the preview actually serves - not a historical
    # previousVersion run that may not be active. resolve_generated_dir mirrors
    # the resolution build() uses internally, so the active pointer is read from
    # the same site dir the build writes to.
    generated_root = resolve_generated_dir(generated_dir)
    previous_snapshot = _find_active_build_generated_files_snapshot(
        runs_root, generated_root, site_id
    )

    # Run ids present before this build so a FAILED build's new run can be found
    # for trace-logging in the SystemExit path below.
    runs_before = (
        {run_dir.name for run_dir in runs_root.iterdir() if run_dir.is_dir()}
        if runs_root.exists()
        else set()
    )

    # Reuse the existing project-wide build (immutable build dir + atomic
    # current.json swap on ok|degraded + honest appliedVisibleEffect + new runId
    # + previous runs untouched). build() raises SystemExit(1) on a failed build
    # after writing build-result.json + tracing the failure and leaving the
    # pointer on the previous build. KÖR-7-STAB #176: we still append a targeted-
    # render outcome event so a FAILED targeted build is never silent, then
    # re-raise (we never swallow the failure).
    try:
        target, run_dir = build_fn(
            dossier_path,
            do_build=do_build,
            runs_dir=runs_dir,
            generated_dir=generated_dir,
        )
    except SystemExit:
        failed_run = _find_new_run_dir(runs_root, runs_before)
        if failed_run is not None:
            _append_targeted_render_event(
                failed_run,
                failed_run.name,
                TargetedRenderResult(
                    siteId=site_id,
                    version=_prompt_meta_version(prompt_meta),
                    previousVersion=_prompt_meta_previous_version(prompt_meta),
                    outcome="failed",
                    affectedRoutes=affected,
                    buildStatus="failed",
                    appliedVisibleEffect=False,
                    previewShouldRefresh=False,
                    runId=failed_run.name,
                    notes=[
                        "Targeted build misslyckades (status=failed); "
                        "current.json lämnades på föregående build, ingen "
                        "preview-omstart.",
                    ],
                ),
            )
        raise

    build_result = load_json(run_dir / "build-result.json")
    build_status = build_result.get("status")
    applied_visible_effect = bool(build_result.get("appliedVisibleEffect", False))
    active_build_id = build_result.get("activeBuildId")

    # Per-route change verification: which routes actually differ from the
    # operator's active build snapshot (captured above). Fall back to the
    # historical previous-version snapshot when no active pointer existed yet
    # (e.g. the very first build, or an injected build_fn in tests). None when
    # there is no comparable previous snapshot at all.
    if previous_snapshot is None:
        previous_snapshot = _find_previous_generated_files_snapshot(
            runs_root, run_dir, prompt_meta
        )
    route_map = _route_segment_to_id_map(run_dir)
    changed = changed_routes_between_snapshots(
        previous_snapshot, run_dir / "generated-files", route_map=route_map
    )
    changed_routes = sorted(changed) if changed is not None else []

    preview_should_refresh = decide_preview_refresh(
        build_status=build_status,
        applied_visible_effect=applied_visible_effect,
    )
    if build_status not in ("ok", "degraded"):
        outcome = "skipped"
    elif preview_should_refresh:
        outcome = "applied"
    else:
        outcome = "no-op"

    notes: list[str] = []
    if changed is None:
        notes.append(
            "Kunde inte diffa per-route (saknar jämförbar föregående snapshot); "
            "appliedVisibleEffect från build-result är auktoritativ."
        )
    elif applied_visible_effect:
        unexpected = [
            route
            for route in changed_routes
            if route not in affected and route != "(shared)"
        ]
        if unexpected:
            notes.append(
                "Varning: routes utanför de förväntade påverkade ändrades också: "
                + ", ".join(unexpected)
            )

    result = TargetedRenderResult(
        siteId=site_id,
        version=build_result.get("version"),
        previousVersion=(build_result.get("prompt") or {}).get("previousVersion"),
        outcome=outcome,
        affectedRoutes=affected,
        changedRoutes=changed_routes,
        buildStatus=build_status,
        appliedVisibleEffect=applied_visible_effect,
        previewShouldRefresh=preview_should_refresh,
        activeBuildId=active_build_id,
        runId=run_dir.name,
        notes=notes,
    )
    _append_targeted_render_event(run_dir, run_dir.name, result)
    return result


def _latest_run_id_for_site(runs_root: Path, site_id: str) -> str | None:
    """Return the newest run id whose build-result.json is for ``site_id``.

    Used by the CLI follow-up entrypoint to find the base run a follow-up
    prompt iterates from (the run whose artefakts the Context Assembler reads).
    Reads only build-result.json (read-only) and picks the most recent by mtime;
    returns ``None`` when no run for the site exists yet.
    """
    if not runs_root.exists():
        return None
    candidates = [d for d in runs_root.iterdir() if d.is_dir()]
    candidates.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    for run_dir in candidates:
        try:
            payload = json.loads(
                (run_dir / "build-result.json").read_text(encoding="utf-8")
            )
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if payload.get("siteId") == site_id:
            return run_dir.name
    return None


def run_followup_chain(
    site_id: str,
    follow_up_prompt: str,
    *,
    base_run_id: str | None = None,
    do_build: bool = True,
    runs_dir: Path | None = None,
    generated_dir: str | Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """KÖR-7 follow-up bridge as a real user path (CLI E2E wiring).

    Runs the WHOLE capability follow-up chain for a single follow-up prompt,
    reusing the existing library modules verbatim - no new engine:

        router (kor-6a)  -> classify the message
        context (kor-7a) -> assemble *lagom* much context (artifacts+sections)
        patch  (kor-7b)  -> propose + validate a transient PatchPlan
        apply  (kor-7c)  -> create the next immutable v<N+1> Project Input
        build  (kor-7d)  -> targeted render + version-build + current.json swap
                            (swap only on ok/degraded, via build())

    The chain is honest at every gate: a message with no patchable edit, an
    empty/rejected plan, or an unmapped apply stops BEFORE any build and reports
    why (no false "changed your site"). Only a validated capability patch that
    apply actually writes reaches the targeted build, whose ``appliedVisibleEffect``
    /``previewShouldRefresh`` stay authoritative (a no-op never refreshes preview).

    Mock-safe: every module on the chain is deterministic with no
    ``OPENAI_API_KEY`` (router/context/patch/apply are pure; build falls back to
    the mock brief/plan). Returns a transient dict summary (never a new canonical
    artefakt, builder-profil §3); the per-step trace events are the durable
    record.
    """
    from packages.generation.orchestration.apply import (
        PatchApplyError,
        apply_patch_plan,
    )
    from packages.generation.orchestration.context import (
        ContextPaths,
        assemble_context,
    )
    from packages.generation.orchestration.patch import plan_patches
    from packages.generation.orchestration.router import (
        RouterContext,
        classify_message_with_llm_fallback,
    )

    runs_root = runs_dir if runs_dir is not None else RUNS_DIR
    prompt_inputs_dir = output_dir if output_dir is not None else PROMPT_INPUTS_DIR

    def _result(stage: str, applied: bool, notes: list[str], **extra: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "siteId": site_id,
            "followUpPrompt": follow_up_prompt,
            "baseRunId": base_run_id,
            "stage": stage,
            "applied": applied,
            "notes": notes,
        }
        payload.update(extra)
        return payload

    # 0. Resolve the base run (the version + artefakts the follow-up builds on).
    if base_run_id is None:
        base_run_id = _latest_run_id_for_site(runs_root, site_id)
    if base_run_id is None:
        raise SystemExit(
            f"Follow-up: hittade ingen tidigare run för siteId={site_id!r} under "
            f"{runs_root}. Kör en init-build först (skapar artefakter att bygga vidare på)."
        )

    paths = ContextPaths(runsDir=runs_root, promptInputsDir=prompt_inputs_dir)

    # 1. Router (kor-6a): what kind of message is this, how much context.
    pre_ctx = assemble_context(
        "artifacts_plus_sections", run_id=base_run_id, paths=paths
    )
    route_sections_payload = pre_ctx.payload.get("routeSections")
    route_sections = (
        {
            route: [s for s in ids if isinstance(s, str)]
            for route, ids in route_sections_payload.items()
            if isinstance(ids, list)
        }
        if isinstance(route_sections_payload, dict)
        else {}
    )
    # KÖR-6b: escalate genuinely ambiguous (unclear/long/complex multi_intent)
    # follow-ups to routerModel when OPENAI_API_KEY is set; identical to the
    # deterministic KÖR-6a heuristic without a key (no-key parity preserved).
    decision = classify_message_with_llm_fallback(
        follow_up_prompt,
        context=RouterContext(siteId=site_id, routeSections=route_sections),
    )

    # 2. Context (kor-7a): the router chose a level; honour it (artifacts+sections
    #    for an edit), plus the component registry to validate any capability.
    context = (
        pre_ctx
        if decision.contextLevel == "artifacts_plus_sections"
        else assemble_context(
            decision.contextLevel,
            site_id=site_id,
            run_id=base_run_id,
            paths=paths,
        )
    )
    registry = assemble_context("component_registry", paths=paths)

    # 3. Patch planner (kor-7b): propose + validate. Applies nothing.
    plan = plan_patches(decision, context, registry=registry)

    # 3b. Restyle (visual_style): the patch planner has no patchable edit for a
    #     theme change, but a restyle is a real follow-up. When the router
    #     classified a visual_style edit, extract an EXPLICIT theme directive
    #     (brand/tone) from the prompt and route it through apply so it
    #     materialises as the next version + targeted render. Gated on the
    #     router intent so an incidental colour word in a NON-restyle prompt
    #     (e.g. "lägg till en blå knapp") never restyles the whole site.
    theme_directive = None
    is_restyle = decision.editKind == "visual_style" or any(
        subtask.editKind == "visual_style" for subtask in decision.subtasks
    )
    if is_restyle:
        from packages.generation.followup.theme_directives import (
            extract_theme_directive,
        )

        theme_directive = extract_theme_directive(follow_up_prompt)

    # 3c. Section add (section_add, section_builder role): the patch planner has
    #     no patchable edit for a whole-section add, but it is a real follow-up.
    #     Mirroring 3b's restyle wiring, resolve the sanctioned section type
    #     (carried on componentIntent) to its capability and route it through the
    #     SAME apply path component_add uses (requestedCapabilities +
    #     selectedDossiers.required), so the existing dossier mounts and the
    #     targeted render reflects it. An unknown/unsupported type is an HONEST
    #     no-op with a clear reason - never a faked section.
    added_capabilities: list[str] = []
    section_unsupported: list[dict[str, str]] = []
    is_section_add = decision.editKind == "section_add" or any(
        subtask.editKind == "section_add" for subtask in decision.subtasks
    )
    if is_section_add:
        from packages.generation.followup.section_directives import (
            resolve_section_capabilities,
        )

        section_types: list[str | None] = []
        if decision.editKind == "section_add":
            section_types.append(decision.componentIntent)
        section_types.extend(
            subtask.componentIntent
            for subtask in decision.subtasks
            if subtask.editKind == "section_add"
        )
        added_capabilities, section_unsupported = resolve_section_capabilities(
            section_types
        )

    if not plan.patches and theme_directive is None and not added_capabilities:
        no_edit_note = (
            f"Router: messageKind={decision.messageKind} "
            f"editKind={decision.editKind}; patch-planeraren föreslog inget "
            "att applicera (ingen byggbar capability-patch)."
        )
        stage = "router_no_edit" if decision.editKind == "none" else "plan_empty"
        if is_section_add:
            reasons = "; ".join(
                f"{item['type']}: {item['reason']}" for item in section_unsupported
            ) or "ingen sanktionerad sektionstyp kunde tolkas."
            no_edit_note = (
                "Router klassade en sektionsadd (section_add) men ingen "
                f"sanktionerad/stödd sektionstyp kunde monteras: {reasons}"
            )
            stage = "section_unsupported"
        elif is_restyle:
            no_edit_note = (
                "Router klassade en stiländring (visual_style) men ingen känd "
                "färg/font kunde tolkas ur prompten; ingen ändring."
            )
        return _result(
            stage,
            applied=False,
            notes=[no_edit_note, *plan.notes],
            messageKind=decision.messageKind,
            editKind=decision.editKind,
        )
    if not plan.valid:
        return _result(
            "plan_rejected",
            applied=False,
            notes=[
                "Patch-planeraren avvisade förslaget (rails). Ingen apply, "
                "ingen build.",
                *[f"rejected {r.field}: {r.reason}" for r in plan.rejected],
            ],
            messageKind=decision.messageKind,
            editKind=decision.editKind,
        )

    # 4. Apply (kor-7c): create the next immutable v<N+1> Project Input. A valid
    #    plan whose patch is unmapped writes nothing (all-or-nothing, honest).
    try:
        apply_result = apply_patch_plan(
            plan,
            site_id=site_id,
            follow_up_prompt=follow_up_prompt,
            output_dir=prompt_inputs_dir,
            base_run_id=base_run_id,
            runs_dir=runs_root,
            theme_directive=theme_directive,
            added_capabilities=added_capabilities,
        )
    except PatchApplyError as exc:
        return _result(
            "apply_rejected",
            applied=False,
            notes=[f"Apply avvisade planen: {exc}"],
            messageKind=decision.messageKind,
            editKind=decision.editKind,
        )

    if not apply_result.applied:
        return _result(
            "apply_unmapped" if apply_result.unmapped else "apply_empty",
            applied=False,
            notes=[
                "Apply skrev ingen ny version (all-or-nothing eller tom plan); "
                "ingen build.",
                *apply_result.notes,
            ],
            messageKind=decision.messageKind,
            editKind=decision.editKind,
        )

    # 5. Targeted render + version-build (kor-7d): reuse build_targeted_version,
    #    which reuses build() (immutable build dir + atomic current.json swap on
    #    ok/degraded only + honest appliedVisibleEffect). No new build engine.
    new_version_path = Path(apply_result.projectInputPath)
    # A section_add that surfaced a dedicated visible route (e.g. ["faq"]) has no
    # contentBlocks patch field, so affected_routes_from_apply yields nothing and
    # the targeted layer would default to the home route. Pass the surfaced route
    # ids so the affected-route attribution + per-route change verification line
    # up with the page the section actually landed on (honest signal).
    section_affected_routes = list(
        getattr(apply_result, "sectionRoutesSurfaced", []) or []
    )
    targeted = build_targeted_version(
        new_version_path,
        apply_result=apply_result,
        affected_routes=section_affected_routes or None,
        do_build=do_build,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    return _result(
        "built",
        applied=True,
        notes=[
            f"Applicerade capability-patch -> v{apply_result.version}; "
            f"targeted render outcome={targeted.outcome}.",
            *targeted.notes,
        ],
        messageKind=decision.messageKind,
        editKind=decision.editKind,
        version=apply_result.version,
        previousVersion=apply_result.previousVersion,
        appliedCapabilities=[c.model_dump() for c in apply_result.appliedCapabilities],
        outcome=targeted.outcome,
        affectedRoutes=targeted.affectedRoutes,
        changedRoutes=targeted.changedRoutes,
        buildStatus=targeted.buildStatus,
        appliedVisibleEffect=targeted.appliedVisibleEffect,
        previewShouldRefresh=targeted.previewShouldRefresh,
        runId=targeted.runId,
        projectInputPath=apply_result.projectInputPath,
    )


def main() -> int:
    # Single source of truth: load the repo-root .env so an operator only has to
    # set SAJTBYGGAREN_GENERATED_DIR (and other builder settings) in ONE file.
    # os.environ wins, so a Viewser spawn / shell export / Cloud secret still
    # takes precedence; a missing .env is a no-op (CI/tests unaffected).
    load_repo_root_env()
    parser = argparse.ArgumentParser(
        description=(
            "Build a generated site from a Project Input, or run a follow-up "
            "prompt through the full kor-7 capability chain (--followup)."
        )
    )
    parser.add_argument(
        "--dossier",
        default=None,
        help="Path to the Project Input JSON file (examples/<siteId>.project-input.json).",
    )
    parser.add_argument(
        "--followup",
        default=None,
        metavar="PROMPT",
        help=(
            "Follow-up prompt mode: run router -> context -> patch -> apply "
            "(new immutable v<N+1>) -> targeted render for an EXISTING site. "
            "Requires --site-id. Reuses the kor-7 modules; builds no new engine."
        ),
    )
    parser.add_argument(
        "--site-id",
        default=None,
        help="siteId to follow up on (required with --followup).",
    )
    parser.add_argument(
        "--base-run-id",
        default=None,
        help=(
            "Optional base run id the follow-up iterates from. Defaults to the "
            "newest run for the site."
        ),
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
    parser.add_argument(
        "--allow-prune",
        action="store_true",
        help=(
            "Opt in to the retention sweep (auto_prune_all) before building. "
            "OFF by default so a manual or smoke `--dossier` build NEVER deletes "
            "existing data/prompt-inputs/ sidecars, data/runs/ or .generated/ "
            "previews when SAJTBYGGAREN_MAX_* caps are set in .env. The Viewser "
            "product flow passes this explicitly to keep its retention behaviour."
        ),
    )
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir).resolve() if args.runs_dir else None

    # Follow-up mode: run the whole capability chain for a follow-up prompt.
    if args.followup is not None:
        if not args.site_id:
            print("--followup requires --site-id.", file=sys.stderr)
            return 1
        result = run_followup_chain(
            args.site_id,
            args.followup,
            base_run_id=args.base_run_id,
            do_build=not args.skip_build,
            runs_dir=runs_dir,
            generated_dir=args.generated_dir,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # Build (init) mode.
    if not args.dossier:
        print("--dossier is required (or use --followup with --site-id).", file=sys.stderr)
        return 1
    dossier_path = Path(args.dossier).resolve()
    if not dossier_path.exists():
        print(f"Dossier not found: {dossier_path}", file=sys.stderr)
        return 1

    build(
        dossier_path,
        do_build=not args.skip_build,
        runs_dir=runs_dir,
        generated_dir=args.generated_dir,
        auto_prune=args.allow_prune,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
