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

import re
import shutil
import subprocess
import time
from pathlib import Path

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
    r"|hör av|kom igång|get in touch|get started",
    flags=re.IGNORECASE,
)
# Scaffolds map ``id="contact"`` i routes.json till olika path-segment.
# Här täcks de varianter som existerande scaffolds använder:
#   - ``kontakt`` / ``contact`` (substring matchar ``/kontakt``,
#     ``/kontakta-oss``, ``/contact-us``)
#   - ``hitta-hit`` (restaurant-hospitality, helt unik path som inte
#     innehåller "kontakt"/"contact"-substring)
# Framtida sprint: läsa scaffoldens routes.json explicit och resolva
# ``id="contact"`` istället för pattern-matching. Registreras som
# tech-debt-not i ``docs/known-issues.md`` om någon ny scaffold tappar
# på pattern-matching här (GPT P2 Badge 2026-05-27).
_CONTACT_ROUTE_FRAGMENTS = ("kontakt", "contact", "hitta-hit")


def _is_contact_href(href: str) -> bool:
    lower = href.lower()
    return any(frag in lower for frag in _CONTACT_ROUTE_FRAGMENTS)


def _is_contact_route_dir(name: str) -> bool:
    lower = name.lower()
    return any(frag in lower for frag in _CONTACT_ROUTE_FRAGMENTS)

# Customer-copy-placeholders only. Dev-markers som "TODO:" och "FIXME"
# var med i v1 men gav brus eftersom check:en skannar både code-comments
# och customer-rendering-strängar — ett "TODO:" i en .tsx-kommentar är inte
# samma kategori som "Lorem ipsum" i en hero-rubrik. Reviewer-fynd på PR
# #129 + #133. Lägg inte tillbaka dev-markers utan att samtidigt smala
# scope:t till bara customer-copy-extensions.
_PLACEHOLDER_PATTERNS = [
    ("Lorem ipsum", re.compile(r"lorem ipsum", re.IGNORECASE)),
    ("TBD", re.compile(r"\bTBD\b", re.IGNORECASE)),
    ("PLATSHÅLLARE", re.compile(r"platshållare", re.IGNORECASE)),
    ("REPLACE_ME", re.compile(r"\bREPLACE_ME\b", re.IGNORECASE)),
    ("<insert ... here>", re.compile(r"<insert\b[^>]*\bhere>", re.IGNORECASE)),
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


def _has_contact_cta(text: str) -> bool:
    for match in _CTA_LINK_RE.finditer(text):
        href = (match.group(1) or match.group(2) or "").lower()
        body = re.sub(r"<[^>]+>", " ", match.group(3))
        # A link is a valid contact CTA if:
        # 1. It's a tel: or mailto: link (href check is sufficient), OR
        # 2. It links to a contact-route page (substring matchar bl.a.
        #    /kontakt, /kontakta-oss, /contact, /contact-us, /hitta-hit), OR
        # 3. The body text matches CTA patterns (regardless of href)
        if (
            href.startswith(("mailto:", "tel:"))
            or _is_contact_href(href)
            or _CTA_TEXT_RE.search(body)
        ):
            return True
    return False


def _find_contact_page(target_dir: Path) -> Path | None:
    """Hitta scaffoldens contact-page genom att iterera ``app/``.

    Tidigare hårdkodades ``app/kontakt/page.tsx`` + ``app/contact/page.tsx``,
    vilket missade scaffolds med alternativa contact-route-paths
    (``agency-studio``/``clinic-healthcare``/``professional-services`` →
    ``/kontakta-oss``, ``restaurant-hospitality`` → ``/hitta-hit``).
    Reviewer-fynd: GPT P2 Badge 2026-05-27 + Cursor BugBot suggestion 4.
    """
    app_dir = target_dir / "app"
    if not app_dir.exists():
        return None
    for entry in app_dir.iterdir():
        if not entry.is_dir():
            continue
        if not _is_contact_route_dir(entry.name):
            continue
        page = entry / "page.tsx"
        if page.exists():
            return page
    return None


def run_contact_cta_presence_check(target_dir: Path) -> CheckResult:
    findings: list[str] = []
    home = target_dir / "app" / "page.tsx"
    contact = _find_contact_page(target_dir)
    if not home.exists() and contact is None:
        return CheckResult(name="contact-cta-presence", status="skipped")
    try:
        home_text = home.read_text(encoding="utf-8")
    except OSError:
        home_text = ""
    hero = (re.search(r"<section\b.*?</section>", home_text, re.IGNORECASE | re.DOTALL) or [home_text])[0]
    if not _has_contact_cta(hero):
        findings.append("app/page.tsx: hero saknar kontakt-CTA")
    if contact is None:
        findings.append("app/: kontaktsida saknas (sökte efter dir med 'kontakt'/'contact'/'hitta-hit')")
    else:
        try:
            contact_text = contact.read_text(encoding="utf-8")
        except OSError:
            contact_text = ""
        if not _has_contact_cta(contact_text):
            findings.append(f"{contact.relative_to(target_dir)}: saknar kontakt-CTA")
    return CheckResult(
        name="contact-cta-presence",
        status="failed" if findings else "ok",
        findings=findings,
    )


def run_placeholder_copy_scan_check(target_dir: Path) -> CheckResult:
    findings: list[str] = []
    for path in target_dir.rglob("*"):
        if any(part in _POLICY_SCAN_SKIP_DIRS for part in path.parts) or path.suffix not in _TEXT_EXTENSIONS:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, line in enumerate(lines, start=1):
            for label, pattern in _PLACEHOLDER_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path.relative_to(target_dir)}:{line_no}: {label}")
    return CheckResult(
        name="placeholder-copy-scan",
        status="failed" if findings else "ok",
        findings=findings[:50],
    )
