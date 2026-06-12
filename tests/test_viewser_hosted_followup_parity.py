"""Source-level locks för hostad request/response-paritet (commit 3).

Lokalt trär ``/api/prompt`` baseRunId + markedSections genom till
``prompt_to_project_input.py`` och returnerar ett rikt svar (version,
briefSource, buildResult, appliedCopyDirectives, changeSet, openClawDecision,
bridge, conversation, answerText). Den hostade vägen tappade tidigare
baseRunId/markedSections (trots att schemat validerar dem) och returnerade
ett tunt svar (runId/siteId/buildStatus/hosted/buildId).

Commit 3 stänger gapet (källkods-lås, samma mönster som de andra
test_viewser_hosted_*-modulerna):

REQUEST
  - ``runHostedPromptFlow`` trär ``payload.baseRunId`` + ``payload.markedSections``
    in i ``startHostedBuild``.
  - Runnern re-validerar baseRunId (run-id-grammatik) och sanerar markedSections
    med SAMMA delade ``sanitizedMarkedSections`` som den lokala spawn-vägen,
    och injicerar ``BASE_RUN_ID`` / ``MARKED_SECTIONS_JSON`` (tomma = ingen
    flagga, set -u-säkert).
  - Sandbox-skriptet forwardar ``--base-run-id`` till BÅDE OpenClaw apply-anropet
    och legacy-PI-anropet, och ``--marked-sections`` till legacy-PI-anropet
    (run_openclaw_followup.py har ingen --marked-sections-flagga, exakt som den
    lokala apply-vägen inte heller forwardar den).

RESPONSE
  - Sandboxen POST:ar ett ``result``-block (HostedFollowupResult) in i
    KV-statusdoken; ``runHostedPromptFlow`` bygger ett svar via
    ``buildHostedFollowupResponse`` som speglar den lokala kontraktsformen.
  - Answer-only: runId:null, ingen build, answerText (TS-genererad).
  - Applied/legacy: ärlig attribution via ``engine`` (legacy maskeras aldrig
    som OpenClaw); openClawDecision honesty-gateas precis som lokalt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.core, pytest.mark.tooling]

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER = REPO_ROOT / "apps" / "viewser"
RUNNER = VIEWSER / "lib" / "hosted-build-runner.ts"
PROMPT_RUNNER = VIEWSER / "lib" / "prompt-runner.ts"
PROMPT_ROUTE = VIEWSER / "app" / "api" / "prompt" / "route.ts"


def _runner() -> str:
    return RUNNER.read_text(encoding="utf-8")


def _route() -> str:
    return PROMPT_ROUTE.read_text(encoding="utf-8")


# --- 1. baseRunId tappas INTE -------------------------------------------------


def test_base_run_id_threaded_and_forwarded() -> None:
    route = _route()
    assert (
        "...(payload.baseRunId ? { baseRunId: payload.baseRunId } : {})" in route
    ), "runHostedPromptFlow måste trä payload.baseRunId in i startHostedBuild."
    runner = _runner()
    # Re-validerad + injicerad som env.
    assert "req.followup && req.baseRunId && /^[a-zA-Z0-9._-]+$/.test(req.baseRunId)" in runner
    assert "BASE_RUN_ID: safeBaseRunId," in runner
    # Forwardas till BÅDE apply-anropet och legacy-PI-anropet (set -u-säkert).
    assert 'BASE_RUN_ID_ARGS=(--base-run-id "$BASE_RUN_ID")' in runner, (
        "OpenClaw apply-anropet måste forwarda --base-run-id."
    )
    assert 'LEGACY_BASE_RUN_ID_ARGS=(--base-run-id "$BASE_RUN_ID")' in runner, (
        "Legacy-PI-anropet måste också forwarda --base-run-id."
    )


# --- 2. markedSections tappas INTE -------------------------------------------


def test_marked_sections_threaded_and_forwarded() -> None:
    route = _route()
    assert (
        "...(payload.markedSections?.length\n        ? { markedSections: payload.markedSections }\n        : {})"
        in route
    ), "runHostedPromptFlow måste trä payload.markedSections in i startHostedBuild."
    runner = _runner()
    assert "sanitizedMarkedSections" in runner, (
        "markedSections måste saneras med den delade sanitizedMarkedSections "
        "(en saneringskälla, två spawn-sömmar)."
    )
    assert "MARKED_SECTIONS_JSON: safeMarkedSections.length" in runner
    # --marked-sections forwardas till legacy-PI-anropet (inte apply — samma
    # som lokala vägen).
    assert 'MARKED_SECTIONS_ARGS=(--marked-sections "$MARKED_SECTIONS_JSON")' in runner


def test_sanitized_marked_sections_is_exported_and_shared() -> None:
    prompt_runner = PROMPT_RUNNER.read_text(encoding="utf-8")
    assert "export function sanitizedMarkedSections" in prompt_runner, (
        "sanitizedMarkedSections måste vara exporterad så hostad + lokal väg "
        "delar EXAKT samma sanering."
    )
    runner = _runner()
    assert (
        'import { sanitizedAssetSetIntent, sanitizedMarkedSections } from "./prompt-runner";'
        in runner
    )


# --- 3. edit-followup via OpenClaw apply (cross-ref commit 2) ------------------


def test_edit_followup_routes_through_openclaw_apply() -> None:
    runner = _runner()
    apply_at = runner.index("scripts/run_openclaw_followup.py --apply")
    legacy_gate_at = runner.index('if [ "\\${OPENCLAW_APPLIED:-0}" != "1" ]; then')
    assert apply_at < legacy_gate_at, (
        "OpenClaw apply måste köras före legacy-fallbacken (edit -> apply, "
        "annars legacy)."
    )


# --- 4. answer-only returnerar answerText UTAN runId/utan bygge ----------------


def test_answer_only_returns_answer_without_run_id() -> None:
    runner = _runner()
    # Sandboxen skriver result med engine=answer-only och bygger inte.
    assert 'write_hosted_result "answer-only"' in runner
    answer_at = runner.index('write_hosted_result "answer-only"')
    exit_at = runner.index("exit 0", answer_at)
    assert exit_at - answer_at < 200, (
        "Answer-only måste skriva result + exit:a UTAN att bygga."
    )
    route = _route()
    # buildHostedFollowupResponse answer-only-grenen: runId:null + answerText.
    block = route.split('if (result.engine === "answer-only") {', 1)[1][:900]
    assert "runId: null," in block
    assert "buildStatus: null," in block
    assert "answerText," in block
    assert "generateConversationAnswer" in block, (
        "answerText hostat måste återvinna den lokala chat-hjälpen."
    )


# --- 5. legacy-fallback är explicit/ärlig — aldrig maskerad som OpenClaw -------


def test_legacy_fallback_is_honest_engine_attribution() -> None:
    runner = _runner()
    # Sandboxen attribuerar legacy explicit och nollar aldrig sanningen.
    assert 'write_hosted_result "legacy"' in runner
    assert 'write_hosted_result "openclaw"' in runner
    # HostedFollowupResult.engine skiljer de tre motorerna.
    assert '"openclaw" | "legacy" | "answer-only"' in runner
    route = _route()
    # Honesty-gate: applied/legacy-svaret bär engine-attributionen vidare och
    # answerText (appliedConfirmation) bara på en synlig OpenClaw-ändring.
    assert "result.engine === \"openclaw\" &&" in route
    assert "generateAppliedConfirmation" in route


# --- 6. hostad response-payload speglar lokala kontraktsformen ----------------


def test_hosted_response_mirrors_local_contract_fields() -> None:
    route = _route()
    block = route.split("async function buildHostedFollowupResponse", 1)[1].split(
        "\n}\n", 1
    )[0]
    for field in (
        "version:",
        "briefSource:",
        "buildResult:",
        "appliedCopyDirectives:",
        "changeSet:",
        "openClawDecision:",
        "bridge:",
        "conversation,",
        "answerText",
        "hosted: true,",
    ):
        assert field in block, (
            f"Hostat done-svar måste bära det lokala kontraktsfältet {field!r}."
        )


def test_hosted_followup_result_type_is_exported() -> None:
    runner = _runner()
    assert "export interface HostedFollowupResult" in runner
    route = _route()
    assert "type HostedFollowupResult," in route, (
        "route.ts måste importera HostedFollowupResult-typen för det rika svaret."
    )
