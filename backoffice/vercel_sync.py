"""Backoffice-wrappers för Vercel-länk, env-pull och build-context-uppladdning.

Speglar ``health.py``-mönstret (subprocess -> ``CheckResult``) men för Vercel-
operationerna: ladda upp Python-byggmotorn (LLM-kedjan) till blob + KV så den
hostade runtimen kör senaste koden. Allt körs read-capture (ingen interaktivitet)
så det fungerar inuti Streamlit. ``vercel link`` är interaktivt och görs INTE
härifrån — vyn visar bara länk-status och hänvisar till terminalen/CLI-skriptet
``scripts/sync_vercel_build_context.py`` när länk saknas.

Blob- och KV-storen delas av alla Vercel-miljöer, så en uppladdning gäller
production/preview/development samtidigt.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from backoffice.health import CheckResult
from backoffice.paths import REPO_ROOT

CHECK_SCRIPT = "apps/viewser/scripts/check-build-context.mjs"
UPLOAD_SCRIPT = "apps/viewser/scripts/upload-build-context-to-blob.mjs"
ENV_FILE = "apps/viewser/.env.vercel.local"


def is_linked() -> bool:
    """True om repot har en Vercel-projektlänk på disk (``.vercel/``)."""
    vercel_dir = REPO_ROOT / ".vercel"
    return (vercel_dir / "project.json").exists() or (vercel_dir / "repo.json").exists()


def _exec_prefix(tool_path: str) -> list[str]:
    """Wrappa Windows-batchshims (``vercel.cmd``) i ``cmd /c``; .exe körs direkt."""
    if os.name == "nt" and tool_path.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", tool_path]
    return [tool_path]


def _missing(name: str, tool: str) -> CheckResult:
    return CheckResult(
        name=name,
        ok=False,
        output=(
            f"{tool} hittades inte i PATH. Installera Node.js (node) respektive "
            "Vercel CLI (`npm i -g vercel`) och försök igen."
        ),
        exit_code=127,
    )


def _run(name: str, tool: str, args: list[str]) -> CheckResult:
    resolved = shutil.which(tool)
    if resolved is None:
        return _missing(name, tool)
    result = subprocess.run(
        _exec_prefix(resolved) + args,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    return CheckResult(
        name=name,
        ok=(result.returncode == 0),
        output=output,
        exit_code=result.returncode,
    )


def run_check() -> CheckResult:
    """Jämför uppladdad build-context-SHA i KV mot aktuell HEAD (ändrar inget)."""
    return _run("build-context:check", "node", [CHECK_SCRIPT])


def run_env_pull() -> CheckResult:
    """``vercel env pull`` -> apps/viewser/.env.vercel.local (development)."""
    return _run("vercel env pull", "vercel", ["env", "pull", ENV_FILE, "--yes"])


def run_upload() -> CheckResult:
    """Paketera + ladda upp build-kontexten (Python-motorn) till blob + KV."""
    return _run("build-context:upload", "node", [UPLOAD_SCRIPT])
