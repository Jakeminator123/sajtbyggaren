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
