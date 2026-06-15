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

pytestmark = [pytest.mark.core, pytest.mark.tooling, pytest.mark.integration]

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


def test_legacy_honesty_gate_requires_concrete_directives() -> None:
    """1c (site-3e7d71ad): den hostade legacy-gaten får INTE nolla det ärliga
    OpenClaw-beslutet enbart på appliedVisibleEffect — den måste kräva konkreta
    direktiv (copy_directives ELLER appliedFollowupDirectiveKinds)."""
    runner = _runner()
    assert "appliedFollowupDirectiveKinds" in runner, (
        "Hostade write_hosted_result måste läsa appliedFollowupDirectiveKinds "
        "ur build-result.json."
    )
    assert "legacy_visible = bool(copy_directives) or bool(applied_directive_kinds)" in runner, (
        "Legacy-gaten måste kräva konkreta direktiv, aldrig enbart "
        "appliedVisibleEffect."
    )
    route = _route()
    assert "extractAppliedFollowupDirectiveKinds" in route, (
        "route.ts legacyPathAppliedVisibleChange måste läsa konkreta "
        "applied-direktiv via extractAppliedFollowupDirectiveKinds."
    )
    # Gaten får inte längre lita på appliedVisibleEffect===true för att nolla
    # beslutet — den raden ska bara använda appliedCopyDirectives + kinds.
    gate = route.split("const legacyPathAppliedVisibleChange", 1)[1].split(";", 1)[0]
    assert "appliedDirectiveKinds.length > 0" in gate
    assert "extractAppliedVisibleEffect" not in gate, (
        "Honesty-gaten får inte nolla beslutet enbart på appliedVisibleEffect."
    )


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


# --- 7. preview-sandbox stoppas vid hostat bygge (paritet med build-runner) ---


def test_hosted_build_stops_preview_sandbox_before_create() -> None:
    """Paritet med lokala build-runner.ts: ett hostat bygge stoppar en ev.
    aktiv preview-sandbox för samma siteId (annars serverar den stale
    innehåll under/efter bygget och kostar ören tills TTL). Best-effort:
    stoppet ligger i try/catch och får ALDRIG falla bygget — och det sker
    FÖRE Sandbox.create så bygg-sandboxen aldrig hinner samexistera med en
    stale preview."""
    runner = _runner()
    assert (
        'import { stopSandboxSessionForSite } from "./vercel-sandbox-sessions";'
        in runner
    ), "hosted-build-runner måste importera stopSandboxSessionForSite."
    start_body = runner.split("export async function startHostedBuild", 1)[1]
    stop_idx = start_body.find("stopSandboxSessionForSite(req.siteId)")
    create_idx = start_body.find("sdk.Sandbox.create(")
    assert stop_idx != -1, (
        "startHostedBuild måste anropa stopSandboxSessionForSite(req.siteId)."
    )
    assert create_idx != -1 and stop_idx < create_idx, (
        "Preview-stoppet måste ske FÖRE Sandbox.create."
    )
    guarded = start_body[:stop_idx].rstrip().endswith("await")
    assert guarded and "try {" in start_body[max(0, stop_idx - 200) : stop_idx], (
        "Stoppet ska vara awaited och ligga i try/catch (best-effort) — "
        "ett stopp-fel får aldrig falla bygget."
    )


# --- 8. Del D: ärlig answerText på VARJE followup-svar (site-3e7d71ad) ---------


def test_followup_outcome_summary_helper_exists_with_honesty_guard() -> None:
    """Del D: route.ts har generateFollowupOutcomeSummary med no-key-guard och
    hårda ärlighetsregler i systemprompten."""
    route = _route()
    assert "async function generateFollowupOutcomeSummary(" in route, (
        "route.ts måste ha helpern generateFollowupOutcomeSummary."
    )
    body = route.split("async function generateFollowupOutcomeSummary(", 1)[1].split(
        "\n}\n", 1
    )[0]
    # No-key → null (deterministiska rader står, ingen fejkad chatt).
    assert 'if (!openaiEnv("OPENAI_API_KEY")) return null;' in body, (
        "Helpern måste returnera null utan OPENAI_API_KEY."
    )
    # Grundning + ärlighetsregler i systemprompten.
    assert "Grunda dig ENBART i Fakta nedan." in body
    assert "INTE syntes/landade" in body, (
        "Systemprompten måste tvinga ett uttryckligt 'syntes/landade inte' på no-op."
    )
    # Återanvänder appliedConfirmation-racet (ingen hängande chatt blockerar svaret).
    assert "APPLIED_CONFIRMATION_TIMEOUT_MS" in body


def test_followup_outcome_summary_called_on_legacy_and_hosted() -> None:
    """Del D: helpern anropas på lokala legacy-grenen OCH i
    buildHostedFollowupResponse, och answerText bärs på legacy-returobjektet."""
    route = _route()
    # Lokala legacy-grenen: facts + answerText på returobjektet.
    assert "generateFollowupOutcomeSummary(payload.prompt, {" in route, (
        "Lokala legacy-grenen måste anropa generateFollowupOutcomeSummary."
    )
    assert "answerText: followupAnswerText," in route, (
        "Lokala legacy-returobjektet måste bära answerText."
    )
    # Hostade buildHostedFollowupResponse else-grenen kör nya helpern; den
    # synliga OpenClaw-ändringen behåller generateAppliedConfirmation.
    hosted_block = route.split("async function buildHostedFollowupResponse", 1)[1].split(
        "\n}\n", 1
    )[0]
    assert "generateFollowupOutcomeSummary(prompt, {" in hosted_block, (
        "buildHostedFollowupResponse måste köra generateFollowupOutcomeSummary "
        "för övriga followup-fall (legacy / openclaw mount-only)."
    )
    assert "generateAppliedConfirmation(" in hosted_block, (
        "Den synligt applicerade OpenClaw-ändringen behåller "
        "generateAppliedConfirmation."
    )


def test_floating_chat_answer_text_replaces_only_content() -> None:
    """Del D: i floating-chat.tsx får answerText ENDAST ersätta content
    (``honestAnswer || <deterministisk>``), aldrig variant."""
    text = (VIEWSER / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert (
        'const honestAnswer =\n      typeof payload.answerText === "string"' in text
    ), "summarizeBuildResult måste läsa payload.answerText som honestAnswer."
    # Ersätter content via ``honestAnswer || ...`` — minst den generiska
    # "Klart!"-grenen och no-op-grenarna.
    assert "honestAnswer || `Klart!" in text, (
        "Den generiska Klart!-grenen måste låta honestAnswer ersätta content."
    )
    # answerText får aldrig sätta variant: honestAnswer förekommer aldrig
    # tillsammans med 'variant:' på samma rad.
    for line in text.splitlines():
        if "honestAnswer" in line:
            assert "variant" not in line, (
                "answerText/honestAnswer får aldrig styra variant — bara content."
            )
