# ADR 0016 - Sprint 3B v1: första mekaniska repair-fixen + sandwich-loop

**Status:** accepted
**Datum:** 2026-05-09
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
