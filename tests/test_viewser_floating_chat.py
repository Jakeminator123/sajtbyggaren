"""Viewser FloatingChat and OpenClaw bridge wiring.

Copy-directive- och change-set-låsen bor i ``test_viewser_copy_change_set.py``
(topic-split per 1200-raders-taket i ``test_test_hygiene.py``, samma mönster
som ``test_viewser_builder_dialogs.py`` och ``test_viewser_openclaw_slice3.py``).
"""

from __future__ import annotations

import re

import pytest

from tests.support.viewser import VIEWSER_DIR


@pytest.mark.tooling
def test_chat_panel_component_is_removed() -> None:
    """B46: legacy ChatPanel component is dead code as of audit-fix
    2026-05-14. PromptBuilder is the only operator-facing prompt
    surface (test_viewser_prompt_primary.py locks it as canonical on
    home). The component file was deleted to remove the second
    "runId == success" code path the audit flagged. Lock the deletion
    here so a future restore would surface as a test failure rather
    than silently re-introducing the false-success surface.
    """
    assert not (VIEWSER_DIR / "components" / "chat-panel.tsx").exists(), (
        "components/chat-panel.tsx should not exist after the B46 audit-fix. "
        "Use PromptBuilder for the operator prompt -> Project Input -> build flow."
    )


def test_floating_chat_composer_ref_used_for_expand_focus() -> None:
    """Anti-regression för auto-focus-flödet i FloatingChat.

    När operatören klickar på den minimerade FAB:en/sidotab:en ska
    panelen expandera OCH focus flytta till composer-textarean i ett
    enda steg, så användaren kan börja skriva direkt utan att Tab:a
    sig in i fältet. Det här testet låser hela kedjan:
      1. composerRef tilldelas Textarea via `ref={composerRef}`
      2. expandAndFocus kallar `composerRef.current?.focus()`
      3. Minimerade FAB-knappen och sidotab-knappen routar onClick
         genom expandAndFocus (inte setIsMinimized(false) direkt).
    Tappar någon av dessa bryts mobil-/desktop-fokuseringen tyst.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "composerRef" in text, (
        "FloatingChat måste ha en composerRef för att kunna flytta focus till textarean vid expand."
    )
    assert "ref={composerRef}" in text, (
        "FloatingChat:s Textarea måste få `ref={composerRef}` så "
        "expand-focus-flödet kan referera DOM-noden."
    )
    assert "composerRef.current?.focus()" in text, (
        "expandAndFocus måste anropa composerRef.current?.focus() — "
        "annars stannar tangentbords-focus på FAB-knappen efter "
        "expand och operatören måste Tab:a sig in i textfältet."
    )
    assert "onClick={expandAndFocus}" in text, (
        "Både mobil-FAB och desktop-sidotab måste routa sin onClick "
        "genom expandAndFocus, inte setIsMinimized(false) direkt — "
        "annars sker ingen focus-flytt vid återöppning."
    )


# ---------------------------------------------------------------------------
# B151+B152+B153 — AI Bug Review-fynd från PR #117 (mobile responsive).
# Source-lock-tester som verifierar fixarnas närvaro i TSX-filerna så de
# inte kan tas bort i framtida UI-refactor utan att testerna failar.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b151_floating_chat_useismobile_feature_detects_addeventlistener() -> None:
    """B151: useIsMobileViewport måste feature-detect:a addEventListener på
    matchMedia-resultatet. iOS Safari < 14 stödjer bara den deprecated
    addListener-/removeListener-signaturen, så ovillkorlig
    ``mq.addEventListener("change", ...)`` kraschar chatten på äldre
    iOS-enheter. AI Bug Review (P 79 %, impact 8/10) flaggade detta på
    PR #117.

    Locks:
      1. ``typeof mq.addEventListener === "function"``-checken finns.
      2. Fallback-grenen anropar ``addListener`` / ``removeListener``
         via en legacy-cast (TS-typen finns inte i lib.dom utan klassisk
         matchMedia-typing).
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    pattern_feature_detect = re.compile(
        r'typeof\s+mq\.addEventListener\s*===\s*["\']function["\']',
        re.MULTILINE,
    )
    assert pattern_feature_detect.search(text), (
        "floating-chat.tsx useIsMobileViewport saknar feature-detect mot "
        "``typeof mq.addEventListener === 'function'``. Krävs för iOS "
        "Safari < 14 fallback per B151."
    )

    pattern_legacy_fallback = re.compile(
        r"\.addListener\(\s*update\s*\)[\s\S]{0,200}?\.removeListener\(\s*update\s*\)",
        re.MULTILINE,
    )
    assert pattern_legacy_fallback.search(text), (
        "floating-chat.tsx useIsMobileViewport saknar legacy "
        "``addListener``/``removeListener``-fallback för iOS Safari < 14. "
        "Båda måste finnas så cleanup-funktionen avregistrerar listenern."
    )


@pytest.mark.tooling
def test_b155_floating_chat_reads_applied_visible_effect() -> None:
    """B155 (2026-05-30): FloatingChat måste läsa ``appliedVisibleEffect``
    från ``build-result.json`` (auktoritativ källa enligt Jakobs
    PR #136). Trace-eventet ``followup.no_op_detected`` skickar samma
    information men ``parseTraceLine`` plockar bara sju kända fält så
    UI-skiktet får inte bero på trace-payloaden.

    Kontraktet låser tre saker:
      1. ``PromptApiResponse`` exponerar ``buildResult`` så fältet faktiskt
         når success-grenen i ``summarizeBuildResult``.
      2. En extractor läser specifikt ``appliedVisibleEffect`` (boolean)
         och ``appliedVisibleEffectReason`` (string) — annars riskerar vi
         att vi börjar parsa trace-eventets ``reason`` av bekvämlighet.
      3. När ``applied === false`` byts success-bubblan till en ärlig
         info-rad i stil med "Ingen synlig ändring fångades" — så
         operatören inte luras tro att fri-text-följdprompten landade.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "buildResult?: Record<string, unknown>" in text, (
        "PromptApiResponse måste deklarera ``buildResult`` så följdprompts "
        "build-result.json når summarizeBuildResult — annars kan UI:t inte "
        "läsa appliedVisibleEffect."
    )
    assert "buildResult.appliedVisibleEffect" in text, (
        "FloatingChat måste läsa ``appliedVisibleEffect`` från build-result "
        "(auktoritativ källa per B155). Trace-eventet är inte ett godkänt "
        "alternativ — parseTraceLine plockar inte ``reason``-fältet."
    )
    assert "appliedVisibleEffectReason" in text, (
        "Reason-fältet måste finnas i extraheringen så vi kan utvidga "
        "info-bubblan med varför ingen synlig effekt sågs (ADR 0034 path)."
    )
    assert "extractAppliedVisibleEffect" in text, (
        "Helper ``extractAppliedVisibleEffect`` ska kapsla boolean-checken "
        "så den inte upprepas i flera grenar — om operatören får en "
        "follow-up som bygger ok men flippar appliedVisibleEffect=false "
        "ska info-grenen fortfarande träffa."
    )
    assert "Jag kunde inte fånga någon synlig ändring" in text, (
        "Den ärliga raden måste ha en igenkännbar text-anchor (ADR-stil) "
        "så fil-disciplin inte tappar B155 under refaktorisering. "
        "Texten matchar Jakobs handoff för ADR 0034 väg B."
    )


@pytest.mark.tooling
def test_b155_floating_chat_no_op_does_not_claim_success() -> None:
    """B155: säkerställ att success-grenen i ``summarizeBuildResult``
    *inte* returnerar variant ``"success"`` när ``appliedVisibleEffect``
    är ``false``. Pattern matchar att info-grenen kommer FÖRE
    standardsuccess-grenen i koden, och att den explicit sätter
    variant ``"info"``.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    pattern = re.compile(
        r"effect\.applied\s*===\s*false[\s\S]{0,400}?"
        r'variant:\s*"info"',
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "Info-grenen för B155 (no-op-followup) saknas eller har bytt form. "
        "När backend rapporterar ``appliedVisibleEffect: false`` ska UI:t "
        'byta success-bubblan till variant ``"info"`` med en ärlig text '
        "— annars luras operatören att tro att följdprompten landade."
    )


@pytest.mark.tooling
def test_floating_chat_differentiates_layout_no_op_honestly() -> None:
    """Bug B-ärlighet: deterministisk codegen-v1 kan ÄNNU inte göra layout-/
    strukturändringar (centrera hero, lägg till gallery) — de blir ärliga
    no-ops med ``appliedVisibleEffectReason: "visible_files_unchanged"``. Att
    då be operatören vara "mer exakt" (samma råd som för
    ``intent_no_semantic_change``) vore vilseledande: problemet är saknad
    codegen-kapabilitet, inte otydlighet. FloatingChat måste därför skilja på
    de två no-op-orsakerna och säga ärligt att layout/struktur inte stöds än,
    utan att lova en synlig ändring. Riktig codegenModel för dessa intents är
    Sprint 3B (backend-lane) — den här testen låser bara UI-ärligheten.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert '"visible_files_unchanged"' in text, (
        "FloatingChat måste gren-skilja på reason ``visible_files_unchanged`` "
        "(bygget gav identiska filer → layout/struktur stöds inte än) från "
        "``intent_no_semantic_change`` (be om konkret text)."
    )
    # Layout-grenen får INTE råda operatören att bara vara mer specifik — den
    # ska ärligt säga att större layout/struktur-ändringar inte stöds än.
    assert "stöds inte än" in text, (
        "Layout-no-op-grenen måste ärligt säga att layout/struktur inte stöds "
        "än, i st.f. att antyda att otydlighet var problemet."
    )
    # Den layout-specifika grenen måste komma FÖRE den generiska
    # 'mer specifik'-raden så rätt råd vinner. Och båda måste vara info,
    # aldrig success (regression-skyddat separat i no_op_does_not_claim_success).
    layout_idx = text.index('"visible_files_unchanged"')
    generic_idx = text.index("Jag kunde inte fånga någon synlig ändring")
    assert layout_idx < generic_idx, (
        "Layout-grenen (visible_files_unchanged) måste utvärderas före den "
        "generiska 'ange exakt rubrik/text'-raden."
    )


@pytest.mark.tooling
def test_floating_chat_dedicated_intent_not_executable_row() -> None:
    """Uppgift H (deferred från #313): reason ``intent_not_executable`` (en
    followup vars intent ingen utförare äger — "ta bort sidan Kontakt", "gör
    badges responsiva") föll i den generiska catch-all-raden ("ange exakt
    rubrik/text"), vars råd är vilseledande: problemet är att önskemålet
    saknar byggförmåga, inte att operatören var otydlig. Lås att FloatingChat
    har en DEDIKERAD deterministisk gren för reason intent_not_executable
    (no-key-fallbacken; #313:s ärliga LLM-answerText ersätter fortsatt content
    när den finns) med variant info, utvärderad FÖRE den generiska raden.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert '"intent_not_executable"' in text, (
        "FloatingChat måste gren-skilja på reason ``intent_not_executable`` "
        "(intent utan utförare — byte-diffen var bara brief-parafras) från "
        "``intent_no_semantic_change`` (be om konkret text)."
    )
    assert "Jag kunde inte koppla önskemålet till någon byggförmåga" in text, (
        "Den dedikerade intent_not_executable-raden måste ha en igenkännbar "
        "text-anchor som ärligt säger att önskemålet inte kunde kopplas till "
        "någon känd byggförmåga (aldrig 'var mer specifik'-rådet)."
    )
    # Grenen måste vara info (aldrig success) och behålla honestAnswer-
    # ersättningen + unapplied-svansen — samma mönster som övriga no-op-grenar.
    branch_pattern = re.compile(
        r'effect\.reason\s*===\s*"intent_not_executable"[\s\S]{0,120}?'
        r'variant:\s*"info"[\s\S]{0,260}?\$\{unappliedNote\}',
        re.MULTILINE,
    )
    assert branch_pattern.search(text), (
        "intent_not_executable-grenen måste sätta variant ``\"info\"`` och "
        "appenda ``${unappliedNote}`` (oapplicerade följd-asks förblir synliga)."
    )
    # Den dedikerade grenen måste utvärderas FÖRE den generiska raden så det
    # ärliga skälet vinner över 'ange exakt rubrik/text'-rådet.
    branch_idx = text.index('effect.reason === "intent_not_executable"')
    generic_idx = text.index("Jag kunde inte fånga någon synlig ändring")
    assert branch_idx < generic_idx, (
        "intent_not_executable-grenen måste ligga före den generiska "
        "'ange exakt rubrik/text'-raden i summarizeBuildResult."
    )


@pytest.mark.tooling
def test_floating_chat_router_decision_readiness() -> None:
    """KÖR-6a readiness: FloatingChat måste kunna ge en ärlig rad per
    ``RouterDecision.messageKind`` OM/NÄR ``/api/prompt`` börjar skicka
    ``routerDecision`` — utan att ändra dagens beteende (fältet skickas inte
    än; classify_message konsumeras bara internt i patch/+context/, follow-up-
    bryggan kor-7d/#176 wirar in det).

    Locks (graceful degradation + ärlighet, samma mönster som
    appliedVisibleEffect):
      1. ``PromptApiResponse`` exponerar ett valfritt ``routerDecision``-fält.
      2. En defensiv ``extractRouterDecision`` läser fältet utan att lita på
         dess typ och returnerar null när det saknas → oförändrat beteende.
      3. ``summarizeRouterDecision`` grenar på de messageKind/buildRequirement
         som routern äger och som UI:t måste vara ärligt om.
      4. Preempten körs INNAN success-/no-op-grenarna i summarizeBuildResult,
         men edit/multi_intent med targeted_rebuild/full_rebuild faller igenom
         (→ null) så den vanliga bygg-summeringen (Bug B) tar vid.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "routerDecision?: Record<string, unknown>" in text, (
        "PromptApiResponse måste exponera ett valfritt routerDecision-fält "
        "(speglar router-decision.schema.json) så UI:t kan tändas när backend "
        "börjar skicka det — utan ny deploy."
    )
    assert "function extractRouterDecision(" in text, (
        "FloatingChat måste läsa routerDecision defensivt (extractRouterDecision), "
        "exakt som extractAppliedVisibleEffect, så ett saknat/okänt fält ger null."
    )
    assert "function summarizeRouterDecision(" in text, (
        "FloatingChat måste härleda en ärlig rad per messageKind (summarizeRouterDecision)."
    )

    # Alla messageKind ur schemat som UI:t måste kunna bemöta ärligt.
    for kind in (
        '"answer_only"',
        '"site_review"',
        '"reference_analysis"',
        '"component_discovery"',
        '"multi_intent"',
        '"unclear"',
    ):
        assert kind in text, (
            f"summarizeRouterDecision måste hantera messageKind {kind} "
            "(annars är readiness-kontraktet ofullständigt mot schemat)."
        )

    # Plan-only/patch-only edits får inte låtsas vara klara: ärlig rad om att
    # bygget som gör ändringen synlig inte är klart än (orchestrator-punkt 5).
    assert '"plan_only"' in text and '"artifact_patch_only"' in text, (
        "summarizeRouterDecision måste skilja plan_only/artifact_patch_only "
        "(plan skapad, inget synligt bygge än) från targeted_rebuild/full_rebuild."
    )

    # Preempten måste ligga FÖRE den vanliga bygg-summeringen så ett router-
    # beslut för icke-bygg-utfall vinner över "Klart!"-raden.
    preempt_idx = text.index("const routerView = extractRouterDecision(payload)")
    ok_branch_idx = text.index('if (outcome === "ok") {')
    assert preempt_idx < ok_branch_idx, (
        "Router-preempten måste utvärderas innan outcome==='ok'-grenen så vi "
        "aldrig visar bygg-success för det routern klassat som fråga/oklart/"
        "referens/discovery/plan-only."
    )

    # B1 (2026-06-05): router-preempten får BARA köra på outcome==='ok'. Annars
    # döljer router-raden (variant 'info') den auktoritativa failed/degraded-
    # grenen och operatören tappar 'Försök igen' (retryPrompt sätts bara på
    # variant 'error'). Lås att gaten finns.
    assert 'if (routerView && outcome === "ok")' in text, (
        "Router-preempten måste vara gated på outcome==='ok' så ett misslyckat "
        "eller degraderat bygge aldrig döljs bakom en router-info-rad (och "
        "behåller 'Försök igen')."
    )

    # Ärlighets-nyans (2026-06-05): en ``unclear``/``requiresClarification``-
    # gissning får INTE preempta när bygget faktiskt rapporterade ett
    # auktoritativt no-op-skäl (B155 ``appliedVisibleEffect.applied === false``).
    # Då är B155-raden ärligare ("kan bara ändra texter, layout stöds ej än")
    # än routerns "jag förstår inte vad du menar" över en tydlig men ej stödd
    # förfrågan ("gör hero-knappen större" klassas deterministiskt som unclear).
    # Preempt-regionen måste alltså konsultera bygg-sanningen innan den fyrar.
    preempt_region = text[preempt_idx:ok_branch_idx]
    assert "extractAppliedVisibleEffect(payload.buildResult)" in preempt_region, (
        "Router-preempten måste läsa appliedVisibleEffect så unclear/"
        "requiresClarification kan lämna över till den mer specifika B155-"
        "no-op-raden när bygget redan rapporterat varför inget syntes."
    )
    assert "requiresClarification" in preempt_region and "unclear" in preempt_region, (
        "Defer-till-bygg-sanningen måste vara begränsad till unclear/"
        "requiresClarification — övriga router-utfall (fråga/referens/discovery/"
        "bug/plan-only) ska fortsatt preempta med sin mer specifika rad."
    )

    # Graceful: edit/multi_intent som krävde ett synligt bygge ska falla igenom
    # till den vanliga summeringen (Bug B m.m.) — summarizeRouterDecision ska
    # alltså ha en gren som returnerar null.
    summarize_start = text.index("function summarizeRouterDecision(")
    summarize_end = text.index("function summarizeBuildResult(")
    summarize_body = text[summarize_start:summarize_end]
    assert "return null;" in summarize_body, (
        "summarizeRouterDecision måste returnera null för bygg-krävande edits "
        "(targeted_rebuild/full_rebuild) så den vanliga bygg-summeringen tar vid."
    )


@pytest.mark.tooling
def test_openclaw_runner_spawns_followup_seam() -> None:
    """Skiva 1b (UI half): ``lib/openclaw-runner.ts`` måste shella till
    ``scripts/run_openclaw_followup.py`` med exakt samma spawn-mönster som
    ``router-classify-runner.ts`` — och ALDRIG kunna krascha /api/prompt.

    Locks:
      1. Exporterar ``runOpenClawFollowup`` + ``OpenClawDecisionPayload``.
      2. Spawnar rätt scripts/-seam (repo-boundaries: viewser importerar aldrig
         packages/ direkt — Python-scriptet äger importen).
      3. ``--`` -separatorn finns så en prompt som börjar med ``-`` inte tolkas
         som ett CLI-flagga, och --site-id/--base-run-id skickas vidare.
      4. En timeout + degradering till ``null`` (read-only metadata får aldrig
         bli en 500 på bygg-routen).
    """
    text = (VIEWSER_DIR / "lib" / "openclaw-runner.ts").read_text(encoding="utf-8")

    assert "export async function runOpenClawFollowup" in text, (
        "openclaw-runner.ts måste exportera runOpenClawFollowup så /api/prompt "
        "kan konsumera OpenClaw-beslutet."
    )
    assert "export type OpenClawDecisionPayload" in text, (
        "Exportera OpenClawDecisionPayload-typen (loose record som speglar "
        "OpenClawDecision.model_dump())."
    )
    assert "run_openclaw_followup.py" in text, (
        "Runnern måste spawna scripts/run_openclaw_followup.py (skiva-1b-seamen)."
    )
    assert 'args.push("--", trimmed)' in text, (
        "``--``-separatorn måste finnas så en prompt som börjar med - inte "
        "tolkas som ett argparse-flagga."
    )
    assert '"--site-id"' in text and '"--base-run-id"' in text, (
        "siteId + baseRunId måste skickas till seamen för RouterContext/context-assembly."
    )
    assert "setTimeout(" in text and "child.kill()" in text, (
        "Runnern måste timeouta + döda subprocessen så en hängd Python inte wedge:ar bygg-routen."
    )
    # Degraderingen: minst en `return null;` så fel/timeout aldrig 500:ar.
    assert "return null;" in text, (
        "Alla felvägar måste degradera till null (aldrig kasta upp i /api/prompt-flödet)."
    )


@pytest.mark.tooling
def test_openclaw_runner_apply_bridge_seam() -> None:
    """Skiva 1b (action half): ``lib/openclaw-runner.ts`` måste exponera
    ``runOpenClawFollowupApply`` som shellar ``run_openclaw_followup.py --apply``
    och returnerar ``{decision, bridge}`` — och ALDRIG krascha /api/prompt.

    Locks:
      1. Exporterar ``runOpenClawFollowupApply`` + apply-result-/bridge-typerna.
      2. Skickar ``--apply`` + ``--site-id`` (apply kräver en konkret sajt).
      3. Tree-killar subprocessen vid timeout (--apply spawnar npm/next-barn —
         ett plain child.kill() vore en process-/fil-lås-läcka, B157-klassen).
      4. Parsar ut ``decision`` + ``bridge`` och degraderar till ``null`` vid fel.
    """
    text = (VIEWSER_DIR / "lib" / "openclaw-runner.ts").read_text(encoding="utf-8")

    assert "export async function runOpenClawFollowupApply" in text, (
        "openclaw-runner.ts måste exportera runOpenClawFollowupApply (action-"
        "bryggan som /api/prompt rutar follow-ups genom)."
    )
    assert "export type OpenClawApplyResult" in text and "export type OpenClawBridge" in text, (
        "Exportera apply-result/bridge-typerna ({decision, bridge:{status, "
        "applied, previewShouldRefresh, chain}})."
    )
    assert '"--apply"' in text and '"--site-id"' in text, (
        "Apply-bryggan måste skicka --apply + --site-id (kräver en konkret sajt)."
    )
    # Tree-kill istället för plain child.kill() i apply-vägen (npm/next-barn).
    assert "killProcessTree(child" in text, (
        "Apply-vägen måste tree-killa subprocess-trädet vid timeout (npm/next "
        "spawnas som barn — child.kill() lämnar dem som läckande processer)."
    )
    apply_start = text.index("export async function runOpenClawFollowupApply")
    apply_body = text[apply_start:]
    assert "obj.decision" in apply_body and "coerceBridge(" in apply_body, (
        "Runnern måste parsa ut både decision och bridge ur scriptets stdout."
    )
    assert "return null;" in apply_body, (
        "Alla felvägar i apply-runnern måste degradera till null (aldrig 500:a bygg-routen)."
    )


@pytest.mark.tooling
def test_prompt_route_exposes_openclaw_decision() -> None:
    """Skiva 1b (action bridge): ``/api/prompt`` måste ruta follow-ups genom
    OpenClaw-apply-bryggan och, när den materialiserade en ändring, exponera
    den runen som det auktoritativa bygget — annars falla tillbaka på legacy
    med samma ärlighetsgrind för ``openClawDecision``.

    Locks:
      1. Routen importerar + anropar runOpenClawFollowupApply.
      2. Anropet är gated på ``payload.mode === "followup"`` (init-flödet är
         byte-för-byte oförändrat).
      3. När ``bridge.applied`` + ``chain.runId`` finns re-surface:as den runen
         (ingen legacy-build → ingen dubbel-build).
      4. Samma legacyPathAppliedVisibleChange-grind nollar beslutet på fallback-
         vägen; ``openClawDecision`` (härledd ur bryggans decision) + ``bridge``
         ligger i return-objektet (NDJSON-vägen sprider ``...result``).
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")

    assert 'import { runOpenClawFollowupApply } from "@/lib/openclaw-runner"' in text, (
        "route.ts måste importera apply-bryggan (runOpenClawFollowupApply)."
    )
    assert "runOpenClawFollowupApply(payload.prompt" in text, (
        "Routen måste anropa apply-bryggan med prompten."
    )
    # Gated på follow-up: init-flödet ska inte spawna bryggan.
    call_idx = text.index("runOpenClawFollowupApply(payload.prompt")
    gate_region = text[text.index("const applyResult") : call_idx]
    assert 'payload.mode === "followup"' in gate_region, (
        "Apply-bryggan får bara köras på follow-ups (init-flödet oförändrat)."
    )
    # När bryggan applicerade: använd dess chain.runId som det riktiga bygget.
    assert "applyResult.bridge.applied" in text, (
        "Routen måste gren:a på bridge.applied (materialiserad ändring)."
    )
    assert "chain.runId" in text, (
        "Den applicerade bryggans chain.runId måste re-surface:as som runId så "
        "klientens preview-refresh-flöde fungerar oförändrat (ingen dubbel-build)."
    )
    assert "const openClawDecision = legacyPathAppliedVisibleChange" in text, (
        "Samma honesty-gate som routerDecision på fallback-vägen: nolla "
        "beslutet när den gamla vägen redan applicerade en synlig ändring."
    )
    # openClawDecision härleds nu ur bryggans decision-fält (ingen andra spawn).
    assert "applyResult?.decision" in text, (
        "openClawDecision ska komma från apply-bryggans decision-fält."
    )
    # Både openClawDecision och bridge måste ligga i return-objektet.
    return_idx = text.index("routerDecision,\n")
    assert text.index("openClawDecision,", return_idx) > return_idx, (
        "openClawDecision måste returneras (NDJSON sprider ...result)."
    )
    assert "bridge: applyResult" in text, (
        "bridge-utfallet måste returneras så FloatingChat kan visa en ärlig "
        "restyle/capability-rad + preview-refresh-status."
    )


@pytest.mark.tooling
def test_floating_chat_renders_openclaw_bridge_honestly() -> None:
    """Skiva 1b (action half): FloatingChat måste visa OpenClaw-apply-utfallet
    ärligt — en success-rad NÄR bryggan materialiserade en ändring, annars
    falla tillbaka på den vanliga summeringen (lovar aldrig en ändring som inte
    landade).

    Locks:
      1. ``PromptApiResponse`` exponerar ett valfritt ``bridge``-fält.
      2. Defensiv ``extractOpenClawBridge`` + ``summarizeOpenClawBridge`` (bara
         success när applied=true; null annars).
      3. Bridge-preempten ligger FÖRE openClawView och är gated på
         ``bridgeView.applied`` + outcome === "ok".
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "bridge?: Record<string, unknown>" in text, (
        "PromptApiResponse måste exponera ett valfritt bridge-fält."
    )
    assert "function extractOpenClawBridge(" in text, (
        "FloatingChat måste läsa bridge defensivt (extractOpenClawBridge)."
    )
    assert "function summarizeOpenClawBridge(" in text, (
        "FloatingChat måste härleda en ärlig success-rad (summarizeOpenClawBridge)."
    )
    # summarizeOpenClawBridge får BARA ge en rad när applied=true.
    summarize_start = text.index("function summarizeOpenClawBridge(")
    summarize_body = text[summarize_start : summarize_start + 1800]
    assert "if (!view.applied) return null;" in summarize_body, (
        "summarizeOpenClawBridge måste returnera null när inget applicerades "
        "(vi lovar aldrig en ändring som bryggan inte materialiserade)."
    )
    # Honesty split (Vercel-agent-fynd 2026-06-08): applied=true men
    # previewShouldRefresh=false (mount-only, ingen synlig effekt) får INTE säga
    # "Jag genomförde ändringen" — då blir det en falsk success. Grinda på
    # previewShouldRefresh och ge en ärlig info-rad i stället.
    assert "if (!view.previewShouldRefresh) {" in summarize_body, (
        "summarizeOpenClawBridge måste grinda den synliga success-raden på "
        "previewShouldRefresh (annars lovar en mount-only-montering en synlig "
        "ändring som inte syns)."
    )
    assert 'variant: "info"' in summarize_body, (
        "Mount-only-utfallet (applied men inte synligt) ska vara en ärlig "
        "info-rad, inte en success-rad."
    )
    # Bridge-preempten ligger FÖRE openClawView-preempten och är gated rätt.
    bridge_preempt_idx = text.index("const bridgeView = extractOpenClawBridge(payload)")
    openclaw_preempt_idx = text.index("const openClawView = extractOpenClawDecision(payload)")
    assert bridge_preempt_idx < openclaw_preempt_idx, (
        "Bridge-utfallet (en faktiskt landad ändring) måste preempta FÖRE "
        "OpenClaw-beslutet (som annars säger 'inte inkopplad än')."
    )
    assert 'bridgeView.applied && outcome === "ok"' in text, (
        "Bridge-preempten måste vara gated på applied + outcome ok (failed/"
        "degraded faller igenom till den auktoritativa fel-/varningsgrenen)."
    )


@pytest.mark.tooling
def test_prompt_route_conversation_gate_answers_without_build() -> None:
    """F1 slice 2 (conductor wiring): när bryggan klassar follow-upen som en
    KONVERSATION (small_talk/site_opinion/question) ska ``/api/prompt`` svara
    med ett ärligt chat-svar (``answerText``) och stanna FÖRE bygget — ett
    skämt eller en omdömesfråga får aldrig skriva en ny version.

    Locks:
      1. De tre konversations-kinds:en speglas i en stängd uppsättning.
      2. Gaten ligger EFTER applied-grenen men FÖRE Phase 1
         (runPromptToProjectInput) — inget bygge kan starta.
      3. Svarstexten genereras via den BEFINTLIGA lib/openai.ts-chathelpern
         (chatWithOpenAi) med ärlig no-key-fallback ("OPENAI_API_KEY saknas"
         — aldrig en låtsad konversation).
      4. Return-objektet bär ``answerText`` + ``runId: null`` och ett tomt
         ``buildResult`` (appliedVisibleEffect kan aldrig bli true för en
         konversation; previewShouldRefresh är false från bryggan).
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )

    # 1. Den stängda kind-uppsättningen (spegel av Python-seamens gate).
    assert "CONVERSATION_ANSWER_KINDS" in text, (
        "route.ts måste hålla konversations-kinds:en i en stängd uppsättning "
        "(spegel av _ANSWER_ONLY_CONVERSATION_KINDS i run_openclaw_followup.py)."
    )
    for kind in ("small_talk", "site_opinion", "question"):
        assert f'"{kind}"' in text, (
            f"route.ts: konversations-kinden {kind!r} saknas i gaten."
        )

    # 2. Gaten ligger före Phase 1 så inget bygge kan starta för en konversation.
    # (B190: gaten återanvänder den redan extraherade conversationMeta i
    # stället för ett andra extractConversation-anrop — ankaret följer med.)
    gate_idx = text.index("const conversation = conversationMeta;")
    phase1_idx = text.index("await runPromptToProjectInput(")
    assert gate_idx < phase1_idx, (
        "route.ts: konversations-gaten måste ligga FÖRE Phase 1 "
        "(runPromptToProjectInput) — annars kan ett skämt starta ett bygge."
    )
    # ...och efter applied-grenen (en faktiskt landad ändring vinner alltid).
    applied_idx = text.index("applyResult.bridge.applied")
    assert applied_idx < gate_idx, (
        "route.ts: applied-grenen (materialiserad ändring) måste preempta "
        "konversations-gaten."
    )

    # 3. Befintliga chathelpern + ärlig no-key-fallback.
    assert 'import { chatWithOpenAi, openaiEnv } from "@/lib/openai"' in text, (
        "route.ts måste återanvända lib/openai.ts-chathelpern (ingen egen "
        "OpenAI-klient)."
    )
    assert "chatWithOpenAi([" in text, (
        "Konversations-svaret ska genereras via chatWithOpenAi."
    )
    assert 'openaiEnv("OPENAI_API_KEY")' in text, (
        "No-key-grenen måste kolla nyckeln via openaiEnv (samma resolution "
        "som övriga OpenAI-rutter)."
    )
    assert "OPENAI_API_KEY saknas" in text, (
        "Utan nyckel måste svaret vara den ärliga svenska no-key-texten — "
        "aldrig en låtsad konversation."
    )

    # 4. Ärligt return-objekt: answerText + runId null + tomt buildResult.
    gate_region = text[gate_idx : gate_idx + 1800]
    assert "runId: null" in gate_region, (
        "Konversations-svaret får inte bära ett runId (ingen version skrevs)."
    )
    assert "answerText," in gate_region, (
        "Return-objektet måste bära answerText (chat-svaret)."
    )
    assert "buildResult: {}" in gate_region, (
        "buildResult måste vara tomt — appliedVisibleEffect kan aldrig bli "
        "true för en konversation."
    )


@pytest.mark.tooling
def test_floating_chat_renders_conversation_answer_honestly() -> None:
    """F1 slice 2 (UI-halvan): FloatingChat ska visa konversations-svaret som
    en ärlig info-bubbla UTAN att trigga bygg-flödet.

    Locks:
      1. ``PromptApiResponse`` exponerar ``answerText`` (valfritt).
      2. Defensiv ``extractConversationAnswer`` som bara gäller när runId
         saknas (ett riktigt bygge går alltid genom den vanliga summeringen).
      3. Svaret hanteras FÖRE ``!payload.runId``-felgrenen (annars hade ett
         ärligt svar renderats som ett fel).
      4. Konversations-grenen anropar ALDRIG onBuildDone (ingen version,
         ingen preview-refresh).
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "answerText?: string | null" in text, (
        "PromptApiResponse måste exponera ett valfritt answerText-fält."
    )
    assert "function extractConversationAnswer(" in text, (
        "FloatingChat måste läsa answerText defensivt (extractConversationAnswer)."
    )
    extract_start = text.index("function extractConversationAnswer(")
    extract_body = text[extract_start : extract_start + 600]
    assert "if (payload.runId) return null;" in extract_body, (
        "extractConversationAnswer: ett payload med runId är ett riktigt "
        "bygge och får aldrig omtolkas som konversations-svar."
    )

    answer_idx = text.index("extractConversationAnswer(payload)")
    error_idx = text.index("!response.ok || !payload.runId || !payload.siteId")
    assert answer_idx < error_idx, (
        "Konversations-svaret måste hanteras FÖRE !payload.runId-felgrenen — "
        "annars renderas ett ärligt svar som ett fel."
    )

    branch_start = text.index("if (conversationAnswer !== null) {")
    branch_end = text.index("return;", branch_start)
    branch_body = text[branch_start:branch_end]
    assert "onBuildDone" not in branch_body, (
        "Konversations-grenen får ALDRIG anropa onBuildDone (ingen version, "
        "ingen preview-refresh)."
    )
    assert 'variant: "info"' in branch_body, (
        "Konversations-svaret ska visas som en neutral info-bubbla, inte som "
        "en success-rad (inget byggdes)."
    )


@pytest.mark.tooling
def test_prompt_route_gate_honours_expects_answer() -> None:
    """B190 (extern granskning 2026-06-10, F4+F5): conversation-grinden i
    /api/prompt måste hedra BÅDE kind-mängden och den explicita
    ``expectsAnswer``-signalen (som use-followup-build + FloatingChat redan
    läser), och återanvända den redan extraherade ``conversationMeta`` i
    stället för ett andra extractConversation-anrop."""
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "CONVERSATION_ANSWER_KINDS.has(conversation.conversationKind)" in text, (
        "Grinden ska fortsatt läsa kind-mängden (källåset från F1 slice 2)."
    )
    assert "conversation.expectsAnswer === true" in text, (
        "Grinden måste OCKSÅ hedra expectsAnswer — annars divergerar servern "
        "från klienternas kontraktsläsning (B190)."
    )
    assert "const conversation = conversationMeta;" in text, (
        "Grind-blocket ska återanvända conversationMeta (F5 — inget andra "
        "extractConversation-anrop i samma scope)."
    )


@pytest.mark.tooling
def test_floating_chat_renders_openclaw_decision_honestly() -> None:
    """Skiva 1b (UI half): FloatingChat måste rendera OpenClaw-beslutet ärligt
    och preempta FÖRE routerDecision (rikare superset), med samma
    failed/degraded-grind.

    Locks:
      1. ``PromptApiResponse`` exponerar ett valfritt ``openClawDecision``-fält.
      2. Defensiv ``extractOpenClawDecision`` (okänd action → null →
         oförändrat beteende, faller tillbaka på routerDecision).
      3. ``summarizeOpenClawDecision`` hanterar alla fyra actions inkl. den
         ärliga patch_plan_request-raden ("inte inkopplad än").
      4. Preempten ligger FÖRE routerView och är gated på outcome === "ok".
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "openClawDecision?: Record<string, unknown>" in text, (
        "PromptApiResponse måste exponera ett valfritt openClawDecision-fält."
    )
    assert "function extractOpenClawDecision(" in text, (
        "FloatingChat måste läsa openClawDecision defensivt (extractOpenClawDecision)."
    )
    assert "function summarizeOpenClawDecision(" in text, (
        "FloatingChat måste härleda en ärlig rad per action (summarizeOpenClawDecision)."
    )
    assert "OPENCLAW_ACTIONS" in text, (
        "En allowlist av kända actions måste finnas så en okänd action ger null."
    )
    # Alla fyra actions ur OpenClawAction-enumen måste vara kända (allowlist)
    # och bemötas i besluts-regionen (patch_plan_request via fall-through).
    decision_start = text.index("const OPENCLAW_ACTIONS")
    decision_end = text.index("function summarizeBuildResult(")
    decision_body = text[decision_start:decision_end]
    for action in (
        '"answer_only"',
        '"clarification"',
        '"plan_only"',
        '"patch_plan_request"',
    ):
        assert action in decision_body, (
            f"OpenClaw-beslutsregionen måste känna till action {action}."
        )
    # patch_plan_request måste vara ärlig om att action-bryggan saknas.
    summarize_start = text.index("function summarizeOpenClawDecision(")
    summarize_body = text[summarize_start:decision_end]
    assert "inte inkopplad än" in summarize_body, (
        "patch_plan_request-raden måste ärligt säga att funktionen som utför "
        "ändringen inte är inkopplad än (V0 fejkar aldrig en success)."
    )
    # Preempten måste ligga FÖRE routerView och vara gated på outcome === "ok".
    openclaw_preempt_idx = text.index("const openClawView = extractOpenClawDecision(payload)")
    router_preempt_idx = text.index("const routerView = extractRouterDecision(payload)")
    assert openclaw_preempt_idx < router_preempt_idx, (
        "OpenClaw-beslutet (rikare superset) måste preempta FÖRE routerDecision."
    )
    assert 'if (openClawView && outcome === "ok")' in text, (
        "OpenClaw-preempten måste vara gated på outcome === 'ok' så ett "
        "misslyckat/degraderat bygge aldrig döljs bakom en info-rad."
    )


def test_tier3_floating_chat_decorative_icons_are_aria_hidden() -> None:
    """Dekorativa ikoner inuti knappar med egen aria-label måste vara
    ``aria-hidden`` så skärmläsare inte läser upp ikonnamnet ovanpå
    knappens label. Vi kontrollerar Send + Loader2 + ImagePlus i
    floating-chat.tsx vars parent-knappar har 'Skicka instruktion'
    respektive 'Bifoga bild' som aria-label.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    # Send-ikonen i Skicka-knappen.
    assert "<Send aria-hidden" in text, (
        "floating-chat.tsx: <Send>-ikonen i Skicka-knappen måste ha "
        "aria-hidden (parent-knappen har aria-label='Skicka instruktion')"
    )
    # ImagePlus-ikonen i Bifoga-bild-knappen.
    assert "<ImagePlus aria-hidden" in text, (
        "floating-chat.tsx: <ImagePlus>-ikonen i Bifoga-bild-knappen måste "
        "ha aria-hidden (parent-knappen har aria-label='Bifoga bild')"
    )


def test_pre_push_toast_viewport_positioned_above_floating_chat() -> None:
    """ToastViewport får inte ligga på ``bottom-*`` — det krockar med
    FloatingChat-composern (desktop bottom-6) och mobil bottom-sheet.
    Top-placement är säkrare yta.
    """
    path = VIEWSER_DIR / "components" / "ui" / "toast.tsx"
    content = path.read_text(encoding="utf-8")
    assert "top-20" in content, (
        "ToastViewport ska använda top-20 så aviseringar inte skymmer "
        "FloatingChat eller PromptBuilder-composern"
    )
    # Säkerhetsnät: bottom-positionering ska inte ha smugit tillbaka.
    # ``bottom-2`` används bara i animations-namnet (slide-in-from-bottom-2)
    # som vi också ändrade — så vi tillåter den substring som regex.
    assert "fixed inset-x-0 bottom-" not in content, (
        "ToastViewport får inte använda bottom-positionering"
    )


def test_floating_chat_first_run_hint_surfaces_core_loop() -> None:
    """Synliggör kärnloopen: FloatingChat ska visa en första-gångs-hint som
    förklarar att en följdprompt bygger om sajten OCH att varje bygge blir en
    ny version. Hinten ska vara dismiss:bar och persisterad (en gång per
    webbläsare) och erbjuda en djuplänk till versionsvyn.
    """
    chat = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "Så funkar det" in chat, "FloatingChat ska ha en första-gångs-hint som förklarar loopen"
    assert "ny version" in chat, "Hinten ska nämna att varje bygge blir en ny version"
    assert "STORAGE_KEY_LOOP_HINT" in chat and "readLoopHintSeen" in chat, (
        "Hinten ska persistera dismissen så den bara visas en gång"
    )
    assert "onShowVersions" in chat and "Visa versioner" in chat, (
        "Hinten ska kunna djuplänka till versionsvyn"
    )
    shell = (VIEWSER_DIR / "components" / "builder" / "builder-shell.tsx").read_text(
        encoding="utf-8"
    )
    assert "onShowVersions={onOpenHistory}" in shell, (
        "BuilderShell ska koppla 'Visa versioner' till historik-ingången"
    )


@pytest.mark.tooling
def test_floating_chat_failed_build_offers_retry() -> None:
    """S3: ett pipeline-failed bygge (summary.variant === 'error') ska
    sätta retryPrompt så ErrorBubble visar 'Försök igen'. Tidigare fick
    bara HTTP/network-fel en retry-knapp, inte själva bygg-felet.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert 'summary.variant === "error" ? trimmed || undefined : undefined' in text, (
        "Failed-bygget ska sätta retryPrompt så retry-knappen dyker upp."
    )


@pytest.mark.tooling
def test_floating_chat_surfaces_unapplied_followup_intents() -> None:
    """A3 (2026-06-05): backend skriver ``unappliedFollowupIntents`` (lista av
    {target, reason}) i build-result.json — följd-asks den deterministiska v1-
    pipelinen kände igen men inte kunde applicera. FloatingChat ignorerade dem
    helt; operatören såg bara den generiska no-op-raden. Source-lock att UI:t
    läser fältet och appenderar det till no-op-/degraded-grenarna.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "function summarizeUnappliedFollowupIntents(" in text, (
        "FloatingChat måste ha en helper som läser unappliedFollowupIntents "
        "defensivt (samma mönster som extractAppliedVisibleEffect)."
    )
    assert "buildResult.unappliedFollowupIntents" in text, (
        "Helpern måste läsa unappliedFollowupIntents från build-result-payloaden."
    )
    assert "const unappliedNote = summarizeUnappliedFollowupIntents(" in text, (
        "summarizeBuildResult ska beräkna en unapplied-svans en gång och "
        "appenda den i no-op-/degraded-grenarna."
    )
    assert text.count("${unappliedNote}") >= 3, (
        "unappliedNote ska appendas i båda no-op-grenarna OCH degraded-grenen "
        "så oapplicerade följd-asks blir synliga oavsett utfall."
    )


@pytest.mark.tooling
def test_floating_chat_persist_gated_on_hydration() -> None:
    """P1: persist-effekterna i FloatingChat skrev default-värdet ('false')
    till localStorage vid mount INNAN hydrerings-IIFE:n läst stored-värdena,
    och nollställde därmed operatörens sparade minimized/quick-prompts-
    preference. Source-lock att en hasHydratedRef-gate finns."""
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "hasHydratedRef" in text, (
        "FloatingChat ska gat:a persist-effekterna mot en hasHydratedRef så "
        "default-värden inte skriver över sparad localStorage före hydrering."
    )
    assert text.count("if (!hasHydratedRef.current) return;") >= 3, (
        "Alla tre persist-effekterna (position/minimized/quick-prompts) ska "
        "early-returna tills hydreringen läst klart."
    )


@pytest.mark.tooling
def test_floating_chat_uses_outcome_to_stage() -> None:
    """P2: onStageChange mappade degraded/unknown → 'success' så progress-cardet
    visade grönt medan chatten rapporterade varning. Source-lock att den nu
    delar outcomeToStage med PromptBuilder."""
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "onStageChange?.(outcomeToStage(outcome));" in text, (
        "FloatingChat ska mappa outcome via outcomeToStage (degraded ≠ success)."
    )


@pytest.mark.tooling
def test_floating_chat_trace_polling_covers_dialog_builds() -> None:
    """C3 (scout-fynd 2026-06-05): trace-polling + stage-refine var gated på
    enbart ``isSending`` (FloatingChat:s egna byggen). Ett dialog-bygge driver
    page-level ``isBuilding`` men inte isSending → BuildProgressCard frös på
    'thinking' hela bygget. Lås att både polling-enabled och stage-refinen
    körs på ``isSending || isBuilding``.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "enabled: isSending || isBuilding," in text, (
        "trace-polling måste aktiveras även för dialog-byggen (isBuilding), C3."
    )
    assert "if ((!isSending && !isBuilding) || !onStageChange) return;" in text, (
        "stage-refinen måste köra för dialog-byggen (isBuilding), inte bara isSending (C3)."
    )
