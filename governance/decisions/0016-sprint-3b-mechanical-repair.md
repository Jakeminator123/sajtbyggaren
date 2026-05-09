# ADR 0016 - Sprint 3B v1: första mekaniska repair-fixen + sandwich-loop

**Status:** accepted
**Datum:** 2026-05-09
**Senast uppdaterad:** 2026-05-09 (v1.1-tillägg: post-merge audit fixar
bug A/B/D + term-disciplin)
**Beroenden:** ADR 0009 (Engine Run + Model Roles), ADR 0013 (schema-lock),
ADR 0014 (Sprint 2B planning helper), ADR 0015 (Sprint 3A codegen + Quality
Gate + Repair skeleton).

## Kontext

Sprint 3A levererade fas-3-vertikalen som tre paket under
`packages/generation/` men Repair Pipeline returnerade alltid
`status="no-fix-applied"` eftersom registret var tomt. Reviewer-rundan
efter `a71d10c` valde **smal Sprint 3B** framför bred:

- **Smal:** aktivera Repair Pipeline med EN riktig mekanisk fix
  (`ensure-default-export`) plus sandwich-loopen som re-kör Quality
  Gate efter mutation, så `repair-result.json` faktiskt rapporterar
  `status="fixed"` när loopen löste något.
- **Bred (avvisat i denna sprint):** real `codegenModel`-LLM-anrop +
  packages/generation/build/-paketet (B13-stängning) + JSON-schemas
  för quality-/repair-result + flera mekaniska fixar samtidigt.

Den smala vägen följer Sprint 3A-rundans dokumenterade lärdom
("hellre 1 riktig fix än 5 halvdana") och är konsekvent med
`governance/policies/fix-registry.v1.json`, som redan beskriver
sandwich-mönstret + loopLimits.

## Beslut

### 1) Första mekaniska fixen: `ensure-default-export`

Registret pekar på `ensure-default-export` (priority 20, stage
`post-codegen`, `idempotent=true`, `onFailure=abort-pipeline`).
Quality Gate `route-scan` emittar findings i två former:

- `"<route> -> <relpath> (saknas)"` - filen finns inte alls.
- `"<route> -> <relpath> (saknar export default)"` - filen finns,
  saknar `export default`.

`ensure-default-export` adresserar **bara** den andra formen.
Att skapa en route-fil ur intet är `route-recovery` (LLM-fix,
Sprint 5+). Varje fix går genom dispatcher i
`packages/generation/repair/repair.py:_dispatch_mechanical_fixes`
som mappar registry-id till en Python-callable. Sprint 3B v1 har
endast en post; framtida fixar pluggas in genom att lägga till en
`elif spec.fix_id == "..."`-gren plus en motsvarande modul under
`packages/generation/repair/fixes/`.

### 2) Sandwich-loop med hård loop-cap

Loopen följer fix-registry-policyns `loopLimits`:

- `maxMechanicalIterationsPerStage = 2`
- `maxTotalSandwichPasses = 3` (hårdcoded i Python via
  `_MAX_TOTAL_SANDWICH_PASSES`; testet
  `test_max_total_sandwich_passes_matches_registry_loop_limit`
  failar om de driver isär).
- `abortBehavior = "mark-degraded-and-emit-engine-event"`.

Varje pass:

1. Dispatcher kör alla registrerade mekaniska fixar i prioritetsordning.
2. Om minst en fix lyckades AND callern skickade `required_routes`
   plus `npm_steps`: re-kör `run_quality_gate(...)` och uppdatera
   cursor-tillståndet.
3. Loopen breakar tidigt om: ingen fix lyckades (vidare iterationer
   skulle ge samma resultat), `qualityStatusAfter == "ok"`, eller
   capen nås.

`iterations`-fältet räknar **lyckade pass**, inte antal försök. Det
gör operatören kan se "1 sandwich-pass löste degraded → ok" som
`iterations=1` istället för 1 + ett misslyckat pass = 2.

### 3) RepairResult-utökning är icke-breaking

Tre nya optional fält på `RepairResult`:

- `qualityStatusBefore: QualityStatus | None`
- `qualityStatusAfter: QualityStatus | None`
- `iterations: int = 0`

Sprint 3A-konsumenter (`tests/test_repair.py` Sprint 3A-tester) läser
inte de nya fälten och påverkas inte. Schemat under `governance/
schemas/` har inga JSON-schemas för `repair-result.json` ännu (medvetet
valt utanför ADR 0013), så det finns ingen schema-validator att
uppdatera. När JSON-schemas läggs till (Sprint 3C eller senare) ska
de tre nya fälten vara optional med default `null` / `0`.

### 4) Sandwich-orkestreringen lever i `packages/generation/repair/`

Fix-registry-policyn säger att sandwich-mönstret körs på **EN** plats.
Sprint 3B implementerar det i `packages/generation/repair/orchestration.py`
genom helpern `execute_phase3_quality_and_repair(*, target_dir,
required_routes, npm_steps, build_status, do_typecheck) -> tuple
[QualityResult, RepairResult]`.

`scripts/build_site.py:run_phase3_quality_and_repair` blir tunnare
(33 rader, väl under `<60`-gränsen i `tests/test_build_site_size.py`)
och har inga Quality Gate- eller Repair-anrop kvar; den anropar bara
helpern och skriver de två JSON-payloaderna.

Den nya helpern kör Quality Gate **två gånger** i kantfall där
sandwich-loopen ändrade status (initialt + ett extra anrop för att
fånga den fulla `QualityResult`-strukturen, inte bara `status`).
Det är pris vi betalar för att slippa duplicera `QualityResult`-
strukturen inuti `RepairResult` (vilket skulle göra
`repair-result.json` markant större). I happy-path (status oförändrad,
eller `iterations=0`) körs Quality Gate exakt en gång - samma kostnad
som i Sprint 3A.

### 5) `packages.generation.quality_gate` är nu indirekt import i scripts/

Sprint 3A krävde att `scripts/build_site.py` importerade alla tre fas-
3-paketen direkt. Sprint 3B flyttar Quality Gate-användningen till
`packages/generation/repair/orchestration.py`, så scripts/ importerar
bara `packages.generation.codegen` + `packages.generation.repair`.
`tests/test_build_site_size.py:test_build_site_imports_sprint_3a_packages`
uppdateras: kollar `codegen` + `repair` direkt i scripts/, plus att
`repair/orchestration.py` importerar `quality_gate`. Fortsatt
regression-skydd; bara via en proxy.

### 6) `dev_generate.py` rörs inte

Mock-driver-pipelinen kör fortsatt `run_repair_pipeline(quality,
target_dir=files_dir, do_repair=False)` direkt. De nya params har
defaults så signaturen är icke-breaking; `iterations=0` blir resultat
och de nya telemetry-fälten populeras med `qualityStatusBefore` /
`qualityStatusAfter` = ingångs-status.

## Konsekvenser

- `repair-result.json` rapporterar nu `status="fixed"` när routes
  saknar default export och en exportable component-cased symbol
  finns. Tidigare var det alltid `no-fix-applied`.
- `quality-result.json` reflekterar **post-repair** status. Pre-repair
  status finns på `repair-result.json:qualityStatusBefore`. Det är
  konsekvent med `build-result.json:status` (som också är post-repair).
- Sandwich-loopen är hårdt cap:ad till 3 pass; en buggig fix som
  råkar emittera success utan att lösa något stoppas av cap:en, inte
  av en oändlig loop.
- `MECHANICAL_FIXES`-dispatch-tabellen (i `packages/generation/repair/
  fixes/__init__.py`) är auktoritativ register-spegel; tester i
  `tests/test_repair_fixes.py` failar om en fix landar i koden utan
  motsvarande post i `governance/policies/fix-registry.v1.json`.
- B13 är **inte** stängd. `scripts/build_site.py` har fortfarande
  `write_pages` / `mount_dossier_components` / `patch_globals_css` /
  renderers. Sprint 3B förvärrar inte skulden (ny logik landar i
  `packages/generation/`) men stänger den inte heller. Reviewer-
  prompten bad uttryckligen om att inte göra B13-refactor i denna
  sprint.

## Vad detta INTE är

- **Inte real `codegenModel`-LLM-anrop.** Codegen är fortfarande
  deterministisk-v1 från Sprint 3A; LLM lands i Sprint 3B-next eller
  Sprint 3C.
- **Inte LLM-fix.** `llmFixesApplied` är fortsatt tom; LLM-fix-vägen
  är dokumenterad i registret men inte implementerad.
- **Inte ny mekanisk fix utöver `ensure-default-export`.**
  `remove-unused-imports`, `fix-jsx-tag-balance`, etc. finns i
  registret men implementeras senare. Reviewer: "hellre 1 riktig fix
  än 5 halvdana."
- **Inte B13-stängning.** `packages/generation/build/`-paketet skapas
  inte i denna sprint. Sprint 3A ADR 0015 §6 dokumenterar skulden;
  Sprint 3C eller senare stänger den.
- **Inte JSON-schemas för quality-/repair-result.json.** Lämnas till
  Sprint 3C när Page Quality Traits-scoring också ska validas.
- **Inte StackBlitzRuntime, commerce-base, Backoffice-rewrite, eller
  någon hard Dossier-import.**

## Alternativ vi övervägde

1. **Real `codegenModel`-anrop som Sprint 3B-mål 1.**
   Avvisat: en aktiv repair-loop ska sitta innan vi kopplar in en
   LLM som kan hallucinera. Risk-ordning: först sandwich-loopen,
   sedan LLM-codegen.

2. **Lägga in `ensure-default-export` direkt i
   `scripts/build_site.py:assert_routes_present`.**
   Avvisat: bryter B13 och repo-boundaries (scripts/ får inte ha
   produktlogik). Och `assert_routes_present` är just en
   regression-utility, inte en del av canonical-flödet längre
   (Sprint 3A tog bort anropet).

3. **Inkludera `route-recovery` (skapa saknad fil) som mekanisk
   fix.**
   Avvisat: registret klassar det som LLM-fix (priority 15, trigger
   `route-scan-fail-required-page-missing`). Att skapa ny route-fil
   kräver kontextkänslighet (komponent-import, layout-konventioner)
   som en deterministisk regex inte kan ge.

4. **Lägga `qualityResultAfter: QualityResult` på `RepairResult`
   istället för `qualityStatusAfter: QualityStatus`.**
   Avvisat: dubblerar QualityResult-strukturen mellan
   `repair-result.json` och `quality-result.json`, gör payloaden
   stor och bryter "en JSON, en sanning"-principen från
   `engine-run.v1.json`.

5. **Returnera tuple från `run_repair_pipeline` direkt
   `(RepairResult, QualityResult)`.**
   Avvisat: bryter Sprint 3A-API:t som flera tester redan beror på.
   Att lägga `execute_phase3_quality_and_repair` som ny helper är
   icke-breaking.

## Verifiering

Sprint 3B v1 anses levererad när:

- `packages/generation/repair/fixes/ensure_default_export.py` finns
  och producerar deterministiska `RepairFix`-entries.
- `run_repair_pipeline` har sandwich-loopen och returnerar
  `status="fixed"` när loopen löser allt.
- `execute_phase3_quality_and_repair` är wiring-yta för
  `scripts/build_site.py`.
- `tests/test_repair_fixes.py` skyddar fix-implementation +
  loop-semantik + registry-paritet.
- `tests/test_repair.py` Sprint 3A-tester fortsätter passera (på den
  nya Sprint 3B v1-reason, inte längre den gamla Sprint 3A v1-reason).
- `tests/test_build_site_size.py` bekräftar att fas-3-orchestratorn
  är `<60` rader och att Quality Gate fortfarande importeras (om än
  indirekt) av scripts/build_site.py.
- `governance_validate`, `rules_sync --check`,
  `check_term_coverage --strict`, `pytest`, `ruff` är gröna.

## B-IDs

Inga nya bug-IDs öppnas av Sprint 3B. Befintliga bug B13 (produktlogik
i scripts/) och bug B20 (commerce-base oharmoniserad) kvarstår per
`docs/known-issues.md`.

## Sprint 3B v1.1 — post-merge audit fixar

Efter `deb3eca` flaggade en cloud-agent + en arkitekt-reviewer fyra
konkreta riskpunkter. Tre var äkta buggar; en var en
arkitektur-disciplin-rekommendation. Alla fyra åtgärdas i en separat
patch som bygger ovanpå Sprint 3B v1 utan att bryta kontraktet.

### Bug A — `generated-files/` snapshot var pre-repair

`scripts/build_site.py:build()` tog `snapshot_generated_files(target,
run_dir)` *före* `run_phase3_quality_and_repair()`. Konsekvens: när
Repair Pipeline lyckades mutera en fil under `target/` så reflekterade
inte längre `data/runs/<runId>/generated-files/`-snapshot:en (som
`build-result.json:generatedFilesDir` pekar på) den faktiska post-repair-
koden. Operatören skulle kunnat se "Repair status=fixed" men ändå läsa
den ofixade filen i Backoffice.

**Fix:** snapshot flyttas till EFTER `run_phase3_quality_and_repair`-
anropet. Phase ordering blir nu deterministisk:
codegen-emit → QG → Repair (som muterar `target/`) → final QG →
snapshot → write build-result. Källkods-regression i
`tests/test_build_site_size.py:test_build_site_snapshot_runs_after_phase3_quality_and_repair`.

### Bug B — `quality-result.json` kunde visa pre-repair findings

`packages/generation/repair/orchestration.py:execute_phase3_quality_and_repair`
hade villkoret `repair_result.qualityStatusAfter !=
initial_quality.status` för att avgöra om gate skulle re-runas en
final gång. Konsekvens: när en sandwich-pass fixade NÅGRA findings men
aggregat-statusen var oförändrad (degraded → degraded med färre
findings), returnerades `initial_quality` med stale findings-list.
`repair-result.json:remainingErrors` visade rätt subset, men
`quality-result.json:checks[].findings` listade fortfarande det fixade
felet.

**Fix:** villkoret förenklas till bara `iterations > 0`. Kostnad: en
extra route-scan + policy-compliance per fixed run (ms-snabbt; typecheck
är redan skipped eller var det redan, build-status går aldrig att
re-validera utan att köra om npm). Regression-test i
`tests/test_repair_fixes.py:test_execute_phase3_orchestration_reruns_when_findings_reduced_but_status_same`.

### Bug C — npm-build kan inte flippa `failed` → `ok` inom samma run

`packages/generation/quality_gate/checks.py:run_build_status_check` läser
det `build_status` som builderns `run_npm` redan producerade. Sandwich-
loopen kör om Quality Gate efter en mekanisk fix, men `run_npm` kallas
INTE om. Konsekvens: om `next build` failade på "missing default
export" så fixar Sprint 3B v1 filen på disk, men `build-status` förblir
`failed` så `qualityStatusAfter` blir `failed` även om route-scan flippade
till `ok`. Operatören ser `repair-result.status="partial-fix"` istället
för `"fixed"`.

**Beslut:** detta är *inte* en bugg; det är medveten Sprint 3B v1-
limitation. npm install + npm run build är dyra (~10s+) och re-run
risk:erar att introducera nya fel som vår mekaniska fix inte var
designad för. En valbar `--rebuild-after-repair`-flagga (eller `do_npm_rerun=True`-
parameter) reserveras för Sprint 3B-next eller en explicit operator-
opt-in. För Sprint 3B v1 är förståelsen: mekaniska fixes adresserar
*soft failures* (route-scan, policy-compliance). *Blocking failures*
(typecheck, build-status) kvarstår som remainingErrors tills LLM-fix
landar (Sprint 5+ per registry's `targeted-file-repair`).

### Bug E — `MECHANICAL_FIXES`-paritet wording var överdriven

Reviewer-rundan flaggade att kommentar och ADR-text påstod att
`packages/generation/repair/fixes/__init__.py:MECHANICAL_FIXES`
"mirrors" registry-listan. Det är inte sant: registret listar 8
mekaniska fixar men dispatchern kör bara `ensure-default-export`.

**Beslut:** registret är **superset**-spec; `MECHANICAL_FIXES` är
**implementation-subset**. Tester verifierar:

1. Varje entry i `MECHANICAL_FIXES` finns i registret (no rogue fixes).
2. För varje implementerad fix mirror:ar `MechanicalFixSpec`
   registry-entry byte-for-byte (id, stage, priority, idempotent,
   onFailure).
3. `unimplemented_registry_fixes()` returnerar listan av registry-id
   som saknar implementation. Sprint 3B v1.1 har 7 av 8 där.

`packages/generation/repair/fixes/__init__.py:unimplemented_registry_fixes()`
exposeras som offentlig API så Backoffice (när BO2 implementeras) kan
rendera "registry coverage". Ny test:
`test_unimplemented_registry_fixes_lists_pluggable_remainder`.

### Bug F — `onFailure=abort-pipeline` matchade inte implementationen

Reviewer-rundan flaggade att registry-entry för `ensure-default-export`
hade `onFailure=abort-pipeline`, men `apply_ensure_default_export`
returnerar `RepairFix(success=False, ...)` för en fil och fortsätter
med nästa finding. Det är de facto `skip-and-log`, inte
`abort-pipeline`.

**Beslut:** korrigera **registret** (inte implementationen). Strikt
abort-pipeline skulle göra Sprint 3B v1.1's `partial-fix`-väg omöjlig
- en fil med "no exportable symbol" skulle aborta hela körningen
även när andra filer är fixbara. Det är fel beteende när partial-fix
är legitimt utfall.

Konkret: `governance/policies/fix-registry.v1.json` bumps till v3,
`mechanicalFixes[id="ensure-default-export"].onFailure` blir
`skip-and-log`. `MechanicalFixSpec.on_failure` följer. Lock-test:
`test_ensure_default_export_uses_skip_and_log_semantics` plus
`test_ensure_default_export_spec_matches_registry_entry` (befintligt).

### Bug D — `_pick_exportable_symbol` kunde exportera fel komponent

`packages/generation/repair/fixes/ensure_default_export.py:_pick_exportable_symbol`
returnerade FÖRSTA component-cased-symbolen i filen. Konsekvens: en
fil med `function Header() { ... }` deklarerad före `function Page()`
fick `export default Header;` appendad. Route-scan blev grön (default
export finns) men Next-sidan renderar `Header`, inte `Page`.

**Fix:** ny heuristic i tre steg:

1. Om `Page`-symbol finns top-level → returnera `"Page"`. Det är
   Next.js App Router-konvention för route-entry i
   `app/<route>/page.tsx`.
2. Annars om EXAKT EN component-cased-symbol finns → returnera den.
   Täcker single-component-filer (`Hero` ensam, etc.).
3. Annars `None`. Multipla candidates utan `Page` är tvetydiga;
   default-exportering av en godtyckligt vald skulle riskera fel
   komponent. Säkrare att returnera `success=False` och låta
   operatören (eller en framtida LLM-fix) välja.

Tests i `tests/test_repair_fixes.py`: `_prefers_page_symbol_over_others`,
`_uses_only_candidate_when_no_page`,
`_skips_when_no_page_and_multiple_candidates`.

### Term-disciplin — utökad `globallyForbidden`

Arkitekt-reviewer-rundan flaggade att den gamla sajtmaskin-vokabulären
om mode, lane och fidelity inte får sprida sig in i sajtbyggaren.
Canonical fas-kedjan är `engine-run.v1.json:phases` (understand /
plan / build); canonical fix-vokabulär är `Quality Gate`,
`Repair Pipeline`, `PreviewRuntime`, `Mechanical Fix`, `LLM Fix`.
Inga lanes; inga parallella tier-axlar.

`governance/policies/naming-dictionary.v1.json` bumpas (v13 lade till
lane- och fidelity-blocklistorna; v14 cleanup tar bort de generella
tier-bokstäverna ur både `globallyForbidden` och Quality Gate's
`aliasesForbidden` så de inte ens behöver namnges i policy-text — de
specifika legacy-flaggor `F2-only`/`F3-only` som faktiskt fanns i
sajtmaskins kod kvarstår). Tilläggen i `globallyForbidden`:

- `verify lane`, `preview lane`, `verify-lane`, `preview-lane`
- `fidelity`, `fidelity levels`

Lock-test:
`tests/test_naming_consistency.py:test_legacy_lane_and_fidelity_terms_are_globally_forbidden`.

### Vad detta INTE är (utöver vad v1 redan utelämnade)

- **Inte ändring av Sprint 3B v1-kontraktet.** `RepairResult`,
  `QualityResult` och `CodegenResult` är oförändrade. Endast
  implementation-detaljer i orchestration-helpern och
  ensure-default-export-heuristic ändras.
- **Inte återinförande av npm-rerun.** Bug C-beslut: dokumentera, inte
  fixa. Sprint 3B-next eller `--rebuild-after-repair`-flagga handles
  det.
- **Inte ny phase eller ny artefakt.** Phase-ordningen flyttas internt;
  artefakterna är samma som ADR 0015 låste.
- **Inte ny canonical term.** Tvärtom: vi hårdar discipline mot
  parallel-vokabulär.

