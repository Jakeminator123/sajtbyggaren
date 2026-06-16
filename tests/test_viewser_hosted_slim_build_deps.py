"""Source-level + consistency locks for the slim hosted build dependency set.

perf(hosted): the cold build sandbox previously ran ``pip install -r
requirements.txt``, which drags in streamlit (-> pandas/pyarrow/numpy/altair),
openai-agents (operator-only ``scripts/component_intake.py``) and the dev tools
(pytest*/ruff) -- none of which the deterministic generation pipe
(scripts/build_site.py, scripts/prompt_to_project_input.py,
scripts/run_openclaw_followup.py, packages/generation/**) imports. A slim
``requirements-build.txt`` lets the sandbox install only what the build path
needs, cutting the heaviest avoidable chunk off every hosted follow-up's
``installing`` phase.

These locks keep that slim list honest:

  * it stays a strict, SAME-SPEC subset of requirements.txt (no version drift,
    never under-installs vs the canonical full list),
  * it never carries the heavy/dev packages the build path does not import,
  * it still carries the build path's real runtime deps,
  * the hosted orchestration script PREFERS it but falls back to
    requirements.txt so an older uploaded build-context tarball keeps working,
  * the build-context packer + freshness guard actually ship + watch the file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.tooling, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = REPO_ROOT / "requirements.txt"
REQUIREMENTS_BUILD = REPO_ROOT / "requirements-build.txt"
RUNNER = REPO_ROOT / "apps" / "viewser" / "lib" / "hosted-build-runner.ts"
UPLOAD_SCRIPT = (
    REPO_ROOT / "apps" / "viewser" / "scripts" / "upload-build-context-to-blob.mjs"
)
CHECK_SCRIPT = (
    REPO_ROOT / "apps" / "viewser" / "scripts" / "check-build-context.mjs"
)

# Direct requirements the deterministic build path NEVER imports. Verified by
# grep: only scripts/component_intake.py (an operator-only tool, lazy import)
# pulls ``agents``; nothing on the build path imports streamlit/pytest/ruff or
# their unique transitive deps (numpy/pandas/pyarrow/altair/mcp/griffe/...).
EXCLUDED_FROM_BUILD = {
    "streamlit",
    "openai-agents",
    "pytest",
    "pytest-cov",
    "pytest-xdist",
    "ruff",
}

# Deps the build path imports at module load (build_site.py imports ``requests``
# at the top; the pipe imports pydantic/jsonschema/openai). Their absence would
# break the sandbox build, so the slim list must keep carrying them.
REQUIRED_IN_BUILD = {"jsonschema", "pydantic", "openai", "requests"}


def _requirement_lines(path: Path) -> list[str]:
    """Non-comment, non-blank requirement specs (CR-safe via strip)."""
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def _package_name(spec: str) -> str:
    """Bare distribution name (strip version operators / extras / markers)."""
    return re.split(r"[<>=!~;\[ ]", spec, maxsplit=1)[0].strip().lower()


def test_requirements_build_file_exists() -> None:
    assert REQUIREMENTS_BUILD.is_file(), (
        "requirements-build.txt saknas -- den hostade bygg-sandboxen behover "
        "den slimmade beroendelistan."
    )


def test_build_deps_are_same_spec_subset_of_full() -> None:
    """Every build dep must appear VERBATIM in requirements.txt: no drift and
    never a looser/diverging version than the canonical list."""
    full = set(_requirement_lines(REQUIREMENTS))
    missing = [spec for spec in _requirement_lines(REQUIREMENTS_BUILD) if spec not in full]
    assert not missing, (
        "requirements-build.txt-rader saknas verbatim i requirements.txt "
        f"(drift): {missing}. Hall samma versionsspec i bada filerna."
    )


def test_build_deps_exclude_heavy_and_dev_packages() -> None:
    names = {_package_name(spec) for spec in _requirement_lines(REQUIREMENTS_BUILD)}
    leaked = names & EXCLUDED_FROM_BUILD
    assert not leaked, (
        "requirements-build.txt far inte bara paket som bygg-pipen aldrig "
        f"importerar (ren latens i kall sandbox): {sorted(leaked)}."
    )


def test_build_deps_cover_build_path_runtime_imports() -> None:
    names = {_package_name(spec) for spec in _requirement_lines(REQUIREMENTS_BUILD)}
    missing = REQUIRED_IN_BUILD - names
    assert not missing, (
        "requirements-build.txt maste bara bygg-pipens runtime-beroenden "
        f"(annars failar importerna i sandboxen): {sorted(missing)}."
    )


def test_full_requirements_stays_complete_superset() -> None:
    """The full list must still carry the excluded packages: local/CI and the
    sandbox fallback path both rely on requirements.txt staying complete."""
    names = {_package_name(spec) for spec in _requirement_lines(REQUIREMENTS)}
    missing = EXCLUDED_FROM_BUILD - names
    assert not missing, (
        f"requirements.txt maste forbli den fulla listan; saknar {sorted(missing)}."
    )


def test_orchestration_prefers_slim_with_fallback() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert 'REQ_FILE="requirements.txt"' in source, (
        "Install-fasen maste defaulta till requirements.txt som fallback for en "
        "aldre uppladdad build-kontext utan den slimmade filen."
    )
    assert "if [ -f requirements-build.txt ]; then" in source, (
        "Install-fasen maste foredra requirements-build.txt nar den finns."
    )
    assert 'REQ_FILE="requirements-build.txt"' in source
    assert '-r "$REQ_FILE"' in source, (
        "pip install maste anvanda den valda REQ_FILE (slim eller fallback)."
    )


def test_build_context_ships_and_watches_slim_file() -> None:
    upload = UPLOAD_SCRIPT.read_text(encoding="utf-8")
    check = CHECK_SCRIPT.read_text(encoding="utf-8")
    assert '"requirements-build.txt"' in upload, (
        "Packaren maste inkludera requirements-build.txt i build-kontext-"
        "tarballen, annars kan sandboxen aldrig foredra den."
    )
    assert '"requirements-build.txt"' in check, (
        "Freshness-guarden maste bevaka requirements-build.txt sa en andring "
        "flaggar att build-kontexten behover laddas upp igen."
    )
