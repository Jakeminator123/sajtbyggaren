"""Source-level locks för hostad answer-only utan sandbox-spinn (G1).

Prod-incidenten 2026-06-12 (site-3e7d71ad): en ren följdfråga ("Vad tycker du
om sajten?") drog hostat igång HELA sandbox-pipelinen (pip install ->
OpenClaw-konduktorbeslut) bara för att nå answer-only-utfallet, vilket sprängde
stream-budgeten. G1 inför en lättviktig pre-klassificering i prompt-routen som
kortsluter till ett grundat chat-svar FÖRE sandbox-start — men ENBART vid hög
konfidens "ren fråga".

Låsen (samma källkods-mönster som test_viewser_hosted_followup_parity.py):

1. Pre-klassificeraren kortsluter ENDAST vid hög konfidens och tar byggvägen
   för ALLT annat (parse-fel, medium/low, timeout, LLM-fel, no-key,
   strukturella byggsignaler i payloaden).
2. Answer-only-vägen skriver inga KV-pekare/artefakter och bumpar ingen
   version: modulen är read-only och routens svar bär runId:null +
   buildStatus:null. Konduktorbeslutet fejkas aldrig (openClawDecision/bridge
   är null på den pre-klassificerade vägen).
3. Grinden ligger i den HOSTADE vägen (runHostedPromptFlow) FÖRE
   startHostedBuild; den lokala vägen (runPromptBuildOnce) är orörd.
4. Ärlighetsraderna i svars-generatorn: SOUL-basen först, de dynamiska
   raderna efter (de vinner), och svaret påstår aldrig en ändring i denna tur.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.core, pytest.mark.tooling]

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER = REPO_ROOT / "apps" / "viewser"
MODULE = VIEWSER / "lib" / "hosted-answer-only.ts"
PROMPT_ROUTE = VIEWSER / "app" / "api" / "prompt" / "route.ts"


def _module() -> str:
    return MODULE.read_text(encoding="utf-8")


def _route() -> str:
    return PROMPT_ROUTE.read_text(encoding="utf-8")


# --- 1. Kortslutning ENDAST vid hög konfidens ---------------------------------


def test_preclassifier_requires_high_confidence_pure_question() -> None:
    module = _module()
    parser = module.split("export function parsePreclassificationReply", 1)[1].split(
        "\n}\n", 1
    )[0]
    assert (
        'obj.classification === "pure_question" && obj.confidence === "high"'
        in parser
    ), "Kortslutning kräver classification=pure_question OCH confidence=high."
    assert parser.count('return "build";') >= 3, (
        "Varje icke-perfekt utfall (saknad JSON, parse-fel, fel form, annan "
        "etikett/konfidens) måste defaulta till byggvägen."
    )


def test_preclassifier_failure_paths_take_build_path() -> None:
    module = _module()
    classify = module.split("async function preclassifyHostedFollowup", 1)[1].split(
        "\n}\n", 1
    )[0]
    assert 'if (!openaiEnv("OPENAI_API_KEY")) return "build";' in classify, (
        "Utan OPENAI_API_KEY är ingen klassificering möjlig — alltid byggvägen."
    )
    assert "PRECLASSIFY_TIMEOUT_MS" in classify and "Promise.race" in classify, (
        "Klassificeringen måste ha en tidsbudget (race) så grinden aldrig blir "
        "en hängpunkt framför sandbox-starten."
    )
    assert 'if (reply === null) return "build";' in classify, (
        "Timeout/LLM-fel måste ge byggvägen."
    )
    # Systemprompten instruerar konservativ klassning (hellre långsam än
    # felklassad) — kärnregeln i G1.
    assert "possible_change" in classify
    assert "minsta osäker" in classify


def test_gate_refuses_structural_build_signals_and_requires_context() -> None:
    module = _module()
    gate = module.split(
        "export async function maybeAnswerHostedFollowupWithoutSandbox", 1
    )[1]
    guard_idx = gate.find(
        "options.hasToolIntent || options.hasMarkedSections || options.hasBaseRunId"
    )
    assert guard_idx != -1, (
        "toolIntent/markedSections/baseRunId är byggsignaler — grinden måste "
        "ta byggvägen för dem."
    )
    classify_idx = gate.find("preclassifyHostedFollowup")
    assert classify_idx != -1 and guard_idx < classify_idx, (
        "De strukturella vakterna måste sitta FÖRE LLM-klassificeringen."
    )
    assert 'if (classification !== "pure_question") return null;' in gate
    assert "if (!context) return null;" in gate, (
        "Utan hostad sajtkontext kortsluter vi inte — byggvägen behåller "
        "dagens ärliga preflight-utfall."
    )


# --- 2. Answer-only skriver inga pekare/artefakter -----------------------------


def test_answer_only_module_is_read_only() -> None:
    module = _module()
    # Skriv-API:er och sandbox-/byggvägs-importer är förbjudna i modulen
    # (anrops-/importformer — JSDoc-prosa som FÖRKLARAR grinden är ok).
    for forbidden in (
        "kvSetJson(",
        'from "./hosted-build-runner"',
        'from "@vercel/sandbox"',
        "stopSandboxSessionForSite(",
        ".put(",
        "writeFiles(",
        "startHostedBuild(",
    ):
        assert forbidden not in module, (
            f"hosted-answer-only.ts får inte innehålla {forbidden!r} — "
            "answer-only-vägen är read-only (inga KV-pekare, inga artefakter, "
            "ingen sandbox)."
        )


def test_preclassified_response_never_claims_a_build() -> None:
    route = _route()
    block = route.split("function hostedPreclassifiedAnswerResponse", 1)[1].split(
        "\n}\n", 1
    )[0]
    for honest_field in (
        "runId: null,",
        "version: null,",
        "buildStatus: null,",
        "buildResult: {},",
        "appliedCopyDirectives: [],",
        "openClawDecision: null,",
        "bridge: null,",
    ):
        assert honest_field in block, (
            f"Pre-klassificerade answer-only-svaret måste bära {honest_field!r} "
            "— inget bygge, ingen version, inget fejkat konduktorbeslut."
        )
    assert "answerText: outcome.answerText," in block
    assert "conversation: outcome.conversation," in block


# --- 3. Grinden sitter i hostade vägen FÖRE sandbox-start ----------------------


def test_gate_runs_in_hosted_flow_before_start_hosted_build() -> None:
    route = _route()
    hosted_flow = route.split("async function runHostedPromptFlow", 1)[1]
    gate_idx = hosted_flow.find("maybeAnswerHostedFollowupWithoutSandbox({")
    start_idx = hosted_flow.find("await startHostedBuild({")
    assert gate_idx != -1, (
        "runHostedPromptFlow måste anropa pre-klassificerings-grinden."
    )
    assert start_idx != -1 and gate_idx < start_idx, (
        "Grinden måste köras FÖRE startHostedBuild — annars har sandboxen "
        "redan startats."
    )
    assert 'payload.mode === "followup" && payload.siteId' in hosted_flow[:start_idx], (
        "Kortslutningen gäller bara följdprompter (init bygger alltid)."
    )
    # Den lokala vägen är orörd: grinden får INTE förekomma i
    # runPromptBuildOnce (lokalt finns ingen sandbox att kortsluta förbi).
    local_flow = route.split("async function runPromptBuildOnce", 1)[1].split(
        "async function runPromptBuildSerially", 1
    )[0]
    assert "maybeAnswerHostedFollowupWithoutSandbox" not in local_flow, (
        "Lokala flödet (runPromptBuildOnce) ska vara opåverkat av G1-grinden."
    )


def test_gate_emits_observability_log_line() -> None:
    route = _route()
    assert '"hosted-answer-only-preclassified"' in route.split(
        "async function runHostedPromptFlow", 1
    )[1], (
        "Kortslutningen måste logga EN strukturerad rad (event + timings) så "
        "svarstids-vinsten är verifierbar i runtime-loggarna."
    )


# --- 4. Svars-generatorns ärlighetskontrakt ------------------------------------


def test_grounded_answer_keeps_honesty_lines_after_soul_base() -> None:
    module = _module()
    answer = module.split("async function generateGroundedHostedAnswer", 1)[1].split(
        "\n}\n", 1
    )[0]
    assert "loadSoulBaseLines() ?? SOUL_FALLBACK_LINES" in answer, (
        "Personan kommer från SOUL.md med defensiv fallback (ADR 0044-mönstret)."
    )
    assert "Du har INTE ändrat sajten i DENNA tur" in answer, (
        "Svaret får aldrig påstå en ändring i denna tur."
    )
    assert "Grunda svaret ENBART i sajtkontexten" in answer, (
        "Svaret måste grundas i den faktiska hostade sajtkontexten."
    )
    soul_idx = answer.find("soulBaseLines")
    dynamic_idx = answer.find("dynamicLines")
    assert soul_idx != -1 and dynamic_idx != -1
    assert "[...soulBaseLines, ...dynamicLines]" in answer, (
        "SOUL-basen FÖRST, de dynamiska ärlighetsraderna EFTER (de vinner)."
    )
    assert "? dynamicLines.join(" in answer, (
        "Vid teckenöverskott släpps SOUL-basen — aldrig ärlighetsraderna."
    )


def test_gate_outcome_carries_honest_conversation_metadata() -> None:
    module = _module()
    assert (
        'conversation: { conversationKind: "question", role: null, expectsAnswer: true }'
        in module
    ), (
        "Grindens conversation-block är den grova ärliga etiketten: kind "
        "question, ingen roll (ingen byggroll agerade), expectsAnswer true."
    )


def test_context_assembly_uses_hosted_read_only_sources() -> None:
    module = _module()
    context = module.split("async function assembleHostedAnswerContext", 1)[1].split(
        "\n}\n", 1
    )[0]
    assert "readHostedSiteComposition" in context, (
        "Grundningen ska återanvända composition-bilden (KV + blob)."
    )
    assert "fetchHostedRunArtefactsTar" in context and "siteBrief" in context, (
        "Grundningen ska även läsa site-brief ur run-artefakt-tarballen."
    )
    assert "CONTEXT_SNIPPET_MAX_CHARS" in context, (
        "Kontext-snittet måste vara begränsat så systemprompten aldrig "
        "spränger openai.ts-taket."
    )
