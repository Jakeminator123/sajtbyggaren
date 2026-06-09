"""Individual Quality Gate checks.

Each check returns a CheckResult and never raises on a soft failure -
the gate aggregates the results without stopping the pipeline. That is
the contract that lets Repair Pipeline see all failures at once.

Sprint 3A v1 implements four checks:

- ``run_typecheck_check`` - delegates to ``npx tsc --noEmit``.
- ``run_route_scan_check`` - file existence + default-export check.
- ``run_build_status_check`` - aggregates npm install / npm run build.
- ``run_policy_compliance_check`` - scans for forbidden ``.env*``
  files (mirrors the policy enforced by scripts/build_site.py during
  write).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .models import CheckResult

# Mirrors scripts/build_site.py:_FORBIDDEN_ENV_PATTERN. Duplicated here
# because repo-boundaries.v1.json forbids quality_gate from importing
# scripts/. The shared rule is policy-derived; both copies must agree.
_FORBIDDEN_ENV_PATTERN = re.compile(r"^\.env(\..+)?$", flags=re.IGNORECASE)
_ALLOWED_ENV_NAMES = {".env.example"}

# Same default-export detection that scripts/build_site.py:assert_routes_present
# uses. Duplicated here so route-scan can run without importing the builder.
# If one regex changes, the other must change in the same commit.
_DEFAULT_EXPORT_RE = re.compile(
    r"export\s+default\s+(?:async\s+)?(?:function|class|const|let|var|\w+)"
    r"|export\s*\{\s*default\b",
    flags=re.MULTILINE,
)

DEFAULT_TYPECHECK_TIMEOUT_SECONDS = 180
_SCAFFOLDS_DIR = Path(__file__).resolve().parents[1] / "orchestration" / "scaffolds"
_FALLBACK_CONTACT_HREFS = {"/kontakt", "/contact", "/kontakta-oss", "/hitta-hit"}


def _route_to_page_path(target: Path, route: str) -> Path:
    if route == "/":
        return target / "app" / "page.tsx"
    return target / "app" / route.lstrip("/") / "page.tsx"


def run_typecheck_check(
    target_dir: Path,
    *,
    do_typecheck: bool = True,
    timeout: float = DEFAULT_TYPECHECK_TIMEOUT_SECONDS,
) -> CheckResult:
    """Run ``npx tsc --noEmit`` on the target.

    Returns ``status=skipped`` when ``do_typecheck`` is False, when
    ``node_modules`` is missing (typecheck needs the type defs that
    npm install resolved), or when ``npx``/``tsc`` is not on PATH.
    Returns ``failed`` with up to 50 findings when tsc reports errors.
    """
    started = time.monotonic()

    if not do_typecheck:
        return CheckResult(
            name="typecheck",
            status="skipped",
            detail="do_typecheck=False (caller asked to skip).",
        )

    if not (target_dir / "node_modules").exists():
        return CheckResult(
            name="typecheck",
            status="skipped",
            detail=(
                "node_modules saknas; tsc behöver type defs från npm install. "
                "Kör utan --skip-build för att aktivera typecheck."
            ),
        )

    # Mirror scripts/build_site.py:run_npm: resolve the executable via
    # shutil.which and call subprocess with shell=False. shell=True with a
    # list silently drops every argument after the first on POSIX (sh -c
    # only treats args[0] as the command and passes the rest as positional
    # args), so the previous shell=True+list invocation collapsed to a
    # bare `npx` on Linux.
    npx_path = shutil.which("npx")
    if npx_path is None:
        return CheckResult(
            name="typecheck",
            status="skipped",
            detail="npx inte tillgängligt på PATH.",
        )

    try:
        result = subprocess.run(
            [npx_path, "--no-install", "tsc", "--noEmit"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        elapsed = int((time.monotonic() - started) * 1000)
        return CheckResult(
            name="typecheck",
            status="failed",
            detail=f"tsc timeout efter {timeout}s",
            durationMs=elapsed,
        )
    except FileNotFoundError:
        return CheckResult(
            name="typecheck",
            status="skipped",
            detail="npx/tsc inte tillgängligt på PATH.",
        )

    elapsed = int((time.monotonic() - started) * 1000)
    if result.returncode == 0:
        return CheckResult(
            name="typecheck",
            status="ok",
            detail="tsc --noEmit passerade.",
            durationMs=elapsed,
        )

    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    findings = [
        line.strip()
        for line in combined.splitlines()
        if line.strip() and ("error TS" in line or ".ts" in line.lower())
    ]
    return CheckResult(
        name="typecheck",
        status="failed",
        detail=f"tsc rapporterade fel (returncode={result.returncode})",
        findings=findings[:50],
        durationMs=elapsed,
    )


def run_route_scan_check(
    target_dir: Path,
    required_routes: list[str],
) -> CheckResult:
    """Verify every required route has a page.tsx with a default export.

    This is the soft sibling of scripts/build_site.py:assert_routes_present,
    which raises SystemExit. Quality Gate must surface route failures
    in QualityResult, not crash the pipeline.
    """
    started = time.monotonic()
    missing: list[str] = []
    no_export: list[str] = []

    for route in required_routes:
        path = _route_to_page_path(target_dir, route)
        if not path.exists():
            missing.append(f"{route} -> {path.relative_to(target_dir)} (saknas)")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            missing.append(
                f"{route} -> {path.relative_to(target_dir)} (oläsbar: {exc})"
            )
            continue
        if not _DEFAULT_EXPORT_RE.search(text):
            no_export.append(
                f"{route} -> {path.relative_to(target_dir)} (saknar export default)"
            )

    elapsed = int((time.monotonic() - started) * 1000)
    findings = missing + no_export

    if not findings:
        return CheckResult(
            name="route-scan",
            status="ok",
            detail=f"Alla {len(required_routes)} required routes finns med export default.",
            durationMs=elapsed,
        )

    return CheckResult(
        name="route-scan",
        status="failed",
        detail=(
            f"{len(missing)} saknade route-filer, "
            f"{len(no_export)} routes utan default export."
        ),
        findings=findings,
        durationMs=elapsed,
    )


def run_build_status_check(
    *,
    build_status: str,
    npm_steps: list[dict],
) -> CheckResult:
    """Aggregate npm install + npm run build into a CheckResult.

    Reads the result that scripts/build_site.py already computed instead
    of running npm again. Quality Gate is downstream of build, not a
    second build runner.
    """
    if build_status == "skipped":
        return CheckResult(
            name="build-status",
            status="skipped",
            detail="--skip-build aktivt; npm install + npm run build hoppades över.",
        )

    failed_steps = [
        step["name"]
        for step in npm_steps
        if isinstance(step, dict) and step.get("ok") is False
    ]

    if build_status == "ok" and not failed_steps:
        return CheckResult(
            name="build-status",
            status="ok",
            detail=f"npm: {len(npm_steps)} steg ok.",
        )

    return CheckResult(
        name="build-status",
        status="failed",
        detail=f"build_status={build_status}, failed steps: {failed_steps or 'unspecified'}",
        findings=failed_steps,
    )


# Directories the policy-compliance scan never descends into. node_modules
# is the dominant time cost (thousands of files) and never contains
# product .env files. .next is the build output directory. .git would only
# appear if a starter accidentally committed nested git history.
_POLICY_SCAN_SKIP_DIRS = {"node_modules", ".next", ".git", "out", ".turbo"}
_TEXT_EXTENSIONS = {".tsx", ".jsx"}
_CTA_LINK_RE = re.compile(
    r"<(?:Link|a)\b(?=[^>]*\bhref=(?:[\"']([^\"']+)[\"']|\{[\"']([^\"']+)[\"']\}))"
    r"[^>]*>(.*?)</(?:Link|a)>",
    flags=re.IGNORECASE | re.DOTALL,
)
_CTA_TEXT_RE = re.compile(
    r"\b(kontakta|boka|begär|ring|contact|book|request|call)\b"
    r"|hör av|hitta hit|kom igång|get in touch|get started",
    flags=re.IGNORECASE,
)


def _normalize_route_path(route_path: str) -> str:
    path = route_path.strip().lower()
    if len(path) > 1:
        path = path.rstrip("/")
    return path


def _normalize_internal_href(href: str) -> str:
    path = href.strip().lower()
    if not path.startswith("/"):
        return path
    path = path.split("#", 1)[0].split("?", 1)[0]
    return _normalize_route_path(path)


def _is_contact_href(href: str, contact_route_path: str | None) -> bool:
    path = _normalize_internal_href(href)
    if contact_route_path is not None:
        return path == _normalize_route_path(contact_route_path)
    return path in _FALLBACK_CONTACT_HREFS

# Customer-copy-placeholders only. Dev-markers som "TODO:" och "FIXME"
# var med i v1 men gav brus eftersom check:en skannar både code-comments
# och customer-rendering-strängar — ett "TODO:" i en .tsx-kommentar är inte
# samma kategori som "Lorem ipsum" i en hero-rubrik. Reviewer-fynd på PR
# #129 + #133. Lägg inte tillbaka dev-markers utan att samtidigt smala
# scope:t till bara customer-copy-extensions.
# Patterns scanned per physical line (literal tokens / single-line shapes).
_PLACEHOLDER_PATTERNS = [
    ("Lorem ipsum", re.compile(r"lorem ipsum", re.IGNORECASE)),
    ("TBD", re.compile(r"\bTBD\b", re.IGNORECASE)),
    ("PLATSHÅLLARE", re.compile(r"platshållare", re.IGNORECASE)),
    ("REPLACE_ME", re.compile(r"\bREPLACE_ME\b", re.IGNORECASE)),
    ("<insert ... here>", re.compile(r"<insert\b[^>]*\bhere>", re.IGNORECASE)),
    # Generic-AI English template slop. Narrowed (PR #244 review) to clear
    # placeholder SHAPES only - "your company name/website/...", "welcome to
    # your company", a bracketed "[company name]", or "company name (goes) here"
    # - so legitimate English prose on a ``language == "en"`` site ("we help
    # your company grow", "our company name has meant quality since 1999") is
    # NOT a false positive. placeholder-copy-scan is a warning lane, and a false
    # warning erodes trust in the gate. Swedish copy uses "ditt företag" /
    # "företagsnamn" and never trips these.
    (
        "your company template",
        re.compile(
            # Deliberately NOT bare "your company name": that also appears in
            # legit form prompts ("tell us your company name"). The unfilled
            # "your company name" template is caught by the bracketed pattern
            # below ("{your company name}") or by "... goes here".
            r"\byour company (?:website|page|site|logo|here)\b"
            r"|\bwelcome to your company\b",
            re.IGNORECASE,
        ),
    ),
    (
        "company name placeholder",
        re.compile(r"\bcompany name (?:goes here|here)\b", re.IGNORECASE),
    ),
    (
        "bracketed company placeholder",
        # Requires a TWO-word placeholder phrase ("company name", "your
        # company", "your company name") inside the brackets. A bare
        # ``{company}`` / ``{ company }`` is deliberately NOT matched: in TSX
        # source that is a legitimate JSX expression interpolating a variable
        # named ``company`` (Codex review fix), not leaked placeholder copy.
        re.compile(
            r"[\[{]\s*(?:your\s+company(?:\s+name)?|company\s+name)\s*[\]}]",
            re.IGNORECASE,
        ),
    ),
    # Imperative "Insert <det> ..." scaffolding (e.g. "Insert your text
    # here"). The determiner requirement keeps it off code identifiers
    # like insertBefore() and off any bare Swedish word.
    (
        "insert <placeholder>",
        re.compile(
            r"\binsert\s+(?:your|the|a|an|company|customer|business|text|"
            r"image|logo|tagline|name)\b",
            re.IGNORECASE,
        ),
    ),
]

# Patterns scanned over the WHOLE file text so a pretty-printed element that
# spans physical lines is still caught (PR #244 review): the per-line scan
# misses ``<h2>\n   \n</h2>``. ``\s`` already matches newlines, so the same
# regex catches both single-line and multi-line empty headings; the match's
# start offset is mapped back to a 1-based line number for the finding.
_PLACEHOLDER_TEXT_PATTERNS = [
    # Empty section heading: <h1></h1>, <h2> </h2>, <h3>&nbsp;</h3>, and the
    # pretty-printed multi-line form. A rendered heading element with no real
    # text is a structural placeholder, never legitimate copy.
    (
        "empty section heading",
        re.compile(
            r"<h([1-6])\b[^>]*>(?:\s|&nbsp;|&#160;)*</h\1>",
            re.IGNORECASE,
        ),
    ),
]


def run_policy_compliance_check(target_dir: Path) -> CheckResult:
    """Walk target_dir and verify no forbidden .env* files exist.

    Mirrors the policy that scripts/build_site.py enforces during write.
    Quality Gate runs the check post-write so a buggy starter (or a
    future codegenModel hallucination) cannot slip a secret-bearing
    file past the build. Skips ``node_modules`` and other generated
    directories to keep runtime bounded.
    """
    started = time.monotonic()
    findings: list[str] = []

    def _walk(directory: Path) -> None:
        try:
            entries = list(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.is_dir():
                if entry.name in _POLICY_SCAN_SKIP_DIRS:
                    continue
                _walk(entry)
                continue
            if not entry.is_file():
                continue
            name = entry.name
            if name in _ALLOWED_ENV_NAMES:
                continue
            if _FORBIDDEN_ENV_PATTERN.match(name):
                findings.append(str(entry.relative_to(target_dir)))

    _walk(target_dir)
    elapsed = int((time.monotonic() - started) * 1000)
    if not findings:
        return CheckResult(
            name="policy-compliance",
            status="ok",
            detail="Inga förbjudna .env-filer hittades.",
            durationMs=elapsed,
        )

    return CheckResult(
        name="policy-compliance",
        status="failed",
        detail=f"{len(findings)} förbjudna .env-fil(er) hittades.",
        findings=findings,
        durationMs=elapsed,
    )


def _load_routes_payload(routes_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(routes_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _default_routes_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    routes = payload.get("defaultRoutes")
    if not isinstance(routes, list):
        return []
    return [route for route in routes if isinstance(route, dict)]


def _contact_path_from_routes_payload(payload: dict[str, Any]) -> str | None:
    for route in _default_routes_from_payload(payload):
        if route.get("id") != "contact":
            continue
        path = route.get("path")
        if isinstance(path, str) and path.startswith("/"):
            return _normalize_route_path(path)
    return None


def _default_route_paths_from_payload(payload: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for route in _default_routes_from_payload(payload):
        path = route.get("path")
        if isinstance(path, str) and path.startswith("/"):
            paths.add(_normalize_route_path(path))
    return paths


def _existing_app_routes(target_dir: Path) -> set[str]:
    app_dir = target_dir / "app"
    if not app_dir.exists():
        return set()

    routes: set[str] = set()
    try:
        pages = list(app_dir.rglob("page.tsx"))
    except OSError:
        return set()

    for page in pages:
        try:
            relative_parent = page.parent.relative_to(app_dir)
        except ValueError:
            continue
        if relative_parent.parts in ((), (".",)):
            routes.add("/")
            continue
        routes.add(_normalize_route_path("/" + "/".join(relative_parent.parts)))
    return routes


def _contact_path_from_matching_scaffold(target_dir: Path) -> str | None:
    existing_routes = _existing_app_routes(target_dir)
    if not existing_routes or not _SCAFFOLDS_DIR.exists():
        return None

    for routes_path in sorted(_SCAFFOLDS_DIR.glob("*/routes.json")):
        payload = _load_routes_payload(routes_path)
        if payload is None:
            continue
        default_paths = _default_route_paths_from_payload(payload)
        if not default_paths or not default_paths.issubset(existing_routes):
            continue
        contact_path = _contact_path_from_routes_payload(payload)
        if contact_path is not None:
            return contact_path
    return None


def _contact_path_from_known_scaffold_contacts(target_dir: Path) -> str | None:
    """Resolve the contact route from any scaffold's ``id="contact"`` path.

    Robustness fallback for partial app trees: ``_contact_path_from_matching_scaffold``
    only matches when a scaffold's *entire* defaultRoutes set is present. When
    codegen dropped a sibling route (e.g. a restaurant site that kept
    ``/hitta-hit`` but lost ``/meny``) the whole-scaffold match fails and the
    contact page would go unvalidated. Here we collect every scaffold's
    canonical contact path from its ``routes.json`` and accept the first one
    that exists as a generated route — still derived from the route contract,
    never from hardcoded ``kontakt``/``contact`` fragments.
    """
    existing_routes = _existing_app_routes(target_dir)
    if not existing_routes or not _SCAFFOLDS_DIR.exists():
        return None
    for routes_path in sorted(_SCAFFOLDS_DIR.glob("*/routes.json")):
        payload = _load_routes_payload(routes_path)
        if payload is None:
            continue
        contact_path = _contact_path_from_routes_payload(payload)
        if contact_path is not None and contact_path in existing_routes:
            return contact_path
    return None


def _resolve_contact_route_path(target_dir: Path) -> str | None:
    payload = _load_routes_payload(target_dir / "routes.json")
    if payload is not None:
        contact_path = _contact_path_from_routes_payload(payload)
        if contact_path is not None:
            return contact_path

    scaffold_path = _contact_path_from_matching_scaffold(target_dir)
    if scaffold_path is not None:
        return scaffold_path

    return _contact_path_from_known_scaffold_contacts(target_dir)


def _has_contact_cta(text: str, contact_route_path: str | None) -> bool:
    for match in _CTA_LINK_RE.finditer(text):
        href = (match.group(1) or match.group(2) or "").lower()
        body = re.sub(r"<[^>]+>", " ", match.group(3) or "")
        # A link counts as a contact CTA when the href itself carries the
        # contact intent: mail/phone protocols are explicit, and page links
        # must point at the scaffold route whose routes.json id is "contact".
        # For page links, CTA text is still required. Body text alone is not
        # enough; otherwise
        # ``<a href="/products">Ring oss</a>`` would be accepted.
        if href.startswith(("mailto:", "tel:")):
            return True
        if _is_contact_href(href, contact_route_path) and _CTA_TEXT_RE.search(body):
            return True
    return False


def _find_contact_page(target_dir: Path) -> Path | None:
    """Find the contact page from the scaffold routes.json contract."""
    contact_path = _resolve_contact_route_path(target_dir)
    if contact_path is None:
        return None
    page = _route_to_page_path(target_dir, contact_path)
    return page if page.exists() else None


def run_contact_cta_presence_check(target_dir: Path) -> CheckResult:
    findings: list[str] = []
    detail = ""
    home = target_dir / "app" / "page.tsx"
    contact_route_path = _resolve_contact_route_path(target_dir)
    contact = (
        _route_to_page_path(target_dir, contact_route_path)
        if contact_route_path is not None
        else None
    )
    if not home.exists() and contact_route_path is None:
        return CheckResult(
            name="contact-cta-presence",
            status="skipped",
            detail="Ingen startsida eller resolvbar contact-route hittades.",
        )
    try:
        home_text = home.read_text(encoding="utf-8")
    except OSError:
        home_text = ""
    hero = (
        re.search(r"<section\b.*?</section>", home_text, re.IGNORECASE | re.DOTALL)
        or [home_text]
    )[0]
    if not _has_contact_cta(hero, contact_route_path):
        findings.append("app/page.tsx: hero saknar kontakt-CTA")
    if contact_route_path is None:
        # A generated site whose contact route cannot be resolved from its own
        # routes.json, a whole-scaffold match, or any known scaffold contact
        # path has effectively lost its contact page. Surface it as a (warning-
        # severity, non-blocking) finding instead of a silent ``ok`` so the
        # operator sees that the contact page could not be validated.
        findings.append(
            'routes.json: contact-route (id="contact") kunde inte resolvas - '
            "kontaktsidan kunde inte valideras"
        )
        detail = (
            "Contact-route kunde inte resolvas från routes.json eller "
            "scaffold-routes; kontaktsidecheck kunde inte köras."
        )
    elif contact is None:
        missing_page = _route_to_page_path(target_dir, contact_route_path)
        findings.append(
            f"{contact_route_path} -> {missing_page.relative_to(target_dir)} (saknas)"
        )
    else:
        try:
            contact_text = contact.read_text(encoding="utf-8")
        except OSError:
            contact_text = ""
        if not _has_contact_cta(contact_text, contact_route_path):
            findings.append(f"{contact.relative_to(target_dir)}: saknar kontakt-CTA")
        else:
            detail = f"Contact-route resolverad från routes.json: {contact_route_path}."
    return CheckResult(
        name="contact-cta-presence",
        status="failed" if findings else "ok",
        detail=detail,
        findings=findings,
    )


def run_placeholder_copy_scan_check(target_dir: Path) -> CheckResult:
    findings: list[str] = []
    for path in target_dir.rglob("*"):
        if any(part in _POLICY_SCAN_SKIP_DIRS for part in path.parts) or path.suffix not in _TEXT_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(target_dir)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for label, pattern in _PLACEHOLDER_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{rel}:{line_no}: {label}")
        # Whole-text scan for shapes that may span pretty-printed lines.
        for label, pattern in _PLACEHOLDER_TEXT_PATTERNS:
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                findings.append(f"{rel}:{line_no}: {label}")
    return CheckResult(
        name="placeholder-copy-scan",
        status="failed" if findings else "ok",
        findings=findings[:50],
    )
