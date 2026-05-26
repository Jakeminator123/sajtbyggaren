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
import subprocess
import sys
import time
import urllib.parse
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_renderer_exports = importlib.import_module("packages.generation.build.renderers")
_static_asset_exports = importlib.import_module("packages.generation.build.static_assets")
_dispatcher_exports = importlib.import_module("packages.generation.build.dispatcher")

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
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_TONE_COLOR_TOKENS: dict[str, dict[str, str]] = {
    "grön": {"primary": "#166534", "accent": "#dcfce7"},
    "green": {"primary": "#166534", "accent": "#dcfce7"},
    "blå": {"primary": "#1d4ed8", "accent": "#dbeafe"},
    "blue": {"primary": "#1d4ed8", "accent": "#dbeafe"},
    "varm": {"primary": "#9a3412", "accent": "#fed7aa"},
    "warm": {"primary": "#9a3412", "accent": "#fed7aa"},
    "premium": {"primary": "#312e81", "accent": "#ddd6fe"},
}


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


_PLACEHOLDER_CONTACT_VALID_FIELDS = (
    "phone",
    "email",
    "addressLines",
    # B133 Codex P2 follow-up: ``openingHours`` is also written from the
    # B88 fallback ("Mån-Fre 09:00-17:00" / "Mon-Fri 09:00-17:00") when
    # neither wizard nor scrape supplied a schedule, so it must be in
    # the operator-warning set too.
    "openingHours",
)


def _prompt_meta_placeholder_contact_fields(
    prompt_meta: dict[str, Any] | None,
) -> list[str]:
    """Return validated B133 placeholderContactFields from prompt meta.

    Filters to the known contact-block keys so a malformed sidecar
    cannot smuggle arbitrary strings into build-result.json — Viewser
    reads the list verbatim to render an operator warning.
    """
    if not prompt_meta:
        return []
    raw = prompt_meta.get("placeholderContactFields")
    if not isinstance(raw, list):
        return []
    fields: list[str] = []
    for value in raw:
        if (
            isinstance(value, str)
            and value in _PLACEHOLDER_CONTACT_VALID_FIELDS
            and value not in fields
        ):
            fields.append(value)
    return fields


def _placeholder_contact_warning_message(fields: list[str]) -> str:
    """Human-readable warning string for build-result.json.

    Composes the canonical operator-facing line that Run Details mirrors
    via ``placeholderContactMessage`` so the warning text is consistent
    whether the operator reads the JSON artefakt or the Viewser badge.
    """
    joined = ", ".join(fields)
    return (
        f"Contact fields {joined} are placeholder values - operator "
        "must fill these before publishing."
    )


def _prompt_meta_wizard_must_have(
    prompt_meta: dict[str, Any] | None,
) -> list[str]:
    """Return validated B132 wizardMustHave list from prompt meta.

    Scout-orchestrator merge 2026-05-19: B132 (page intent warnings) and
    B133 (placeholder contact warnings) both add new helpers in this
    section. The two sets of helpers are orthogonal — one reads
    ``placeholderContactFields`` from the sidecar, the other reads
    ``wizardMustHave``. Kept side by side so build_result downstream can
    surface both warnings.
    """
    if not prompt_meta:
        return []
    raw_must_have = prompt_meta.get("wizardMustHave")
    if not isinstance(raw_must_have, list):
        return []

    labels: list[str] = []
    seen: set[str] = set()
    for item in raw_must_have:
        if not isinstance(item, str):
            continue
        label = item.strip()
        if not label or label in seen:
            continue
        labels.append(label)
        seen.add(label)
    return labels


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
    """Returnera alla AssetRef-objekt som finns i Project Input
    (`brand.logo`, `brand.heroImage`, varje item i `gallery`, samt
    `media.favicon` / `media.ogImage` / `media.backgroundVideo`). Tar
    bara med refs där alla fält schemat kräver finns; trasiga refs
    hoppas över så build:en inte kraschar på en korrupt manifest.json."""
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


# Hosts allowed when fetching bytes from ``ref.sourceUrl``. The builder
# must not turn arbitrary Project Input data into an SSRF primitive; only
# the public Vercel Blob host shape emitted by VercelBlobAssetStore is
# valid here. If another remote AssetStore driver is added, add its public
# read host explicitly instead of widening this check.
_ALLOWED_ASSET_FETCH_HOSTS: tuple[str, ...] = (
    "public.blob.vercel-storage.com",
)

# Remote sourceUrl bytes cap. 8 MB is well above the optimized.webp
# budget, but prevents a build from reading an accidentally huge asset.
_REMOTE_ASSET_MAX_BYTES = 8 * 1024 * 1024

# Per-request timeout. A dead blob URL should skip one asset, not block
# the whole build.
_REMOTE_ASSET_TIMEOUT_SEC = 15
_REMOTE_ASSET_CHUNK_BYTES = 64 * 1024


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

        # 1. Disk-lookup först — Local disk har företräde när bytes finns.
        source_dir: Path | None = None
        for candidate in candidate_dirs:
            if (candidate / asset_id).is_dir():
                source_dir = candidate / asset_id
                break

        if source_dir is not None:
            candidates = [
                source_dir / "optimized.webp",
                source_dir / "original.svg",
                source_dir / "original.png",
                source_dir / "original.jpg",
                source_dir / "original.webp",
                source_dir / "original.mp4",
                source_dir / "original.webm",
            ]
            source_file: Path | None = next((c for c in candidates if c.exists()), None)
            if source_file is not None:
                dest = public_uploads / filename
                shutil.copy2(source_file, dest)
                copied += 1
                continue
            # Source-dir finns men ingen variant-fil — fortsätt till
            # sourceUrl-fallback istället för att skippa direkt.
            print(
                f"copy_operator_uploads: asset {asset_id} saknar variant-fil "
                f"i {source_dir}. Försöker sourceUrl-fallback.",
            )

        # 2. Remote-fallback från sourceUrl när disk saknas.
        source_url = ref.get("sourceUrl")
        if isinstance(source_url, str) and source_url.strip():
            cleaned_source_url = source_url.strip()
            if not _is_allowed_asset_source_url(cleaned_source_url):
                print(
                    f"copy_operator_uploads: sourceUrl for asset {asset_id} "
                    f"is not an allowed HTTPS Vercel Blob URL ({cleaned_source_url!r}). "
                    "Skipping asset.",
                )
                continue
            data = _fetch_asset_bytes_from_url(cleaned_source_url)
            if data is None:
                continue
            dest = public_uploads / filename
            dest.write_bytes(data)
            copied += 1
            continue

        # 3. Båda saknas — logga och hoppa över.
        print(
            f"copy_operator_uploads: asset {asset_id} saknas både på disk "
            f"(letade i {candidate_dirs}) och saknar sourceUrl. Hoppar över.",
        )

    return copied


def _normalise_hex_color(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not _HEX_COLOR_RE.fullmatch(cleaned):
        return None
    return cleaned.lower()


def _foreground_for_background(hex_color: str) -> str:
    """Return a high-contrast foreground token for a validated #RRGGBB color."""
    red = int(hex_color[1:3], 16) / 255
    green = int(hex_color[3:5], 16) / 255
    blue = int(hex_color[5:7], 16) / 255

    def linearise(channel: float) -> float:
        if channel <= 0.03928:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    luminance = (
        0.2126 * linearise(red)
        + 0.7152 * linearise(green)
        + 0.0722 * linearise(blue)
    )
    dark_contrast = (luminance + 0.05) / 0.05
    light_contrast = 1.05 / (luminance + 0.05)
    return "#1c1c1a" if dark_contrast >= light_contrast else "#fafaf9"


def _hex_to_hsl(hex_color: str) -> tuple[float, float, float]:
    """Konvertera ``#RRGGBB`` till HSL.

    Returnerar ``(h, s, l)`` där ``h ∈ [0, 360]`` och ``s, l ∈ [0, 100]``.
    Anropare ska redan ha validerat ``hex_color`` mot ``_HEX_COLOR_RE``.

    Implementationen följer standard HSL-formeln (samma som CSS
    ``hsl()``-funktionen och Tailwinds palette-generator). Vi använder
    den för att bygga skalor (``_build_color_scale``) där vi bevarar
    hue + saturation och justerar lightness.
    """
    red = int(hex_color[1:3], 16) / 255
    green = int(hex_color[3:5], 16) / 255
    blue = int(hex_color[5:7], 16) / 255

    cmax = max(red, green, blue)
    cmin = min(red, green, blue)
    delta = cmax - cmin
    lightness = (cmax + cmin) / 2

    if delta == 0:
        hue = 0.0
        saturation = 0.0
    else:
        if lightness in (0.0, 1.0):
            saturation = 0.0
        else:
            saturation = delta / (1 - abs(2 * lightness - 1))
        if cmax == red:
            hue = ((green - blue) / delta) % 6
        elif cmax == green:
            hue = (blue - red) / delta + 2
        else:
            hue = (red - green) / delta + 4
        hue *= 60

    return (hue, saturation * 100, lightness * 100)


def _hsl_to_hex(hue: float, saturation: float, lightness: float) -> str:
    """Konvertera ``(h, s, l)`` till ``#rrggbb``-sträng.

    ``hue ∈ [0, 360]``, ``saturation, lightness ∈ [0, 100]``. Inverterar
    ``_hex_to_hsl`` med tolerans för flyttalsavrundning (alla tre
    värden klampas innan multiplikation till 0-255).
    """
    s = max(0.0, min(100.0, saturation)) / 100
    lum = max(0.0, min(100.0, lightness)) / 100
    h = hue % 360

    c = (1 - abs(2 * lum - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = lum - c / 2

    if h < 60:
        r, g, b = c, x, 0.0
    elif h < 120:
        r, g, b = x, c, 0.0
    elif h < 180:
        r, g, b = 0.0, c, x
    elif h < 240:
        r, g, b = 0.0, x, c
    elif h < 300:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x

    red = max(0, min(255, round((r + m) * 255)))
    green = max(0, min(255, round((g + m) * 255)))
    blue = max(0, min(255, round((b + m) * 255)))
    return f"#{red:02x}{green:02x}{blue:02x}"


# Tailwind-liknande lightness-skala. Värdena valda så att 500-bandet
# ligger nära Tailwind v3:s default-palette (där t.ex. blue-500 har
# L≈53%, slate-500 har L≈48%). 50/100 är extremt ljusa (subtila
# bakgrundstinter), 800/900 är mörka nog för text på ljus bakgrund.
# Saturation-cap används så att hög-mättade input (#ff0000) inte
# producerar neon-aktig 500-band i CTAs — vi vill ha "brand-aware"
# palettes, inte "screaming"-palettes.
_BRAND_SCALE_LIGHTNESS: tuple[tuple[str, float], ...] = (
    ("50", 97.0),
    ("100", 94.0),
    ("200", 86.0),
    ("300", 76.0),
    ("400", 66.0),
    ("500", 56.0),
    ("600", 48.0),
    ("700", 38.0),
    ("800", 28.0),
    ("900", 18.0),
)
_BRAND_SCALE_MAX_SATURATION = 85.0


def _build_color_scale(hex_color: str) -> dict[str, str]:
    """Bygg en 10-stegs Tailwind-liknande palett från en bas-färg.

    Bevarar ``hue`` och ``saturation`` (cap:ad vid 85% för att undvika
    neon-känsla på fullt mättade input som ``#ff0000``), ersätter
    lightness med ``_BRAND_SCALE_LIGHTNESS``. Returnerar en dict
    ``{ "50": "#...", "100": "#...", ..., "900": "#..." }`` som
    ``variant_css`` emitterar som ``--primary-50`` .. ``--primary-900``
    CSS-tokens. Generated render-funktioner kan sedan referera dem
    för subtila bakgrunder (50/100), borders (200/300), accenter
    (500/600) och text på ljus bg (800/900) — utan att hårdkoda hex
    i varje sektion.

    Anropare måste ha validerat ``hex_color`` mot ``_HEX_COLOR_RE``.
    """
    hue, saturation, _lightness = _hex_to_hsl(hex_color)
    capped_saturation = min(saturation, _BRAND_SCALE_MAX_SATURATION)
    return {
        step: _hsl_to_hex(hue, capped_saturation, lightness)
        for step, lightness in _BRAND_SCALE_LIGHTNESS
    }


def _token_overrides_from_project_input(
    project_input: dict[str, Any] | None,
) -> tuple[dict[str, str], list[str]]:
    """Return safe CSS token overrides derived from explicit brand/tone fields."""
    if not isinstance(project_input, dict):
        return {}, []

    overrides: dict[str, str] = {}
    warnings: list[str] = []
    brand = project_input.get("brand") if isinstance(project_input.get("brand"), dict) else {}
    primary_hex_provided = bool(brand.get("primaryColorHex"))
    accent_hex_provided = bool(brand.get("accentColorHex"))
    primary_hex = _normalise_hex_color(brand.get("primaryColorHex"))
    accent_hex = _normalise_hex_color(brand.get("accentColorHex"))
    if primary_hex_provided and primary_hex is None:
        warnings.append("brand.primaryColorHex invalid; variant primary token kept")
    if accent_hex_provided and accent_hex is None:
        warnings.append("brand.accentColorHex invalid; variant accent token kept")

    if primary_hex:
        overrides["primary"] = primary_hex
        overrides["primaryForeground"] = _foreground_for_background(primary_hex)
    if accent_hex:
        overrides["accent"] = accent_hex
        overrides["accentForeground"] = _foreground_for_background(accent_hex)

    if "primary" not in overrides and not primary_hex_provided:
        tone = project_input.get("tone") if isinstance(project_input.get("tone"), dict) else {}
        tone_tokens: dict[str, str] | None = None
        tone_primary = tone.get("primary")
        if isinstance(tone_primary, str):
            tone_tokens = _TONE_COLOR_TOKENS.get(tone_primary.strip().lower())
        # B139 fallback: när tone.primary saknar color-signal (t.ex.
        # generiska wizard-tags som "professionell" / "lugn och
        # förtroendeingivande") får tone.secondary fungera som
        # color-token-källa. Annars läcker en färgsignal som operatören
        # angett i sekundär-position tyst på vägen till variant_css.
        # Primary vinner alltid när den har en signal — secondary
        # fungerar bara som fallback, aldrig som override.
        if tone_tokens is None:
            secondary = tone.get("secondary")
            if isinstance(secondary, list):
                for entry in secondary:
                    if not isinstance(entry, str):
                        continue
                    candidate = _TONE_COLOR_TOKENS.get(entry.strip().lower())
                    if candidate is not None:
                        tone_tokens = candidate
                        break
        if tone_tokens is not None:
            overrides["primary"] = tone_tokens["primary"]
            overrides["primaryForeground"] = _foreground_for_background(
                tone_tokens["primary"]
            )
            if "accent" not in overrides and not accent_hex_provided:
                overrides["accent"] = tone_tokens["accent"]
                overrides["accentForeground"] = _foreground_for_background(
                    tone_tokens["accent"]
                )

    return overrides, warnings


"""Typography palette per variant.

Maps ``variant.id`` to a (display-font, body-font, google-fonts-query)
tuple. Each variant gets a distinct visual character beyond color alone:
warm serif for craft, tight editorial for noir, geometric sans for fit,
classic Georgia-style for trust, etc.

Fallback: when variant.id is not in the table, both fonts fall back to
``Inter`` which matches the starter's pre-typography baseline (Geist
replacement) without breaking the cascade.

`google_query` is the path part after ``css2?`` in the Google Fonts URL
(`family=Fraunces:wght@400;600;700&display=swap`). We assemble the full
URL at emit time so the value remains URL-safe and reviewable in
governance diffs.
"""
_VARIANT_TYPOGRAPHY: dict[str, dict[str, str]] = {
    # local-service-business variants
    "nordic-trust": {
        "display": "'Inter', system-ui, -apple-system, sans-serif",
        "body": "'Inter', system-ui, -apple-system, sans-serif",
        "google_query": "family=Inter:wght@400;500;600;700&display=swap",
        "display_tracking": "-0.02em",
    },
    "warm-craft": {
        "display": "'Fraunces', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.015em",
    },
    "clinical-calm": {
        "display": "'Source Sans 3', system-ui, sans-serif",
        "body": "'Source Sans 3', system-ui, sans-serif",
        "google_query": (
            "family=Source+Sans+3:wght@400;500;600;700&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "midnight-counsel": {
        "display": "'Playfair Display', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Playfair+Display:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.025em",
    },
    "pulse-fit": {
        "display": "'Manrope', system-ui, sans-serif",
        "body": "'Manrope', system-ui, sans-serif",
        "google_query": "family=Manrope:wght@400;500;700;800&display=swap",
        "display_tracking": "-0.03em",
    },
    # ecommerce-lite variants
    "clean-store": {
        "display": "'Inter', system-ui, sans-serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": "family=Inter:wght@400;500;600;700&display=swap",
        "display_tracking": "-0.02em",
    },
    "earth-wellness": {
        "display": "'Cormorant Garamond', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Cormorant+Garamond:wght@400;500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "mono-tech": {
        "display": "'JetBrains Mono', ui-monospace, monospace",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=JetBrains+Mono:wght@500;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.04em",
    },
    "noir-editorial": {
        "display": "'Bodoni Moda', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Bodoni+Moda:opsz,wght@6..96,500;6..96,700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.025em",
    },
    "street-vivid": {
        "display": "'Space Grotesk', system-ui, sans-serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Space+Grotesk:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.035em",
    },
}

_TYPOGRAPHY_FALLBACK: dict[str, str] = {
    "display": "'Inter', system-ui, sans-serif",
    "body": "'Inter', system-ui, sans-serif",
    "google_query": "family=Inter:wght@400;500;600;700&display=swap",
    "display_tracking": "-0.02em",
}


# Fas 4 — tone-driven typography overlay.
#
# Mappar ``tone.primary`` (en fri sträng från Site Brief / project-input)
# till en typografi-palett som överrider variantens default. Detta är
# additivt och OPT-IN: när ``tone.primary`` saknas eller inte matchar
# någon nyckel här används variantens egen typografi exakt som idag.
#
# Designprincip — vi mappar bara på TONE-NYCKLAR som är tydligt
# kopplade till en visuell karaktär. Generiska ord som "professional"
# eller "trustworthy" lämnar vi orörda — de skulle göra mappningen
# luddig (snart sagt varje sajt kallar sig professional) och variant-
# defaultsen är redan tunade för "trustworthy" som baseline.
#
# Nyckeln matchas case-insensitive efter ``.strip().lower()``. Svenska
# och engelska former listas separat så vi inte hash-collision:ar med
# fel mapping.
# Wizard-strängar (``TONE_OPTIONS`` i
# ``apps/viewser/components/discovery-wizard/wizard-constants.ts``) är
# på svenska och kan vara multi-word ("Lugn och förtroendeingivande").
# ``_TONE_TYPOGRAPHY`` använder semantiska engelska single-word-keys
# ("calm", "playful"). Utan översättning matchar wizard-tags aldrig
# → Sprint A.2:s typografi-overlay triggas inte för svenska operatörer.
#
# Den här tabellen är översättningslagret. Keys är ``.strip().lower()``-
# normaliserade wizard-strängar; values är semantiska keys i
# ``_TONE_TYPOGRAPHY``. Att hålla dessa separata (istället för att
# duplicera font-paletten 7 gånger) gör att framtida paletter-tweaks
# bara behöver göras på ett ställe.
#
# Synkronisera den här tabellen med ``TONE_OPTIONS`` i wizard-
# constants när nya ton-alternativ läggs till. ``tests/test_builder_smoke``
# har en täckningskoll som garanterar att varje wizard-tag mappar till
# en känd ``_TONE_TYPOGRAPHY``-key.
_TONE_KEY_ALIASES: dict[str, str] = {
    # Wizard ``TONE_OPTIONS`` (svenska multi-word) → semantiska keys.
    "professionell": "modern",
    "varm och personlig": "warm",
    "lekfull": "playful",
    "exklusiv / lyxig": "luxury",
    "rak och enkel": "modern",
    "modern och teknisk": "tech",
    "lugn och förtroendeingivande": "calm",
    # Vanliga briefModel-output på engelska som tydligt mappar mot en
    # specifik palett. ``professional`` och ``trustworthy`` lämnas
    # MEDVETET bort — de är generiska och får bättre resultat med
    # variant-defaulten (befintlig kontrakt-test i test_builder_smoke).
    "calm and trustworthy": "calm",
    "warm and personal": "warm",
    "playful and energetic": "playful",
    "exclusive": "luxury",
    "luxurious": "luxury",
    "clean and simple": "modern",
    "modern and technical": "tech",
}


_TONE_TYPOGRAPHY: dict[str, dict[str, str]] = {
    # CALM / WELLNESS — elegant serif för rubriker, neutral sans för
    # body. Passar hudvård, spa, terapi, yoga, mindfulness.
    "calm": {
        "display": "'Cormorant Garamond', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Cormorant+Garamond:wght@400;500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "lugn": {
        "display": "'Cormorant Garamond', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Cormorant+Garamond:wght@400;500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "wellness": {
        "display": "'Cormorant Garamond', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Cormorant+Garamond:wght@400;500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    # BOLD / TECH — geometrisk sans med tight tracking. Passar SaaS,
    # konsult, byggteknik, modern e-handel.
    "bold": {
        "display": "'Space Grotesk', system-ui, sans-serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Space+Grotesk:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.035em",
    },
    "modern": {
        "display": "'Space Grotesk', system-ui, sans-serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Space+Grotesk:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.035em",
    },
    "tech": {
        "display": "'Space Grotesk', system-ui, sans-serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Space+Grotesk:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.035em",
    },
    # PLAYFUL / WARM — rundad sans + mjukare body. Passar barn-
    # verksamhet, café, kreativa småföretag.
    "playful": {
        "display": "'Quicksand', system-ui, sans-serif",
        "body": "'Nunito', system-ui, sans-serif",
        "google_query": (
            "family=Quicksand:wght@500;600;700"
            "&family=Nunito:wght@400;500;600&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "warm": {
        "display": "'Quicksand', system-ui, sans-serif",
        "body": "'Nunito', system-ui, sans-serif",
        "google_query": (
            "family=Quicksand:wght@500;600;700"
            "&family=Nunito:wght@400;500;600&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "friendly": {
        "display": "'Quicksand', system-ui, sans-serif",
        "body": "'Nunito', system-ui, sans-serif",
        "google_query": (
            "family=Quicksand:wght@500;600;700"
            "&family=Nunito:wght@400;500;600&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    # PREMIUM / EDITORIAL — high-contrast display serif. Passar lyx,
    # arkitektur, gallerier, fine dining.
    "premium": {
        "display": "'Playfair Display', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Playfair+Display:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.025em",
    },
    "editorial": {
        "display": "'Playfair Display', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Playfair+Display:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.025em",
    },
    "luxury": {
        "display": "'Playfair Display', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Playfair+Display:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.025em",
    },
}


def _typography_for_variant(variant: dict) -> dict[str, str]:
    """Return the typography palette for a variant, with a safe fallback.

    Unknown variant IDs degrade gracefully to Inter so an experimental
    variant added without a typography entry still renders, just without
    the bespoke font pairing.
    """
    return _VARIANT_TYPOGRAPHY.get(variant.get("id", ""), _TYPOGRAPHY_FALLBACK)


def _normalize_tone_key(raw: str) -> str:
    """Normalisera en tone-sträng till en semantisk ``_TONE_TYPOGRAPHY``-key.

    Pipelinen är:
      1. ``.strip().lower()`` så case/whitespace inte spelar roll
      2. Slå upp i ``_TONE_KEY_ALIASES`` (wizard-strängar → semantiska
         keys, t.ex. ``"lekfull"`` → ``"playful"``)
      3. Returnera resultatet — om ingen alias matchar returneras den
         normaliserade strängen oförändrad (så engelska keys som redan
         är semantiska, t.ex. ``"calm"``, fortsatt fungerar direkt)

    Den här funktionen är single source of truth för "är denna tone-
    sträng matchbar?" — använd den i alla nya konsumenter (Sprint B/3
    hero-routing m.fl.) istället för att duplicera alias-tabellen.
    """
    key = raw.strip().lower()
    return _TONE_KEY_ALIASES.get(key, key)


def _typography_overlay_for_tone(
    project_input: dict[str, Any] | None,
) -> dict[str, str] | None:
    """Returnera en typografi-palett baserad på ``tone.primary`` om den
    matchar en känd nyckel i ``_TONE_TYPOGRAPHY``, annars ``None``.

    När ``None`` returneras använder ``variant_css`` variant-defaulten
    från ``_VARIANT_TYPOGRAPHY`` — så vi lägger ALDRIG på en font-
    override när vi inte har en stark anledning. Detta gör Sprint A.2
    opt-in: existerande projekt utan tone.primary får exakt samma
    output som idag.

    Wizard-strängar (svenska multi-word, t.ex. "Lugn och
    förtroendeingivande") normaliseras via ``_TONE_KEY_ALIASES`` så
    Sprint A.2:s overlay triggas även när operatören väljer ton via
    chips istället för att skriva engelska keys manuellt.
    """
    if not isinstance(project_input, dict):
        return None
    tone = project_input.get("tone")
    if not isinstance(tone, dict):
        return None
    primary = tone.get("primary")
    if not isinstance(primary, str):
        return None
    key = _normalize_tone_key(primary)
    return _TONE_TYPOGRAPHY.get(key)


def _motion_css_block(level: str) -> str:
    """Return a CSS block that applies subtle entry animations on the
    first paint of every ``<section>``. The block is empty for
    ``level == "none"``.

    All animations are gated behind ``prefers-reduced-motion: no-preference``
    so operators on reduced-motion settings see a static page. The
    stagger uses ``nth-of-type`` so the sequence reads top-to-bottom
    without any JavaScript or scroll-observer.

    Levels:

    - ``none``     : no animations emitted
    - ``subtle``   : 600ms fade-in only, 80ms stagger across the first
                     six sections. Reads as "polished but quiet" — fits
                     trust, clinical, calm vibes.
    - ``expressive``: 700ms fade-up + 12px translate, 120ms stagger.
                     Suits warm-craft, pulse-fit, noir, street vibes
                     where a hint of motion reinforces the brand.
    """
    if level == "none":
        return ""

    if level == "expressive":
        duration_ms = 700
        translate_y = "12px"
        stagger_ms = 120
    else:
        # default to subtle for unknown values (e.g. "normal" from older
        # variants) so we never crash on unexpected enum values.
        duration_ms = 600
        translate_y = "0"
        stagger_ms = 80

    stagger_rules = "\n".join(
        f"  main > section:nth-of-type({i}) {{ animation-delay: {stagger_ms * (i - 1)}ms; }}"
        for i in range(1, 7)
    )

    # Fas 2.2 — utöka motion-blocket med scroll-driven animations. När
    # browser:n stödjer ``animation-timeline: view()`` (Chrome/Edge 115+,
    # Opera 101+) får varje sektion utöver de första sex en mjuk fade-in
    # vid scroll, utan JavaScript. Safari + Firefox ignorerar @supports-
    # block och visar sektionerna direkt — degraderar snyggt.
    #
    # ``view()``-axeln binder animationen till element-positionen i
    # viewporten: 0% = ovan viewport, 100% = nedanför. Vi spelar bara
    # animationen i första 30%-fönstret (entering bottom) så sektionen
    # är fullt synlig innan animationen är klar.
    scroll_translate = translate_y if translate_y != "0" else "8px"
    scroll_block = (
        "  @supports (animation-timeline: view()) {\n"
        "    @keyframes sajtbyggaren-section-scroll-enter {\n"
        f"      from {{ opacity: 0; transform: translateY({scroll_translate}); }}\n"
        "      to { opacity: 1; transform: translateY(0); }\n"
        "    }\n"
        "    main > section:nth-of-type(n+7) {\n"
        "      animation: sajtbyggaren-section-scroll-enter linear both;\n"
        "      animation-timeline: view();\n"
        "      animation-range: entry 0% entry 30%;\n"
        "    }\n"
        "  }\n"
    )

    return (
        "@media (prefers-reduced-motion: no-preference) {\n"
        "  @keyframes sajtbyggaren-section-enter {\n"
        f"    from {{ opacity: 0; transform: translateY({translate_y}); }}\n"
        "    to { opacity: 1; transform: translateY(0); }\n"
        "  }\n"
        "  main > section {\n"
        f"    animation: sajtbyggaren-section-enter {duration_ms}ms cubic-bezier(0.16, 1, 0.3, 1) both;\n"
        "  }\n"
        f"{stagger_rules}\n"
        f"{scroll_block}"
        "}\n"
    )


def variant_css(
    variant: dict,
    token_overrides: dict[str, str] | None = None,
    *,
    typography_overlay: dict[str, str] | None = None,
) -> str:
    tokens = variant["tokens"]
    color = dict(tokens["color"])
    if token_overrides:
        for token_name in (
            "primary",
            "primaryForeground",
            "accent",
            "accentForeground",
        ):
            override = token_overrides.get(token_name)
            if override:
                color[token_name] = override
    radius = tokens["radius"]
    spacing = tokens["spacing"]
    # Fas 4 — tone-driven typography overlay. När anroparen har
    # extraherat en känd ``tone.primary`` via ``_typography_overlay_
    # for_tone`` ersätter vi variantens default-typografi med den.
    # Annars (vanligaste fallet, inkl. alla befintliga tester) faller
    # vi tillbaka till ``_typography_for_variant`` och CSS-outputen
    # blir byte-identisk med innan denna kwarg infördes.
    typography = typography_overlay if typography_overlay else _typography_for_variant(variant)
    # Google Fonts import — placed in @import at the top of the variant
    # block. `&display=swap` ensures the page renders with fallback fonts
    # while the webfont loads, avoiding FOIT. We use Google's HTTPS CDN
    # which is reliable enough for the MVP; a future iteration may swap
    # to `next/font/google` for self-hosting + zero FOUC.
    font_import = (
        f"@import url('https://fonts.googleapis.com/css2?{typography['google_query']}');\n"
    )
    motion_level = (
        tokens.get("motion", {}).get("level", "subtle")
        if isinstance(tokens.get("motion"), dict)
        else "subtle"
    )
    motion_block = _motion_css_block(motion_level)
    # Fas 4 — brand color scales (Tailwind-liknande 10-stegs palettes
    # genererade från primary/accent). Vi emitterar dem som CSS-tokens
    # så render_*-funktionerna kan referera ``var(--primary-50)`` för
    # subtila sektion-bakgrunder, ``var(--primary-100)`` för card-
    # hovers, ``var(--primary-600)`` för CTAs och ``var(--primary-900)``
    # för text — istället för att hårdkoda en enda mid-tone "primary"
    # överallt och få "alla sajter ser ut likadana"-effekten oavsett
    # brand. Skalan tar hue + (cap:ad) saturation från base-färgen och
    # varierar bara lightness deterministiskt. Generated css-output är
    # additiv: existerande ``--primary`` / ``--accent`` ligger kvar
    # exakt som idag så render-funktioner som inte uppgraderats än
    # fortsätter rendera identiskt.
    primary_scale = _build_color_scale(color["primary"]) if _HEX_COLOR_RE.fullmatch(color["primary"]) else None
    accent_scale = _build_color_scale(color["accent"]) if _HEX_COLOR_RE.fullmatch(color["accent"]) else None
    scale_block = ""
    if primary_scale:
        scale_block += "".join(
            f"  --primary-{step}: {value};\n" for step, value in primary_scale.items()
        )
    if accent_scale:
        scale_block += "".join(
            f"  --accent-{step}: {value};\n" for step, value in accent_scale.items()
        )

    return (
        font_import
        + ":root {\n"
        f"  --background: {color['background']};\n"
        f"  --foreground: {color['foreground']};\n"
        f"  --muted: {color['muted']};\n"
        f"  --border: {color['border']};\n"
        f"  --primary: {color['primary']};\n"
        f"  --primary-foreground: {color['primaryForeground']};\n"
        f"  --accent: {color['accent']};\n"
        f"  --accent-foreground: {color['accentForeground']};\n"
        + scale_block
        + f"  --radius-sm: {radius['sm']};\n"
        f"  --radius-md: {radius['md']};\n"
        f"  --radius-lg: {radius['lg']};\n"
        f"  --section-spacing: {spacing['section']};\n"
        f"  --container-width: {spacing['container']};\n"
        f"  --font-display: {typography['display']};\n"
        f"  --font-body: {typography['body']};\n"
        f"  --display-tracking: {typography['display_tracking']};\n"
        "}\n"
        # Apply font families at the element level so existing render_*
        # functions don't need a className change — body inherits the
        # body font; headings inherit the display font with bespoke
        # letter-spacing per variant.
        #
        # Fas 3.1 — typografiska OpenType-features per kontext:
        #   * body  : ``ss01`` (stylistic set 1 — Inter:s grotesque-alts),
        #             ``cv02`` ``cv03`` ``cv11`` (open digit + bättre kolon),
        #             ``cv05`` ``cv10`` (alternativa l/L),
        #             ``ss03`` (curl-alternativ), ``calt`` (contextual
        #             alternates för auto-ligature i webfonts).
        #   * h1-h4 : ``ss02`` (display-orienterad stylistic-set när
        #             tillgänglig), ``cv11``. Headlines håller
        #             tab-alignment med rubrik-siffror så "2026" och
        #             "1 999 kr" radas snyggt.
        #   * pris/data: ``.font-tabular`` utility-class (tabular-nums +
        #             lining-nums) som render_*-helpers kan applicera
        #             på pristext, statistik, datum.
        #
        # Browsers som inte stödjer en feature ignorerar den tyst.
        # Google Fonts levererar alla features ovan för Inter, DM Sans,
        # Manrope och Plus Jakarta Sans (våra defaults).
        "body {\n"
        "  font-family: var(--font-body);\n"
        "  font-feature-settings: \"ss01\", \"ss03\", \"cv02\", \"cv03\", \"cv05\", \"cv10\", \"cv11\", \"calt\";\n"
        "  font-variant-ligatures: common-ligatures contextual;\n"
        "}\n"
        "h1, h2, h3, h4 {\n"
        "  font-family: var(--font-display);\n"
        "  letter-spacing: var(--display-tracking);\n"
        "  font-feature-settings: \"ss02\", \"cv11\";\n"
        "  font-variant-numeric: lining-nums;\n"
        "}\n"
        ".font-tabular {\n"
        "  font-variant-numeric: tabular-nums lining-nums;\n"
        "  font-feature-settings: \"tnum\", \"lnum\";\n"
        "}\n"
        # Fas 3.3 — CSS-only parallax. Bilden zoomas 1.0 → 1.08 över
        # hero-exit-fönstret när browser:n stödjer animation-timeline.
        # ``contain``-fönstret startar när bilden börjar lämna viewporten
        # (cover 50%) och slutar när den lämnar helt (cover 100%).
        # Detta gör att zoomen sker när användaren scrollar förbi hero
        # — exakt som Apple och Stripe-sajter, men utan JavaScript.
        # Safari + Firefox ignorerar @supports och visar statisk bild.
        "@supports (animation-timeline: view()) {\n"
        "  @media (prefers-reduced-motion: no-preference) {\n"
        "    @keyframes sajtbyggaren-hero-parallax {\n"
        "      from { transform: scale(1.0); }\n"
        "      to { transform: scale(1.08); }\n"
        "    }\n"
        "    .parallax-hero {\n"
        "      animation: sajtbyggaren-hero-parallax linear both;\n"
        "      animation-timeline: view();\n"
        "      animation-range: cover 0% cover 100%;\n"
        "      will-change: transform;\n"
        "    }\n"
        "  }\n"
        "}\n"
        # Sprint 1.4 — print-styles. Småföretagssajter skrivs ofta ut
        # (offert-sidor, om-oss, kontakt). Default Tailwind print:n är
        # plain-white men släpper igenom flera hög-impact-element som
        # förstör utskriften:
        #
        #   * sticky header + footer dyker upp på varje sida-sida
        #   * background-gradienter slukar svart-bläck
        #   * scroll-animations triggas inte i print men reserverar
        #     ändå space (de börjar med opacity:0)
        #   * hover-shadows ger spöktryck längs kortets kanter
        #
        # Vi nollar dessa explicit. Ingen branch-specifik logik —
        # samma regler funkar för alla sajter eftersom de matchar
        # generiska klasser (sticky, scroll-anim, bg-gradient).
        "@media print {\n"
        "  *, *::before, *::after {\n"
        "    background: transparent !important;\n"
        "    color: black !important;\n"
        "    box-shadow: none !important;\n"
        "    text-shadow: none !important;\n"
        "  }\n"
        "  header, footer, nav { display: none !important; }\n"
        "  a, a:visited { text-decoration: underline; color: black !important; }\n"
        "  a[href]::after { content: \" (\" attr(href) \")\"; font-size: 80%; }\n"
        "  a[href^=\"#\"]::after, a[href^=\"javascript:\"]::after { content: \"\"; }\n"
        "  img { max-width: 100% !important; page-break-inside: avoid; }\n"
        "  .scroll-anim, .scroll-anim-stagger > * {\n"
        "    opacity: 1 !important;\n"
        "    transform: none !important;\n"
        "    animation: none !important;\n"
        "  }\n"
        "  .parallax-hero { animation: none !important; transform: none !important; }\n"
        "  h2, h3 { page-break-after: avoid; }\n"
        "  p, blockquote { orphans: 3; widows: 3; }\n"
        "  blockquote, pre { page-break-inside: avoid; }\n"
        "}\n"
        + motion_block
    )


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
    marker = "/* sajtbyggaren-variant-tokens:start */"
    end = "/* sajtbyggaren-variant-tokens:end */"
    if marker in original:
        before, _, rest = original.partition(marker)
        _, _, after = rest.partition(end)
        base_contents = f"{before}{after}".rstrip()
    else:
        base_contents = original.rstrip()
    # Append last so starter defaults earlier in globals.css cannot win the cascade.
    new_contents = f"{base_contents}\n\n{marker}\n{block}{end}\n"
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


_OPERATOR_DIRECTIVE_NOTE_PREFIX = "Operator: "


def _apply_operator_directive_note(brief: dict, dossier: dict) -> None:
    """Gap 5: Prepend wizardens ``directives.notesForPlanner`` på SiteBrief.

    Operatörens fritext-orientering kommer från
    ``apps/viewser/components/discovery-wizard/wizard-payload.ts:496-514``
    (concat:erar ``answers.specialRequests`` + USP-listan). Resolvern har
    persisterat den till ``project_input.directives.notesForPlanner`` (cap
    1024 chars). Här prepend:ar vi den med prefix ``"Operator: "`` framför
    briefens egen ``notesForPlanner`` så ``planningModel`` ser
    operator-intent först. Tom/saknad directive = no-op (briefens fält
    rörs inte).
    """
    directives = dossier.get("directives")
    if not isinstance(directives, dict):
        return
    raw_note = directives.get("notesForPlanner")
    if not isinstance(raw_note, str):
        return
    note = raw_note.strip()
    if not note:
        return
    existing = brief.get("notesForPlanner")
    operator_block = f"{_OPERATOR_DIRECTIVE_NOTE_PREFIX}{note}"
    if isinstance(existing, str) and existing.strip():
        brief["notesForPlanner"] = f"{operator_block}\n\n{existing}"
    else:
        brief["notesForPlanner"] = operator_block


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
    page_intent_warnings: list[dict[str, Any]] | None,
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
    print("Writing pages: " + ", ".join(routes_to_write) + " and layout")
    paths_written = write_pages(
        target,
        dossier,
        scaffold_routes,
        dossier_routes,
        extra_routes=wizard_extra_routes or None,
        variant_id=variant.get("id") if isinstance(variant, dict) else None,
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
        site_plan.get("pageIntentWarnings"),
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
