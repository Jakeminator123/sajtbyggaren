"""Source-level locks för den hostade OpenClaw apply-sömmen (commit 2).

Lokalt kör ``runPromptBuildOnce`` (apps/viewser/app/api/prompt/route.ts)
``runOpenClawFollowupApply`` FÖRST på en followup och grenar:
``applied`` -> använd OpenClaw-bygget; answer-only/conversation -> svara utan
bygge; annars (applied=false icke-conversation, eller bridge-fel) -> fall
igenom till legacy-bygget. Den hostade vägen körde tidigare ALLTID legacy
(``prompt_to_project_input --followup-site-id`` + ``build_site.py --dossier``).

Commit 2 ger hostat samma grindordning i sandbox-skriptet:

1. I followup-läget körs ``scripts/run_openclaw_followup.py --apply --site-id``
   FÖRST (med ``SAJTBYGGAREN_GENERATED_DIR`` exporterad så
   ``run_followup_chain``:s build landar i sandboxens generated-dir).
2. Den sista ``OPENCLAW_BRIDGE_JSON:``-raden parsas (samma sentinel som
   ``openclaw-runner.ts``); bara kontrollerade enum/id-fält når env-filen.
3. Grenar:
   - ``answer_only`` -> INGET bygge, ``post_status done``, ``exit 0``.
   - ``applied`` (ok/degraded) -> ``RUN_ARTIFACT_RUN_ID`` = ``chain.runId``,
     fortsätt till den befintliga upload-/persist-fasen (current.json är redan
     swappad).
   - ``applied_failed`` -> ärlig ``fail`` (aldrig maskera som lyckat, fall
     INTE till legacy -> ingen dubbel-build).
   - annars -> legacy-vägen tar över (ärlig fallback; bevarar dagens
     fungerande hostade copy-direktivväg).
4. Maskerar aldrig legacy-success som OpenClaw: legacy-grenen sätter aldrig
   OPENCLAW_APPLIED=1.

Skyddar B198 del b: apply-vägen delegerar till oförändrade
``run_followup_chain`` — inga contact-form/section-render-vägar rörs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.core, pytest.mark.tooling, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "apps" / "viewser" / "lib" / "hosted-build-runner.ts"


def _runner_source() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_followup_invokes_openclaw_apply_with_generated_dir() -> None:
    source = _runner_source()
    assert (
        'export SAJTBYGGAREN_GENERATED_DIR="$GENERATED_DIR"' in source
    ), (
        "run_followup_chain tar inte --generated-dir via CLI:t — sandboxen "
        "MÅSTE exportera SAJTBYGGAREN_GENERATED_DIR så apply-bygget landar i "
        "rätt generated-dir."
    )
    assert (
        'scripts/run_openclaw_followup.py --apply --site-id "$SITE_ID"' in source
    ), "Followup-grenen måste köra OpenClaw apply-sömmen."
    # PROMPT_TEXT når CLI:t bara som quotad env-expansion efter `--`.
    assert '-- "$PROMPT_TEXT" 2>&1) || true' in source, (
        "Prompten får aldrig interpoleras i bash-kod; `--`-separatorn skyddar "
        "mot flagg-tolkning och `|| true` låter parsen avgöra fallback."
    )


def test_apply_seam_runs_before_legacy_path() -> None:
    """OpenClaw-grinden ligger FÖRE legacy-blocket (samma ordning som lokalt)."""
    source = _runner_source()
    apply_at = source.index("scripts/run_openclaw_followup.py --apply")
    legacy_gate_at = source.index('if [ "\\${OPENCLAW_APPLIED:-0}" != "1" ]; then')
    assert apply_at < legacy_gate_at, (
        "Apply-sömmen måste köras före legacy-fallbacken (applied -> "
        "answer-only -> legacy), precis som runPromptBuildOnce."
    )


def test_bridge_parsed_via_sentinel_contract() -> None:
    source = _runner_source()
    assert 'SENT = "OPENCLAW_BRIDGE_JSON:"' in source, (
        "Bridge-payloaden måste läsas bakom samma sentinel-prefix som "
        "openclaw-runner.ts (B174-kontraktet)."
    )
    # Bara kontrollerade fält skrivs till env-filen som source:as.
    for key in ("APPLY_KIND=", "APPLY_RUN_ID=", "APPLY_VERSION=", "APPLY_BUILD_STATUS="):
        assert key in source, f"Parsen måste emittera {key!r}."
    # runId valideras mot run-id-grammatiken innan det source:as.
    assert 're.fullmatch(r"[A-Za-z0-9._-]+", rid)' in source, (
        "chain.runId måste valideras mot run-id-grammatiken innan det blir "
        "RUN_ARTIFACT_RUN_ID (det source:as i bash)."
    )


def test_answer_only_starts_no_build() -> None:
    source = _runner_source()
    answer_at = source.index("answer_only)")
    # answer_only-grenen skriver result, postar done och exit:ar UTAN att
    # bygga/ladda upp (commit 3 la till write_hosted_result före post_status).
    segment = source[answer_at : answer_at + 520]
    assert 'write_hosted_result "answer-only"' in segment
    assert 'post_status "done" "" ""' in segment
    assert "exit 0" in segment, (
        "Answer-only måste exit:a före bygg-/upload-faserna — inget bygge."
    )


def test_applied_sets_run_artifact_run_id_from_chain() -> None:
    source = _runner_source()
    applied_at = source.index("    applied)")
    segment = source[applied_at : applied_at + 360]
    assert 'RUN_ARTIFACT_RUN_ID="$APPLY_RUN_ID"' in segment, (
        "applied-grenen måste använda chain.runId som artefakt-run-id så "
        "persistensen tarballar rätt data/runs/<runId>/."
    )
    assert "OPENCLAW_APPLIED=1" in segment


def test_applied_failed_is_honest_fail_not_legacy() -> None:
    source = _runner_source()
    failed_at = source.index("    applied_failed)")
    segment = source[failed_at : failed_at + 360]
    assert "fail " in segment, (
        "Ett applicerat men misslyckat bygge måste fela ärligt — inte "
        "dubbel-bygga via legacy."
    )
    assert "OPENCLAW_APPLIED=1" not in segment


def test_legacy_fallback_never_masks_as_openclaw() -> None:
    """Legacy-grenen sätter aldrig OPENCLAW_APPLIED=1 (ärlig attribution)."""
    source = _runner_source()
    gate_at = source.index('if [ "\\${OPENCLAW_APPLIED:-0}" != "1" ]; then')
    # Från legacy-grinden till slutet av build-blocket finns inget
    # OPENCLAW_APPLIED=1 (legacy får aldrig maskeras som OpenClaw-apply).
    active_build_at = source.index(
        "Aktiv immutable build via current.json", gate_at
    )
    segment = source[gate_at:active_build_at]
    assert "OPENCLAW_APPLIED=1" not in segment, (
        "Legacy-fallbacken får ALDRIG sätta OPENCLAW_APPLIED=1 — det skulle "
        "maskera ett legacy-bygge som en OpenClaw-apply."
    )
    # Legacy bevarar den fungerande copy-vägen (build_site.py --dossier).
    assert 'scripts/build_site.py --dossier "$DOSSIER_PATH"' in segment


def test_run_state_version_branches_for_apply_path() -> None:
    """RUN_STATE_VERSION tas från bridgen på apply-vägen (PI_OUT är osatt)."""
    source = _runner_source()
    assert 'if [ "$OPENCLAW_APPLIED" = "1" ]; then' in source
    assert 'RUN_STATE_VERSION="$RUN_STATE_VERSION_OVERRIDE"' in source, (
        "På apply-vägen finns ingen PI_OUT-stdout — versionen måste komma "
        "från bridgens chain.version (set -u-säkert)."
    )
