"""Viewser prompt route, prompt runner/builder, runs API and build invocation."""

from __future__ import annotations

import re

import pytest

from tests.support.viewser import VIEWSER_DIR

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core


@pytest.mark.tooling
def test_build_runner_whitelists_dossier_path_overrides() -> None:
    """Prompt-till-sajt MVP v1 låter API-routen `/api/prompt` skicka in en
    absolut dossier-path direkt till `runBuild`. Det är medvetet, men en
    crafted payload får ALDRIG kunna peka build_site.py mot en godtycklig
    fil utanför `examples/` eller `data/prompt-inputs/`. Lås whitelist-
    funktionen så en framtida refactor inte tar bort guarden."""
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")
    assert "ALLOWED_DOSSIER_ROOTS" in text, (
        "build-runner.ts saknar ALLOWED_DOSSIER_ROOTS-whitelist för "
        "dossier-path overrides från prompt-flödet."
    )
    assert "examples" in text and "prompt-inputs" in text, (
        "build-runner.ts whitelisten måste täcka både examples/ och "
        "data/prompt-inputs/ - de två rötter där en Project Input får ligga."
    )
    assert "assertDossierPathAllowed" in text, (
        "build-runner.ts saknar assertDossierPathAllowed-anrop som "
        "validerar override-paths innan spawn av build_site.py."
    )


@pytest.mark.tooling
def test_build_runner_uses_per_site_mutex_not_global_inflight() -> None:
    """Reviewer-fynd 2026-05-25 (Round 2 #5): den tidigare implementationen
    hade en enda global ``let inFlight: Promise | null = null`` som
    serialiserade ALLA byggen i Viewser-processen. Ett segt eller
    hängande bygge på t.ex. ``cafe-bistro`` blockerade då en helt
    orelaterad ``painter-palma``-build i samma process. Per-siteId-
    låsen är nödvändig (två build_site.py-processer som samtidigt
    skriver till ``.generated/<siteId>/`` ger korrupta artefakter),
    men den ska INTE vara global.

    Fix: ``Map<string, Promise<...>>`` keyat på siteId.
    ``runBuild(siteId)`` queue:ar bara mot SAMMA siteId — olika
    siteIds kan köra parallellt.

    Source-lock-mönstret:
      1. NEGATIVT: ingen ``let inFlight: Promise<...> | null`` (skalär).
      2. POSITIVT: ``const inFlight = new Map<string, Promise<...>>()``.
      3. POSITIVT: ``runBuild(siteId)``-loop:en kollar
         ``inFlight.has(siteId)`` (siteId-keyat) snarare än ``inFlight``
         (truthy global).
      4. POSITIVT: rensning sker via ``inFlight.delete(siteId)`` med
         identity-guard så en samtidig follow-up build inte nukas av
         misstag.
    """
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")

    # Negativt: gamla globala scalar-formen får inte återinföras.
    forbidden_global = re.compile(
        r"let\s+inFlight\s*:\s*Promise\s*<[^>]*>\s*\|\s*null",
        re.MULTILINE,
    )
    assert not forbidden_global.search(text), (
        "build-runner.ts: ``let inFlight: Promise<...> | null`` är "
        "den gamla globala mutex:en som blockerade orelaterade siteIds. "
        "Använd ``const inFlight = new Map<string, Promise<...>>()`` "
        "istället (Reviewer Round 2 #5)."
    )

    # Positivt: Map-deklaration med siteId-key + Promise-value.
    map_decl = re.compile(
        r"const\s+inFlight\s*=\s*new\s+Map\s*<\s*string\s*,\s*Promise\s*<[^>]*>\s*>\s*\(\s*\)",
        re.MULTILINE,
    )
    assert map_decl.search(text), (
        "build-runner.ts saknar ``const inFlight = new Map<string, "
        "Promise<...>>()``. Per-siteId-mutex kräver Map keyat på siteId "
        "så olika sajter kan bygga parallellt."
    )

    # Positivt: while-loop:en måste kolla per-siteId, inte den globala
    # Map-instansens truthy:hood.
    while_check = re.compile(
        r"while\s*\(\s*inFlight\s*\.\s*has\s*\(\s*siteId\s*\)\s*\)",
        re.MULTILINE,
    )
    assert while_check.search(text), (
        "build-runner.ts: ``while (inFlight.has(siteId))`` saknas. "
        "Tidigare ``while (inFlight)`` blockerade alla siteIds — den "
        "nya per-siteId-mutex:en måste kolla pending build för EXAKT "
        "den siteId callern frågar om."
    )

    # Positivt: rensningen ska gå via Map.delete med identity-guard så
    # en samtidig follow-up build (som hunnit skriva ny entry) inte
    # nukas av misstag.
    delete_with_guard = re.compile(
        r"if\s*\(\s*inFlight\s*\.\s*get\s*\(\s*siteId\s*\)\s*===\s*promise\s*\)\s*\{\s*"
        r"inFlight\s*\.\s*delete\s*\(\s*siteId\s*\)",
        re.MULTILINE,
    )
    assert delete_with_guard.search(text), (
        "build-runner.ts: rensningen i ``finally``-grenen ska göra "
        "``if (inFlight.get(siteId) === promise) inFlight.delete(siteId)`` "
        "så en samtidig follow-up build (som hunnit skriva ny entry för "
        "samma siteId) inte oavsiktligt nukas. Speglar samma identity-"
        "guard som den tidigare globala ``if (inFlight === promise)``."
    )


@pytest.mark.tooling
def test_prompt_route_returns_400_for_zod_validation_errors() -> None:
    """Audit fynd 1: ogiltig payload (tom prompt, för lång prompt, fel
    typ) är ett klient-/valideringsfel, inte serverfel. Före fixen
    fångade en bred try alla fel som 500, vilket gjorde API-kontraktet
    missvisande och försvårade felsökning.

    Lås att routen särskiljer ZodError -> 400 från övriga fel -> 500
    så framtida refactor inte återinför den breda 500-grenen.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert "instanceof z.ZodError" in text, (
        "/api/prompt måste skilja Zod-valideringsfel från serverfel via "
        "`error instanceof z.ZodError` och returnera 400 för validering, "
        "inte den breda 500-grenen."
    )
    assert re.search(r"status:\s*400", text), (
        "/api/prompt saknar `status: 400`-svar för Zod-validering. "
        "Klient-/valideringsfel ska aldrig returneras som 500."
    )


@pytest.mark.tooling
def test_prompt_payload_schema_trims_whitespace_before_length_check() -> None:
    """Audit fynd 2: en whitespace-only prompt (`"   "`) passerar
    `.string().min(1)` men trimmades senare i `runPromptToProjectInput`
    och kastades som "Prompt får inte vara tom." vilket sedan blev 500.
    UI:n stoppar normalfallet men API-gränsen gjorde inte det.

    Lås att schemat trimmar FÖRE min/max så whitespace-only fångas vid
    API-gränsen och returneras som 400 (via ZodError).
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    pattern = re.compile(
        r"z\s*\.\s*string\(\)\s*\.\s*trim\(\)\s*\.\s*min\(\s*1",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "PromptPayloadSchema.prompt måste vara `z.string().trim().min(1)..."
        ".max(4000)` så whitespace-only payloads fångas av `.min(1)` "
        "EFTER trim. Utan trim slipper `' '` igenom till helpern."
    )


@pytest.mark.tooling
def test_prompt_route_passes_dossier_override_to_run_build() -> None:
    """Prompt-flödet får inte falla tillbaka till `runBuild(siteId)` utan
    dossier-path override - det skulle leta i `examples/` istället för
    `data/prompt-inputs/` och misslyckas med 'Project Input saknas'.
    Lås kontraktet att routen alltid skickar in helper.dossierPath."""
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert "runBuild(helper.siteId, helper.dossierPath)" in text, (
        "/api/prompt måste anropa runBuild med BÅDE siteId och "
        "helper.dossierPath. Utan path-override hamnar lookupen i "
        "examples/ och det prompt-genererade Project Inputet hittas "
        "inte (det ligger i data/prompt-inputs/)."
    )


@pytest.mark.tooling
def test_prompt_route_supports_followup_mode_without_schema_migration() -> None:
    """Follow-up prompt ska styras av sidecar-meta, inte Project Input-schema."""
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert 'z.enum(["init", "followup"])' in text, (
        "/api/prompt måste ha explicit init/followup-läge så UI:t kan "
        "skilja ny sajt från ny version."
    )
    assert "siteId" in text and "Följdprompt kräver valt siteId" in text, (
        "Följdprompt-läget måste kräva siteId vid API-gränsen innan prompt-helpern spawnas."
    )
    assert "projectId: z" not in text and "version: z" not in text, (
        "/api/prompt ska inte validera projectId/version som klientpayload; "
        "sidecar-meta räcker i denna sprint."
    )


@pytest.mark.tooling
def test_b169_prompt_route_uses_per_site_mutex_not_global_inflight() -> None:
    """B169 (bug-sweep 2026-06-10): the prompt route's mutex must be
    per-siteId, not a single global ``promptInFlight``.

    DELIBERATE UPDATE (was ``test_prompt_route_serializes_prompt_helper_
    before_build``): the prior version of this test locked the GLOBAL
    ``let promptInFlight: Promise | null`` queue and only asserted that the
    queue wraps both Phase 1 (helper) and Phase 2 (build). That global queue
    was exactly the B169 antipattern — it serialised ALL sites, so a slow /
    hanging build on site A blocked init/follow-up on site B. ``build-runner.ts``
    already fixed the identical antipattern with a per-site ``Map`` (Reviewer
    Round 2 #5); this route must do the same. We rewrite the lock here on
    purpose so the new per-site contract is the one that's enforced.

    Per-site serialisation MUST be preserved: two follow-ups for the SAME
    siteId still queue (Phase 1 reads/bumps ``meta.version`` + writes the PI
    snapshot — that must not race). Init has no siteId at the API boundary and
    generates a collision-free one in Phase 1, so inits get a unique key and
    run in parallel.

    Source-lock mönstret (speglar test_build_runner_uses_per_site_mutex_...):
      1. NEGATIVT: ingen ``let promptInFlight: Promise<...> | null`` (skalär).
      2. POSITIVT: ``const promptInFlight = new Map<string, Promise<...>>()``.
      3. POSITIVT: serialiserings-loopen kollar ``promptInFlight.has(queueKey)``
         (per-site), inte ``while (promptInFlight)`` (truthy global).
      4. POSITIVT: ``queueKey`` deriveras ur ``payload.siteId`` så follow-ups
         serialiseras per sajt.
      5. POSITIVT: rensning via ``promptInFlight.delete(queueKey)`` med
         identity-guard så en samtidig follow-up inte nukas av misstag.
      6. Ordningen Phase 1 (helper) före Phase 2 (build) bevaras.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")

    # 1. NEGATIVT: gamla globala scalar-formen får inte återinföras.
    forbidden_global = re.compile(
        r"let\s+promptInFlight\s*:\s*Promise\s*<[^>]*>\s*\|\s*null",
        re.MULTILINE,
    )
    assert not forbidden_global.search(text), (
        "route.ts: ``let promptInFlight: Promise<...> | null`` är den gamla "
        "globala mutex:en som blockerade ALLA sajter (B169). Använd "
        "``const promptInFlight = new Map<string, Promise<...>>()`` istället."
    )

    # 2. POSITIVT: Map-deklaration keyat på siteId (string) -> Promise.
    map_decl = re.compile(
        r"const\s+promptInFlight\s*=\s*new\s+Map\s*<\s*string\s*,\s*Promise\s*<[^>]*>\s*>\s*\(\s*\)",
        re.MULTILINE,
    )
    assert map_decl.search(text), (
        "route.ts saknar ``const promptInFlight = new Map<string, "
        "Promise<...>>()``. Per-siteId-mutex kräver Map keyat på siteId "
        "så olika sajter (och parallella inits) kan köra samtidigt (B169)."
    )

    # 3. POSITIVT: loopen väntar per-queueKey, inte på den globala instansens
    #    truthy:hood.
    while_check = re.compile(
        r"while\s*\(\s*promptInFlight\s*\.\s*has\s*\(\s*queueKey\s*\)\s*\)",
        re.MULTILINE,
    )
    assert while_check.search(text), (
        "route.ts: ``while (promptInFlight.has(queueKey))`` saknas. Tidigare "
        "``while (promptInFlight)`` blockerade alla sajter — den nya per-site-"
        "mutex:en måste vänta bara på pending prompt-build för EXAKT denna "
        "queueKey (B169)."
    )

    # 4. POSITIVT: queueKey deriveras ur siteId så follow-ups serialiseras per
    #    sajt (versionsrace-skyddet bevaras).
    assert re.search(r"const\s+queueKey\s*=\s*payload\.siteId\s*\?\?", text), (
        "route.ts måste derivera ``const queueKey = payload.siteId ?? ...`` så "
        "follow-ups serialiseras per sajt och inits (utan siteId) får en unik "
        "nyckel (B169)."
    )

    # 5. POSITIVT: rensning via Map.delete med identity-guard.
    delete_with_guard = re.compile(
        r"if\s*\(\s*promptInFlight\s*\.\s*get\s*\(\s*queueKey\s*\)\s*===\s*promise\s*\)\s*\{\s*"
        r"promptInFlight\s*\.\s*delete\s*\(\s*queueKey\s*\)",
        re.MULTILINE,
    )
    assert delete_with_guard.search(text), (
        "route.ts: ``finally``-rensningen ska göra "
        "``if (promptInFlight.get(queueKey) === promise) "
        "promptInFlight.delete(queueKey)`` så en samtidig follow-up för samma "
        "siteId inte nukas (B169, speglar build-runner.ts:s identity-guard)."
    )

    # 6. Phase 1 (helper) före Phase 2 (build) — serialiseringen omfattar båda
    #    via runPromptBuildOnce.
    helper_index = text.index("const helper = await runPromptToProjectInput")
    build_index = text.index("runBuild(helper.siteId, helper.dossierPath)")
    assert helper_index < build_index, (
        "Phase 1 (prompt-helper) måste köra före Phase 2 (runBuild) inom den "
        "per-site-serialiserade runPromptBuildOnce."
    )


@pytest.mark.tooling
def test_b172_detect_latest_run_filters_by_site_id() -> None:
    """B172 (bug-sweep 2026-06-10): ``detectLatestRunIdByMtime`` saknade ett
    siteId-filter. På en SUCCESS med trunkerad stdout (ingen ``runId:``-rad)
    plockade den GLOBALT nyaste run-mappen under ``data/runs/``. Eftersom
    byggen för olika siteIds serialiseras oberoende (per-site-mutex:en låter
    dem köra parallellt) kunde ett parallellt bygge på en ANNAN sajt vara den
    nyaste mappen och returneras som DENNA build:s runId i /api/prompt-svaret.

    Fix: filtrera kandidaterna på siteId (läs ``build-result.json``:s
    ``siteId``) i mtime-ordning innan valet. Failure-vägen (B42) är oförändrad
    och rörs inte — den får ALDRIG falla tillbaka på mtime-detektionen.

    Source-lock:
      1. Funktionen tar en ``siteId``-parameter.
      2. Anropet på success-vägen skickar in siteId.
      3. Filtret jämför mot ``build-result.json``:s siteId (readBuildResult +
         ``buildResult.siteId === siteId``).
    """
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")

    # 1. Signaturen måste ta en siteId-parameter.
    assert re.search(
        r"async\s+function\s+detectLatestRunIdByMtime\s*\(\s*siteId\s*:\s*string\s*\)",
        text,
    ), (
        "build-runner.ts: detectLatestRunIdByMtime måste ta en ``siteId: "
        "string``-parameter så fallbacken kan filtrera kandidater på sajt (B172)."
    )

    # 2. Success-vägens anrop måste skicka in siteId.
    assert re.search(
        r"detectLatestRunIdByMtime\s*\(\s*siteId\s*\)",
        text,
    ), (
        "build-runner.ts: success-vägens mtime-fallback måste anropas som "
        "``detectLatestRunIdByMtime(siteId)`` (B172)."
    )

    # 3. Filtret måste matcha mot build-result.json:s siteId.
    function_start = text.index("async function detectLatestRunIdByMtime")
    function_body = text[function_start : text.index("async function runBuildOnce")]
    assert "readBuildResult" in function_body, (
        "build-runner.ts: detectLatestRunIdByMtime måste läsa "
        "build-result.json (readBuildResult) för att avgöra varje kandidats "
        "siteId (B172)."
    )
    assert re.search(r"buildResult\.siteId\s*===\s*siteId", function_body), (
        "build-runner.ts: detectLatestRunIdByMtime måste filtrera kandidater "
        "på ``buildResult.siteId === siteId`` innan mtime-valet (B172)."
    )
    # Behåll ENOENT-toleransen (test_build_runner_latest_run_fallback_...).
    assert 'code === "ENOENT"' in function_body and "return null" in function_body, (
        "detectLatestRunIdByMtime måste fortsatt returnera null när data/runs "
        "saknas i en färsk miljö (oförändrat efter B172-filtret)."
    )


@pytest.mark.tooling
def test_b164_prompt_route_recovers_chain_version_on_bridge_failure() -> None:
    """B164 (bug-sweep 2026-06-10): ett OpenClaw-bridge-fel EFTER att KÖR-7-
    kedjan redan skrivit en ny version gav ett tyst DUBBELBYGGE.
    ``runOpenClawFollowupApply`` returnerar ``null`` vid timeout/exit!=0/
    trunkerad stdout/parse-fel, och route:n föll då igenom till legacy Phase
    1+2 — som byggde en ANDRA version ovanpå den kedjan redan landat
    (``build_site.py`` skriver PI före targeted render).

    Fix: snapshot:a senaste KLARA run för siteId FÖRE bridge-anropet, och om
    bridge:n returnerar null på en follow-up — jämför mot senaste run EFTER.
    Om en ny runId dykt upp landade kedjan en version: re-surfa DEN runen med
    ärlig degraded-status i stället för att dubbelbygga. Ingen retry, ingen ny
    modellroll. En vanlig no-op (``applied=false``) är säker och triggar INTE
    recovery (kedjan stannade vid en ärlig gate före bygget).

    Source-lock:
      1. Pre-bridge-snapshot via latestCompletedRunForSite FÖRE
         runOpenClawFollowupApply-anropet.
      2. Recovery-grenen är gated på ``applyResult === null`` + follow-up.
      3. Den jämför pre/post runId och re-surfar bara vid skillnad.
      4. Den returnerar en degraderad status (aldrig tyst grön success).
      5. Recovery sker FÖRE legacy-bygget (runBuild) i koden.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")

    # 1. Pre-bridge-snapshot måste tas FÖRE bridge-anropet.
    assert "latestCompletedRunForSite" in text, (
        "route.ts måste ha en latestCompletedRunForSite-helper som snapshot:ar "
        "senaste klara run för siteId (B164)."
    )
    snapshot_idx = text.index("const preBridgeLatestRun")
    bridge_call_idx = text.index("await runOpenClawFollowupApply(")
    assert snapshot_idx < bridge_call_idx, (
        "route.ts: pre-bridge-snapshotet (preBridgeLatestRun) måste tas FÖRE "
        "runOpenClawFollowupApply-anropet — annars kan vi inte avgöra om "
        "kedjan landat en version under ett bridge-fel (B164)."
    )

    # 2. Recovery-grenen gated på null-bridge + follow-up.
    assert re.search(r"applyResult\s*===\s*null", text), (
        "route.ts: B164-recovery måste vara gated på ``applyResult === null`` "
        "(bridge-felvägen) — en applied=false-no-op är säker och får inte "
        "trigga recovery."
    )

    # 3. Jämför pre/post runId och re-surfa bara vid skillnad.
    assert "const postBridgeLatestRun" in text, (
        "route.ts: B164-recovery måste läsa om senaste run EFTER bridge-felet "
        "(postBridgeLatestRun)."
    )
    assert re.search(
        r"postBridgeLatestRun\.runId\s*!==\s*preBridgeLatestRun\.runId",
        text,
    ), (
        "route.ts: B164-recovery får bara re-surfa när en NY runId dykt upp "
        "(postBridgeLatestRun.runId !== preBridgeLatestRun.runId) — annars "
        "skrev kedjan ingen version och legacy-bygget ska köra."
    )

    # 4. Ärlig degraded-status — aldrig tyst grön success över ett bridge-fel.
    recovery_idx = text.index("postBridgeLatestRun.runId !== preBridgeLatestRun.runId")
    # Avgränsa recovery-grenen vid KÖR-6a-kommentaren som följer den, så vi
    # läser hela return-blocket (degraded-status + bridge-markör).
    recovery_block = text[recovery_idx : text.index("// KÖR-6a", recovery_idx)]
    assert '"degraded"' in recovery_block, (
        "route.ts: den re-surfade runen måste få en ärlig degraded-status "
        "(B164) — inte presenteras som en ren success."
    )
    assert '"degraded-recovered"' in recovery_block, (
        "route.ts: B164-recovery ska markera bridgen som "
        "``status: \"degraded-recovered\"`` så UI:t ser att en version landat "
        "men att apply-bryggan degraderade."
    )

    # 5. Recovery måste returnera FÖRE legacy-bygget (runBuild).
    return_in_recovery_idx = text.index("return {", recovery_idx)
    legacy_build_idx = text.index("runBuild(helper.siteId, helper.dossierPath)")
    assert return_in_recovery_idx < legacy_build_idx, (
        "route.ts: B164-recovery-grenen måste ``return`` innan legacy-bygget "
        "(runBuild) — annars dubbelbyggs en andra version (B164)."
    )


@pytest.mark.tooling
def test_b175_recovery_covers_first_completed_run() -> None:
    """B175 (B164-uppföljning): recoveryn gällde bara sajter som redan HADE en
    klar run före bridge-anropet (gaten krävde ``preBridgeLatestRun !== null``).
    Om KÖR-7-kedjan landade sajtens FÖRSTA klara run (init-runen prunad via
    SAJTBYGGAREN_MAX_RUNS, eller aldrig fullbordad) och bryggan sedan failade
    rapportera, hoppades recoveryn över och legacy Phase 1+2 dubbelbyggde —
    exakt det B164 skulle förhindra.

    Fixen: gaten kräver inte längre ett pre-bridge-run; i stället avgörs
    "kedjan landade en NY run" med runId-diff när ett pre-run finns, och med
    run-katalogens mtime >= request-start (minus liten fs-tidsstämpel-marginal)
    när pre-snapshotet är null. Mtime-kravet bevarar ursprungs-skyddet: ett
    pre-snapshot som failade transient kan aldrig få en GAMMAL run att
    re-surfas som om prompten producerade den.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )

    # 1. Request-start måste fångas FÖRE bridge-anropet (mtime-jämförelsens
    #    referenspunkt).
    start_idx = text.index("const requestStartMs = Date.now();")
    bridge_call_idx = text.index("await runOpenClawFollowupApply(")
    assert start_idx < bridge_call_idx, (
        "route.ts: requestStartMs måste fångas FÖRE runOpenClawFollowupApply — "
        "annars kan first-run-recoveryn inte avgöra om runen skapades under "
        "requesten (B175)."
    )

    # 2. Gaten får INTE längre kräva preBridgeLatestRun !== null.
    assert (
        'if (applyResult === null && payload.mode === "followup" && payload.siteId) {'
        in text
    ), (
        "route.ts: B164-recovery-gaten får inte kräva preBridgeLatestRun !== "
        "null — first-run-scenariot (B175) måste också kunna återvinnas."
    )

    # 3. First-run-grenen: mtime-färskhetskravet med fs-marginal.
    assert "postBridgeLatestRun.mtimeMs >=" in text, (
        "route.ts: när preBridgeLatestRun är null måste recoveryn kräva att "
        "post-runen uppstod UNDER requesten (mtime >= requestStart - marginal) "
        "— annars kan en stale run re-surfas (B175)."
    )
    assert "FS_TIMESTAMP_ALLOWANCE_MS" in text, (
        "route.ts: mtime-jämförelsen behöver en liten fs-tidsstämpel-marginal "
        "(grova fs-timestamps) — utan den missas legitima chain-runs (B175)."
    )

    # 4. Helpern måste exponera mtimeMs så jämförelsen alls är möjlig.
    assert "return { runId: name, version, mtimeMs };" in text, (
        "route.ts: latestCompletedRunForSite måste returnera run-katalogens "
        "mtimeMs (B175)."
    )


@pytest.mark.tooling
def test_prompt_runner_uses_double_dash_to_protect_dashed_prompts() -> None:
    """Audit fynd 3: vanliga prompter börjar med `-` eller `--` (t.ex.
    en inklistrad punktlista: "- skapa en sajt..."). Utan `--`-separator
    tolkar argparse i `scripts/prompt_to_project_input.py` prompten som
    en CLI-option och spawnen fallerar innan Project Input hinner
    skrivas.

    Lås att lib/prompt-runner.ts skickar in `--` mellan scriptPath och
    prompten så argparse stannar option-parsning.
    """
    text = (VIEWSER_DIR / "lib" / "prompt-runner.ts").read_text(encoding="utf-8")
    pattern = re.compile(
        r"args\.push\(\s*\"--\"\s*,\s*trimmed\s*\)",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "prompt-runner.ts spawn-args måste lägga `--` direkt före prompten "
        "så en prompt som börjar med `-` (punktlista) eller `--` inte "
        "tolkas som CLI-option av argparse i prompt_to_project_input.py."
    )


@pytest.mark.tooling
def test_prompt_runner_passes_followup_site_id_to_helper() -> None:
    text = (VIEWSER_DIR / "lib" / "prompt-runner.ts").read_text(encoding="utf-8")
    assert "--followup-site-id" in text, (
        "prompt-runner.ts måste kunna skicka valt siteId till "
        "prompt_to_project_input.py för följdprompt-versioner."
    )
    assert "Följdprompt kräver ett valt siteId" in text, (
        "prompt-runner.ts måste stoppa följdprompt utan siteId innan spawn."
    )


@pytest.mark.tooling
def test_project_input_picker_includes_prompt_inputs_directory() -> None:
    text = (VIEWSER_DIR / "lib" / "project-inputs.ts").read_text(encoding="utf-8")
    assert '"prompt-inputs"' in text, (
        "listProjectInputs måste även läsa data/prompt-inputs/ så operatorn "
        "kan välja prompt-genererade siteIds för följdprompt."
    )
    assert '"examples"' in text, "examples/ måste fortsatt finnas kvar som Project Input-källa."
    assert "return null" in text and "JSON.parse" in text, (
        "Korrupta Project Input-filer ska hoppas över lokalt i listProjectInputs "
        "så en trasig fil inte 500:ar hela /api/runs."
    )
    assert "bySiteId.set(item.siteId, item)" in text, (
        "listProjectInputs måste dedupe:a på siteId och låta prompt-inputs "
        "vinna över examples när samma siteId finns i båda rötter."
    )


@pytest.mark.tooling
def test_prompt_builder_exposes_followup_mode_and_consumes_ndjson_stream() -> None:
    text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    # Följdprompt-läget exponerades tidigare via en synlig "Ny sajt /
    # Följdprompt"-pill-rad. Efter total-minimalism 2026-05-27 deriveras
    # läget automatiskt från `followupReady` istället. Testet förankrar
    # därför auto-derive-mönstret som det stabila kontraktet.
    assert '"followup"' in text and "followupReady" in text, (
        "PromptBuilder måste fortfarande exponera followup-läge — antingen "
        "via UI-val eller auto-derivering."
    )
    assert 'followupReady ? "followup" : "init"' in text, (
        "PromptBuilder måste auto-derivera mode från followupReady så "
        "operatorns prompt routas rätt utan manuell pill-växling."
    )
    assert 'submissionMode: "followup"' in text, (
        "PromptBuilder måste skicka submissionMode='followup' till "
        "executeBuild när followupReady är sant."
    )
    # B122-fix 2026-05-27: setTimeout(1500)-baserad stage-flip ersatt
    # av NDJSON-stream från /api/prompt. PromptBuilder ska skicka
    # `Accept: application/x-ndjson`, läsa `response.body` som stream
    # och flippa stage på `stage:"building"`-eventet.
    # `setTimeout(` (med öppningsparentes) flaggar faktiska function-
    # anrop. Historiska referenser i kommentarer/docstrings ("den gamla
    # setTimeout-baserade flippen") är tillåtna så fixet kan dokumentera
    # bort-refaktoreringen utan att triggas av sin egen förklaringstext.
    assert "setTimeout(" not in text, (
        "PromptBuilder får inte ANROPA setTimeout för stage-transitions "
        "längre — använd riktig signal från /api/prompt:s NDJSON-stream."
    )
    assert '"application/x-ndjson"' in text, (
        "PromptBuilder måste sätta Accept: application/x-ndjson så "
        "/api/prompt svarar med stream istället för synkron JSON."
    )
    assert "response.body.getReader()" in text, (
        "PromptBuilder måste läsa /api/prompt-svaret som stream via response.body.getReader()."
    )
    assert 'event.stage === "building"' in text, (
        "PromptBuilder måste flippa stage till 'building' när NDJSON-"
        'eventet `stage:"building"` kommer från route:n (riktig signal).'
    )
    assert 'event.stage === "done"' in text, (
        'PromptBuilder måste behandla `stage:"done"`-eventet som '
        "slutsignal med runId + siteId + buildStatus."
    )


@pytest.mark.tooling
def test_runs_api_handles_missing_runs_dir_and_invalid_since() -> None:
    runs_lib = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")
    trace_route = (
        VIEWSER_DIR / "app" / "api" / "runs" / "[runId]" / "trace" / "route.ts"
    ).read_text(encoding="utf-8")

    assert 'code === "ENOENT"' in runs_lib and "return []" in runs_lib, (
        "listRuns ska returnera tom lista när data/runs saknas i en färsk miljö."
    )
    assert "Ogiltigt since-timestamp" in runs_lib, (
        "readRunTrace ska flagga ogiltig since i stället för att tyst "
        "returnera hela trace-loggen igen."
    )
    assert "Ogiltigt since" in trace_route and "status: 400" in trace_route, (
        "trace API ska rapportera ogiltig since som 400 inputfel."
    )


@pytest.mark.tooling
def test_build_runner_latest_run_fallback_tolerates_missing_runs_dir() -> None:
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")
    function_start = text.index("async function detectLatestRunIdByMtime")
    function_body = text[function_start : text.index("async function runBuildOnce")]

    assert 'code === "ENOENT"' in function_body and "return null" in function_body, (
        "detectLatestRunIdByMtime ska returnera null när data/runs saknas "
        "så färska miljöer inte 500:ar efter en lyckad build utan stdout-runId."
    )


@pytest.mark.tooling
def test_prompt_route_surfaces_build_status() -> None:
    """B44: /api/prompt must propagate build-result.json:status to the
    client so PromptBuilder can render success / degraded / failed
    instead of treating any returned runId as a green build.
    build-runner.ts intentionally returns the structured failure path
    with a runId (B40) so failed runs still appear in Run History;
    without buildStatus on the wire the operator UI used to flag those
    as "Build klar".
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert "buildStatus" in text, (
        "/api/prompt route.ts must include `buildStatus` in the response "
        "payload so PromptBuilder can classify the build outcome."
    )
    assert "extractBuildStatus" in text or "buildResult.status" in text, (
        "/api/prompt route.ts must read build-result.json:status to populate "
        "buildStatus on the response."
    )


def test_ui_textarea_forwards_ref_explicitly() -> None:
    """Lock the explicit `ref` forwarding in the shared Textarea wrapper.

    FloatingChat (``apps/viewser/components/builder/floating-chat.tsx``)
    auto-fokuserar composern när panelen expanderas från minimerat
    läge via ``composerRef.current?.focus()``. Det fungerar bara om
    Textarea-komponenten explicit destrukturerar ``ref`` ur props och
    vidarebefordrar den till underliggande ``<textarea>``.

    Tidigare läckte komponenten ref bara via ``{...props}``-spread,
    vilket är en bräcklig React 19-detalj (ref behandlas som vanlig
    prop sedan v19, men spread-vidarebefordran är inte garanterat
    dokumenterad). Den här testen låser explicit destruktur + bindning
    så en framtida refaktor inte tyst kan tappa ref:n och bryta
    auto-focus utan att någon märker det förrän en operator klagar.
    """
    text = (VIEWSER_DIR / "components" / "ui" / "textarea.tsx").read_text(encoding="utf-8")
    # Destruktur av `ref` ur funktionssignaturen — det är detta som
    # gör ref tillgänglig som en explicit referens istället för att
    # gömmas i `...props`.
    assert "ref,\n" in text or "ref," in text, (
        "Textarea måste destrukturera `ref` ur sina props så ref-"
        "vidarebefordran är explicit. Förlita dig inte på att "
        "{...props}-spread implicit propsar ref."
    )
    # `ref={ref}` på <textarea>-elementet — den faktiska bindningen.
    assert "ref={ref}" in text, (
        "Textarea måste explicit binda `ref={ref}` på underliggande "
        "<textarea>-element så DOM-noden exponeras för callers som "
        "FloatingChat:s composerRef auto-focus."
    )


def test_prompt_route_emits_ndjson_stream_on_accept_header() -> None:
    """B122-fix 2026-05-27: /api/prompt måste exponera en NDJSON-stream
    när klienten signalerar `Accept: application/x-ndjson`, så PromptBuilder
    kan flippa stage från `thinking` till `building` på en RIKTIG signal
    (Phase 1 → Phase 2-övergången) istället för den gamla gissade
    `setTimeout(1500)`-flippen som producerade falsk 'Bygger sajt' om
    svaret kom under 1.5s eller motsatt — hängde i 'thinking' om Phase 1
    tog över 1.5s.

    Stream-kontrakt:
      1. `{stage:"building"}` exakt när Phase 1 (runPromptToProjectInput)
         är klar — innan runBuild startar.
      2. `{stage:"done", runId, siteId, ...}` när Phase 2 (runBuild) är klar.
      3. `{stage:"error", error:"..."}` vid fel.

    Bakåtkompatibelt: klienter som INTE skickar Accept-headern (t.ex.
    floating-chat.tsx och use-followup-build.ts) får fortfarande en
    synkron NextResponse.json med samma fält som tidigare.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert '"application/x-ndjson"' in text, (
        "/api/prompt route.ts måste exponera content-type 'application/x-ndjson' "
        "när Accept-headern begär stream-läge."
    )
    assert "ReadableStream" in text, (
        "/api/prompt route.ts måste returnera en ReadableStream när klienten begär NDJSON-läge."
    )
    assert "onPhase1Done" in text, (
        "/api/prompt route.ts måste skicka ett `onPhase1Done`-callback "
        "in i runPromptBuildOnce/runPromptBuildSerially så stream-läget "
        "kan emittera `stage:'building'` exakt mellan Phase 1 och Phase 2."
    )
    assert 'stage: "building"' in text, (
        "/api/prompt route.ts måste emittera `{stage:'building'}` i "
        "NDJSON-streamen när Phase 1 är klar."
    )
    assert 'stage: "done"' in text, (
        "/api/prompt route.ts måste emittera `{stage:'done', ...result}` "
        "som slutevent i NDJSON-streamen."
    )
    assert 'stage: "error"' in text, (
        "/api/prompt route.ts måste emittera `{stage:'error', error:'...'}` "
        "om något fas-anrop kastar inom streamen."
    )
    # Bakåtkompatibilitet: synkron NextResponse.json-fallback finns kvar
    # för klienter utan Accept-headern (floating-chat, use-followup-build).
    assert "NextResponse.json(await runPromptBuildSerially(payload))" in text, (
        "/api/prompt route.ts måste behålla den synkrona NextResponse.json-"
        "fallbacken för klienter som inte sätter Accept: application/x-ndjson."
    )


@pytest.mark.tooling
def test_prompt_builder_classifies_failed_build_distinctly() -> None:
    """B44: PromptBuilder must classify build outcomes via classifyBuildStatus
    and render distinct UI for success / degraded / failed instead of
    falling through to a single green "Build klar" banner whenever a
    runId is present. Lock the classification helper and the three
    distinct UI strings so a future refactor cannot collapse them.
    """
    text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "classifyBuildStatus" in text, (
        "prompt-builder.tsx must export/use a classifyBuildStatus helper "
        "that maps build-result.json:status to ok/degraded/failed/unknown."
    )
    assert "PromptBuildOutcome" in text, (
        "prompt-builder.tsx must expose a PromptBuildOutcome type so page.tsx "
        "can render an outcome-aware header instead of a hard-coded 'Build klar'."
    )
    for stage_literal in (
        '"degraded"',
        '"failed"',
    ):
        assert stage_literal in text, (
            f"prompt-builder.tsx must distinguish stage {stage_literal} so "
            "degraded/failed builds do not render as success."
        )
    assert "Build klar med varning" in text, (
        "prompt-builder.tsx must render a degraded headline distinct from the success banner."
    )
    assert "Build misslyckades" in text, (
        "prompt-builder.tsx must render a dedicated failure headline when "
        "build-result.json status=failed."
    )


@pytest.mark.tooling
def test_page_uses_outcome_aware_header_for_prompt_build_done() -> None:
    """B44: app/page.tsx must propagate the PromptBuildOutcome from
    PromptBuilder into setStatusText so the page header does not say
    "Build klar via prompt:" for a structured failure run. Source-lock
    the headerStatusForOutcome helper so a future refactor cannot drop
    the classification.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")
    assert "PromptBuildOutcome" in text, (
        "page.tsx must import PromptBuildOutcome from @/components/prompt-builder."
    )
    assert "headerStatusForOutcome" in text, (
        "page.tsx must use headerStatusForOutcome to map the outcome to a "
        "header string instead of hardcoding 'Build klar via prompt:'."
    )
    assert "Build misslyckades" in text, (
        "page.tsx header must show a dedicated failure string when the "
        "PromptBuilder reports outcome=failed."
    )


@pytest.mark.tooling
def test_build_runner_returns_structured_failure_instead_of_throwing() -> None:
    """B40: when scripts/build_site.py exits 1 because npm install /
    npm run build failed, it STILL writes the canonical artefakter
    (build-result.json with status=failed, plus quality-result.json +
    repair-result.json + the generated-files/ snapshot) per the
    Builder MVP contract. The dev wrapper used to throw on any
    non-zero exit, which dropped the runId on the floor and forced
    /api/build to return 500 with no way for the UI to surface a
    failed run. The defensive path now reads build-result.json from
    disk and returns it as a normal result so the Run History entry
    shows up with status=failed and the RunDetailsPanel can render
    the four artefakter for diagnosis. Only when there's no runId
    AND no structured artefakt does the wrapper throw.
    """
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")

    # B40: the failure branch must read build-result.json from disk so
    # the UI sees a structured failed run instead of bare 500.
    assert re.search(r"exitCode\s*!==\s*0", text), (
        "build-runner.ts saknar exitCode !== 0-gren - hela B40-kontraktet hänger på den."
    )
    assert "readBuildResult" in text, (
        "build-runner.ts måste läsa build-result.json från disk i failure-"
        "grenen så failed runs når UI:t med strukturerad data istället för "
        "bare 500."
    )

    # B42 (post-review-2): the failure path must NOT fall back to
    # detectLatestRunIdByMtime() - that would return a PRIOR run-dir
    # whenever build_site.py crashes BEFORE printing `runId:`,
    # mislabeling someone else's run as the current failed build.
    # Only the success path may use the mtime fallback (where
    # exitCode === 0 guarantees the latest dir IS this build's).
    failure_block = re.search(
        r"if\s*\(\s*exitCode\s*!==\s*0\s*\)\s*\{[\s\S]*?\n\s{0,4}\}",
        text,
        re.MULTILINE,
    )
    assert failure_block, (
        "Kunde inte hitta `if (exitCode !== 0) { ... }`-blocket i build-runner.ts."
    )
    assert "detectLatestRunIdByMtime" not in failure_block.group(0), (
        "build-runner.ts failure-grenen får inte använda "
        "detectLatestRunIdByMtime() som fallback. När build_site.py "
        "kraschar FÖRE `print(runId:)` returnerar mtime-fallbacken en "
        "tidigare run och felaktigt märker den som denna build:s "
        "strukturerade failure (B42 post-review-2 fynd)."
    )


@pytest.mark.tooling
def test_page_useeffect_guards_success_path_with_cancelled_check() -> None:
    """Race-condition guard for app/page.tsx initial fetch:
    the success path of the useEffect-IIFE used to call refreshRuns()
    which itself ran setRuns / setProjectInputs / setSelectedRunId /
    setSelectedSiteId / setStatusText UNCONDITIONALLY after its own
    await. The cancelled-flag on the catch branch then only protected
    error-path stale updates, not success-path stale updates. If the
    component unmounted (or the dependency array changed) while
    /api/runs was in flight, a successful resolution arriving after
    unmount still wrote five setState calls onto a stale tree.

    The fix splits the call into a pure ``fetchRuns`` data fetcher
    and a separate ``applyRunsData`` state mutator, with the
    cancelled-guard sitting between them. Source-lock that ordering
    so a future refactor cannot collapse the two back into one
    function and silently drop the guard.

    Tier 1 (2026-06-01): vi extraherade fetch-loopen till en
    återanvändbar ``loadRuns``-callback (för retry-knapp i
    runsLoadError-cardet). Guarden använder nu ``cancelledRef.current``
    istället för en bool-variabel ``cancelled``. Båda mönstren
    accepteras av denna regex.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")

    # Look for ``await fetchRuns()`` -> ``if (cancelled) return`` eller
    # ``if (cancelledRef?.current) return`` -> ``applyRunsData`` (eller
    # ``setRuns(``) ordering inside the same try-block. 0-300 character
    # window håller regexen tight.
    pattern = re.compile(
        r"await\s+fetchRuns\(\)[\s\S]{0,300}?"
        r"if\s*\(\s*(?:cancelled|cancelledRef\??\.current)\s*\)\s*return\s*;"
        r"[\s\S]{0,300}?(?:applyRunsData|setRuns\()",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "page.tsx useEffect saknar cancelled-guard mellan await fetchRuns() "
        "och applyRunsData / setRuns. Det skapar race condition där en "
        "stale success-resolution skriver state efter unmount."
    )


@pytest.mark.tooling
def test_page_on_build_done_passes_apply_runs_context() -> None:
    """Stale-closure guard: after onBuildDone sets selectedRunId, the
    fetchRuns().then(applyRunsData) path must pass an explicit context
    snapshot so applyRunsData does not read a pre-build selectedRunId
    and reset selectedSiteId to the first Project Input.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")
    pattern = re.compile(
        r"fetchRuns\(\)[\s\S]{0,400}?applyRunsData\(\s*data\s*,\s*\{[\s\S]{0,200}?selectedRunId:\s*runId",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "page.tsx onBuildDone ska anropa applyRunsData med ctx.selectedRunId "
        "= runId — annars vinner stale closure och run-following bryts."
    )


@pytest.mark.tooling
def test_prompt_builder_blocks_followup_when_run_siteid_unknown() -> None:
    """Follow-up guard: when the selected run has siteId unknown the UI
    must not fall back to selectedSiteId for targetSiteId (silent wrong
    site). Source-lock runSiteIdUnknown + explicit submit error.
    """
    prompt_text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "runSiteIdUnknown" in prompt_text
    assert "follow-up kan inte" in prompt_text
    picker_text = (VIEWSER_DIR / "components" / "project-input-picker.tsx").read_text(
        encoding="utf-8"
    )
    assert "project-input-run-siteid-unknown" in picker_text


# ----------------------------------------------------------------------
# Jakob-handoff bite-A + bite-C (post-PR #139)
# ----------------------------------------------------------------------
# Två låg-impact-fynd som flaggades av Jakobs bot efter PR #139:
#   A. prompt-builder.tsx NDJSON-parsing: inre try/catch runt JSON.parse
#      så en korrupt rad inte sprider "Unexpected token X" till operatören.
#      Final-buffer-union utökades med "building" så snabba builds där
#      Phase 1 + Phase 2 hamnar i samma chunk inte typ-fail:ar.
#   C. more-info-dialog.tsx activeTab-state ska nollställas till "about"
#      varje gång dialogen öppnas (Radix unmountar inte tree:t mellan
#      open-toggles när controlled).


def test_handoff_a_prompt_builder_ndjson_parse_is_defensive() -> None:
    """``prompt-builder.tsx`` NDJSON-parsing måste ha inre try/catch
    runt BÅDA ``JSON.parse``-anrop (line-iterator + final-buffer) så
    en korrupt NDJSON-rad inte sprider SyntaxError till operatören.
    """
    path = VIEWSER_DIR / "components" / "prompt-builder.tsx"
    content = path.read_text(encoding="utf-8")
    # Räkna JSON.parse-anrop i samma kontext — båda måste vara inom
    # en try/catch-block som loggar och fortsätter/fallback:ar.
    parse_calls = re.findall(r"JSON\.parse\((line|buffer)\)", content)
    assert len(parse_calls) == 2, (
        f"Förväntade 2 JSON.parse-anrop (line + buffer), hittade {len(parse_calls)}: {parse_calls}"
    )
    # Båda måste föregås av ``try {`` på samma indent (inom while-loopen
    # för line, eller efter ``if (buffer.trim())`` för buffer).
    assert content.count("try {\n            event = JSON.parse(line)") == 1, (
        "JSON.parse(line) måste vara inom inre try-block i NDJSON-loopen"
    )
    assert content.count("try {\n          event = JSON.parse(buffer)") == 1, (
        "JSON.parse(buffer) måste vara inom inre try-block i final-buffern"
    )
    # Final-buffer-union ska inkludera "building" — annars typfail om
    # en snabb build pushar building+done i samma chunk utan terminator.
    final_buffer_section = content[content.index("if (buffer.trim())") :]
    final_buffer_section = final_buffer_section[: final_buffer_section.index("}") + 200]
    assert '"building"' in final_buffer_section, (
        'final-buffer-union måste ha ``stage: "building"`` för att hantera '
        "snabba builds där Phase 1 + done hamnar i samma chunk"
    )


@pytest.mark.tooling
def test_prompt_builder_does_not_replay_stale_stage_on_callback_change() -> None:
    """C5 (scout-fynd 2026-06-05): stage-rapporteringen var gated på
    [stage, onStageChange]. onStageChange byter identitet i page.tsx
    (builderActive ? undefined : setBuildStage), så vid 'Ny sajt' re-kördes
    effekten med ett oförändrat stage (oftast 'success' från init-bygget) och
    skrev över 'idle' som onNewSite precis satt → ViewerPanel visade ett stale
    success-card. Lås att vi bara rapporterar när stage FAKTISKT ändrats sedan
    förra rapporten (ref-vakt).
    """
    text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "lastReportedStageRef" in text, (
        "PromptBuilder måste spåra senast rapporterade stage i en ref (C5)."
    )
    assert "if (lastReportedStageRef.current === stage) return;" in text, (
        "stage-effekten måste bail:a när stage är oförändrat så en ren "
        "callback-identitetsändring inte replayar ett stale stage (C5)."
    )
