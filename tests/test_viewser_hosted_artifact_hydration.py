"""Source-level locks för hostad run-artefakt-hydrering (B199).

Lokalt ligger de kanoniska run-artefakterna (``data/runs/<runId>/``:
input/site-brief/site-plan/generation-package/build-result/quality-result)
på operatörens disk. I en färsk Vercel Sandbox fanns de aldrig, så OpenClaw
apply-sömmen (``run_followup_chain`` / ``assemble_context(
"artifacts_plus_sections")``) och ``prompt_to_project_input --base-run-id``
hade inget att läsa hostat. B194 persisterar bara PI/meta-paret.

B199 (commit 1 av hostad follow-up-paritet) stänger gapet med EN tarball:

1. Efter varje lyckat hostat bygge tarballas ``data/runs/<runId>/`` och laddas
   upp versions-scopat till blob under
   ``run-artifacts/<siteId>/v<N>/run-artifacts.tar.gz``; pekaren
   ``viewser:site:<siteId>:run-state`` (B194) utökas med ``runId`` +
   ``runArtifactsUrl`` — men BARA när tarballen faktiskt publicerades.
2. ``startHostedBuild`` läser pekarens nya fält pre-flight och injicerar dem
   som env ``RUN_ARTIFACTS_URL`` / ``RUN_ARTIFACTS_RUN_ID`` (tomma vid
   initialbygge / äldre pekare — set -u-säkert).
3. Vid followup curlar + extraherar skriptet tarballen till ``data/runs/``
   INNAN bygg-/apply-kommandot körs — exakt den layout Python-sidan läser.
4. En äldre pekare (före B199) eller misslyckad nedladdning är INTE fatal:
   apply degraderar ärligt till legacy-vägen (som bara behöver PI/meta).

Begränsningen i v1 (pekaren spårar bara SENASTE versionen) är stängd av
B199 v2: runId-indexet ``viewser:run:<runId>`` låter ``startHostedBuild``
hydrera en HISTORISK baseRunId:s artefakter — se
``test_viewser_hosted_run_history.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.core, pytest.mark.tooling, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "apps" / "viewser" / "lib" / "hosted-build-runner.ts"


def _runner_source() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_artifact_urls_reach_sandbox_as_env() -> None:
    """URL:erna injiceras alltid (set -u-säkert): tomma vid initialbygge."""
    source = _runner_source()
    assert 'RUN_ARTIFACTS_URL: runState?.runArtifactsUrl ?? ""' in source
    assert 'RUN_ARTIFACTS_RUN_ID: runState?.runId ?? ""' in source


def test_script_hydrates_artifacts_before_build_command() -> None:
    """Bash-sidan: tarballen hämtas + extraheras till data/runs/ före bygget."""
    source = _runner_source()
    # set -u-säkra referenser (template-literal-escapade i källan).
    assert '"\\${RUN_ARTIFACTS_URL:-}"' in source
    assert '"\\${RUN_ARTIFACTS_RUN_ID:-}"' in source
    # Extraheras till data/runs så data/runs/<runId>/ återställs exakt.
    assert 'tar -xzf /tmp/run-artifacts.tar.gz -C "$REPO_DIR/data/runs"' in source
    # Hydreringen måste ske INNAN prompt_to_project_input körs.
    hydrate_at = source.index('tar -xzf /tmp/run-artifacts.tar.gz')
    followup_call_at = source.index("--followup-site-id")
    assert hydrate_at < followup_call_at, (
        "Artefakt-hydreringen måste ske INNAN bygg-/apply-kommandot körs."
    )


def test_artifact_hydration_failure_is_non_fatal() -> None:
    """Saknad/misslyckad tarball → varning (degradera till legacy), inte fail."""
    source = _runner_source()
    warning_at = source.index("run-artefakt-tarballen kunde inte hamtas")
    # Felvägen får inte anropa fail() — apply degraderar till legacy.
    segment = source[warning_at - 200 : warning_at + 200]
    assert "fail " not in segment and 'fail "' not in segment, (
        "En saknad artefakt-tarball får inte fälla followupen — legacy-vägen "
        "behöver bara PI/meta."
    )


def test_hydration_is_followup_only() -> None:
    """Hydreringen ligger i FOLLOWUP_MODE-grenen, inte i initialbygget."""
    source = _runner_source()
    # Hydreringsblocket ligger efter run-state-fetch (followup-grenen) och före
    # det icke-followup init-anropet (--site-id "$SITE_ID").
    hydrate_at = source.index('if [ -n "\\${RUN_ARTIFACTS_URL:-}" ]')
    init_call_at = source.index('--site-id "$SITE_ID"')
    followup_fetch_at = source.index('fetch_run_state "$RUN_STATE_PI_URL"')
    assert followup_fetch_at < hydrate_at < init_call_at, (
        "Artefakt-hydreringen hör hemma i followup-grenen (efter PI/meta-"
        "fetch, före init-anropet)."
    )
