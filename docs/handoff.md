# Handoff – Sajtbyggaren

**Datum:** 2026-05-09
**Aktuell HEAD:** kör `git log --oneline -1` för verifierad SHA. Senaste milstolpe: post-3C-lite-audit-2 + Builder UX MVP (B38 + B39 + RunDetailsPanel). Föregående baseline var `6b8c45e` (Sprint 3C-lite + audit-fix).
**Aktiv branch:** `main` (per `governance/rules/branch-discipline.md` är direkt commit + push mot `origin/main` standardflödet — PR används bara när operatören uttryckligen ber om det).

Detta är en operatörsfri översikt så att en ny agent kan ta över på 5 minuter utan att läsa hela transkriptet.

## Vad är Sajtbyggaren

En policy-driven hemsidegenerator som ersätter `Jakeminator123/sajtmaskin`. Mål: 9/10 kvalitet, ingen plattformsinlåsning, governance som sanningskälla.

Tre lager:

- **`governance/`** – JSON-policies + JSON-Schemas + ADR. Sanningskällan.
- **`backoffice/` + `backend.py`** – Streamlit-administration (inte runtime).
- **`packages/` + `apps/`** – framtida runtime + kund-UI (`apps/` är tom utöver `apps/viewser/`-prototypen).

## Vad funkar idag (post-Sprint 3C-lite, `6b8c45e`)

### Governance + guards

- ADR 0001–0017 + 15 policies + matchande schemas under `governance/schemas/` (inkl. nya `project-input.schema.json`, `quality-result.schema.json`, `repair-result.schema.json` från Sprint 3C-lite).
- 5 automatiska checks: `governance_validate.py`, `rules_sync.py --check`, `check_term_coverage.py --strict`, `pytest`, `ruff check .`. GitHub Actions kör alla på push/PR. `tests/test_docs_freshness.py` är en sjätte mjuk guard mot doc-drift.
- **352 tester passerar**, 3 skipped (env-gated: `SAJTBYGGAREN_VERIFY_BUILD`, `SAJTBYGGAREN_E2E briefModel`, `SAJTBYGGAREN_E2E codegenModel`). 0 ruff findings.

### Phase 1 + 2 (Sprint 2A + 2B)

- `briefModel` (gpt-5.4) via OpenAI structured output när `OPENAI_API_KEY` finns; mock-fallback annars. `briefSource`: `real` / `mock-no-key` / `mock-llm-error`.
- `planningModel` via shared `packages.generation.planning.produce_site_plan`. Båda `scripts/build_site.py` och `scripts/dev_generate.py` använder samma helper (B19 stängd). Builder skickar `pinned={scaffoldId, variantId}` från Project Input; dev_generate kör utan pinning.

### Phase 3 — Sprint 3A → 3C-lite

| Sprint | Vad landade |
|---|---|
| 3A (ADR 0015) | Tre paket under `packages/generation/`: `codegen/`, `quality_gate/`, `repair/`. Real Quality Gate-checks (typecheck, route-scan, build-status, policy-compliance). Deterministisk codegenModel-manifest. No-fix-applied Repair Pipeline. |
| 3B v1 (ADR 0016) | Första mekaniska fix (`ensure-default-export`) + sandwich-loop som re-kör Quality Gate efter mutation. `_MAX_TOTAL_SANDWICH_PASSES=3` matchar fix-registry. |
| 3B v1.1 audit | Bug A (snapshot post-repair), Bug B (orchestration final-QG), Bug D (`Page`-prefer heuristic), term-disciplin (mode/tier-vokabulär blockad). |
| Post-3B audit (B29-B32) | Project Input schema sync, JSX-escape via `_jsx_safe_string`, extern dossier-path, npm timeout-stderr. |
| B30 follow-up | `render_layout` JSX-escape (var missad i första rundan). |
| 3B-next (ADR 0017) | Real codegenModel via `OPENAI_API_KEY` + structured `CodegenLLMResponse` (rationale + 0-3 riskNotes). Files-listan stannar deterministisk för att skydda mot LLM-hallucinationer. Truth-fields: `real` / `mock-llm-error` / `mock-no-key` / `deterministic-v1`. |
| 3C-lite (ADR 0017 §) | JSON-schemas för `quality-result.json` + `repair-result.json` + drift-guards (top-level + nested `$defs`). `modelUsage.byRole` med tre canonical LLM-roller (briefModel/planningModel som null tills de spårar usage; codegenModel populerad på `source="real"`). Page Quality Traits dokumenterad som Sprint 3C-full-arbete. |
| Post-3C-lite audit (B33-B36) | dev_generate emitterar samma `modelUsage`-shape som builder via shared `compose_model_usage` helper. Nested drift-guard. Doc-fix om partial run-dir. Schema-description filename. |
| Post-3C-lite audit-2 (B38, B39) | `dev_generate.py:run_phase_build` läser `briefSource` från Phase 1 site-brief så `modelUsage.source` återger verklig pipeline-källa istället för hårdkodat `mock-no-key`. Doc-drift i `handoff.md` (CLI-flaggor per script) + `known-issues.md` (line-ref till `build_site.py:1523`). Tre nya regression-tester (parametriserade real / mock-no-key / mock-llm-error + fallback-default). |
| Builder UX MVP | Operator-prototypen `apps/viewser/` får en `<RunDetailsPanel>` med fem pedagogiska sektioner (Build / Quality / Repair / Codegen / Models) som läser från ny endpoint `/api/runs/[runId]/artifacts`. UI defensivt mot saknade fält i äldre runs ("saknas i äldre run" / "ej spårad än" / "unknown"). `<RunHistory>` får status-färgning, `<ChatPanel>` får `BuildStatusIndicator` + experimentell prompt-märkning, `<ViewerPanel>` får pedagogisk fallback för dev_generate-mock-runs. PreviewRuntime / StackBlitzRuntime / FlyRuntime är fortsatt parkerat som Sprint 4-5. |

### Phase 3 ordering (canonical)

```text
1. Copy starter -> target/
2. Patch starter (package.json, layout.tsx, globals.css)
3. Mount Dossier components
4. Write pages (target/app/<route>/page.tsx)
5. npm install + npm run build  (skipped via --skip-build)
6. codegen.manifest.emitted     (real LLM via codegenModel om OPENAI_API_KEY + marketing-base)
7. Quality Gate (initial)       (4 checks)
8. Repair Pipeline              (sandwich loop, kan mutera target/)
9. Quality Gate (final)         (re-run om iterations > 0)
10. Snapshot generated-files/   (POST-repair)
11. write build-result.json     (status, codegen, modelUsage.byRole)
```

Validatorerna i steg 7-9 skyddar de specifika artefakterna från att skrivas malformade — partial run-dir kan finnas på disk vid sent schemafel (Phase 1+2 redan skrivna). Operatörer som vill ha all-or-nothing rensar manuellt.

### Skiriptyta

- `scripts/build_site.py`: deterministisk Builder MVP. Skriver alla canonical artefakter inkl. `generated-files/`-snapshot. Tunn wiring runt `packages/generation/`-paketen (B13 är inte stängd men tre nya paket växte under den).
- `scripts/dev_generate.py`: mock-pipeline för regression. Skriver alla 8 artefakter + `trace.ndjson`. Sedan post-3C-lite-audit emitterar samma `modelUsage`-shape som builder, och `modelUsage.source` följer faktisk `briefSource` istället för att vara hårdkodad (B38).
- CLI-flaggor skiljer sig mellan scripten: `scripts/build_site.py` har `--skip-build` + `--runs-dir`; `scripts/dev_generate.py` har `--phase {brief,plan,build,all}` + `--data-runs-dir`. Ingen av flaggorna är delade.

### Backoffice + Viewser

- Backoffice (`streamlit run backend.py`) visar Status, Governance, LLM Engine, Building Blocks, Engine Runs, Evals, Playground.
- `apps/viewser/` är operator-prototyp (localhost-only) per ADR 0003 + repo-boundaries v8.

### Scaffolds + Dossiers

- Två scaffolds har innehåll: `local-service-business` (variant `nordic-trust`) och `ecommerce-lite` (variant `clean-store`, mappar till `commerce-base` via `SCAFFOLD_TO_STARTER`).
- En Dossier är implementerad: `interactive-game-loop` (soft).

## Vad är mock än så länge

- **Real `codegenModel`**: aktiv på `marketing-base` med `OPENAI_API_KEY`, men ger bara `rationale + riskNotes` — files-listan är fortfarande deterministisk. Sprint 3C-full eller separat sprint vidgar LLM till file-emission när drift-fångst är beprövad.
- **LLM-fix**: `llmFixesApplied` är alltid tom. Sprint 5+ wirar in `targeted-file-repair` / `route-recovery` / etc. per `fix-registry.v1.json:llmFixes`.
- Page-quality-traits-scoring: `governance/policies/page-quality-traits.v1.json` finns som spec men ingen QG-check gör scoring än. Sprint 3C-full-arbete; doc-only flagga i `docs/architecture/builder-mvp.md`.
- **brief/planning usage tracking**: `briefModel` och `planningModel` returnerar inte token-counts. `modelUsage.byRole.briefModel` / `planningModel` är null tills resolvers utvidgas. `compose_model_usage` är klar att ta emot dem.
- **modelUsage cost-aggregation**: `totalCostUsd` är alltid 0.0 — kräver per-model price-table policy.
- **Preview Runtime**: `apps/viewser/` är operator-prototyp; canonical `PreviewRuntime` (`StackBlitzRuntime` / `LocalRuntime` / `FlyRuntime`) är Sprint 4-5.
- `data/starters/commerce-base/` harmoniserad från `vercel/commerce` och bygger utan Shopify-env (B20 stängd).
- 11 av 14 scaffolds är gitkeep-mappar utan content.
- `apps/web/` finns inte alls.

## För nästa agent: efter Builder UX MVP

Builder UX MVP är levererad i denna runda: operator-flödet **Project Input → Build → Run skapas → Run-lista → Preview → Artefaktpaneler** fungerar end-to-end. Naturliga nästa spår är:

1. **PreviewRuntime / StackBlitzRuntime / LocalRuntime / FlyRuntime** (Sprint 4-5). Befintlig StackBlitz-embed i `viewer-panel.tsx` är dev-prototyp, inte canonical runtime.
2. **Backoffice trace-vy (BO2)** — `data/runs/<runId>/trace.ndjson` borde grupperas per fas och färgas efter status; bra parallellt UX-spår.
3. B13 — produktlogik flyttas ut ur `scripts/build_site.py` när LLM file-emission widens i Sprint 3C-full.
4. **Page Quality Traits-scoring** (Sprint 3C-full) — femte Quality Gate-check enligt `governance/policies/page-quality-traits.v1.json`.
5. **Brief / planning usage tracking** — utvidga resolvers så `modelUsage.byRole.briefModel` / `planningModel` flippar från null till usage-dict.

### Säkra utgångspunkter

- `data/runs/<runId>/build-result.json` har **partiell shape-parity** mellan `scripts/build_site.py` och `scripts/dev_generate.py`. Båda emitterar `runId`, `status`, `codegen` (källa + rationale + riskNotes + usage) och `modelUsage.byRole` med tre canonical LLM-roller (post-Sprint 3C-lite + B38). Builder skriver dessutom `siteId`, `routes`, `npmSteps`, `generatedFilesDir`, `devPreviewDir`, `briefSource` på top-level — dev_generate-mocken gör inte det. `<RunDetailsPanel>` är skriven defensivt mot detta: top-level-fält som saknas renderas som "saknas i äldre run" / "saknas (dev_generate-pipeline kör inte npm)" istället för krascher.
- `data/runs/<runId>/quality-result.json` + `repair-result.json` är schema-låsta (`governance/schemas/{quality,repair}-result.schema.json`) med drift-guards mot Pydantic-modellen på top-level + nested `$defs`.
- `data/runs/<runId>/trace.ndjson` är append-only Engine Events; har `engine.run.started` / `understand.*` / `plan.*` / `build.*` / `phase.completed` events.
- `examples/<siteId>.project-input.json` är schema-låst (`governance/schemas/project-input.schema.json` v1).
- `apps/viewser/app/api/runs/[runId]/artifacts/route.ts` returnerar de fyra canonical Engine Run-artefakterna i ett anrop: `{runId, buildResult, qualityResult, repairResult, siteBrief, missingArtefacts}`. Saknade filer surfaceas via `missingArtefacts[]`-listan så framtida UI-arbete inte behöver särfall-koda enskilda 404:or.

### Out-of-scope för Builder UX MVP (per reviewer + ADR)

- Ingen LLM file-emission (Sprint 3C-full eller senare)
- Ingen StackBlitz / FlyRuntime (Sprint 4-5)
- Ingen ny Dossier-import (separat starter-harmoniserings-spår)
- Ingen ny scaffold (de 11 gitkeep-mapparna får vänta)
- Ingen B13-storrefactor (`scripts/build_site.py` produktlogik kvar)
- Ingen ny Quality Gate-check (Page Quality Traits är 3C-full)
- Inga nya canonical termer utan ADR (term-disciplin per `governance/rules/no-duplicate-terms.md`)

### Filer att läsa först

- `AGENTS.md` (top-level rules + venv-setup)
- `docs/glossary.md`
- `governance/policies/naming-dictionary.v1.json` (kanonisk vokabulär)
- `governance/policies/engine-run.v1.json` (artefaktkedjan)
- `governance/policies/repo-boundaries.v1.json` v9 (vad får importera vad)
- `governance/decisions/0015` (Sprint 3A), `0016` (Sprint 3B), `0017` (Sprint 3B-next + 3C-lite)
- `docs/architecture/builder-mvp.md` (Phase 3 ordering, Quality Gate / Repair Pipeline tabeller, modelUsage byRole-kontrakt)
- `docs/known-issues.md` (öppna + stängda B-IDs)

### Kvarvarande risker (icke-blockerande)

| ID | Allvar | Beskrivning |
|---|---|---|
| B13 | Låg | Produktlogik i `scripts/build_site.py` (write_pages / mount_dossier_components / patch_globals_css). Stängs naturligt när LLM file-emission widens. |
| B20 | Låg | Stängd: `commerce-base` är harmoniserad och `ecommerce-lite` mappar dit. |
| BO2 | Medel | Backoffice trace-vy är rå dataframe. Bra parallellt UX-spår. |
| BO4 | Medel | `backoffice/views/playground.py` 180s blocking subprocess. Async-cancellation behövs. |

## Beslutsläge för arkitektur-frågor

| Förslag | Status | Referens |
|---|---|---|
| 6-stegs-flow ersätter 3-fas | avvisat — canonical: `understand → plan → build` | `engine-run.v1.json`, ADR 0009 |
| 4 dossier-typer (`site/feature/integration/data`) | avvisat — endast `soft` och `hard` | ADR 0012, naming-dictionary v14 |
| 5 starters istället för 14 | accepterat som plan — bara `marketing-base` har content idag | README "Starter"-listan |
| Scaffolds som ärvt arbetsmaterial | accepterat | ADR 0011 |
| Tier-uppdelning av Quality Gate | avvisat (post-3B v1.1) — EN gate; den gamla sajtmaskin-vokabulären om mode/tier-axlar blockad i `globallyForbidden` | ADR 0016, naming-dictionary v14 |
| `codegenModel` som file-writer | skjutet till Sprint 3C-full eller senare — Sprint 3B-next har LLM som metadata-emitter; files är deterministisk | ADR 0017 |

## Köra och testa

```powershell
# Lokal venv (rekommenderat - .venv/ är gitignorerad)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Backoffice
streamlit run backend.py

# Engine Run i mock-pipeline (anropar briefModel om OPENAI_API_KEY finns)
python scripts/dev_generate.py "Skapa hemsida för en elektriker i Malmö"

# Builder MVP - genererar riktig Next.js-sajt
python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build

# Med riktig brief + planning + codegen
$env:OPENAI_API_KEY = "sk-..."
python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build

# Alla 5 guards
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python -m ruff check .
python -m pytest tests/ -q
```

## Commit-krav

- Aldrig commit utan att alla 5 guards passerar
- Standardflöde: commit + push direkt mot `origin/main`. PR används bara när operatören explicit ber om det. Detaljer i `governance/rules/branch-discipline.md`.
- Multi-line commit-meddelanden på Windows/PowerShell: skriv till `$env:TEMP\sb-commit-msg.txt`, aldrig till `.commit-msg.tmp` i repo-roten (PowerShell saknar bash-heredoc).
- Commit-meddelanden på engelska, dokumentation på svenska
- ÅÄÖ ska skrivas korrekt – aldrig `\u00f6` eller ASCII-translit

## Stil i kommunikation

- Kod, identifierare, commits, branchnamn: **engelska**
- Operatörs-UI, dokumentation, ADR, agent-svar: **svenska**
- Slutanvändar-prompter och genererade sajter: **språkagnostiska** (detekteras av `briefModel`)
