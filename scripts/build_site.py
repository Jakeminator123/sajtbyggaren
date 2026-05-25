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
import functools
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

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
        contact_idx = next(
            (i for i, (href, _label) in enumerate(items) if href == "/kontakt"),
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


def render_layout(
    dossier: dict,
    dossier_routes: list[str],
    *,
    scaffold_default_routes: list[dict] | None = None,
    contact_path: str | None = None,
    extra_routes: list[dict] | None = None,
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
    nav_items = _nav_items_from_scaffold(
        scaffold_default_routes,
        dossier_routes,
        extra_routes,
    )
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
        # Fas 2.5 — snyggare default-monogram. Två-tons gradient som
        # förgrund (primary → accent) och en mjuk shadow-ring så symbolen
        # står ut även mot ljusa bakgrunder. tracking-wider gör att två
        # bokstäver inte trycks ihop. samma gradient används i footer:n
        # för konsistens.
        monogram_text = _jsx_safe_string(company["name"][:2])
        header_logo_jsx = (
            '              <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[color:var(--primary)] to-[color:var(--accent)] text-[color:var(--primary-foreground)] text-[11px] font-bold uppercase tracking-wider shadow-sm ring-1 ring-[color:var(--primary)]/20">'
            f"{monogram_text}</span>"
        )
        footer_logo_jsx = (
            '              <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-[color:var(--primary)] to-[color:var(--accent)] text-[color:var(--primary-foreground)] text-xs font-bold uppercase tracking-wider shadow-sm mb-2">'
            f"{monogram_text}</span>"
        )

    # Fas 1.6 — favicon + Open Graph + Apple touch-icon. Vi använder
    # Next.js Metadata API:s `icons` och `openGraph.images` så headern
    # genereras automatiskt utan att vi behöver injicera <link>/<meta>
    # i body:n. Saknas asset:n hoppas fältet — Next.js default-favicon
    # (eller den som ligger i ``public/favicon.ico``) tar över.
    favicon_asset = resolve_media_asset(dossier, "favicon")
    og_image_asset = resolve_media_asset(dossier, "ogImage")
    metadata_extras: list[str] = []
    if isinstance(favicon_asset, dict) and favicon_asset.get("filename"):
        favicon_url = "/uploads/" + str(favicon_asset["filename"])
        # ``apple-touch-icon`` ska helst vara 180×180 PNG. Vi använder
        # samma asset eftersom operatör-uppladdade favicons normalt har
        # högre upplösning än 32×32. Browsern resize:ar utan tappad kvalitet.
        metadata_extras.append(
            "  icons: {\n"
            f"    icon: {_js_string_literal(favicon_url)},\n"
            f"    apple: {_js_string_literal(favicon_url)},\n"
            "  },\n"
        )
    # Sprint 1.5 — använd operator-uppladdad og-image om den finns,
    # annars fallback till generated SVG-kort (skrivs av write_pages
    # till public/og-image-fallback.svg). På så sätt har VARJE genererad
    # sajt en delningsfärdig preview-bild från första bygget.
    if isinstance(og_image_asset, dict) and og_image_asset.get("filename"):
        og_url = "/uploads/" + str(og_image_asset["filename"])
        og_alt = og_image_asset.get("alt") or company["tagline"] or company["name"]
        og_image_type_block = ""
    else:
        og_url = "/og-image-fallback.svg"
        og_alt = company["tagline"] or company["name"]
        # SVG-fallback: explicit ``type`` så Next.js Metadata API
        # serialiserar det som image/svg+xml i meta-taggen. Vissa
        # äldre social-parsers använder type-hinten istället för att
        # sniffa MIME från Content-Type.
        og_image_type_block = '        type: "image/svg+xml",\n'
    metadata_extras.append(
        "  openGraph: {\n"
        f"    title: {_js_string_literal(company['name'])},\n"
        f"    description: {_js_string_literal(company['tagline'])},\n"
        "    images: [\n"
        "      {\n"
        f"        url: {_js_string_literal(og_url)},\n"
        f"        alt: {_js_string_literal(og_alt)},\n"
        "        width: 1200,\n"
        "        height: 630,\n"
        f"{og_image_type_block}"
        "      },\n"
        "    ],\n"
        "  },\n"
        "  twitter: {\n"
        '    card: "summary_large_image",\n'
        f"    title: {_js_string_literal(company['name'])},\n"
        f"    description: {_js_string_literal(company['tagline'])},\n"
        f"    images: [{_js_string_literal(og_url)}],\n"
        "  },\n"
    )
    metadata_extras_block = "".join(metadata_extras)

    # Fas 2.4 — themeColor + viewport. ``theme-color`` påverkar mobil
    # adress-fält och Android task-switcher; vi använder brand.primaryColorHex
    # när den finns och faller tillbaka till ett neutralt ljust värde
    # som matchar default --background. Detta gör att mobilen visuellt
    # ankrar mot sajtens identitet redan innan första paint.
    brand = dossier.get("brand") or {}
    primary_hex_raw = (
        brand.get("primaryColorHex") if isinstance(brand, dict) else None
    )
    theme_color_hex = _normalise_hex_color(primary_hex_raw) or "#ffffff"
    viewport_block = (
        "\n"
        "export const viewport: Viewport = {\n"
        f"  themeColor: {_js_string_literal(theme_color_hex)},\n"
        "};\n"
        "\n"
    )

    return (
        'import type { Metadata, Viewport } from "next";\n'
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
        f"{metadata_extras_block}"
        "};\n"
        f"{viewport_block}"
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
        # Sprint 1.1 — preconnect + dns-prefetch till Google Fonts.
        # ``variant_css`` skickar ett ``@import url(fonts.googleapis.com)``
        # in i globals.css; preconnect:en låter browsern öppna TCP +
        # TLS-handskakningar parallellt med HTML-parsningen, vilket
        # raderar 300-700 ms från LCP enligt webvitals.
        #
        # `crossOrigin="anonymous"` på `fonts.gstatic.com` är obligatoriskt
        # eftersom font-filerna serveras med CORS — utan attributet öppnar
        # browsern en ny anslutning för font-fetchen och preconnect-en gör
        # ingenting. Detta är samma mönster Google själv dokumenterar.
        #
        # Sprint 2.1 — JSON-LD LocalBusiness. Inline-script i <head>
        # så Google + Bing + DuckDuckGo plockar upp markeringen direkt
        # vid första crawl. dangerouslySetInnerHTML är säkert här
        # eftersom innehållet är förseraliserad JSON med ``</`` →
        # ``<\/``-escape (se _render_structured_data_jsonld).
        "      <head>\n"
        '        <link rel="preconnect" href="https://fonts.googleapis.com" />\n'
        '        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />\n'
        '        <link rel="dns-prefetch" href="https://fonts.googleapis.com" />\n'
        '        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: '
        + _js_string_literal(_render_structured_data_jsonld(dossier))
        + " }} />\n"
        # Sprint 5 — runtime CSS-token-listener. Tar emot postMessage
        # från Sajtbyggarens Site Inspector (TokensTab) och uppdaterar
        # CSS custom properties direkt på <html>-elementet, vilket
        # låter operatören se färgändringar utan en ny build.
        #
        # Säkerhetsmodell:
        #   * Strikt event-type-filter (``"sajtbyggaren:set-token"``).
        #     Vi accepterar inte vilket meddelande som helst — bara
        #     vårt eget namespace, så random extensions och tredje
        #     parts iframes kan inte påverka sajten.
        #   * Värdet valideras med en exakt ``#RRGGBB`` regex
        #     (hex-färg). Övriga payloads ignoreras tyst.
        #   * Token-namnet whitelist:as (primary/accent/background/
        #     foreground) så ingen kan injicera arbiträra CSS-vars
        #     som ``--font-family-system`` eller liknande.
        #   * Värsta-fall vid missbruk: sajten ser tillfälligt ful
        #     ut i den browser där meddelandet skickades. Ingen
        #     XSS, ingen exfiltration, ingen persistence — page
        #     reload återställer canonical.
        #
        # Scriptet är hårdkodad konstant — innehåller ingen operator-
        # data — så ``dangerouslySetInnerHTML`` är säkert.
        "        <script dangerouslySetInnerHTML={{ __html: "
        + _js_string_literal(_RUNTIME_TOKEN_LISTENER_JS)
        + " }} />\n"
        "      </head>\n"
        '      <body className="min-h-full flex flex-col bg-[color:var(--background)] text-[color:var(--foreground)]">\n'
        # Sprint 2.5 — skip-link. Visuellt dolda tills den får fokus
        # (tab från adressfältet) sen popup:ar den högst upp till
        # vänster med stark kontrast. Detta är WCAG 2.1 SC 2.4.1
        # ("Bypass Blocks") och en av de få a11y-features som även
        # tangentbordsanvändare utan screen-reader använder dagligen.
        # `focus:not-sr-only` är den standardiserade Tailwind-pattern
        # för exakt detta beteende.
        '        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[color:var(--primary)] focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-[color:var(--primary-foreground)] focus:shadow-lg focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-[color:var(--primary)]">Hoppa till innehållet</a>\n'
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
        # Sprint 2.4/2.5 — skip-link-mål.
        # Varje page-renderer (render_home, render_services, …) har
        # redan en egen ``<main>``-tag. Dubbla ``<main>``-element är
        # ogiltig HTML och förvirrar screen-readers, så layout-
        # wrappern stannar som ``<div>``. ``id="main-content"`` matchar
        # skip-link:en ovan och ``tabIndex={-1}`` gör att fokus
        # verkligen flyttas dit när användaren aktiverar länken
        # (annars hoppar fokus tillbaka till body i Chromium-baserade
        # browsers eftersom <div> inte är fokuserbar by default).
        '        <div id="main-content" tabIndex={-1} className="flex-1 outline-none">{children}</div>\n'
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


def render_section_hero(
    dossier: dict,
    *,
    dossier_routes: list[str],
    listing_route: dict | None,
    contact_path: str,
    variant_id: str | None,
) -> str:
    """Render the hero section for the home route.

    Combines two visual elements that always appear at the top of the
    home page:

      1. Optional operator-uploaded hero image banner (rendered when
         ``dossier.brand.heroImage.filename`` is set).
      2. Variant-aware hero block with CTA, location tag, USPs and
         optional background video, dispatched through
         ``_render_hero_block`` based on ``_hero_style_for`` (which
         consults ``directives.layoutHint`` first, then
         ``_HERO_STYLE_BY_VARIANT`` and finally
         ``_HERO_STYLE_BY_TONE``).

    Path B step 1 (GAP-backend-path-b-section-renderer): this function
    is the first per-section renderer extracted from ``render_home``.
    It must produce byte-identical output to the inline implementation
    it replaces — verified against the LSB / commerce / restaurant
    snapshots taken before the extraction. ``render_home`` still owns
    icon-collection (``_collect_icons_for_pages`` + ``Check`` /
    ``Quote`` cross-section additions) and the page-shell wrapper;
    those move into a shared ``render_route_generic`` dispatcher in
    commit 6.
    """
    company = dossier["company"]
    location = dossier["location"]
    contact = dossier["contact"]
    usp_list = _extract_usps(dossier)
    spel_cta = (
        '          <a href="/spel" className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Gamepad2 className="size-4" />Spela direkt</a>\n'
        if "/spel" in dossier_routes
        else ""
    )
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
    # B101 (re-Verifierings-Scout 3 2026-05-18): when CTA is shop the
    # primary hero button must link to the products listing, not the
    # contact route. Booking and quote variants keep contact as target.
    hero_cta_href = _route_href(
        _hero_cta_target_path(dossier, listing_route, contact_path)
    )

    # Operator-uploaded hero image (if present) renders as a banner
    # above the gradient section. The asset is placed in public/uploads/
    # by copy_operator_uploads. We render a raw <img> (not next/image)
    # because the webp files are pre-compressed by sharp and the
    # starters ship without a Next.js Image loader config.
    #
    # Sprint 1.3 — LCP boost: hero-bilden är typiskt Largest Contentful
    # Paint. Tre attribut tillsammans ger ~700ms LCP-vinst utan att
    # introducera next/image-import:
    #   * fetchPriority="high" — säger åt browsern att prioritera nedladdning
    #     före andra subresources (CSS-bakgrunder, lazy-bilder)
    #   * loading="eager" — explicit (default är eager, men explicit är
    #     defensivt mot framtida change i browser-defaults)
    #   * decoding="async" — paint sker utan att blockera main thread
    #     på image-decode (annars kan en stor JPEG blocka 80-200ms)
    brand_block = dossier.get("brand") if isinstance(dossier.get("brand"), dict) else {}
    hero_asset = brand_block.get("heroImage") if isinstance(brand_block, dict) else None
    hero_section_jsx = ""
    if isinstance(hero_asset, dict) and hero_asset.get("filename"):
        hero_filename = hero_asset["filename"]
        hero_alt = hero_asset.get("alt") or company["tagline"]
        hero_section_jsx = (
            '      <section className="relative w-full overflow-hidden bg-[color:var(--background)]">\n'
            '        <div className="mx-auto w-[var(--container-width)] pt-[var(--section-spacing)]">\n'
            f'          <img src={_jsx_safe_string("/uploads/" + hero_filename)} alt={_js_string_literal(hero_alt)} fetchPriority="high" loading="eager" decoding="async" className="aspect-[16/9] w-full rounded-2xl object-cover shadow-sm" />\n'
            "        </div>\n"
            "      </section>\n"
            "\n"
        )

    # Variant-aware hero layout. Resolves to one of three layouts
    # (gradient/centered/split) based on directives.layoutHint or
    # variant_id; falls back to gradient when neither is set, which
    # matches the pre-#2 baseline so legacy callers (tests without a
    # variant_id) keep their expected JSX shape.
    # C1 — Unsplash-fallback för split-layouten. Pre-resolved här så
    # ``_render_hero_block`` slipper röra dossiern. Returnerar ``None``
    # när business-typ saknar en kuraterad photo-ID i mappningen, vilket
    # behåller den befintliga accent-tinted-fallbacken.
    unsplash_fallback_url = _unsplash_hero_url(dossier)
    # Fas 1.6 — background_video är optional. Operatören laddar upp en
    # mp4/webm i wizardens MediaStep; build_site.py renderar den som
    # absolut-positionerat ``<video>`` bakom hero-texten med poster
    # fallback mot hero-bilden. Saknas videon renderas hero som vanligt.
    hero_video_asset = resolve_media_asset(dossier, "backgroundVideo")
    hero_block_jsx = _render_hero_block(
        _hero_style_for(dossier, variant_id),
        company=company,
        location_tag=location_tag,
        hero_cta_label=hero_cta_label,
        hero_cta_href=hero_cta_href,
        contact_phone=contact["phone"],
        spel_cta=spel_cta,
        hero_asset=hero_asset,
        usps=usp_list,
        unsplash_fallback_url=unsplash_fallback_url,
        background_video=hero_video_asset,
    )
    return hero_section_jsx + hero_block_jsx


def render_section_products_intro(dossier: dict) -> str:
    """Render the /produkter route header block (eyebrow + h1 + lead).

    Static Swedish copy today ("Produkter" / "Vårt sortiment" /
    "Här är våra produkter…") — ``dossier`` is reserved for a future
    branch-aware copy switch (e.g. "Smyckessortimentet" / "Klädkollektionen")
    when ecommerce niches get their own copy table.

    Path B step 5 (GAP-backend-path-b-section-renderer): extracted
    from ``render_products`` as a block fragment (no ``<section>``
    wrapper) so it can sit alongside ``render_section_product_grid``
    and the bottom shop-CTA inside the same gradient page section.
    """
    del dossier  # reserved for branch-aware copy
    return (
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Produkter</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Vårt sortiment</h1>\n'
        '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Här är våra produkter. Hör av dig om du undrar något så hjälper vi dig hela vägen till beställning.</p>\n'
        "          </header>\n"
    )


def render_section_product_grid(dossier: dict) -> str:
    """Render the /produkter product-grid block.

    Iterates ``dossier.services`` (the ecommerce-lite scaffold reuses
    the services array for products until SCAFFOLD_TO_STARTER flips
    to ``commerce-base``; see B13). Produces a 3-column responsive
    grid of article cards with icon + label + summary.

    Path B step 5: extracted from ``render_products``. Returned as a
    block fragment (no ``<section>`` wrapper) so the route-renderer
    can compose it with the products-intro header and shop-CTA inside
    a single gradient page section. Output is byte-identical to the
    inline implementation it replaces.
    """
    products = dossier["services"]
    items = "\n".join(
        f'          <article key={_jsx_safe_string(item["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
        f'            <span className="mb-4 inline-flex size-12 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><{_icon_for_service(item["id"])} className="size-6" /></span>\n'
        f'            <h2 className="text-xl font-semibold">{_jsx_safe_string(item["label"])}</h2>\n'
        f'            <p className="mt-3 text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(item["summary"])}</p>\n'
        "          </article>"
        for item in products
    )
    return (
        '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{items}\n"
        "          </div>\n"
    )


def render_section_contact_cta(
    dossier: dict,
    *,
    contact_path: str,
) -> str:
    """Render the home-page closing contact-CTA section.

    Produces the primary-coloured full-bleed "Hör av dig idag" banner
    with a single ArrowRight CTA pointing at ``contact_path``. Always
    rendered (no suppression branch) because the home shell has
    historically always closed with a contact prompt; future scaffolds
    that want a different closing section should compose a different
    section list in their sections.json instead.

    Path B step 4 (GAP-backend-path-b-section-renderer): extracted
    from ``render_home``. ``dossier`` is currently unused (the static
    Swedish copy is hard-coded) but the signature matches the future
    section-renderer protocol so the registry in commit 6 can call
    every renderer with the same shape.
    """
    del dossier  # reserved for future branch-aware copy
    contact_href = _route_href(contact_path)
    return (
        '      <section className="border-t border-[color:var(--border)] bg-[color:var(--primary)] text-[color:var(--primary-foreground)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-[var(--section-spacing)]">\n'
        '          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Hör av dig idag</h2>\n'
        '          <p className="max-w-2xl text-base opacity-90 md:text-lg">Beskriv kort vad du behöver så återkommer vi inom en arbetsdag.</p>\n'
        f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary-foreground)] px-5 py-3 text-sm font-medium text-[color:var(--primary)] hover:opacity-90 transition-opacity">Kontakta oss<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
    )


def render_section_contact_info(dossier: dict) -> str:
    """Render the contact-page Phone / Mail / Address card section.

    Produces the gradient-headed /kontakt section with three articles
    (telephone with opening hours, email, multi-line address). The
    address is rendered as ``<address>`` with one ``<span>`` per line
    so the markup degrades gracefully when ``addressLines`` only has
    one entry.

    Path B step 4: extracted from ``render_contact``. Output is
    byte-identical to the inline implementation it replaces.
    """
    contact = dossier["contact"]
    address_lines = "\n".join(
        f'                <span className="block">{_jsx_safe_string(line)}</span>'
        for line in contact["addressLines"]
    )
    return (
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
    )


def render_section_trust_proof(dossier: dict) -> str:
    """Render the home-page "Varför oss" trust-proof bullet section.

    Pulls ``dossier.trustSignals`` and produces a 2-column ShieldCheck-
    iconed bullet list. Returns "" when the list is empty so the
    section is suppressed entirely (mirrors the pre-existing
    ``trust = []`` handling in ``render_home``).

    Path B step 3 (GAP-backend-path-b-section-renderer): extracted
    from ``render_home``. Note that ``render_home`` is also responsible
    for suppressing this section when the richer testimonials section
    has rendered (it sets the local string to "" in that case) — that
    cross-section coordination stays in ``render_home`` until the
    section-driven dispatcher lands in commit 6.
    """
    trust = dossier["trustSignals"]
    if not trust:
        return ""
    trust_items = "\n".join(
        f'            <li key="trust-{i}" className="flex items-start gap-3">\n'
        f'              <ShieldCheck className="mt-0.5 size-5 shrink-0 text-[color:var(--primary)]" />\n'
        f'              <span className="text-base">{_jsx_safe_string(item)}</span>\n'
        "            </li>"
        for i, item in enumerate(trust)
    )
    return (
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


def render_section_about_story(dossier: dict) -> str:
    """Render the about-page header + story-card block.

    Produces the page header (the about-page eyebrow + company name
    h1) and the quote-iconed story card (``company.story``). Used as
    the leading block inside the AboutPage shell.

    Path B step 3: extracted from ``render_about``. Together with
    ``render_section_team`` and the inline gallery/location sub-blocks
    these form the LSB ``about`` route's section list. Output is
    byte-identical to the inline implementation.
    """
    company = dossier["company"]
    return (
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Om oss</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{_jsx_safe_string(company["name"])}</h1>\n'
        "          </header>\n"
        '          <div className="relative max-w-3xl rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 md:p-8">\n'
        '            <Quote className="absolute -top-3 -left-3 size-8 text-[color:var(--primary)]/20" />\n'
        f'            <p className="text-lg text-[color:var(--foreground)] leading-relaxed">{_jsx_safe_string(company["story"])}</p>\n'
        "          </div>\n"
    )


def render_section_team(dossier: dict) -> str:
    """Render the about-page team-grid block.

    Iterates ``dossier.company.team`` (array of ``{name, role}``) into
    a 3-column responsive grid of monogram cards. Returns "" when the
    team is empty (B94 fix: no empty "Teamet" + ``<ul>`` shell).

    Path B step 3: extracted from ``render_about``. Output is
    byte-identical to the inline implementation.
    """
    company = dossier["company"]
    team = company.get("team", [])
    if not team:
        return ""
    team_items = "\n".join(
        f'            <li key={_jsx_safe_string(member["name"])} className="rounded-xl border border-[color:var(--border)] p-6">\n'
        f'              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-full bg-[color:var(--accent)] text-[color:var(--accent-foreground)] text-sm font-semibold uppercase">{_jsx_safe_string(_member_initials(member["name"]))}</span>\n'
        f'              <p className="text-base font-semibold">{_jsx_safe_string(member["name"])}</p>\n'
        f'              <p className="mt-1 text-sm text-[color:var(--muted)]">{_jsx_safe_string(member["role"])}</p>\n'
        "            </li>"
        for member in team
    )
    return (
        '          <div className="flex flex-col gap-4">\n'
        '            <h2 className="text-2xl font-semibold tracking-tight">Teamet</h2>\n'
        '            <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{team_items}\n"
        "            </ul>\n"
        "          </div>\n"
    )


def render_section_services_summary(
    dossier: dict,
    *,
    listing_route: dict | None,
) -> str:
    """Render the home-page services-summary section.

    Produces the service-grid block (3-column on lg, 2-column on md)
    with branch-aware listing copy (e.g. "Menyn" for restaurants,
    "Sortimentet" for ecommerce) and an optional listing-link CTA
    that points at ``listing_route`` when set.

    Path B step 2 (GAP-backend-path-b-section-renderer): second
    per-section renderer extracted from ``render_home``. Output is
    byte-identical to the pre-extraction inline implementation,
    verified against LSB / commerce / restaurant snapshots.
    """
    services = dossier["services"]
    services_grid = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--card,var(--background))] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
        f'              <span className="mb-4 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)] transition-transform group-hover:scale-105"><{_icon_for_service(svc["id"])} className="size-5" /></span>\n'
        f'              <h3 className="text-lg font-semibold">{_jsx_safe_string(svc["label"])}</h3>\n'
        f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </li>"
        for svc in services
    )
    # Branch-specifik listing-copy: när dossiern har en businessType som
    # finns i ``_BRANCH_LISTING_COPY`` använder vi den (t.ex. "Menyn" /
    # "Det vi serverar" för restaurang) istället för den generiska
    # route-id-baserade copy:n. Faller tillbaka till routebaserad copy
    # för okända branscher så befintliga tester och dossiers utan
    # businessType fortsätter funka.
    listing_copy = _LISTING_COPY_BY_ROUTE_ID["services"]
    branch_copy = _branch_listing_copy(dossier)
    if listing_route is not None:
        listing_copy = _LISTING_COPY_BY_ROUTE_ID.get(
            listing_route["id"], _LISTING_COPY_BY_ROUTE_ID["services"]
        )
    if branch_copy:
        # Branch-copy vinner över route-baserad copy — branschen är
        # närmare operatörens verklighet än scaffold-typen.
        listing_copy = {**listing_copy, **branch_copy}
    listing_link = ""
    if listing_route is not None:
        listing_href = _route_href(listing_route["path"])
        listing_link = f'          <a href={listing_href} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">{listing_copy["cta"]}<ArrowRight className="size-4" /></a>\n'
    return (
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
    )


def _collect_home_icons(dossier: dict, dossier_routes: list[str]) -> list[str]:
    """Compose the icon-import set for the LSB home page.

    Mirrors the pre-shim render_home logic: starts with
    ``_collect_icons_for_pages``, adds ``Check`` when any USP chips
    will render, and adds ``Quote`` when either the story-section or
    a testimonials-cards section will render. Lifted into its own
    helper so the render_home shim can reuse it.
    """
    services = dossier["services"]
    icons_used = _collect_icons_for_pages(services, dossier_routes)
    if _extract_usps(dossier) and "Check" not in icons_used:
        icons_used = sorted({*icons_used, "Check"})
    story_text = (dossier.get("company") or {}).get("story") or ""
    trust_count = sum(
        1
        for item in (dossier.get("trustSignals") or [])
        if isinstance(item, str) and item.strip()
    )
    needs_quote_icon = (
        bool(str(story_text).strip()) or trust_count >= _HOME_TESTIMONIAL_MIN_ITEMS
    )
    if needs_quote_icon and "Quote" not in icons_used:
        icons_used = sorted({*icons_used, "Quote"})
    return icons_used


def render_home(
    dossier: dict,
    dossier_routes: list[str],
    *,
    listing_route: dict | None = None,
    contact_path: str = "/kontakt",
    variant_id: str | None = None,
) -> str:
    """Home page renderer — Path B step 11 dispatcher shim.

    The actual section composition lives in ``render_section_*``
    helpers and is dispatched through ``render_route_generic`` from
    the section list declared in
    ``local-service-business/sections.json``. The shim still owns
    two cross-section concerns that the dispatcher cannot infer
    from the scaffold contract alone:

    1. Icon-import line — composed deterministically from the
       services list, USP chips and story/testimonials presence
       (see ``_collect_home_icons``).
    2. Testimonials suppress trust-proof — when the dossier carries
       enough ``trustSignals`` for the testimonials cards section
       to render, the classic trust-proof bullet list is removed
       from the effective section list so the same proof never
       renders twice.

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
    icons_used = _collect_home_icons(dossier, dossier_routes)
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'

    # Cross-section coordination: testimonials cards (when they
    # render at all) suppress the classic trust-proof bullet list
    # so the same proof is not shown twice. We pre-compute the
    # testimonials body so the home-page section order can drop
    # trust-proof before render_route_generic walks the list.
    testimonials_will_render = bool(_render_home_testimonials_section(dossier))

    # The home-page section order is owned by the renderer (not
    # the scaffold contract) because LSB interleaves required and
    # optional sections — story / gallery / testimonials sit
    # between services-summary and trust-proof, and faq sits
    # between trust-proof and the closing contact-cta. sections.
    # json declares which sections exist; the shim arranges them.
    section_order: list[str] = [
        "hero",
        "service-summary",
        "story",
        "gallery",
        "testimonials",
    ]
    if not testimonials_will_render:
        section_order.append("trust-proof")
    section_order.append("faq")
    section_order.append("contact-cta")

    effective_sections = {
        "home": {"requiredSections": section_order, "optionalSections": []}
    }

    body = render_route_generic(
        dossier,
        route_id="home",
        scaffold_sections=effective_sections,
        dossier_routes=dossier_routes,
        listing_route=listing_route,
        contact_path=contact_path,
        variant_id=variant_id,
    )

    return (
        icon_import + "\n"
        "export default function Home() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + body
        + "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_section_service_list(
    dossier: dict,
    *,
    contact_path: str,
) -> str:
    """Render the service-list section for the /tjanster route.

    Produces the gradient-headered services page section with article
    cards (one per service) and a bottom-of-page CTA whose verb
    follows the dossier's hero CTA family (shop / booking / quote).

    Path B step 2 (GAP-backend-path-b-section-renderer): second
    per-section renderer extracted from ``render_services``. Output
    is byte-identical to the inline implementation it replaces.
    """
    services = dossier["services"]
    contact_href = _route_href(contact_path)
    items = "\n".join(
        f'          <article key={_jsx_safe_string(svc["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
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
    )


def render_services(
    dossier: dict,
    *,
    contact_path: str = "/kontakt",
) -> str:
    services = dossier["services"]
    icons_used = sorted({_icon_for_service(svc["id"]) for svc in services} | {"ArrowRight"})
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'
    # Path B step 2 — service-list section now produced by
    # ``render_section_service_list``. Output is byte-identical to
    # the pre-extraction inline implementation.
    service_list_section = render_section_service_list(
        dossier,
        contact_path=contact_path,
    )
    return (
        icon_import + "\n"
        "export default function ServicesPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        f"{service_list_section}"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_about(dossier: dict) -> str:
    company = dossier["company"]
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
    # Path B step 3 — about-story (header + quote-iconed story card)
    # and team-grid blocks are now produced by ``render_section_about_story``
    # and ``render_section_team``. Output is byte-identical.
    about_story_block = render_section_about_story(dossier)
    team_section = render_section_team(dossier)

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
            f'              <img src={_jsx_safe_string("/uploads/" + item["filename"])} alt={_js_string_literal(item.get("alt") or company["name"])} loading="lazy" decoding="async" className="aspect-[4/3] w-full object-cover" />\n'
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
        f"{about_story_block}"
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
    # Path B step 4 — contact-info card grid (Phone / Mail / Address)
    # is produced by ``render_section_contact_info``. Output is
    # byte-identical to the inline implementation.
    contact_info_section = render_section_contact_info(dossier)
    return (
        'import { Clock, Mail, MapPin, Phone } from "lucide-react";\n'
        "\n"
        "export default function ContactPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        f"{contact_info_section}"
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
    # Path B step 5 — products-intro header and product-grid blocks
    # are now produced by ``render_section_products_intro`` and
    # ``render_section_product_grid``. Output is byte-identical.
    products_intro_block = render_section_products_intro(dossier)
    product_grid_block = render_section_product_grid(dossier)
    # B102 (re-Verifierings-Scout 3 2026-05-18): shop-flavoured bottom-CTA.
    # Länken mot kontakt-routen behålls eftersom builder MVP inte har
    # checkout, men verbet ("Hör av dig för att beställa") matchar
    # shop-tonen från hero ("Shoppa nu") i stället för offert-känslan
    # i den gamla copyn "Fråga om en beställning".
    bottom_cta_label = _commerce_bottom_cta_label(dossier)
    return (
        icon_import + "\n"
        "export default function ProductsPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        f"{products_intro_block}"
        f"{product_grid_block}"
        f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity"><ShoppingBag className="size-4" />{bottom_cta_label}<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


# ---------------------------------------------------------------------------
# Path B step 6 — section-renderer registry + generic dispatcher.
#
# Every section renderer above is registered here under the section id
# used by the scaffold's ``sections.json``. ``render_route_generic``
# reads the section list for a route from a scaffold's sections.json
# (loaded via ``_load_scaffold_sections``), looks each id up in the
# registry and concatenates the resulting JSX fragments.
#
# Section renderers have heterogeneous keyword arguments (some need
# ``listing_route``, others ``contact_path`` or ``variant_id``). The
# dispatcher inspects each renderer's signature so callers can pass a
# single uniform kwargs bag and each renderer receives only the keys it
# accepts. Renderers that need no kwargs simply ignore the bag.
#
# This step adds the infrastructure but does not flip ``write_pages``
# yet: existing route renderers (render_home, render_services, ...)
# still compose their sections directly. Future scaffolds can reuse the
# dispatcher without adding a new ``elif`` branch in ``write_pages``.
# ---------------------------------------------------------------------------


_SECTION_RENDERERS: dict[str, Callable[..., str]] = {
    "hero": render_section_hero,
    "service-summary": render_section_services_summary,
    "services-summary": render_section_services_summary,
    "service-list": render_section_service_list,
    "trust-proof": render_section_trust_proof,
    "about-story": render_section_about_story,
    "team": render_section_team,
    "contact-cta": render_section_contact_cta,
    "contact-info": render_section_contact_info,
    "products-intro": render_section_products_intro,
    "product-grid": render_section_product_grid,
}


_SCAFFOLD_SECTIONS_CACHE: dict[Path, dict] = {}


def _load_scaffold_sections(scaffold_dir: Path) -> dict:
    """Load and cache ``sections.json`` for a scaffold directory.

    Returns an empty dict if the file is missing so a scaffold without
    a sections.json simply makes the dispatcher a no-op for unknown
    routes (the caller falls back to its specialised renderer).
    """
    cached = _SCAFFOLD_SECTIONS_CACHE.get(scaffold_dir)
    if cached is not None:
        return cached
    sections_path = scaffold_dir / "sections.json"
    if not sections_path.is_file():
        _SCAFFOLD_SECTIONS_CACHE[scaffold_dir] = {}
        return {}
    try:
        loaded = json.loads(sections_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            "Builder failed: scaffold sections.json at "
            f"{sections_path} is not valid JSON ({exc.msg} at "
            f"line {exc.lineno}). Path B requires a parsable "
            "sections.json so render_route_generic can compose the "
            "route's sections deterministically."
        ) from exc
    if not isinstance(loaded, dict):
        raise SystemExit(
            "Builder failed: scaffold sections.json at "
            f"{sections_path} must be a JSON object whose keys are "
            "route ids (e.g. \"home\", \"menu\"). Found "
            f"{type(loaded).__name__}."
        )
    _SCAFFOLD_SECTIONS_CACHE[scaffold_dir] = loaded
    return loaded


@functools.cache
def _section_renderer_kwargs(renderer: Callable[..., str]) -> tuple[str, ...]:
    """Return the keyword-argument names a section renderer accepts.

    Cached because the dispatcher hits each renderer once per route per
    build and ``inspect.signature`` is not cheap. The first positional
    parameter (``dossier``) is always passed positionally and is
    omitted from the returned tuple.
    """
    sig = inspect.signature(renderer)
    return tuple(
        name
        for name in sig.parameters
        if name != "dossier" and sig.parameters[name].kind
        in (
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    )


def _call_section_renderer(
    renderer: Callable[..., str],
    dossier: dict,
    kwargs: dict[str, Any],
) -> str:
    """Call a section renderer passing only the kwargs it accepts.

    Any extra kwargs in ``kwargs`` are silently dropped so callers can
    pass a uniform context bag to every renderer in a route without
    each renderer having to declare ``**kwargs`` itself.
    """
    accepted = _section_renderer_kwargs(renderer)
    filtered = {name: kwargs[name] for name in accepted if name in kwargs}
    return renderer(dossier, **filtered)


def render_route_generic(
    dossier: dict,
    *,
    route_id: str,
    scaffold_sections: dict,
    **kwargs: Any,
) -> str:
    """Compose a route body from its declared sections.

    Reads the section list for ``route_id`` from
    ``scaffold_sections[route_id]`` (a dict with
    ``requiredSections`` and optional ``optionalSections`` lists),
    looks each id up in ``_SECTION_RENDERERS`` and concatenates the
    resulting JSX fragments in declaration order — required sections
    first, optionals after — so a scaffold can extend a route just by
    appending an optional section to its sections.json.

    Returns the concatenated body fragments only. Page shell (icon
    imports, ``export default function``, ``<main>`` wrapper) is the
    caller's responsibility. Cross-section coordination (e.g. a
    testimonials section suppressing the trust-proof block) is also
    the caller's responsibility — the dispatcher itself stays
    deterministic and side-effect free.

    Raises ``SystemExit`` for section ids that have no registered
    renderer so a scaffold cannot silently emit an empty route by
    naming a section that does not exist yet.
    """
    route_block = scaffold_sections.get(route_id) or {}
    section_ids: list[str] = []
    required = route_block.get("requiredSections")
    if isinstance(required, list):
        section_ids.extend(str(item) for item in required if isinstance(item, str))
    optional = route_block.get("optionalSections")
    if isinstance(optional, list):
        section_ids.extend(str(item) for item in optional if isinstance(item, str))
    body_fragments: list[str] = []
    for section_id in section_ids:
        renderer = _SECTION_RENDERERS.get(section_id)
        if renderer is None:
            raise SystemExit(
                "Builder failed: section id "
                f"{section_id!r} (used by route {route_id!r}) has no "
                "renderer in _SECTION_RENDERERS in "
                "scripts/build_site.py. Add a "
                f"render_section_{section_id.replace('-', '_')}() "
                "function and register it, or remove the section from "
                "the scaffold's sections.json."
            )
        body_fragments.append(_call_section_renderer(renderer, dossier, kwargs))
    return "".join(body_fragments)


# ---------------------------------------------------------------------------
# Wizard-driven extra routes (B132 follow-up sprint 2026-05-21)
#
# The new routes share a few small helpers: every renderer ends in a
# contact CTA that uses the scaffold's threaded contact_path, a section
# heading uses the same eyebrow/h1 idiom as the existing service/about
# pages, and every customer-supplied string goes through
# _jsx_safe_string so JSX-special characters cannot break the build.
#
# The renderers stay deterministic and integration-free: no booking
# layer, no payments, no editorial CMS. They read what is already in
# the Project Input dossier (services, contact, location, gallery,
# team, trustSignals) and rely on Swedish "vi har inget att visa här
# ännu, hör av dig"-fallbacks when the dossier does not have data.
# That keeps the operator promise honest: a route exists, the visitor
# does not hit a 404, and the page never invents customer-specific
# content the operator did not authorise.
# ---------------------------------------------------------------------------


def _wizard_section_heading(
    eyebrow: str,
    heading: str,
    intro: str | None = None,
) -> str:
    """Reusable hero-style header for the wizard-route renderers.

    Matches the eyebrow + h1 idiom of the existing about/services
    pages so the new routes feel consistent with the rest of the
    generated site. ``intro`` renders as a muted lead paragraph and
    is dropped when empty.
    """
    intro_jsx = ""
    if intro:
        intro_jsx = (
            '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">'
            f"{_jsx_safe_string(intro)}</p>\n"
        )
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(eyebrow)}</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{_jsx_safe_string(heading)}</h1>\n'
        f"{intro_jsx}"
        "          </header>\n"
    )


def _wizard_contact_cta(dossier: dict, contact_path: str) -> str:
    """Trailing contact CTA used by every wizard-route renderer.

    Re-uses ``_hero_cta_label`` so booking-driven businesses say
    "Boka tid" instead of "Begär offert" on /priser and /portfolio,
    matching the home/services pages. Mirrors the route-href guard
    discipline from B50 (path goes through ``_route_href``).
    """
    cta_href = _route_href(contact_path)
    cta_label = _hero_cta_label(dossier)
    return (
        '          <div>\n'
        f'            <a href={cta_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{cta_label}<ArrowRight className="size-4" /></a>\n'
        "          </div>\n"
    )


def _wizard_page_footer() -> str:
    """Closing tags shared by every wizard-route renderer."""
    return (
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


_FAQ_DEFAULT_SV: list[tuple[str, str]] = [
    (
        "Hur snabbt får jag svar?",
        "Vi återkommer normalt inom en arbetsdag på telefon och e-post.",
    ),
    (
        "Kostar det något att höra av sig?",
        "Nej, vi tar inte betalt för en första kontakt eller en kostnadsfri offert.",
    ),
    (
        "Vilka områden täcker ni?",
        "Vi jobbar i {areas}. Kontakta oss om du är osäker på om vi täcker just din adress.",
    ),
]


def _faq_pairs(dossier: dict) -> list[tuple[str, str]]:
    """Compose FAQ items from the dossier without inventing facts."""
    location = dossier.get("location") or {}
    area_values = location.get("serviceAreas") if isinstance(location, dict) else None
    if isinstance(area_values, list) and area_values:
        areas = ", ".join(str(area) for area in area_values if isinstance(area, str))
    else:
        city = location.get("city") if isinstance(location, dict) else None
        country = location.get("country") if isinstance(location, dict) else None
        areas = str(city or country or "ditt närområde")
    pairs: list[tuple[str, str]] = []
    for question, answer_template in _FAQ_DEFAULT_SV:
        pairs.append((question, answer_template.format(areas=areas)))
    contact = dossier.get("contact") or {}
    opening = contact.get("openingHours") if isinstance(contact, dict) else None
    if isinstance(opening, str) and opening.strip():
        pairs.append(
            (
                "När har ni öppet?",
                f"Vi har öppet {opening.strip()}.",
            )
        )
    return pairs


def render_faq(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /faq route.

    Deterministic FAQ built from the dossier: three default questions
    plus an opening-hours question when ``contact.openingHours`` is
    set. No invented service prices or warranties — operator-specific
    answers belong on the operator's wishlist, not in v1 codegen.
    """
    pairs = _faq_pairs(dossier)
    items = "\n".join(
        f'            <article key={_jsx_safe_string(f"faq-{i}")} className="rounded-xl border border-[color:var(--border)] p-6">\n'
        f'              <h2 className="text-lg font-semibold">{_jsx_safe_string(question)}</h2>\n'
        f'              <p className="mt-2 text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(answer)}</p>\n'
        "            </article>"
        for i, (question, answer) in enumerate(pairs)
    )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function FaqPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Vanliga frågor",
            "Det vi får höra ofta",
            "Korta svar på de frågor våra kunder ställer oftast. "
            "Saknas något du undrar över? Hör av dig så svarar vi.",
        )
        + '          <div className="grid gap-3 md:grid-cols-2">\n'
        + items
        + "\n          </div>\n"
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def _gallery_images(dossier: dict) -> list[dict]:
    items = dossier.get("gallery") or []
    selected: list[dict] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("filename"):
                selected.append(item)
    return selected


_HOME_GALLERY_MAX_ITEMS = 6

# Antal FAQ-frågor som visas i den kompakta home-sektionen. Tre matchar
# 2/3-kolumns-griden och håller sektionen visuellt snäv; resterande
# frågor (när /faq-routen aktiveras) lever på dedikerade sidan så
# operatören inte tappar information.
_HOME_FAQ_MAX_ITEMS = 4

# Minsta antal trustSignals för att rendra dem som riktiga testimonial-
# kort istället för bullet-list. Under detta tröskelvärde faller vi
# tillbaka på den befintliga ``trust_section`` i ``render_home`` (en
# enkel checkbox-lista) eftersom 1–2 punkter inte fyller ett 3-kolumns-
# grid och kort skulle se underbefolkat ut.
_HOME_TESTIMONIAL_MIN_ITEMS = 3


# Branch/business-type-specifik listing-copy. När operatören har en
# typisk restaurant/retail/service/medical-typ vill vi att rubriken
# på home-sidans listing-sektion (services-grid) känns relevant för
# branschen istället för den generiska "Vad vi tar oss an". Mappningen
# läses i ``_branch_listing_copy``; om business-typ saknas eller inte
# matchar någon nyckel faller vi tillbaka på ``_LISTING_COPY_BY_ROUTE_ID``
# (route-id-baserade copy). Värdena är medvetet mjuka och beskrivande,
# inte säljiga, för att inte krocka med variant-tonen.
_BRANCH_LISTING_COPY: dict[str, dict[str, str]] = {
    "restaurant": {
        "eyebrow": "Menyn",
        "heading": "Det vi serverar",
        "cta": "Se hela menyn",
    },
    "cafe": {
        "eyebrow": "Menyn",
        "heading": "Smaker från oss",
        "cta": "Se hela menyn",
    },
    "bakery": {
        "eyebrow": "Sortimentet",
        "heading": "Det vi bakar",
        "cta": "Se hela sortimentet",
    },
    "retail": {
        "eyebrow": "Sortimentet",
        "heading": "Det vi säljer",
        "cta": "Se hela sortimentet",
    },
    "e-commerce": {
        "eyebrow": "Sortimentet",
        "heading": "Vårt sortiment",
        "cta": "Se alla produkter",
    },
    "salon": {
        "eyebrow": "Behandlingar",
        "heading": "Det vi gör",
        "cta": "Se alla behandlingar",
    },
    "barbershop": {
        "eyebrow": "Behandlingar",
        "heading": "Det vi gör",
        "cta": "Se alla behandlingar",
    },
    "medical": {
        "eyebrow": "Vården",
        "heading": "Det vi hjälper med",
        "cta": "Se hela vårdutbudet",
    },
    "clinic": {
        "eyebrow": "Vården",
        "heading": "Det vi hjälper med",
        "cta": "Se hela vårdutbudet",
    },
    "consulting": {
        "eyebrow": "Erbjudandet",
        "heading": "Det vi hjälper med",
        "cta": "Se hela erbjudandet",
    },
    "agency": {
        "eyebrow": "Erbjudandet",
        "heading": "Det vi gör",
        "cta": "Se hela erbjudandet",
    },
    "fitness": {
        "eyebrow": "Träningen",
        "heading": "Det vi erbjuder",
        "cta": "Se hela utbudet",
    },
    "gym": {
        "eyebrow": "Träningen",
        "heading": "Det vi erbjuder",
        "cta": "Se hela utbudet",
    },
    "education": {
        "eyebrow": "Utbildningarna",
        "heading": "Det vi lär ut",
        "cta": "Se hela utbudet",
    },
    "hotel": {
        "eyebrow": "Boende",
        "heading": "Det vi erbjuder",
        "cta": "Se alla rum",
    },
    "real-estate": {
        "eyebrow": "Tjänster",
        "heading": "Det vi förmedlar",
        "cta": "Se hela utbudet",
    },
}


# Unsplash-fallback per business-type när operatören inte laddat upp
# en egen hero-bild i split-layouten. Vi väljer kuraterade query-strings
# (inte slumpmässiga Unsplash-bilder) så generated sites får en bild
# som åtminstone matchar branschen. Värdena är Unsplash-photo-IDn så
# vi får deterministisk rendering — random query skulle annars
# producera olika bilder mellan builds och sabotera test-snapshots.
#
# Photo-ID:n är hämtade från Unsplash Editorial collection och har
# fria-användning-licens. När operatören har laddat upp en hero-bild
# används den istället; denna fallback aktiveras bara när hero_asset
# saknas OCH variant-style är ``split`` (där en bild krävs för att
# layouten ska läsa rätt).
_UNSPLASH_HERO_BY_BRANCH: dict[str, str] = {
    "restaurant": "1414235077428-338989a2e8c0",
    "cafe": "1554118811-1e0d58224f24",
    "bakery": "1517433670267-08bbd4be890f",
    "retail": "1441986300917-64674bd600d8",
    "e-commerce": "1556909114-f6e7ad7d3136",
    "salon": "1560066984-138dadb4c035",
    "barbershop": "1503951914875-452162b0f3f1",
    "medical": "1576091160399-112ba8d25d1d",
    "clinic": "1581595220892-b0739db3ba8c",
    "consulting": "1497366216548-37526070297c",
    "agency": "1497366754035-f200968a6e72",
    "fitness": "1517836357463-d25dfeac3438",
    "gym": "1534438327276-14e5300c3a48",
    "education": "1503676260728-1c00da094a0b",
    "hotel": "1566073771259-6a8506099945",
    "real-estate": "1564013799919-ab600027ffc6",
    "construction": "1503387762-cbe48e8fc7d3",
    "automotive": "1502877338535-766e1452684a",
}


def _branch_listing_copy(dossier: dict) -> dict[str, str]:
    """Resolve branch-specific listing copy (eyebrow + heading + CTA)
    from the dossier's ``businessType``. Returns the matching
    ``_BRANCH_LISTING_COPY`` entry when business-type maps cleanly,
    otherwise ``None`` so the caller falls back on the existing
    route-id-based ``_LISTING_COPY_BY_ROUTE_ID`` lookup.

    Branch matching is case-insensitive and tolerates the
    ``"local-service-business"`` placeholder by treating it as
    "no specific branch" (returning ``None``) so the generic copy
    keeps applying.
    """
    company = dossier.get("company") or {}
    business_type = _normalize_business_type(company.get("businessType"))
    if not business_type:
        return {}
    return _BRANCH_LISTING_COPY.get(business_type, {})


def _unsplash_hero_url(dossier: dict, *, width: int = 1200, height: int = 1500) -> str | None:
    """Return a deterministic Unsplash CDN URL for the dossier's
    business-type, or ``None`` when no matching photo-ID exists. Used
    by ``_render_hero_block`` (split-layout) as a fallback when the
    operator has not uploaded their own hero image.

    The URL is built with explicit ``w=``/``h=``/``fit=crop`` params
    so Next.js can serve the right size without an Image-loader
    config, matching how operator-uploaded ``/uploads/*.webp`` files
    are rendered. ``auto=format`` lets Unsplash pick WebP/AVIF based
    on the visitor's browser headers.
    """
    company = dossier.get("company") or {}
    business_type = _normalize_business_type(company.get("businessType"))
    photo_id = _UNSPLASH_HERO_BY_BRANCH.get(business_type)
    if not photo_id:
        return None
    return (
        f"https://images.unsplash.com/photo-{photo_id}"
        f"?w={width}&h={height}&fit=crop&auto=format&q=80"
    )


_HERO_STYLE_BY_VARIANT: dict[str, str] = {
    # local-service-business
    "nordic-trust": "gradient",
    "warm-craft": "centered",
    "clinical-calm": "centered",
    "midnight-counsel": "split",
    "pulse-fit": "gradient",
    # ecommerce-lite
    "clean-store": "split",
    "earth-wellness": "centered",
    "mono-tech": "split",
    "noir-editorial": "split",
    "street-vivid": "gradient",
    # restaurant-hospitality (Path A — render_menu + render_booking)
    "warm-bistro": "centered",
    "nordic-fine-dining": "split",
    "casual-cafe": "gradient",
    "midnight-bar": "split",
}

# Tone-driven fallback för hero-stil när layoutHint saknas OCH varianten
# inte har en mapping i ``_HERO_STYLE_BY_VARIANT`` (sannolikt en framtida
# experimentell variant). Mappar mot semantiska tone-keys (post-
# normalisering via ``_normalize_tone_key``), så svenska wizard-tags
# som "Lekfull" / "Exklusiv / lyxig" automatiskt får rätt stil utan
# explicit konfiguration.
#
# Sprint B/3 (2026-05-22): säkerhetsnät så ingen tone-väljare blir
# helt utan effekt på above-the-fold-upplevelsen ens om operatören
# hoppar över vibe-steget eller en framtida variant inte registrerats.
_HERO_STYLE_BY_TONE: dict[str, str] = {
    "calm": "split",
    "playful": "centered",
    "warm": "centered",
    "premium": "split",
    "luxury": "split",
    "editorial": "split",
    "bold": "gradient",
    "modern": "split",
    "tech": "split",
}

_VALID_HERO_STYLES: frozenset[str] = frozenset({"gradient", "centered", "split"})


_HERO_USP_MAX = 4


def _extract_usps(dossier: dict) -> list[str]:
    """Return up to ``_HERO_USP_MAX`` unique selling points for the hero
    chip row. Reads from two locations in priority order:

    1. ``dossier["uniqueSellingPoints"]`` — once the operator's USPs are
       propagated into Project Input by ``prompt_to_project_input.py``
       (currently blocked by ``project-input.schema.json``
       ``additionalProperties: false``; tracked as backend gap).
    2. ``dossier["directives"]["uniqueSellingPoints"]`` — the structured
       v2 directives block that lives on ``dossier`` when the brief
       persister chooses to pass it through.

    Returns ``[]`` when neither source has a non-empty list. Each item
    is trimmed and falsy values are dropped so the renderer can rely on
    every item being a printable string. The cap of four keeps the
    chip row visually balanced regardless of variant.
    """
    candidates: list[str] | None = None
    raw = dossier.get("uniqueSellingPoints")
    if isinstance(raw, list):
        candidates = [str(item).strip() for item in raw if isinstance(item, str)]
    if not candidates:
        directives = dossier.get("directives")
        if isinstance(directives, dict):
            raw = directives.get("uniqueSellingPoints")
            if isinstance(raw, list):
                candidates = [
                    str(item).strip() for item in raw if isinstance(item, str)
                ]
    if not candidates:
        return []
    return [item for item in candidates if item][:_HERO_USP_MAX]


def _render_hero_usp_chips(usps: list[str], *, centered: bool = False) -> str:
    """Render a ``<ul>`` of USP chips. Empty list collapses to ``""`` so
    the chip row is not emitted at all when the operator has no USPs.

    Each chip uses the variant's ``--accent`` background with a
    ``Check`` glyph from lucide-react so the visual weight matches the
    surrounding hero buttons without competing for attention.
    """
    if not usps:
        return ""
    align_class = "justify-center" if centered else ""
    items = "\n".join(
        f'            <li key={_jsx_safe_string("usp-" + str(i))} className="inline-flex items-center gap-1.5 rounded-full bg-[color:var(--accent)]/40 px-3 py-1 text-xs font-medium text-[color:var(--accent-foreground)]"><Check className="size-3" />{_jsx_safe_string(item)}</li>'
        for i, item in enumerate(usps)
    )
    return (
        f'          <ul className="flex flex-wrap gap-2 {align_class}">\n'
        f"{items}\n"
        "          </ul>\n"
    )


def _hero_style_for(dossier: dict, variant_id: str | None) -> str:
    """Resolve which hero layout to render for the home page.

    Precedence:

    1. ``dossier["directives"]["layoutHint"]`` — operator override
       coming from the wizard's visual step. Frontend may set
       ``"gradient" | "centered" | "split"``; anything else is ignored
       so we never trust unknown strings.
    2. ``_HERO_STYLE_BY_VARIANT[variant_id]`` — vibe-aware default. A
       warm-craft variant gets a centered hero by default, a noir-
       editorial gets a split hero, etc.
    3. ``_HERO_STYLE_BY_TONE[normalized_tone]`` — tone-aware fallback
       (Sprint B/3). Triggas när varianten saknar mapping (framtida
       experimentella variants) ELLER när variantId helt saknas men
       tone är satt. Svenska wizard-tags ("Lekfull", "Lugn och
       förtroendeingivande") normaliseras via ``_normalize_tone_key``
       så samma mapping fungerar oavsett om operatören valde tone
       via chips eller skrev en engelsk semantisk key.
    4. ``"gradient"`` — universal fallback. Matches the pre-#2 behavior
       so tests that call ``render_home`` with no variant_id keep the
       same JSX shape they used to.
    """
    directives = dossier.get("directives")
    if isinstance(directives, dict):
        hint = directives.get("layoutHint")
        if isinstance(hint, str) and hint in _VALID_HERO_STYLES:
            return hint
    if variant_id and variant_id in _HERO_STYLE_BY_VARIANT:
        return _HERO_STYLE_BY_VARIANT[variant_id]
    tone = dossier.get("tone")
    if isinstance(tone, dict):
        primary = tone.get("primary")
        if isinstance(primary, str) and primary.strip():
            normalized = _normalize_tone_key(primary)
            if normalized in _HERO_STYLE_BY_TONE:
                return _HERO_STYLE_BY_TONE[normalized]
    return "gradient"


def _render_hero_background_video(
    background_video: dict | None, hero_asset: dict | None
) -> str:
    """Render a tyst loopande bakgrundsvideo bakom hero-textinnehållet.

    Avgör layout: <video> ligger som ``absolute inset-0`` i en wrapper
    så texten kan staplas ovanpå. ``poster`` pekar mot hero-bilden om
    den finns — då ser första frame snyggt ut även om autoplay blockas
    (Safari low-power mode, prefers-reduced-motion-användare).

    En semi-transparent overlay (``bg-background/40``) lägger sig över
    videon så texten håller WCAG AA-kontrast oavsett vad operatorn
    laddade upp. Marknadsledande mönster (Apple, Stripe, Linear).

    Returnerar tom sträng om ingen video — då renderas hero som vanligt
    utan video-wrapper.
    """
    if not isinstance(background_video, dict):
        return ""
    filename = background_video.get("filename")
    if not isinstance(filename, str) or not filename:
        return ""
    mime = background_video.get("mimeType")
    if mime not in ("video/mp4", "video/webm"):
        return ""
    poster_attr = ""
    if isinstance(hero_asset, dict) and hero_asset.get("filename"):
        poster_path = "/uploads/" + str(hero_asset["filename"])
        poster_attr = f" poster={_jsx_safe_string(poster_path)}"
    video_src = "/uploads/" + filename
    return (
        '        <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">\n'
        f'          <video src={_jsx_safe_string(video_src)}{poster_attr} autoPlay loop muted playsInline aria-hidden className="h-full w-full object-cover" />\n'
        '          <div className="absolute inset-0 bg-[color:var(--background)]/60 backdrop-blur-[2px]"></div>\n'
        "        </div>\n"
    )


def _render_hero_block(
    style: str,
    *,
    company: dict,
    location_tag: str,
    hero_cta_label: str,
    hero_cta_href: str,
    contact_phone: str,
    spel_cta: str,
    hero_asset: dict | None,
    usps: list[str] | None = None,
    unsplash_fallback_url: str | None = None,
    background_video: dict | None = None,
) -> str:
    """Render the hero <section> for the home page in one of three
    layouts. Customer-text (company.name, company.tagline) is always
    wrapped via ``_jsx_safe_string`` so the JSX-escape tests (B30)
    pass for every variant.

    Layouts:

    - ``gradient``: full-width gradient panel, location tag + h1 +
       tagline stacked left-aligned. The pre-#2 baseline.
    - ``centered``: text-aligned center, no gradient, generous vertical
       rhythm. Suits calm/serif/editorial vibes (warm-craft, clinical-
       calm, earth-wellness).
    - ``split``: two-column on md+: text left, hero image right. When
       the operator has uploaded a hero image we render it; otherwise
       a soft accent-tinted block sits in the right column so the
       layout reads correctly even with no asset. Suits editorial and
       commerce vibes (midnight-counsel, noir-editorial, clean-store).
    """
    safe_name = _jsx_safe_string(company["name"])
    safe_tagline = _jsx_safe_string(company["tagline"])
    usp_list = usps or []
    usp_chips_left = _render_hero_usp_chips(usp_list, centered=False)
    usp_chips_centered = _render_hero_usp_chips(usp_list, centered=True)
    video_layer = _render_hero_background_video(background_video, hero_asset)
    has_video = bool(video_layer)
    cta_buttons = (
        '          <div className="flex flex-wrap gap-3">\n'
        f'            <a href={hero_cta_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{hero_cta_label}<ArrowRight className="size-4" /></a>\n'
        f'            <a href={_jsx_safe_string("tel:" + _phone_href(contact_phone))} className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />Ring {_jsx_safe_string(contact_phone)}</a>\n'
        f"{spel_cta}"
        "          </div>\n"
    )

    if style == "centered":
        # location_tag in the centered layout sits as an eyebrow above
        # the title and is text-centered alongside it. We translate the
        # left-aligned default to a centered one inline rather than
        # branching upstream.
        centered_location = (
            location_tag.replace("flex items-center gap-2", "flex items-center gap-2 justify-center")
            if location_tag
            else ""
        )
        section_classes = (
            "relative overflow-hidden bg-[color:var(--background)]"
            if has_video
            else "bg-[color:var(--background)]"
        )
        return (
            f'      <section className="{section_classes}">\n'
            f"{video_layer}"
            '        <div className="relative mx-auto flex w-[var(--container-width)] flex-col items-center gap-8 py-[calc(var(--section-spacing)*1.25)] text-center">\n'
            f"{centered_location}"
            f'          <h1 className="max-w-3xl text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl lg:text-7xl">{safe_name}</h1>\n'
            f'          <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed md:text-xl">{safe_tagline}</p>\n'
            f"{usp_chips_centered}"
            '          <div className="flex flex-wrap items-center justify-center gap-3">\n'
            f'            <a href={hero_cta_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{hero_cta_label}<ArrowRight className="size-4" /></a>\n'
            f'            <a href={_jsx_safe_string("tel:" + _phone_href(contact_phone))} className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />Ring {_jsx_safe_string(contact_phone)}</a>\n'
            f"{spel_cta}"
            "          </div>\n"
            "        </div>\n"
            "      </section>\n"
            "\n"
        )

    if style == "split":
        if isinstance(hero_asset, dict) and hero_asset.get("filename"):
            hero_filename = hero_asset["filename"]
            hero_alt = hero_asset.get("alt") or company["tagline"]
            # Fas 3.3 — CSS-only parallax via scroll-driven animations.
            # ``parallax-hero``-klassen definieras i variant_css och
            # zoomar bilden 1.0 → 1.08 över hela hero-exit-fönstret när
            # browsern stödjer animation-timeline (Chrome/Edge 115+).
            # Safari + Firefox ignorerar utility:n och visar bilden statiskt.
            right_column = (
                '          <div className="relative aspect-square w-full overflow-hidden rounded-2xl ring-1 ring-[color:var(--border)] shadow-sm md:aspect-[4/5]">\n'
                # Sprint 1.3 — split-layout hero är också above-the-fold
                # på desktop. Samma LCP-attribut som banner-hero.
                f'            <img src={_jsx_safe_string("/uploads/" + hero_filename)} alt={_js_string_literal(hero_alt)} fetchPriority="high" loading="eager" decoding="async" className="parallax-hero h-full w-full object-cover" />\n'
                "          </div>\n"
            )
        elif unsplash_fallback_url:
            # C1 — branch-baserad Unsplash-fallback. Operatören har inte
            # laddat upp en hero-bild men vi har en branschmatchande
            # bild från Unsplash editorial collection. Vi använder en
            # raw ``<img>`` med ``loading="lazy"`` och en explicit alt
            # som refererar till företagets tagline, så bilden får
            # samma a11y-och-prestanda-behandling som operatör-uppladdade
            # filer under ``/uploads/``.
            fallback_alt = company.get("tagline") or company.get("name") or "Hero-bild"
            right_column = (
                '          <div className="relative aspect-square w-full overflow-hidden rounded-2xl ring-1 ring-[color:var(--border)] shadow-sm md:aspect-[4/5]">\n'
                f'            <img src={_jsx_safe_string(unsplash_fallback_url)} alt={_js_string_literal(fallback_alt)} loading="lazy" decoding="async" className="parallax-hero h-full w-full object-cover" />\n'
                "          </div>\n"
            )
        else:
            # No hero image and no branch-fallback: render a soft
            # accent-tinted shape so the split layout still reads
            # correctly. Pure CSS, no asset.
            right_column = (
                '          <div className="relative aspect-square w-full overflow-hidden rounded-2xl bg-gradient-to-br from-[color:var(--accent)] to-[color:var(--primary)]/40 md:aspect-[4/5]">\n'
                '            <div className="absolute inset-12 rounded-full bg-[color:var(--background)]/30 blur-3xl"></div>\n'
                "          </div>\n"
            )
        split_section_classes = (
            "relative overflow-hidden bg-[color:var(--background)]"
            if has_video
            else "bg-[color:var(--background)]"
        )
        return (
            f'      <section className="{split_section_classes}">\n'
            f"{video_layer}"
            '        <div className="relative mx-auto grid w-[var(--container-width)] gap-10 py-[var(--section-spacing)] md:grid-cols-2 md:items-center md:gap-16">\n'
            '          <div className="flex flex-col gap-8">\n'
            f"{location_tag}"
            f'            <h1 className="max-w-2xl text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl">{safe_name}</h1>\n'
            f'            <p className="max-w-xl text-lg text-[color:var(--muted)] leading-relaxed md:text-xl">{safe_tagline}</p>\n'
            "            "
            + cta_buttons.lstrip()
            + f"{usp_chips_left}"
            + "          </div>\n"
            + right_column
            + "        </div>\n"
            "      </section>\n"
            "\n"
        )

    # Default — gradient (pre-#2 baseline). Gradient sektionen har
    # redan ``relative overflow-hidden`` så video-lagret blandar sig
    # snyggt med den befintliga gradient-bakgrunden.
    return (
        '      <section className="relative overflow-hidden bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/30">\n'
        f"{video_layer}"
        '        <div className="relative mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        f"{location_tag}"
        f'          <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">{safe_name}</h1>\n'
        f'          <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed md:text-xl">{safe_tagline}</p>\n'
        f"{usp_chips_left}"
        + cta_buttons
        + "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_home_gallery_section(dossier: dict) -> str:
    """Render an optional gallery section on the home page.

    Re-uses ``dossier["gallery"]`` (the same source as ``render_gallery``
    for the dedicated ``/galleri`` route). Renders up to
    ``_HOME_GALLERY_MAX_ITEMS`` figures in a responsive 1/2/3-column
    grid; a full /galleri route still exists for the long tail.

    Returns ``""`` when the operator has not uploaded any gallery
    images, so the section never leaks empty placeholder copy onto the
    home page. The empty string short-circuits the whole `<section>`
    block in ``render_home`` so other sections rendered after it
    (trust, contact CTA) keep their `border-t` divider.

    Fas 2.1 — om story-sektionen körs (``company.story`` finns) så
    konsumerar den första gallery-bilden i en two-column layout. Vi
    hoppar över första bilden här så samma foto inte syns dubbelt på
    startsidan. Bilden finns kvar i /galleri-routen via ``render_gallery``
    så den fortfarande är synlig på sajten.
    """
    images = _gallery_images(dossier)
    if not images:
        return ""
    company = dossier.get("company") or {}
    story_text = company.get("story")
    story_consumed = isinstance(story_text, str) and bool(story_text.strip())
    if story_consumed and len(images) >= 2:
        images = images[1:]
    elif story_consumed and len(images) == 1:
        # Single image was already lifted into the story-section.
        # Suppress the gallery to avoid rendering an empty section.
        return ""
    selected = images[:_HOME_GALLERY_MAX_ITEMS]
    # Fas 3.2 — smarta bildramar. ``ring-1`` ger en hairline-kant som
    # tar över när hover-state lyfter shadow:n. ``shadow-sm`` på vila
    # och ``shadow-md`` på hover ger en mjuk floating-känsla.
    figures = "\n".join(
        f'            <figure key={_jsx_safe_string(item.get("assetId") or item["filename"])} className="group overflow-hidden rounded-xl ring-1 ring-[color:var(--border)] bg-[color:var(--background)] shadow-sm transition-all duration-300 hover:shadow-md">\n'
        f'              <img src={_jsx_safe_string("/uploads/" + item["filename"])} alt={_js_string_literal(item.get("alt") or company.get("name") or "Bild")} loading="lazy" decoding="async" className="aspect-[4/3] w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.03]" />\n'
        "            </figure>"
        for item in selected
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Vårt arbete</p>\n'
        '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Ett urval från projekten</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">\n'
        f"{figures}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_home_story_section(dossier: dict) -> str:
    """Render a compact story section on the home page when the
    operator has a non-empty ``company.story``. The section reuses
    the ``Quote``-flanked card pattern from ``render_about`` so the
    visual language is consistent between home and the dedicated
    /om-oss route.

    Returns ``""`` when ``company.story`` is missing or blank so the
    section never leaks generic filler onto the home page. Tests in
    ``test_builder_audit_post_3b_next.py`` exercise ``render_home``
    directly with various dossier shapes; the empty-story short-
    circuit is what keeps those tests passing without forcing every
    operator to supply a story.

    Icon dependency: this helper consumes ``Quote`` from lucide-react.
    The caller (``render_home``) is responsible for including
    ``Quote`` in its icon-import line; ``_collect_icons_for_pages``
    cannot detect this dependency from ``services`` alone, so
    ``render_home`` whitelists ``Quote`` whenever this section is
    emitted (mirrors the ``Check`` whitelist for USP chips).
    """
    company = dossier.get("company") or {}
    story = company.get("story")
    if not isinstance(story, str) or not story.strip():
        return ""
    safe_story = _jsx_safe_string(story.strip())

    # Fas 2.1 — om gallery har minst en bild lyfter vi den första
    # bredvid story-kortet i en two-column layout. Detta ger startsidan
    # ett ankrat foto bredvid berättelsen istället för att alla bilder
    # försvinner ner i gallery-sektionen. Story-bilden konsumeras
    # fortfarande av render_gallery (/galleri-routen renderar hela
    # listan), och _render_home_gallery_section slipper visa den första
    # bilden igen via en offset (se motsvarande fix där).
    images = _gallery_images(dossier)
    story_image: dict | None = images[0] if images else None

    if story_image is None:
        return (
            '      <section className="border-t border-[color:var(--border)] bg-[color:var(--accent)]/10">\n'
            '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[var(--section-spacing)]">\n'
            '          <div className="flex flex-col gap-3">\n'
            '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Vår historia</p>\n'
            '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Det här är vi</h2>\n'
            "          </div>\n"
            '          <div className="relative max-w-3xl rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 md:p-8">\n'
            '            <Quote className="absolute -top-3 -left-3 size-8 text-[color:var(--primary)]/25" />\n'
            f'            <p className="text-lg text-[color:var(--foreground)] leading-relaxed">{safe_story}</p>\n'
            "          </div>\n"
            "        </div>\n"
            "      </section>\n"
            "\n"
        )

    story_alt = story_image.get("alt") or company.get("name") or "Story-bild"
    story_filename = story_image["filename"]
    return (
        '      <section className="border-t border-[color:var(--border)] bg-[color:var(--accent)]/10">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Vår historia</p>\n'
        '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Det här är vi</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-8 md:grid-cols-[1.1fr_1fr] md:items-center md:gap-12">\n'
        '            <div className="relative rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 md:p-8">\n'
        '              <Quote className="absolute -top-3 -left-3 size-8 text-[color:var(--primary)]/25" />\n'
        f'              <p className="text-lg text-[color:var(--foreground)] leading-relaxed">{safe_story}</p>\n'
        "            </div>\n"
        '            <div className="relative aspect-[4/5] w-full overflow-hidden rounded-xl ring-1 ring-[color:var(--border)] shadow-sm">\n'
        f'              <img src={_jsx_safe_string("/uploads/" + story_filename)} alt={_js_string_literal(story_alt)} loading="lazy" decoding="async" className="h-full w-full object-cover" />\n'
        "            </div>\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_home_testimonials_section(dossier: dict) -> str:
    """Render a testimonials-style section on the home page when the
    dossier has at least ``_HOME_TESTIMONIAL_MIN_ITEMS`` trustSignals.

    The threshold is intentional: with only 1–2 trustSignals, a
    3-column card grid looks underpopulated. The caller falls back to
    the existing ``trust_section`` (bullet list with ``ShieldCheck``
    icons) below this threshold. With 3+ items we render each
    trustSignal as a card with a ``Quote``-glyph and bold attribution
    ("Sagt om oss") so the visual feel matches real customer
    testimonials, even though the source is operator-authored copy.

    Returns ``""`` when fewer than the minimum number of items exist,
    so the caller can decide whether to render its bullet-list
    fallback or skip the section entirely.

    Icon dependency: ``Quote`` (caller whitelists this when the
    section is emitted; ``_collect_icons_for_pages`` doesn't see
    trustSignals).
    """
    trust = dossier.get("trustSignals") or []
    if not isinstance(trust, list):
        return ""
    items: list[str] = [
        str(item).strip()
        for item in trust
        if isinstance(item, str) and item.strip()
    ]
    if len(items) < _HOME_TESTIMONIAL_MIN_ITEMS:
        return ""
    # Fas 2.3 — hover-effekter på testimonial-cards. Identisk timing
    # och easing som services-cards så hover-känslan är konsistent
    # över startsidan. ``-translate-y-0.5`` ger en lätt lyft-effekt
    # som Apple/Stripe använder för dwell-tid på cards.
    cards = "\n".join(
        f'            <figure key={_jsx_safe_string(f"trust-card-{i}")} className="group relative flex h-full flex-col gap-4 rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
        f'              <Quote className="size-6 text-[color:var(--primary)]/30 transition-colors group-hover:text-[color:var(--primary)]/60" />\n'
        f'              <blockquote className="text-base text-[color:var(--foreground)] leading-relaxed">{_jsx_safe_string(item)}</blockquote>\n'
        f'              <figcaption className="mt-auto text-xs uppercase tracking-widest text-[color:var(--muted)]">Sagt om oss</figcaption>\n'
        "            </figure>"
        for i, item in enumerate(items)
    )
    return (
        '      <section className="border-t border-[color:var(--border)] bg-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Förtroende</p>\n'
        '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Det här uppskattar våra kunder</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{cards}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_home_faq_section(dossier: dict, *, has_faq_route: bool) -> str:
    """Render a compact FAQ section on the home page using the
    deterministic ``_faq_pairs`` helper that ``render_faq`` already
    uses for the dedicated /faq route. Shows up to
    ``_HOME_FAQ_MAX_ITEMS`` pairs in a 2-column grid; when the dossier
    has a /faq route the section ends with a "Se alla frågor"-CTA
    that links to it, otherwise the CTA is omitted to avoid ghost
    routes.

    ``_faq_pairs`` returns 3–4 deterministic pairs (three defaults
    plus an opening-hours pair when ``contact.openingHours`` is set),
    so this section always renders when called — there's no
    operator-data dependency that could short-circuit it to ``""``.
    Callers that want to suppress FAQs entirely should skip calling
    this helper.

    Icon dependency: ``ArrowRight`` (already in render_home's icon-
    set whenever ``listing_link`` is rendered, so the caller doesn't
    need additional whitelisting; we still soft-import via the icon
    collector to be explicit).
    """
    pairs = _faq_pairs(dossier)
    if not pairs:
        return ""
    items = "\n".join(
        f'            <article key={_jsx_safe_string(f"home-faq-{i}")} className="rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6">\n'
        f'              <h3 className="text-base font-semibold leading-snug">{_jsx_safe_string(question)}</h3>\n'
        f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(answer)}</p>\n'
        "            </article>"
        for i, (question, answer) in enumerate(pairs[:_HOME_FAQ_MAX_ITEMS])
    )
    faq_link = ""
    if has_faq_route:
        faq_link = (
            '          <a href="/faq" className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Se alla frågor<ArrowRight className="size-4" /></a>\n'
        )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Vanliga frågor</p>\n'
        '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Det vi får höra ofta</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-3 md:grid-cols-2">\n'
        f"{items}\n"
        "          </div>\n"
        f"{faq_link}"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_gallery(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /galleri route.

    Uses ``dossier["gallery"]`` images that ``copy_operator_uploads``
    already placed under ``public/uploads/``. An empty gallery falls
    back to honest copy ("Vi laddar upp bilder snart...") rather than
    rendering generic stock placeholders.
    """
    company = dossier.get("company") or {}
    images = _gallery_images(dossier)
    body: str
    if images:
        figures = "\n".join(
            f'            <figure key={_jsx_safe_string(item.get("assetId") or item["filename"])} className="overflow-hidden rounded-xl border border-[color:var(--border)] bg-[color:var(--background)]">\n'
            f'              <img src={_jsx_safe_string("/uploads/" + item["filename"])} alt={_js_string_literal(item.get("alt") or company.get("name") or "Bild")} loading="lazy" decoding="async" className="aspect-[4/3] w-full object-cover" />\n'
            "            </figure>"
            for item in images
        )
        body = (
            '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
            + figures
            + "\n          </div>\n"
        )
    else:
        body = (
            '          <div className="rounded-xl border border-dashed border-[color:var(--border)] bg-[color:var(--background)] p-6 text-[color:var(--muted)]">\n'
            '            <p className="text-base leading-relaxed">Bilder från våra senaste uppdrag publiceras här löpande. Vill du se exempel direkt? Hör av dig så delar vi referensbilder via mejl.</p>\n'
            "          </div>\n"
        )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function GalleryPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Galleri",
            "Bilder från våra uppdrag",
            "Ett urval av jobb vi har gjort. Bilderna laddas upp av "
            "oss i takt med att nya projekt blir klara.",
        )
        + body
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def _team_members(dossier: dict) -> list[dict]:
    company = dossier.get("company") or {}
    team = company.get("team") if isinstance(company, dict) else None
    if not isinstance(team, list):
        return []
    return [member for member in team if isinstance(member, dict) and member.get("name")]


def render_team(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /team route.

    Reads ``company.team`` (same source as render_about) and renders
    one card per member. Empty teams fall back to honest copy instead
    of inventing roles or photos.
    """
    members = _team_members(dossier)
    if members:
        cards = "\n".join(
            f'            <li key={_jsx_safe_string(member["name"])} className="rounded-xl border border-[color:var(--border)] p-6">\n'
            f'              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-full bg-[color:var(--accent)] text-[color:var(--accent-foreground)] text-sm font-semibold uppercase">{_jsx_safe_string(_member_initials(member["name"]))}</span>\n'
            f'              <p className="text-base font-semibold">{_jsx_safe_string(member["name"])}</p>\n'
            f'              <p className="mt-1 text-sm text-[color:var(--muted)]">{_jsx_safe_string(member.get("role") or "")}</p>\n'
            "            </li>"
            for member in members
        )
        body = (
            '          <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
            + cards
            + "\n          </ul>\n"
        )
    else:
        body = (
            '          <div className="rounded-xl border border-dashed border-[color:var(--border)] bg-[color:var(--background)] p-6 text-[color:var(--muted)]">\n'
            '            <p className="text-base leading-relaxed">Vi presenterar teamet här när vi hunnit fylla på med bilder och roller. Vill du veta vem du kommer prata med? Hör av dig så berättar vi gärna.</p>\n'
            "          </div>\n"
        )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function TeamPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Team",
            "Människorna bakom",
            "Här ser du vilka du kommer i kontakt med när du anlitar oss.",
        )
        + body
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def render_pricing(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /priser route.

    Lists the dossier's ``services`` array as price-quote cards with
    honest "Pris efter offert"-copy. No invented price points: a
    fake hourly rate or fixed price could mislead customers and is
    out of scope for the deterministic Builder.
    """
    services = dossier.get("services") or []
    if isinstance(services, list) and services:
        cards = "\n".join(
            f'            <article key={_jsx_safe_string(svc["id"])} className="rounded-xl border border-[color:var(--border)] p-6">\n'
            f'              <h2 className="text-xl font-semibold">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc.get("summary") or "")}</p>\n'
            '              <p className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-[color:var(--primary)]">Pris efter offert</p>\n'
            "            </article>"
            for svc in services
            if isinstance(svc, dict) and svc.get("id") and svc.get("label")
        )
        body = (
            '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
            + cards
            + "\n          </div>\n"
        )
    else:
        body = (
            '          <div className="rounded-xl border border-dashed border-[color:var(--border)] bg-[color:var(--background)] p-6 text-[color:var(--muted)]">\n'
            '            <p className="text-base leading-relaxed">Vi lägger upp en aktuell prislista här inom kort. Vill du ha pris på ett specifikt uppdrag direkt? Hör av dig så återkommer vi med offert.</p>\n'
            "          </div>\n"
        )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function PricingPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Priser",
            "Vad kostar det?",
            "Priserna beror på uppdragets omfattning. Begär en "
            "kostnadsfri offert så får du ett tydligt pris innan vi "
            "startar.",
        )
        + body
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def render_portfolio(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /portfolio route.

    Combines uploaded gallery images with the services list as
    case-style cards. Empty input falls back to a friendly "vi
    bygger på portföljen"-message.
    """
    images = _gallery_images(dossier)
    services = dossier.get("services") or []
    blocks: list[str] = []
    if images:
        figures = "\n".join(
            f'            <figure key={_jsx_safe_string(item.get("assetId") or item["filename"])} className="overflow-hidden rounded-xl border border-[color:var(--border)] bg-[color:var(--background)]">\n'
            f'              <img src={_jsx_safe_string("/uploads/" + item["filename"])} alt={_js_string_literal(item.get("alt") or "Case-bild")} loading="lazy" decoding="async" className="aspect-[4/3] w-full object-cover" />\n'
            f'              <figcaption className="px-4 py-3 text-sm text-[color:var(--muted)]">{_jsx_safe_string(item.get("alt") or "Genomfört uppdrag")}</figcaption>\n'
            "            </figure>"
            for item in images
        )
        blocks.append(
            '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
            + figures
            + "\n          </div>\n"
        )
    if isinstance(services, list) and services:
        cards = "\n".join(
            f'            <article key={_jsx_safe_string(svc["id"])} className="rounded-xl border border-[color:var(--border)] p-6">\n'
            f'              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Exempel på uppdrag</p>\n'
            f'              <h2 className="mt-2 text-xl font-semibold">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc.get("summary") or "")}</p>\n'
            "            </article>"
            for svc in services
            if isinstance(svc, dict) and svc.get("id") and svc.get("label")
        )
        blocks.append(
            '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
            + cards
            + "\n          </div>\n"
        )
    if not blocks:
        blocks.append(
            '          <div className="rounded-xl border border-dashed border-[color:var(--border)] bg-[color:var(--background)] p-6 text-[color:var(--muted)]">\n'
            '            <p className="text-base leading-relaxed">Vi bygger på portföljen löpande. Vill du höra om liknande uppdrag vi har gjort? Hör av dig så delar vi referenser.</p>\n'
            "          </div>\n"
        )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function PortfolioPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Portfolio",
            "Tidigare uppdrag",
            "Ett urval av jobb och case som visar hur vi arbetar.",
        )
        + "".join(blocks)
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def render_map(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /karta route.

    Shows the contact address, service areas and a Google Maps query
    link based on the dossier address. Avoids embedded map iframes
    because they require an API key and would shift the runtime
    contract. The link is opt-in for the visitor and clearly labelled.
    """
    location = dossier.get("location") or {}
    contact = dossier.get("contact") or {}
    address_lines: list[str] = []
    if isinstance(contact, dict):
        raw_lines = contact.get("addressLines")
        if isinstance(raw_lines, list):
            for line in raw_lines:
                if isinstance(line, str) and line.strip():
                    address_lines.append(line.strip())
    if not address_lines:
        city = location.get("city") if isinstance(location, dict) else None
        if isinstance(city, str) and city.strip():
            address_lines.append(city.strip())
    address_jsx = "\n".join(
        f'                <span className="block">{_jsx_safe_string(line)}</span>'
        for line in address_lines
    )
    address_block: str
    if address_lines:
        address_block = (
            '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><MapPin className="size-5" /></span>\n'
            '              <h2 className="text-base font-semibold">Adress</h2>\n'
            '              <address className="mt-2 not-italic">\n'
            f"{address_jsx}\n"
            "              </address>\n"
            "            </article>\n"
        )
    else:
        address_block = (
            '            <article className="rounded-xl border border-[color:var(--border)] p-6 text-[color:var(--muted)]">\n'
            '              <p className="text-base leading-relaxed">Vi lägger upp adressen så fort den är bekräftad. Ring eller mejla oss om du vill ha vägbeskrivning direkt.</p>\n'
            "            </article>\n"
        )
    service_areas: list[str] = []
    if isinstance(location, dict):
        raw_areas = location.get("serviceAreas")
        if isinstance(raw_areas, list):
            for area in raw_areas:
                if isinstance(area, str) and area.strip():
                    service_areas.append(area.strip())
    if service_areas:
        areas_block = (
            '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><MapPin className="size-5" /></span>\n'
            '              <h2 className="text-base font-semibold">Områden vi arbetar i</h2>\n'
            f'              <p className="mt-2 text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(", ".join(service_areas))}</p>\n'
            "            </article>\n"
        )
    else:
        areas_block = ""
    query_source = ", ".join(address_lines) if address_lines else (
        (location.get("city") if isinstance(location, dict) else None) or ""
    )
    map_block: str
    if isinstance(query_source, str) and query_source.strip():
        maps_url = (
            "https://www.google.com/maps/search/?api=1&query="
            + _url_quote(query_source.strip())
        )
        map_block = (
            '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><MapPin className="size-5" /></span>\n'
            '              <h2 className="text-base font-semibold">Hitta hit</h2>\n'
            '              <p className="mt-2 text-sm text-[color:var(--muted)]">Öppna platsen i Google Maps för vägbeskrivning.</p>\n'
            f'              <a href={_js_string_literal(maps_url)} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-2 rounded-md border border-[color:var(--border)] px-4 py-2 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors">Visa på karta<ArrowRight className="size-4" /></a>\n'
            "            </article>\n"
        )
    else:
        map_block = ""
    return (
        'import { ArrowRight, MapPin } from "lucide-react";\n'
        "\n"
        "export default function MapPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Hitta hit",
            "Vägbeskrivning och områden",
            "Här hittar du adressen och vilka områden vi arbetar i. "
            "Vill du ha hjälp med vägbeskrivning är det bara att ringa.",
        )
        + '          <div className="grid gap-4 md:grid-cols-2">\n'
        + address_block
        + areas_block
        + map_block
        + "          </div>\n"
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


# ---------------------------------------------------------------------------
# Restaurant-hospitality default-route renderers (Issue #90).
#
# These two functions wire the ``menu`` and ``booking`` route ids declared
# by ``packages/generation/orchestration/scaffolds/restaurant-hospitality/
# routes.json`` so a full build of a restaurant Project Input no longer
# exits with a SystemExit from ``write_pages``. They are scaffold-default
# renderers (registered as ``elif`` arms below), not wizard-extras, so
# they do NOT live in ``_WIZARD_ROUTE_RENDERERS``.
#
# Scope per Issue #90: static markup only. No third-party booking
# integration, no payment flow, no real-time availability — the
# scaffold's compatible-dossiers.json declares ``menu-display`` and
# ``booking-cta`` as required dossiers and the dossier-mounting layer
# adds any dynamic UI on top during a separate compositional pass.
#
# Path B (section-driven renderer registry from
# docs/scaffold-runtime-extension-needed.md) is deliberately deferred
# to a future sprint; for Issue #90 we follow Path A (per-route
# functions in the existing if/elif chain) to keep the change small
# and reviewable.
# ---------------------------------------------------------------------------


def _menu_items(dossier: dict) -> list[dict]:
    """Return menu items for a restaurant project input.

    The project-input schema's ``services[]`` is structurally identical
    to a menu item (``id`` + ``label`` + ``summary``), and the schema's
    top-level ``additionalProperties: false`` forbids adding a separate
    ``menu`` field. Restaurant operators therefore put menu items in
    the ``services`` array; ``render_menu`` reads them back here.

    The fallback returns a short sample so the page still has visible
    content for projects that pin restaurant-hospitality without
    supplying any items — that is rare in production but useful when
    the planner picks the scaffold from a thin prompt.
    """
    items = dossier.get("services") or []
    cleaned: list[dict] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("id") and item.get("label"):
                cleaned.append(item)
    if cleaned:
        return cleaned
    return [
        {
            "id": "house-special",
            "label": "Dagens rätt",
            "summary": (
                "Vår kock väljer en huvudrätt utifrån säsongens råvaror. "
                "Fråga personalen vad som serveras idag."
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Path B step 7 — restaurant-hospitality section renderers.
#
# Each helper renders a single section from the restaurant scaffold's
# sections.json. They are deliberately self-contained ``<section>``
# blocks so render_route_generic can compose them in any order (for
# example: hero + menu-preview + book-table-cta on home, then
# menu-intro + menu-list + dietary-key on /menu). All customer text is
# routed through ``_jsx_safe_string`` so JSX-special characters in
# operator-supplied copy never break ``next build``.
#
# Optional sections (large-party-note, cancellation-policy) return an
# empty string when the dossier has no content for them so a scaffold
# can list them in optionalSections without forcing every site to
# render an empty card.
# ---------------------------------------------------------------------------


def render_section_menu_intro(dossier: dict) -> str:
    """Header section for the restaurant /meny route.

    Eyebrow + heading + lead paragraph using the wizard idiom so the
    section visually matches the existing about/services pages.
    Customer text from the dossier is not interpolated here yet — the
    copy is deterministic and operator-safe per the restaurant
    scaffold contract.
    """
    eyebrow = _jsx_safe_string("Meny")
    heading = _jsx_safe_string("Vad vi serverar just nu")
    intro = _jsx_safe_string(
        "Menyn växlar med säsongen och tillgången på råvaror. "
        "Be gärna personalen om dagens rekommendation eller hör av dig "
        "i förväg om du har önskemål eller allergier."
    )
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{eyebrow}</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{heading}</h1>\n'
        f'            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">{intro}</p>\n'
        "          </header>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_menu_list(dossier: dict) -> str:
    """Card grid of menu items for the restaurant /meny route.

    Reads ``services`` from the dossier via ``_menu_items`` (project
    input schema reuses the services array for menu items). Each card
    shows the item label and an optional summary. Empty dossiers fall
    back to a "Dagens rätt" placeholder via ``_menu_items`` so the
    page never renders an empty grid.
    """
    items = _menu_items(dossier)
    card_fragments: list[str] = []
    for item in items:
        key_attr = _jsx_safe_string("menu-" + str(item["id"]))
        label_attr = _jsx_safe_string(str(item["label"]))
        summary_value = item.get("summary")
        summary_fragment = ""
        if isinstance(summary_value, str) and summary_value.strip():
            summary_attr = _jsx_safe_string(summary_value)
            summary_fragment = (
                '              <p className="mt-2 text-sm '
                'text-[color:var(--muted)] leading-relaxed">'
                f"{summary_attr}</p>\n"
            )
        card_fragments.append(
            f"            <article key={key_attr} "
            'className="rounded-xl border border-[color:var(--border)] '
            "bg-[color:var(--card,var(--background))] p-6 transition-all "
            "duration-300 hover:-translate-y-0.5 "
            'hover:border-[color:var(--primary)] hover:shadow-md">\n'
            f'              <h2 className="text-lg font-semibold">{label_attr}</h2>\n'
            f"{summary_fragment}"
            "            </article>"
        )
    cards = "\n".join(card_fragments)
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{cards}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_dietary_key(dossier: dict) -> str:
    """Optional dietary-marker key for the /meny route.

    Renders a small panel listing common Swedish dietary markers
    (vegetariskt, veganskt, glutenfritt, laktosfritt) so visitors can
    scan the menu legend at a glance. Empty when no menu item refers
    to a marker; the dispatcher includes the section because the
    restaurant scaffold's sections.json marks it as required, but the
    panel itself stays minimal so it does not dominate the page.
    """
    markers: list[tuple[str, str]] = [
        ("V", "Vegetariskt"),
        ("VG", "Veganskt"),
        ("GF", "Glutenfritt"),
        ("LF", "Laktosfritt"),
    ]
    rows = "\n".join(
        '            <li className="inline-flex items-center gap-2 rounded-full '
        'border border-[color:var(--border)] px-3 py-1 text-xs '
        'text-[color:var(--muted)]">'
        f'<span className="font-semibold text-[color:var(--foreground)]">{_jsx_safe_string(short)}</span>'
        f'<span>{_jsx_safe_string(label)}</span>'
        "</li>"
        for short, label in markers
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-3 py-8">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Kostmarkeringar</p>\n'
        '          <ul className="flex flex-wrap gap-2">\n'
        f"{rows}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_booking_intro(dossier: dict) -> str:
    """Header section for the restaurant /bokning route.

    Mirrors render_section_menu_intro's structure with reservation-
    flavoured copy. Per Issue #90 we do NOT embed a third-party
    booking provider — the operator's preferred provider lands via the
    ``booking-cta`` dossier in a separate compositional pass — so this
    intro frames the contact-driven booking flow.
    """
    eyebrow = _jsx_safe_string("Boka bord")
    heading = _jsx_safe_string("Boka en plats hos oss")
    intro = _jsx_safe_string(
        "Just nu tar vi bokningar via telefon och e-post. Ring eller "
        "skriv så bekräftar vi tid och antal personer. För större "
        "sällskap, hör av dig minst två dagar i förväg."
    )
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{eyebrow}</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{heading}</h1>\n'
        f'            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">{intro}</p>\n'
        "          </header>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_booking_form_or_embed(dossier: dict) -> str:
    """Booking-form placeholder card for the /bokning route.

    The MVP intentionally has no embedded reservation widget so the
    section renders a copy block explaining that the operator handles
    bookings via phone or email. A future scaffold variant can swap
    this renderer for a Resoo / Tablefy / Quandoo embed without
    touching the dispatcher.
    """
    body = _jsx_safe_string(
        "Vi tar bokningar manuellt så att vi kan stämma av specialönskemål, "
        "allergier och större sällskap. Använd kontaktuppgifterna nedan "
        "eller hör av dig på sociala medier."
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-[var(--section-spacing)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Bokningsförfrågan</p>\n'
        f'          <p className="max-w-2xl text-base text-[color:var(--foreground)] leading-relaxed">{body}</p>\n'
        "        </div>\n"
        "      </section>\n"
    )


def render_section_hours_summary(dossier: dict) -> str:
    """Opening-hours summary card for /bokning and /hitta-hit.

    Reads ``contact.openingHours`` from the dossier and renders a
    single card. Returns an empty string when no hours are set so the
    section is invisible rather than rendering an empty placeholder.
    """
    contact = dossier.get("contact") or {}
    opening = contact.get("openingHours") if isinstance(contact, dict) else None
    if not isinstance(opening, str) or not opening.strip():
        return ""
    safe_hours = _jsx_safe_string(opening.strip())
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-8">\n'
        '          <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Öppettider</p>\n'
        f'            <p className="mt-2 text-base">{safe_hours}</p>\n'
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_fallback_phone(dossier: dict) -> str:
    """Phone + email fallback cards for /bokning.

    Reads ``contact.phone`` and ``contact.email``. Renders cards only
    for the channels the operator actually staffs so the visitor does
    not see "Boka via e-post" links pointing nowhere. Returns empty
    when neither channel is configured.
    """
    contact = dossier.get("contact") or {}
    phone = contact.get("phone") if isinstance(contact, dict) else None
    email = contact.get("email") if isinstance(contact, dict) else None
    cards: list[str] = []
    if isinstance(phone, str) and phone.strip():
        cards.append(
            '            <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Boka via telefon</p>\n'
            f'              <a href={_jsx_safe_string("tel:" + _phone_href(phone))} '
            f'className="mt-2 inline-flex items-center gap-2 text-base hover:underline">{_jsx_safe_string(phone)}</a>\n'
            "            </div>"
        )
    if isinstance(email, str) and email.strip():
        cards.append(
            '            <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Boka via e-post</p>\n'
            f'              <a href={_jsx_safe_string("mailto:" + email.strip())} '
            f'className="mt-2 inline-flex items-center gap-2 text-base hover:underline">{_jsx_safe_string(email.strip())}</a>\n'
            "            </div>"
        )
    if not cards:
        return ""
    grid = "\n".join(cards)
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-8">\n'
        '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{grid}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_large_party_note(dossier: dict) -> str:
    """Optional 'larger party' guidance for /bokning.

    Static text encouraging visitors with bigger groups to call ahead.
    The MVP keeps the copy generic; a future scaffold variant can
    wire this to a per-restaurant max-party-size from the dossier.
    """
    body = _jsx_safe_string(
        "För sällskap över sex personer ber vi dig kontakta oss direkt så "
        "vi kan reservera plats och förbereda menyn. Boka helst minst "
        "två dagar i förväg."
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-3 py-8">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Större sällskap</p>\n'
        f'          <p className="max-w-2xl text-base text-[color:var(--foreground)] leading-relaxed">{body}</p>\n'
        "        </div>\n"
        "      </section>\n"
    )


def render_section_cancellation_policy(dossier: dict) -> str:
    """Optional cancellation-policy block for /bokning.

    Static placeholder text matching the MVP's manual-booking flow.
    A scaffold variant or operator override can replace this with the
    operator's actual policy via a future dossier field.
    """
    body = _jsx_safe_string(
        "Behöver du avboka eller ändra antalet personer? Hör av dig så "
        "snart du kan, så hjälper vi nästa gäst som står på väntelistan."
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-3 py-8">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Avbokning</p>\n'
        f'          <p className="max-w-2xl text-base text-[color:var(--foreground)] leading-relaxed">{body}</p>\n'
        "        </div>\n"
        "      </section>\n"
    )


def _restaurant_optional_section_stub(dossier: dict) -> str:
    """No-op renderer for optional restaurant sections without bespoke copy.

    Returned by ``render_section_wine_pairings``,
    ``render_section_lunch_rotation_note`` and
    ``render_section_menu_download_cta`` so a future operator-driven
    fix can add real copy by simply replacing the renderer with a
    section-shaped function. Until then these slots stay empty so
    the page does not render placeholder marketing copy that the
    operator did not approve.
    """
    return ""


def render_section_wine_pairings(dossier: dict) -> str:
    """Optional wine-pairing recommendations panel for /meny.

    Empty MVP stub: a future scaffold variant or operator override
    will populate this section with a curated list pulled from a
    new dossier field. Returning empty keeps the page slim until
    real content is wired.
    """
    return _restaurant_optional_section_stub(dossier)


def render_section_lunch_rotation_note(dossier: dict) -> str:
    """Optional lunch-rotation note for /meny.

    Empty MVP stub: weekday lunch rotations require a structured
    schedule the project-input schema does not yet model. The
    section is still registered so a scaffold listing it in
    optionalSections does not raise SystemExit at build time.
    """
    return _restaurant_optional_section_stub(dossier)


def render_section_menu_download_cta(dossier: dict) -> str:
    """Optional menu-PDF download CTA for /meny.

    Empty MVP stub: file uploads are routed through
    ``public/uploads`` only for hero/gallery/logo today. A future
    scaffold can wire a menu PDF upload through the same path and
    swap this stub for a real download button.
    """
    return _restaurant_optional_section_stub(dossier)


# Restaurant section renderers register here so render_route_generic
# can dispatch on the section ids declared in
# packages/generation/orchestration/scaffolds/restaurant-hospitality/sections.json.
# Optional sections without bespoke copy register a no-op stub so the
# dispatcher can include them without raising SystemExit; operators or
# scaffold variants can replace each stub with a real renderer when
# the corresponding dossier fields land.
_SECTION_RENDERERS.update(
    {
        "menu-intro": render_section_menu_intro,
        "menu-list": render_section_menu_list,
        "dietary-key": render_section_dietary_key,
        "wine-pairings": render_section_wine_pairings,
        "lunch-rotation-note": render_section_lunch_rotation_note,
        "menu-download-cta": render_section_menu_download_cta,
        "booking-intro": render_section_booking_intro,
        "booking-form-or-embed": render_section_booking_form_or_embed,
        "hours-summary": render_section_hours_summary,
        "fallback-phone": render_section_fallback_phone,
        "large-party-note": render_section_large_party_note,
        "cancellation-policy": render_section_cancellation_policy,
    }
)


# ---------------------------------------------------------------------------
# Path B step 9 — LSB home-page alias renderers.
#
# render_home today emits four extra sections beyond the four declared
# in local-service-business/sections.json: story, gallery, testimonials
# and faq. The implementations live in private ``_render_home_*``
# helpers because they were extracted before the section dispatcher
# existed. To complete Path B for LSB we expose them under stable
# ``render_section_*`` names and register them in the dispatcher so a
# scaffold's sections.json can reference them by id. The aliases are
# 1-1 wrappers — output stays byte-identical with the inline calls in
# render_home.
#
# render_section_faq accepts a ``dossier_routes`` kwarg so the
# dispatcher can pass the same list render_home computes today; when
# the list contains "/faq" the section appends a "Se alla frågor"-CTA
# pointing at the dedicated /faq route, otherwise the CTA is dropped
# so the section never emits a ghost link.
# ---------------------------------------------------------------------------


def render_section_story(dossier: dict) -> str:
    """LSB home-page story section.

    Thin alias for ``_render_home_story_section``. Returns "" when
    the dossier has no ``company.story`` content so a scaffold can
    list ``story`` in optionalSections without forcing an empty
    section onto every site.
    """
    return _render_home_story_section(dossier)


def render_section_gallery(dossier: dict) -> str:
    """LSB home-page gallery section.

    Thin alias for ``_render_home_gallery_section``. Renders up to
    ``_HOME_GALLERY_MAX_ITEMS`` operator-uploaded gallery images;
    returns "" when no gallery is set or the story section already
    consumed the only available image.
    """
    return _render_home_gallery_section(dossier)


def render_section_testimonials(dossier: dict) -> str:
    """LSB home-page testimonials section.

    Thin alias for ``_render_home_testimonials_section``. Renders
    real cards when ``trustSignals`` has at least
    ``_HOME_TESTIMONIAL_MIN_ITEMS`` entries, otherwise returns "" so
    the classic ``trust-proof`` bullet section stays as fallback.
    Cross-section coordination (suppressing trust-proof when
    testimonials are visible) is the caller's responsibility.
    """
    return _render_home_testimonials_section(dossier)


def render_section_faq(
    dossier: dict,
    *,
    dossier_routes: list[str] | None = None,
) -> str:
    """LSB home-page FAQ section.

    Thin alias for ``_render_home_faq_section`` that derives the
    ``has_faq_route`` flag from ``dossier_routes`` so the dispatcher
    can pass the same list ``render_home`` already computes. When
    /faq is in the route list the section ends with a "Se alla
    frågor"-CTA pointing at the dedicated route, otherwise the CTA
    is omitted to avoid a ghost link.
    """
    has_faq_route = "/faq" in (dossier_routes or [])
    return _render_home_faq_section(dossier, has_faq_route=has_faq_route)


def render_section_service_area(dossier: dict) -> str:
    """LSB optional service-area section — MVP stub.

    LSB's sections.json lists ``service-area`` as an optional home
    section so a future renderer can surface a "vi täcker dessa
    områden"-block without a structural change. The MVP stub returns
    "" so the page stays slim until that renderer lands; the
    location-aware copy already lives on /om-oss via render_about's
    inline location-section.
    """
    return ""


def render_section_reviews(dossier: dict) -> str:
    """LSB optional reviews section — MVP stub.

    Reserved slot for an external-review widget (Google reviews,
    Reco, etc.) once the operator-side integration lands. Returns
    "" so the dispatcher can include the section without forcing
    every site to render an empty placeholder.
    """
    return ""


def render_section_certifications(dossier: dict) -> str:
    """LSB optional certifications section — MVP stub.

    Reserved slot for a row of certification logos / badges once
    the project-input schema models them. Today the dossier carries
    free-form trust signals only, which the trust-proof section
    already surfaces. Returns "" until structured certifications
    are wired.
    """
    return ""


_SECTION_RENDERERS.update(
    {
        "story": render_section_story,
        "gallery": render_section_gallery,
        "testimonials": render_section_testimonials,
        "faq": render_section_faq,
        "service-area": render_section_service_area,
        "reviews": render_section_reviews,
        "certifications": render_section_certifications,
    }
)


_LSB_SCAFFOLD_DIR = (
    REPO_ROOT
    / "packages"
    / "generation"
    / "orchestration"
    / "scaffolds"
    / "local-service-business"
)


_RESTAURANT_SCAFFOLD_DIR = (
    REPO_ROOT
    / "packages"
    / "generation"
    / "orchestration"
    / "scaffolds"
    / "restaurant-hospitality"
)


def _render_restaurant_route(
    dossier: dict,
    *,
    route_id: str,
    page_function_name: str,
    contact_path: str,
) -> str:
    """Compose a restaurant route via the section dispatcher.

    Loads ``restaurant-hospitality/sections.json`` for the section
    list, dispatches each id through ``render_route_generic``, then
    appends the standard contact-CTA section so the visitor always
    has a path back to opening hours and phone. The page shell
    (icon import + ``<main>`` wrapper + closing tags) is added
    here so the renderer remains a drop-in replacement for the
    previous specialised implementation.

    ``page_function_name`` controls the name of the exported React
    component (``MenuPage`` / ``BookingPage``) so a future scaffold
    can reuse this helper for any new route.
    """
    sections = _load_scaffold_sections(_RESTAURANT_SCAFFOLD_DIR)
    body = render_route_generic(
        dossier,
        route_id=route_id,
        scaffold_sections=sections,
        contact_path=contact_path,
    )
    cta_section = render_section_contact_cta(dossier, contact_path=contact_path)
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        f"export default function {page_function_name}() {{\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + body
        + cta_section
        + "    </main>\n"
        + "  );\n"
        + "}\n"
    )


def render_menu(dossier: dict, *, contact_path: str = "/hitta-hit") -> str:
    """Render the restaurant /meny route via the section dispatcher.

    Path B step 8 thin shim. The actual section composition lives
    in ``render_section_menu_intro`` / ``render_section_menu_list``
    / ``render_section_dietary_key`` and is dispatched through
    ``render_route_generic`` based on the section list declared in
    ``restaurant-hospitality/sections.json``. A future scaffold can
    extend the route by appending an optional section (for example
    ``wine-pairings``) to its sections.json without editing this
    file.

    The trailing contact CTA is added here as a deliberate page-
    level affordance — the scaffold's sections.json keeps the
    /menu route lean (intro + list + dietary key) and the CTA is
    surfaced by the page wrapper so a hungry visitor always has a
    path back to opening hours and phone.

    ``contact_path`` defaults to ``/hitta-hit`` to match the
    scaffold's ``contact`` route slug.
    """
    return _render_restaurant_route(
        dossier,
        route_id="menu",
        page_function_name="MenuPage",
        contact_path=contact_path,
    )


def render_booking(dossier: dict, *, contact_path: str = "/hitta-hit") -> str:
    """Render the restaurant /bokning route via the section dispatcher.

    Path B step 8 thin shim. The actual section composition lives
    in ``render_section_booking_intro`` /
    ``render_section_booking_form_or_embed`` /
    ``render_section_hours_summary`` /
    ``render_section_fallback_phone`` and is dispatched through
    ``render_route_generic`` based on the section list declared in
    ``restaurant-hospitality/sections.json``.

    Per Issue #90 we still do NOT embed a third-party booking
    provider — the dispatcher composes a static reservation page
    where the operator handles bookings via phone and email. A
    scaffold variant can swap
    ``render_section_booking_form_or_embed`` for an embedded
    widget without touching the dispatcher.
    """
    return _render_restaurant_route(
        dossier,
        route_id="booking",
        page_function_name="BookingPage",
        contact_path=contact_path,
    )


_WIZARD_ROUTE_RENDERERS: dict[str, Any] = {
    "faq": render_faq,
    "gallery": render_gallery,
    "team": render_team,
    "pricing": render_pricing,
    "portfolio": render_portfolio,
    "map": render_map,
}


def _url_quote(value: str) -> str:
    """Small wrapper around urllib's quoting for Maps query strings.

    Local import keeps the module-level imports clean; the helper only
    runs on the wizard-driven /karta path.
    """
    from urllib.parse import quote

    return quote(value, safe="")


def render_robots_txt() -> str:
    """Return a minimal ``robots.txt`` body. Sprint 2.2.

    Generated sites are intended to be publicly indexed by default —
    Sajtbyggaren's whole point is to ship a site that operators can
    point Google at. Therefore the policy is "allow all" plus a
    sitemap-pointer.

    We use a relative sitemap-URL (``/sitemap.xml``) instead of an
    absolute one because the deployment domain isn't known at build
    time. Google + Bing both honour relative URLs in robots.txt as
    long as they're served from the same origin as the robots file.
    Operatorer som vill blockera enskilda paths (t.ex. /admin) lägger
    till regler i builder:n senare; default-statet är index-allt.
    """
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "Sitemap: /sitemap.xml\n"
    )


def render_sitemap_xml(written_paths: list[str]) -> str:
    """Return a ``sitemap.xml`` body listing every route the builder
    actually wrote. Sprint 2.3.

    We use the XML 0.9 Sitemap Protocol (the universal one Google,
    Bing, Yandex and DuckDuckGo all parse). Three notable choices:

      * URLs är relativa (``loc>/tjanster</loc``) av samma anledning
        som robots.txt — vi vet inte vilken domän operatorn
        deployar på. Google klarar relativa URLs så länge sitemapen
        serveras från samma host.
      * ``priority`` skala 1.0 (startsida) → 0.7 (sekundära sidor).
        Detta är heuristiskt — Google ignorerar det numera, men
        Bing och flera SEO-verktyg använder det fortfarande.
      * ``changefreq=weekly`` är en rimlig default för småföretags-
        sajter. Inga av våra renderers genererar dynamiskt innehåll
        som ändras dagligen.
    """
    import html as _html_module

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    # Avduplicera och normalisera så ``/`` och ``/`` inte räknas två
    # gånger om någon scaffold råkar lägga in den dubbelt.
    seen: set[str] = set()
    for raw in written_paths:
        if not isinstance(raw, str):
            continue
        path = raw if raw.startswith("/") else "/" + raw
        if path in seen:
            continue
        seen.add(path)
        priority = "1.0" if path == "/" else "0.7"
        # Bug-fix: XML-escape path (defensivt mot framtida scaffold-paths
        # som innehåller ``&`` eller ``<`` — t.ex. /artiklar?id=...).
        # ``quote=False`` håller ``"`` orörd eftersom vi inte är i ett
        # attribut-värde. Standard-paths som ``/tjanster`` är oförändrade.
        safe_path = _html_module.escape(path, quote=False)
        lines.append("  <url>")
        lines.append(f"    <loc>{safe_path}</loc>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    return "\n".join(lines)


def _render_structured_data_jsonld(dossier: dict) -> str:
    """Return a JSON-LD ``LocalBusiness`` blob (string) suitable for
    embedding in a ``<script type="application/ld+json">`` tag. Sprint 2.1.

    Why LocalBusiness specifically: Sajtbyggaren targets svenska små-
    företag (måleri, café, hantverk, restaurang, konsult etc.) — alla
    matchar Schema.org/LocalBusiness exakt. För dem som har en fysisk
    adress fungerar det dessutom direkt med Google Business Profile.
    Mer specialiserade typer (Restaurant, Dentist, Cafe, etc.) finns,
    men för MVP rendrar vi en generisk ``LocalBusiness`` så vi inte
    behöver mappning per bransch här — operatorn kan byta till en
    specifik subtyp senare via builder-prompts.

    Vi inkluderar bara fält där dossier:n verkligen har data, så
    Google Rich Results inte avvisar markeringen för ``null``-värden.
    Tom telephone, address eller adress utan locality skulle förstöra
    "Verified Business"-badge:n.

    Returns the raw JSON-LD content (without script-tag wrapper) so
    layout-byggaren kan bädda in det med korrekt JSX-escaping.
    """
    import json as _json_module

    company = dossier["company"]
    location = dossier.get("location") if isinstance(dossier.get("location"), dict) else {}
    contact = dossier.get("contact") if isinstance(dossier.get("contact"), dict) else {}

    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": company.get("name") or "",
    }
    if company.get("tagline"):
        payload["description"] = company["tagline"]
    if contact.get("phone"):
        payload["telephone"] = contact["phone"]
    if contact.get("email"):
        payload["email"] = contact["email"]

    address_lines = contact.get("addressLines") if isinstance(contact, dict) else None
    address_part: dict[str, Any] = {}
    if isinstance(address_lines, list) and address_lines:
        address_part["streetAddress"] = ", ".join(
            line.strip() for line in address_lines if isinstance(line, str) and line.strip()
        )
    if location.get("city"):
        address_part["addressLocality"] = location["city"]
    if location.get("country"):
        address_part["addressCountry"] = location["country"]
    if address_part:
        address_part["@type"] = "PostalAddress"
        payload["address"] = address_part

    service_areas = location.get("serviceAreas") if isinstance(location, dict) else None
    if isinstance(service_areas, list):
        clean_areas = [
            area.strip()
            for area in service_areas
            if isinstance(area, str) and area.strip()
        ]
        if clean_areas:
            payload["areaServed"] = clean_areas

    if contact.get("openingHours"):
        # OpeningHours-fältet i Schema.org förväntar ett strukturerat
        # format (e.g. "Mo-Fr 09:00-17:00"). Dossier-värdet är fri
        # svensk text ("Mån-Fre 09:00-17:00"). Vi rendrar den som
        # ``openingHoursSpecification`` i ren string-form — Google
        # accepterar både den och den strukturerade varianten.
        payload["openingHours"] = contact["openingHours"]

    # ``json.dumps`` skapar valid JSON; vi förlitar oss på Reacts
    # inbyggda JSX-escaping för att skydda script-innehållet via
    # ``dangerouslySetInnerHTML`` (det är godtagbart för JSON-LD —
    # innehållet är data, inte exekverbar kod, och vi har redan
    # serialiserat bort potentiella ``</script>``-strängar via
    # ensure_ascii=False och en explicit re-escape nedan).
    serialized = _json_module.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Skydd mot inbäddade ``</script>``-strängar i operator-input som
    # annars skulle bryta sig ut ur scriptet. ``\u003c`` är giltig
    # JSON och rendreras tillbaka som ``<`` i alla parsers.
    return serialized.replace("</", "<\\/")


def render_og_fallback_svg(dossier: dict) -> str:
    """Return an SVG (string) used as Open Graph fallback when the
    operator hasn't uploaded a custom og-image. Sprint 1.5.

    Why SVG and not PNG/JPG:

      * Server-side PNG-generation requires either Satori/Resvg-js
        (Node deps) or Pillow (Python; works but adds 30 MB to the
        Docker image and a long cold-start). SVG is built with string
        concatenation — zero deps, deterministic, ~2 KB on disk.
      * 95 % of social platforms (Twitter, Facebook, LinkedIn, Slack,
        Discord, iMessage, WhatsApp, Telegram) render SVG og:images
        without a problem. The 5 % that don't fall back to the page
        title which is still better than the "naked" no-preview state
        we have today.
      * The SVG is brand-tinted via primaryColorHex so it actually
        looks intentional, not like a default placeholder.

    Returns the raw SVG (XML declaration + <svg> + content). The
    caller writes it to ``public/og-image-fallback.svg`` so Next.js
    serves it under that URL.
    """
    company = dossier["company"]
    brand = dossier.get("brand") if isinstance(dossier.get("brand"), dict) else {}
    primary_hex_raw = brand.get("primaryColorHex") if isinstance(brand, dict) else None
    primary_hex = _normalise_hex_color(primary_hex_raw) or "#0f172a"
    # Tagline kan vara None/empty; visa då bara namnet centrerat.
    # Bug-fix: trim långa namn så de inte overflowar 1200px-canvasen.
    # ~52 tecken @ 56px font-size får plats med ~100px vänster-gutter
    # och 50px höger-marginal. Längre namn ellips:as.
    raw_name = (company.get("name") or "").strip() or "Sajten"
    if len(raw_name) > 52:
        raw_name = raw_name[:49].rstrip() + "…"
    raw_tagline = (company.get("tagline") or "").strip()
    # XML-escapa för att skydda mot " < > & ' i operator-input. SVG är
    # XML — vi får INTE skicka rå text in i <text>-noder.
    import html as _html_module

    safe_name = _html_module.escape(raw_name, quote=False)
    safe_tagline = _html_module.escape(raw_tagline, quote=False)
    monogram = _html_module.escape(raw_name[:2].upper(), quote=False)
    # Beräkna kontrast-säker text-färg mot bakgrund. Om brand-hex är
    # ljus (luma > 0.6) väljer vi mörk text; annars vit. Standard luma:
    # 0.2126·R + 0.7152·G + 0.0722·B (sRGB-perception).
    r = int(primary_hex[1:3], 16) / 255.0
    g = int(primary_hex[3:5], 16) / 255.0
    b = int(primary_hex[5:7], 16) / 255.0
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    text_color = "#0f172a" if luma > 0.6 else "#ffffff"
    muted_color = "rgba(15,23,42,0.65)" if luma > 0.6 else "rgba(255,255,255,0.75)"
    # Auto-skala texten om namnet är långt — annars stora namn flödar
    # ut ur 1200×630-ramen.
    name_font_size = 96 if len(raw_name) <= 18 else 72 if len(raw_name) <= 28 else 56
    tagline_block = ""
    if safe_tagline:
        tagline_block = (
            f'  <text x="100" y="450" font-family="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif" '
            f'font-size="36" font-weight="400" fill="{muted_color}">'
            f"{safe_tagline[:80]}"
            "</text>\n"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">\n'
        f'  <rect width="1200" height="630" fill="{primary_hex}" />\n'
        # Decorativ gradient overlay (subtilt ljus från övre högra hörnet)
        '  <defs>\n'
        '    <radialGradient id="glow" cx="80%" cy="20%" r="60%">\n'
        '      <stop offset="0%" stop-color="white" stop-opacity="0.25" />\n'
        '      <stop offset="100%" stop-color="white" stop-opacity="0" />\n'
        '    </radialGradient>\n'
        '  </defs>\n'
        '  <rect width="1200" height="630" fill="url(#glow)" />\n'
        # Monogram-cirkel i högra övre hörnet
        f'  <circle cx="1050" cy="150" r="80" fill="{text_color}" fill-opacity="0.12" />\n'
        f'  <text x="1050" y="172" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif" '
        f'font-size="56" font-weight="700" fill="{text_color}">{monogram}</text>\n'
        # Företagsnamn — stort, vänsterställt mot vänster gutter
        f'  <text x="100" y="350" font-family="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif" '
        f'font-size="{name_font_size}" font-weight="700" fill="{text_color}" letter-spacing="-2">'
        f"{safe_name}"
        "</text>\n"
        f"{tagline_block}"
        # Decorativ accent-stapel under tagline
        f'  <rect x="100" y="520" width="120" height="6" fill="{text_color}" fill-opacity="0.4" rx="3" />\n'
        "</svg>\n"
    )


def render_not_found(dossier: dict) -> str:
    """Render an ``app/not-found.tsx`` page used by Next.js when no route
    matches the URL. Sprint 1.2.

    We replace the default Next.js black-on-white text-only 404 with a
    branded experience that:

      * Reuses the company name + tagline so the page feels like the rest
        of the site (not an interruption).
      * Suggests the home page + the primary listing route (services or
        products depending on scaffold) so the operator gets back to
        useful content in one click.
      * Surfaces the contact phone number for high-intent visitors who
        clearly tried to find something specific.

    Customer-text is JSX-escaped via ``_jsx_safe_string`` so the same
    B30 safety net the rest of the renderers use protects this page too.
    """
    company = dossier["company"]
    contact = dossier["contact"]
    safe_name = _jsx_safe_string(company["name"])
    safe_tagline = _jsx_safe_string(company["tagline"])
    phone_href = _jsx_safe_string("tel:" + _phone_href(contact["phone"]))
    return (
        'import Link from "next/link";\n'
        'import { ArrowLeft, Phone } from "lucide-react";\n'
        "\n"
        "export default function NotFound() {\n"
        "  return (\n"
        '    <main className="mx-auto flex w-[var(--container-width)] flex-col items-center gap-8 py-[calc(var(--section-spacing)*1.5)] text-center">\n'
        '      <p className="font-mono text-xs uppercase tracking-[0.3em] text-[color:var(--muted)]">404 — sidan hittades inte</p>\n'
        f'      <h1 className="max-w-2xl text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl">Vi hittade inte det du letade efter</h1>\n'
        f'      <p className="max-w-xl text-lg text-[color:var(--muted)] leading-relaxed">Sidan kan ha flyttats eller tagits bort. Hör av dig till {safe_name} så hjälper vi dig vidare.</p>\n'
        '      <div className="flex flex-wrap items-center justify-center gap-3">\n'
        '        <Link href="/" className="inline-flex items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity"><ArrowLeft className="size-4" />Tillbaka till startsidan</Link>\n'
        f'        <a href={phone_href} className="inline-flex items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />{_jsx_safe_string(contact["phone"])}</a>\n'
        "      </div>\n"
        f'      <p className="text-xs text-[color:var(--muted)]">{safe_tagline}</p>\n'
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_global_error(dossier: dict) -> str:
    """Render an ``app/error.tsx`` page shown by Next.js when a server
    component throws. Sprint 1.2.

    Next.js requires this file to be a Client Component (it needs the
    ``reset`` callback) so we emit ``"use client"`` at the top. The
    page mirrors not-found.tsx visually but with a recovery action:
    a ``Försök igen``-button bound to ``reset()`` which re-mounts the
    failing tree without a full page reload.
    """
    company = dossier["company"]
    contact = dossier["contact"]
    safe_name = _jsx_safe_string(company["name"])
    phone_href = _jsx_safe_string("tel:" + _phone_href(contact["phone"]))
    return (
        '"use client";\n'
        "\n"
        'import { useEffect } from "react";\n'
        'import { Phone, RefreshCw } from "lucide-react";\n'
        "\n"
        "export default function ErrorBoundary({\n"
        "  error,\n"
        "  reset,\n"
        "}: {\n"
        "  error: Error & { digest?: string };\n"
        "  reset: () => void;\n"
        "}) {\n"
        "  useEffect(() => {\n"
        "    // Surface the error to whatever telemetry the operator wires up\n"
        "    // (Sentry, Logflare, Vercel Analytics). For now a console.error\n"
        "    // keeps the digest discoverable in production logs without\n"
        "    // exposing the stack trace to end users.\n"
        '    console.error("[error.tsx]", error);\n'
        "  }, [error]);\n"
        "  return (\n"
        '    <main className="mx-auto flex w-[var(--container-width)] flex-col items-center gap-8 py-[calc(var(--section-spacing)*1.5)] text-center">\n'
        '      <p className="font-mono text-xs uppercase tracking-[0.3em] text-[color:var(--muted)]">500 — något gick fel</p>\n'
        '      <h1 className="max-w-2xl text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl">Ett tekniskt fel uppstod</h1>\n'
        f'      <p className="max-w-xl text-lg text-[color:var(--muted)] leading-relaxed">Vi ber om ursäkt — sidan kunde inte laddas just nu. Försök igen eller kontakta {safe_name} så hjälper vi dig.</p>\n'
        '      <div className="flex flex-wrap items-center justify-center gap-3">\n'
        '        <button type="button" onClick={() => reset()} className="inline-flex items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity"><RefreshCw className="size-4" />Försök igen</button>\n'
        f'        <a href={phone_href} className="inline-flex items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />{_jsx_safe_string(contact["phone"])}</a>\n'
        "      </div>\n"
        '      {error.digest ? (\n'
        '        <p className="font-mono text-[10px] text-[color:var(--muted)]/70">Fel-ID: {error.digest}</p>\n'
        "      ) : null}\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def write_pages(
    target: Path,
    dossier: dict,
    scaffold_routes: dict,
    dossier_routes: list[str],
    extra_routes: list[dict] | None = None,
    variant_id: str | None = None,
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
                variant_id=variant_id,
            )
        elif route_id == "services":
            content = render_services(dossier, contact_path=contact_route["path"])
        elif route_id == "products":
            content = render_products(dossier, contact_path=contact_route["path"])
        elif route_id == "menu":
            content = render_menu(dossier, contact_path=contact_route["path"])
        elif route_id == "booking":
            content = render_booking(dossier, contact_path=contact_route["path"])
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
    sanitized_extras: list[dict] = []
    if extra_routes:
        default_paths = {route["path"] for route in default_routes}
        seen_extra_paths: set[str] = set()
        for route in extra_routes:
            if not isinstance(route, dict):
                continue
            route_id = route.get("id")
            path = route.get("path")
            if not isinstance(route_id, str) or not isinstance(path, str):
                continue
            if path in default_paths or path in seen_extra_paths:
                continue
            renderer = _WIZARD_ROUTE_RENDERERS.get(route_id)
            if renderer is None:
                raise SystemExit(
                    "Builder failed: wizard extra route id "
                    f"{route_id!r} (path={path!r}) has no registered "
                    "renderer in scripts/build_site.py. Register it in "
                    "_WIZARD_ROUTE_RENDERERS or remove it from the "
                    "wizard extra route list in "
                    "packages/generation/planning/plan.py."
                )
            content = renderer(dossier, contact_path=contact_route["path"])
            write(route_to_page_path(target, path), content)
            written.append(path)
            seen_extra_paths.add(path)
            sanitized_extras.append({"id": route_id, "path": path})
    write(
        target / "app" / "layout.tsx",
        render_layout(
            dossier,
            dossier_routes,
            scaffold_default_routes=default_routes,
            contact_path=contact_route["path"],
            extra_routes=sanitized_extras or None,
        ),
    )
    # Sprint 1.2 — branded 404 + error pages. Skrivs alltid (de har
    # inga ``id``-baserade renderers och behöver inte registreras i
    # scaffold:s defaultRoutes). Next.js plockar upp filerna automatiskt
    # via filsystem-routing: ``not-found.tsx`` används för 404 och
    # ``error.tsx`` för uncaught exceptions i alla under-routes.
    write(target / "app" / "not-found.tsx", render_not_found(dossier))
    write(target / "app" / "error.tsx", render_global_error(dossier))
    # Sprint 1.5 — auto-OG-fallback. SVG:n skrivs alltid till
    # ``public/og-image-fallback.svg`` så Next.js Metadata API kan
    # länka dit oberoende av om operatorn laddat upp en egen.
    # ``render_layout`` använder den som default när
    # ``project_input.media.ogImage`` saknas; om operatorn HAR laddat
    # upp en egen vinner den, men fallback-filen ligger ändå kvar för
    # framtida sociala delningar utan extra build-steg.
    write(
        target / "public" / "og-image-fallback.svg",
        render_og_fallback_svg(dossier),
    )
    # Sprint 2.2/2.3 — robots.txt + sitemap.xml. Skrivs alltid så att
    # genererade sajter är Google-indexerbara från första bygget.
    # ``written`` innehåller alla scaffold-default routes plus wizard
    # extra routes (galleri, team, pricing, portfolio osv.) — sitemapen
    # speglar exakt det som faktiskt finns på disk.
    write(target / "public" / "robots.txt", render_robots_txt())
    write(target / "public" / "sitemap.xml", render_sitemap_xml(written))
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

    warnings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for category_id in category_ids:
        forbidden = _INTENT_GUARD_CONFLICTS.get(category_id)
        if not forbidden:
            continue
        for blocked in forbidden:
            if not any(blocked in term for term in candidate_terms):
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
