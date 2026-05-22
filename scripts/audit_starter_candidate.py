#!/usr/bin/env python3
"""Audit an external Next.js template/starter candidate, read-only.

The script inspects a directory the operator points at and produces a
structured report describing whether the candidate could become a
Sajtbyggaren ``data/starters/<id>/`` Starter as-is, after cleanup, or
whether it belongs somewhere else (Dossier or reference-only).

Hard guarantees (Starter Candidate Auditor v1 scope):

- The audit is **read-only**. The script never copies files, never
  writes outside the optional ``--report-out`` path, never imports the
  candidate as a Starter, and never touches the Starter Registry,
  ``SCAFFOLD_TO_STARTER``, ``_REAL_CODEGEN_STARTERS``, the Discovery
  Taxonomy or any other governance artefact.
- Only the path passed via ``--path`` is inspected. ``data/starters/``
  inside this repo is never read by the audit.

Usage::

    python scripts/audit_starter_candidate.py --path <path-to-candidate>
    python scripts/audit_starter_candidate.py --path <path-to-candidate> --json

Exit codes::

    0  Audit completed (regardless of classification).
    2  Candidate path missing or not a directory.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

DESIRED_NEXT_MAJOR = 16
DESIRED_TAILWIND_MAJOR = 4

ENV_LEAK_FILES = {".env", ".env.local", ".env.production", ".env.development"}
ENV_EXAMPLE_FILES = {".env.example", ".env.template", ".env.sample"}
DISALLOWED_LOCKFILES = {"pnpm-lock.yaml", "yarn.lock"}
REQUIRED_LOCKFILE = "package-lock.json"
TRACKED_BUILD_ARTEFACTS = {"node_modules", ".next", "out", "build", "dist", ".turbo"}

REQUIRED_SCRIPTS = ("dev", "build", "start")
NICE_TO_HAVE_SCRIPTS = ("lint", "prettier", "prettier:check", "test")

LARGE_ASSET_WARN_BYTES = 5 * 1024 * 1024
LARGE_ASSET_BLOCK_BYTES = 50 * 1024 * 1024

# Subset of well-known binary/asset extensions. The list is intentionally
# small: the goal is "easy to detect" not "exhaustive virus scanner".
ASSET_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".mp4",
    ".mov",
    ".webm",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".zip",
    ".tar",
    ".gz",
    ".pdf",
    ".psd",
    ".ai",
}

# Directories we never descend into when walking the candidate.
WALK_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".next",
    ".turbo",
    "out",
    "build",
    "dist",
    ".cache",
    ".vercel",
    ".svelte-kit",
    ".astro",
    "coverage",
}

# Text file extensions we are willing to scan for demo signals and
# customer-copy heuristics. Keeping this list narrow keeps the audit
# fast on candidate repos with large code bases.
TEXT_SCAN_EXTENSIONS = {
    ".md",
    ".mdx",
    ".tsx",
    ".jsx",
    ".ts",
    ".js",
    ".html",
    ".astro",
}

DEMO_MARKERS = (
    "deploy on vercel",
    "view source on github",
    "open in stackblitz",
    "open in codesandbox",
)

# ---------------------------------------------------------------------------
# Integration detection
# ---------------------------------------------------------------------------

# Patterns ending with ``/`` are scope prefixes (for npm scopes) and
# match by ``startswith``. Other patterns match by exact equality.
INTEGRATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "auth": (
        "next-auth",
        "@auth/",
        "@clerk/",
        "@workos-inc/",
        "@auth0/",
        "@supabase/auth-helpers",
        "@supabase/auth-helpers-nextjs",
        "@supabase/auth-helpers-react",
        "@supabase/ssr",
        "lucia",
        "@stytch/",
        "@kinde-oss/",
        "iron-session",
        "firebase-auth",
        "firebase",
        "@firebase/auth",
    ),
    "database": (
        "prisma",
        "@prisma/client",
        "drizzle-orm",
        "drizzle-kit",
        "mongodb",
        "mongoose",
        "pg",
        "postgres",
        "mysql",
        "mysql2",
        "@neondatabase/serverless",
        "@vercel/postgres",
        "@vercel/kv",
        "@planetscale/database",
        "kysely",
        "sequelize",
        "typeorm",
        "@upstash/redis",
        "redis",
        "ioredis",
    ),
    "payment": (
        "stripe",
        "@stripe/",
        "@paddle/",
        "@lemonsqueezy/",
        "@adyen/",
        "braintree",
    ),
    "cms": (
        "contentful",
        "@contentful/",
        "@sanity/",
        "next-sanity",
        "@payloadcms/",
        "payload",
        "@strapi/",
        "@storyblok/",
        "@hygraph/",
        "@datocms/",
        "@prismicio/",
        "@builder.io/",
    ),
    "analytics": (
        "@vercel/analytics",
        "@vercel/speed-insights",
        "posthog-js",
        "posthog-node",
        "mixpanel",
        "mixpanel-browser",
        "@segment/analytics-next",
        "@amplitude/",
        "react-ga4",
        "react-ga",
        "plausible-tracker",
        "@hotjar/",
        "@datadog/browser-rum",
        "@datadog/browser-logs",
        "@sentry/nextjs",
        "@sentry/react",
        "@sentry/browser",
    ),
}

# Heavy integrations make a candidate "too-integrated" because they
# require runtime config that does not belong in a Starter. Lighter
# integrations make a candidate "better-as-dossier".
HEAVY_INTEGRATION_KINDS = ("auth", "database", "payment", "cms")
LIGHT_INTEGRATION_KINDS = ("analytics",)

VALID_CLASSIFICATIONS = (
    "starter-candidate-ready",
    "needs-cleanup",
    "too-integrated",
    "better-as-dossier",
    "reference-only",
    "blocked",
)

# Scripts allowed to interact with this auditor.
PROGRAM_NAME = "audit_starter_candidate"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class AuditResult:
    """Structured result of one audit run.

    Most lists in the JSON output (``blockers``, ``warnings``,
    ``filesDisallowed``, ``filesPresent``, ``scriptsPresent``,
    ``scriptsMissing``, ``scriptsNiceToHavePresent``, ``demoSignals``,
    ``largeAssets`` (by ``path``) and the inner lists of
    ``integrations``) are alphabetically sorted in :meth:`to_dict` so
    the JSON shape is stable across runs on the same candidate.

    ``nextActions`` is the deliberate exception: it preserves the
    priority order produced by :func:`_build_next_actions` so the
    classification-specific action appears first and the universal
    "Never run this script on a path..." trailer appears last when
    :func:`render_text` prints the report. The shape is still byte-
    stable across runs because the construction logic itself is
    deterministic.
    """

    candidate_path: Path
    classification: str = "blocked"
    summary: str = ""
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    detected_stack: dict[str, Any] = field(default_factory=dict)
    integrations: dict[str, list[str]] = field(default_factory=dict)
    scripts_present: list[str] = field(default_factory=list)
    scripts_missing: list[str] = field(default_factory=list)
    scripts_nice_to_have_present: list[str] = field(default_factory=list)
    files_present: list[str] = field(default_factory=list)
    files_disallowed: list[str] = field(default_factory=list)
    large_assets: list[dict[str, Any]] = field(default_factory=list)
    demo_signals: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "candidatePath": str(self.candidate_path),
            "classification": self.classification,
            "summary": self.summary,
            "blockers": sorted(self.blockers),
            "warnings": sorted(self.warnings),
            "detectedStack": self.detected_stack,
            "integrations": {
                kind: sorted(deps) for kind, deps in sorted(self.integrations.items())
            },
            "scriptsPresent": sorted(self.scripts_present),
            "scriptsMissing": sorted(self.scripts_missing),
            "scriptsNiceToHavePresent": sorted(self.scripts_nice_to_have_present),
            "filesPresent": sorted(self.files_present),
            "filesDisallowed": sorted(self.files_disallowed),
            "largeAssets": sorted(self.large_assets, key=lambda item: item["path"]),
            "demoSignals": sorted(self.demo_signals),
            "nextActions": list(self.next_actions),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Return (parsed-json, error). One of them is always None."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"could not read {path.name}: {exc}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"{path.name} is not valid JSON: {exc.msg}"
    if not isinstance(data, dict):
        return None, f"{path.name} top-level value must be an object"
    return data, None


def _major_from_range(value: str | None) -> int | None:
    """Extract the major version from an npm range string.

    Handles the common shapes ``^16.0.0``, ``~15.4.2``, ``>=14``,
    ``16.x``, and ``next@16``. Returns ``None`` if no integer can be
    extracted.
    """
    if not value:
        return None
    match = re.search(r"(\d+)", value)
    if not match:
        return None
    return int(match.group(1))


def _matches_integration(dep_name: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        if pattern.endswith("/"):
            if dep_name.startswith(pattern):
                return True
        elif dep_name == pattern:
            return True
    return False


def _iter_files(root: Path) -> Iterable[Path]:
    """Walk ``root`` skipping ``WALK_SKIP_DIRS`` directories."""
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in WALK_SKIP_DIRS)
        current_path = Path(current)
        for filename in sorted(files):
            yield current_path / filename


def _relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# Audit logic
# ---------------------------------------------------------------------------


def audit_candidate(path: Path | str) -> AuditResult:
    """Run the full read-only audit and return the structured result."""
    root = Path(path).expanduser().resolve()
    result = AuditResult(candidate_path=root)
    if not root.exists():
        result.blockers.append(f"path does not exist: {root}")
        result.classification = "blocked"
        result.summary = "Candidate path does not exist."
        result.next_actions = _build_next_actions(result)
        return result
    if not root.is_dir():
        result.blockers.append(f"path is not a directory: {root}")
        result.classification = "blocked"
        result.summary = "Candidate path is not a directory."
        result.next_actions = _build_next_actions(result)
        return result

    _audit_top_level_files(root, result)
    _audit_nested_env_files(root, result)
    _audit_package_json(root, result)
    _audit_tsconfig(root, result)
    _audit_components_json(root, result)
    _audit_disallowed_artefacts(root, result)
    _audit_assets_and_text(root, result)

    result.classification = _classify(result)
    result.summary = _build_summary(result)
    result.next_actions = _build_next_actions(result)
    return result


def _audit_top_level_files(root: Path, result: AuditResult) -> None:
    files = {child.name for child in root.iterdir() if child.is_file()}
    dirs = {child.name for child in root.iterdir() if child.is_dir()}

    for required in ("package.json",):
        if required in files:
            result.files_present.append(required)
        else:
            result.blockers.append(f"missing {required}")

    if REQUIRED_LOCKFILE in files:
        result.files_present.append(REQUIRED_LOCKFILE)
    else:
        result.warnings.append(
            f"missing {REQUIRED_LOCKFILE}; run npm install before importing"
        )

    for disallowed in sorted(DISALLOWED_LOCKFILES & files):
        result.files_disallowed.append(disallowed)
        result.warnings.append(
            f"{disallowed} present; convert to npm and commit {REQUIRED_LOCKFILE}"
        )

    for env_leak in sorted(ENV_LEAK_FILES & files):
        result.files_disallowed.append(env_leak)
        result.blockers.append(
            f"{env_leak} present; remove before any import (potential secret leak)"
        )

    if ENV_EXAMPLE_FILES & files:
        result.files_present.extend(sorted(ENV_EXAMPLE_FILES & files))
    else:
        result.warnings.append(
            "no .env.example/.env.template; add an empty example before import"
        )

    if ".gitignore" in files:
        result.files_present.append(".gitignore")

    if ".git" in dirs:
        result.blockers.append(
            "nested .git directory present; remove before any import"
        )
        result.files_disallowed.append(".git/")

    for artefact in sorted(TRACKED_BUILD_ARTEFACTS & dirs):
        result.files_disallowed.append(f"{artefact}/")
        result.warnings.append(
            f"tracked {artefact}/ directory present; "
            "delete and add to .gitignore before import"
        )


def _audit_nested_env_files(root: Path, result: AuditResult) -> None:
    """Detect ``.env*`` secret files buried below the top level.

    Top-level ``.env``, ``.env.local``, ``.env.production`` etc. are
    handled in :func:`_audit_top_level_files`. This walk catches the
    false-negative case where a candidate hides ``apps/web/.env.local``
    (or similar) inside a sub-directory and would otherwise pass the
    audit. Any file whose name starts with ``.env`` is treated as a
    potential secret leak unless it is one of the explicitly allowed
    example shapes (``.env.example``, ``.env.template``,
    ``.env.sample``).
    """
    resolved_root = root.resolve()
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in WALK_SKIP_DIRS]
        rel = Path(current).resolve().relative_to(resolved_root)
        if rel == Path("."):
            continue
        for filename in files:
            if filename in ENV_EXAMPLE_FILES:
                continue
            if filename != ".env" and not filename.startswith(".env."):
                continue
            entry = (rel / filename).as_posix()
            if entry not in result.files_disallowed:
                result.files_disallowed.append(entry)
                result.blockers.append(
                    f"{entry} present below top level; remove before any "
                    "import (nested secret leak)"
                )


def _audit_package_json(root: Path, result: AuditResult) -> None:
    package_path = root / "package.json"
    if not package_path.is_file():
        return
    pkg, error = _read_json(package_path)
    if error or pkg is None:
        result.blockers.append(error or "package.json could not be parsed")
        return

    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    if not isinstance(deps, dict):
        result.blockers.append("package.json dependencies have wrong shape")
        return

    next_range = deps.get("next")
    next_major = _major_from_range(next_range)
    result.detected_stack["next"] = {
        "range": next_range,
        "major": next_major,
    }
    if next_range is None:
        result.warnings.append("next.js dependency missing; not a Next.js app")
    elif next_major is None:
        result.warnings.append(f"could not parse next version range: {next_range!r}")
    elif next_major < DESIRED_NEXT_MAJOR:
        result.warnings.append(
            f"next major {next_major} below desired {DESIRED_NEXT_MAJOR}; "
            f"upgrade required before import"
        )

    tailwind_range = (
        deps.get("tailwindcss")
        or deps.get("@tailwindcss/postcss")
        or deps.get("@tailwindcss/cli")
    )
    tailwind_major = _major_from_range(tailwind_range)
    result.detected_stack["tailwind"] = {
        "range": tailwind_range,
        "major": tailwind_major,
    }
    if tailwind_range is None:
        result.warnings.append("tailwindcss dependency missing")
    elif tailwind_major is None:
        result.warnings.append(
            f"could not parse tailwind version range: {tailwind_range!r}"
        )
    elif tailwind_major < DESIRED_TAILWIND_MAJOR:
        result.warnings.append(
            f"tailwind major {tailwind_major} below desired "
            f"{DESIRED_TAILWIND_MAJOR}; upgrade required before import"
        )

    result.detected_stack["typescript"] = {
        "declared": deps.get("typescript") is not None,
        "range": deps.get("typescript"),
    }
    if deps.get("typescript") is None:
        result.warnings.append("typescript dependency missing")

    result.detected_stack["lucideReact"] = {
        "declared": deps.get("lucide-react") is not None,
        "range": deps.get("lucide-react"),
    }
    if deps.get("lucide-react") is None:
        result.warnings.append(
            "lucide-react missing; required for shadcn-aligned starters"
        )

    scripts = pkg.get("scripts") or {}
    if not isinstance(scripts, dict):
        result.blockers.append("package.json scripts have wrong shape")
        scripts = {}
    for required in REQUIRED_SCRIPTS:
        if required in scripts:
            result.scripts_present.append(required)
        else:
            result.scripts_missing.append(required)
            result.warnings.append(f"missing required npm script: {required}")
    for nice in NICE_TO_HAVE_SCRIPTS:
        if nice in scripts:
            result.scripts_nice_to_have_present.append(nice)

    integrations: dict[str, list[str]] = {}
    for kind, patterns in INTEGRATION_PATTERNS.items():
        matched = sorted(
            name for name in deps if _matches_integration(name, patterns)
        )
        if matched:
            integrations[kind] = matched
    if integrations:
        result.integrations = integrations
        for kind, hits in sorted(integrations.items()):
            result.warnings.append(
                f"{kind} integration detected via dependency: {', '.join(hits)}"
            )


def _audit_tsconfig(root: Path, result: AuditResult) -> None:
    tsconfig_path = root / "tsconfig.json"
    stack_entry: dict[str, Any] = {"present": False, "strict": None}
    if not tsconfig_path.is_file():
        result.warnings.append("tsconfig.json missing; TypeScript strict not provable")
        result.detected_stack["tsconfig"] = stack_entry
        return
    stack_entry["present"] = True
    result.files_present.append("tsconfig.json")
    data, error = _read_json(tsconfig_path)
    if error or data is None:
        result.warnings.append(
            "tsconfig.json could not be parsed; treat strict mode as unknown"
        )
        result.detected_stack["tsconfig"] = stack_entry
        return
    compiler_options = data.get("compilerOptions") or {}
    strict = compiler_options.get("strict")
    stack_entry["strict"] = bool(strict) if strict is not None else None
    if strict is True:
        pass
    elif strict is False:
        result.warnings.append(
            "tsconfig.json compilerOptions.strict is false; must be true"
        )
    else:
        result.warnings.append(
            "tsconfig.json compilerOptions.strict missing; must be set to true"
        )
    result.detected_stack["tsconfig"] = stack_entry


def _audit_components_json(root: Path, result: AuditResult) -> None:
    components_path = root / "components.json"
    if components_path.is_file():
        result.files_present.append("components.json")
        result.detected_stack["shadcn"] = {"componentsJsonPresent": True}
        return
    result.detected_stack["shadcn"] = {"componentsJsonPresent": False}
    result.warnings.append(
        "components.json missing; shadcn/ui not initialised in candidate"
    )


def _audit_disallowed_artefacts(root: Path, result: AuditResult) -> None:
    """Report tracked build/cache artefacts buried below top-level too.

    Top-level cases are already handled in
    :func:`_audit_top_level_files`. This walk only catches the rarer
    pattern of a tracked ``node_modules`` (or similar) inside a
    sub-package such as ``packages/web/node_modules``.
    """
    resolved_root = root.resolve()
    for current, dirs, _files in os.walk(root):
        rel = Path(current).resolve().relative_to(resolved_root)
        if rel == Path("."):
            for skip in WALK_SKIP_DIRS:
                if skip in dirs:
                    dirs.remove(skip)
            continue
        for artefact in TRACKED_BUILD_ARTEFACTS:
            if artefact in dirs:
                entry = (rel / artefact).as_posix() + "/"
                if entry not in result.files_disallowed:
                    result.files_disallowed.append(entry)
                    result.warnings.append(
                        f"tracked {entry} present below top level; "
                        "delete before import"
                    )
        for skip in WALK_SKIP_DIRS:
            if skip in dirs:
                dirs.remove(skip)


def _audit_assets_and_text(root: Path, result: AuditResult) -> None:
    demo_hits: set[str] = set()
    for file_path in _iter_files(root):
        try:
            stat = file_path.stat()
        except OSError:
            continue
        suffix = file_path.suffix.lower()
        rel = _relative_posix(file_path, root)
        if suffix in ASSET_EXTENSIONS and stat.st_size >= LARGE_ASSET_WARN_BYTES:
            entry = {
                "path": rel,
                "sizeBytes": stat.st_size,
            }
            result.large_assets.append(entry)
            severity = "warning"
            if stat.st_size >= LARGE_ASSET_BLOCK_BYTES:
                severity = "blocker"
                result.blockers.append(
                    f"asset {rel} is {stat.st_size} bytes; "
                    "do not commit binaries this large"
                )
            else:
                result.warnings.append(
                    f"asset {rel} is {stat.st_size} bytes; "
                    "review before commit"
                )
            entry["severity"] = severity
            continue
        if suffix not in TEXT_SCAN_EXTENSIONS:
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lowered = text.lower()
        for marker in DEMO_MARKERS:
            if marker in lowered:
                demo_hits.add(marker)
    if demo_hits:
        result.demo_signals = sorted(demo_hits)
        result.warnings.append(
            "demo markers detected (e.g. Deploy on Vercel/View source on GitHub); "
            "candidate looks like a public demo, not a clean base"
        )


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _classify(result: AuditResult) -> str:
    if result.blockers:
        return "blocked"
    integration_kinds = set(result.integrations)
    if integration_kinds & set(HEAVY_INTEGRATION_KINDS):
        return "too-integrated"
    if integration_kinds & set(LIGHT_INTEGRATION_KINDS):
        return "better-as-dossier"
    if result.demo_signals:
        return "reference-only"
    if result.warnings:
        return "needs-cleanup"
    return "starter-candidate-ready"


def _build_summary(result: AuditResult) -> str:
    cls = result.classification
    base = {
        "starter-candidate-ready": (
            "Candidate passes all hard requirements and is ready to be "
            "considered for data/starters/<id>/ import."
        ),
        "needs-cleanup": (
            f"Candidate is fixable but has {len(result.warnings)} "
            "warning(s) that must be resolved before import."
        ),
        "too-integrated": (
            "Candidate ships heavy runtime integrations "
            f"({', '.join(sorted(set(result.integrations) & set(HEAVY_INTEGRATION_KINDS)))}); "
            "those belong in a Dossier or operator setup, not a Starter."
        ),
        "better-as-dossier": (
            "Candidate is mostly clean but ships analytics/tracking; "
            "consider extracting it as a Dossier instead of a Starter."
        ),
        "reference-only": (
            "Candidate looks like a public demo (Deploy on Vercel / View "
            "source markers); useful as reference, not as a Starter base."
        ),
        "blocked": (
            f"Candidate has {len(result.blockers)} hard blocker(s); "
            "cannot proceed with import in its current state."
        ),
    }
    return base.get(cls, "Audit completed.")


def _build_next_actions(result: AuditResult) -> list[str]:
    actions: list[str] = []
    cls = result.classification
    if cls == "blocked":
        actions.append(
            "Fix every blocker before re-running this auditor; "
            "no Starter import or registry change is allowed yet."
        )
    if cls == "too-integrated":
        actions.append(
            "Decide whether to extract integrations into a Dossier or "
            "drop the candidate; do not import as Starter."
        )
    if cls == "better-as-dossier":
        actions.append(
            "Strip analytics/tracking and re-audit; or keep the "
            "candidate as a Dossier instead of a Starter."
        )
    if cls == "reference-only":
        actions.append(
            "Keep notes and copy-able patterns, but do not import as "
            "Starter without first removing demo branding."
        )
    if cls == "needs-cleanup":
        actions.append(
            "Address every warning, then re-run this auditor; only "
            "import once the result is starter-candidate-ready."
        )
    if cls == "starter-candidate-ready":
        actions.append(
            "Operator may now propose a Starter import via ADR + "
            "starter-registry.v1.json update; this script does not "
            "perform either step."
        )
    actions.append(
        "Never run this script on a path that already lives under "
        "data/starters/; the auditor only inspects external candidates."
    )
    return actions


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"Starter Candidate Auditor v{SCHEMA_VERSION}")
    lines.append(f"  candidate path: {report['candidatePath']}")
    lines.append(f"  classification: {report['classification']}")
    lines.append(f"  summary: {report['summary']}")
    lines.append("")

    stack = report.get("detectedStack", {})
    lines.append("Detected stack:")
    for key in sorted(stack):
        lines.append(f"  {key}: {stack[key]}")
    lines.append("")

    lines.append(f"Blockers ({len(report['blockers'])}):")
    if not report["blockers"]:
        lines.append("  (none)")
    for item in report["blockers"]:
        lines.append(f"  - {item}")
    lines.append("")

    lines.append(f"Warnings ({len(report['warnings'])}):")
    if not report["warnings"]:
        lines.append("  (none)")
    for item in report["warnings"]:
        lines.append(f"  - {item}")
    lines.append("")

    lines.append("Scripts:")
    lines.append(
        f"  required present: {', '.join(report['scriptsPresent']) or '(none)'}"
    )
    lines.append(
        f"  required missing: {', '.join(report['scriptsMissing']) or '(none)'}"
    )
    lines.append(
        f"  nice-to-have present: "
        f"{', '.join(report['scriptsNiceToHavePresent']) or '(none)'}"
    )
    lines.append("")

    lines.append("Integrations detected:")
    if not report["integrations"]:
        lines.append("  (none)")
    for kind, hits in report["integrations"].items():
        lines.append(f"  {kind}: {', '.join(hits)}")
    lines.append("")

    lines.append("Disallowed files/dirs:")
    if not report["filesDisallowed"]:
        lines.append("  (none)")
    for item in report["filesDisallowed"]:
        lines.append(f"  - {item}")
    lines.append("")

    if report["largeAssets"]:
        lines.append("Large assets:")
        for entry in report["largeAssets"]:
            lines.append(
                f"  - {entry['path']} ({entry['sizeBytes']} bytes, "
                f"{entry.get('severity', 'warning')})"
            )
        lines.append("")

    if report["demoSignals"]:
        lines.append("Demo signals:")
        for marker in report["demoSignals"]:
            lines.append(f"  - {marker}")
        lines.append("")

    lines.append("Next actions:")
    for action in report["nextActions"]:
        lines.append(f"  - {action}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description=(
            "Read-only audit of an external Next.js starter/template "
            "candidate. Never imports or modifies anything in this repo."
        ),
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Path to the candidate directory (external repo).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--report-out",
        default=None,
        help=(
            "Optional file to write the JSON report to. Useful when "
            "auditing several candidates and keeping a paper trail."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    candidate_path = Path(args.path).expanduser()
    if not candidate_path.exists():
        print(f"error: path does not exist: {candidate_path}", file=sys.stderr)
        return 2
    if not candidate_path.is_dir():
        print(f"error: path is not a directory: {candidate_path}", file=sys.stderr)
        return 2

    result = audit_candidate(candidate_path)
    report = result.to_dict()

    if args.report_out:
        out_path = Path(args.report_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
