# Migrationsplan från sajtmaskin

Sajtbyggaren ärver inte `Jakeminator123/sajtmaskin@master` rakt av. Vi gör en kontrollerad rekonstruktion. Detta dokument håller listan över vad som plockats från vilken commit och varför. Manual ports loggas i [`docs/migration/import-log.md`](migration/import-log.md).

Beslutet att skjuta upp baseline-eval (tidigare steg 3) tills LLM-flödet finns är dokumenterat i [ADR 0008](../governance/decisions/0008-defer-evals-until-flow-exists.md).

## Arbetsordning (uppdaterad efter ADR 0008 och ADR 0009)

1. **Governance-skelett** (klart)
   - Alla policies under [`governance/policies/`](../governance/policies/) inkl. `engine-run.v1.json` och `llm-models.v1.json`
2. **Backoffice-skelett** (klart): [`backend.py`](../backend.py) + `backoffice/`-modulen
3. **Term-disciplin och regression-tester** (klart): scripts + `tests/` + GitHub Actions
4. **Sprint 1 - Mock Engine Run** (klart): [`scripts/dev_generate.py`](../scripts/dev_generate.py) producerar alla 8 artefakter + `trace.ndjson` utan riktiga LLM-anrop. Låser artefaktkontraktet.
5. **Sprint 2 - Riktig fas 1 + fas 2 + andra scaffolden**: koppla in `briefModel` och `planningModel`. `local-service-business`-scaffolden finns redan med alla obligatoriska filer (`scaffold.json`, `routes.json`, `sections.json`, `quality-contract.json`, `compatible-dossiers.json`, `selection-profile.json`) och en variant (`nordic-trust`). `ecommerce-lite` (variant `clean-store`) tillagd i Sprint 2B med samma sex obligatoriska filer.
   - **Sprint 2A klar (PR #7, `3dbffe4`)**: både `scripts/build_site.py` och `scripts/dev_generate.py` anropar `briefModel` via `OPENAI_API_KEY` när nyckeln finns. Saknad nyckel eller LLM-fel faller tillbaka till Mock Mode och markerar `site-brief.json` med `briefSource` (`real`, `mock-no-key`, `mock-llm-error`) och `modelUsed`. Tester (`tests/test_builder_brief.py`) täcker real/mock-paths och determinism.
   - **ADR 0013 är klar**: artefaktkontrakt låst för `site-brief.json`, `site-plan.json`, `generation-package.json` och `sections.json`. `capability-map.v1.json` registrerar 12 capability-slugs men bara `interactive-game` har en riktig Dossier idag (`interactive-game-loop`). Alla andra slugs är dokumenterade gap som väntar på MIN_IDE-import i Sprint 3.
   - **Sprint 2B klar (planningModel + ecommerce-lite + b19 closure)**: `packages/generation/planning/produce_site_plan` är enda källan för Site Plan + Generation Package. Båda scripten är tunna wrappers ovanpå helpern. `dev_generate.py` lämnar `pinned=None` så helpern kan välja via `planningModel` (real när nyckel finns, mock-no-key/mock-llm-error annars). `build_site.py` skickar `pinned={scaffoldId, variantId}` från Project Input vilket ger `planSource=pinned` och skippar LLM (operatörens val är auktoritativt). Capability-filter ("tom dossier-lista = gap") körs centralt så `selectedDossiers.rejected[]` alltid speglar verkligheten. Builder läser `starterId` från planen istället för att hårdkoda `marketing-base`. **b19 stängd.** `ecommerce-lite` mappar till `marketing-base`-starter via `SCAFFOLD_TO_STARTER`-konstanten tills `data/starters/commerce-base/` är harmoniserad (separat starter-sprint enligt issue-id b20 i `docs/known-issues.md`).
6. **Sprint 3 - Riktig fas 3**: `codegenModel` + Repair Pipeline (mekaniska fixes + ev. LLM-fix) + Quality Gate (typecheck + route-scan + policy-compliance + manual score). **Sprint 3A klar (ADR 0015):** smalaste vertikala slice landad - deterministisk `codegenModel v1` under `packages/generation/codegen/`, Quality Gate med fyra checks (typecheck/route-scan/build-status/policy-compliance) under `packages/generation/quality_gate/`, no-fix-applied Repair Pipeline under `packages/generation/repair/`. Real `codegenModel`-LLM-anrop, mekaniska fixes och LLM-fix kommer i Sprint 3B+. Quality Gate-scoring mot Page Quality Traits kommer i Sprint 3C.
7. **Sprint 4 - LocalRuntime placeholder och iframe-preview**: enklast tänkbara dev-runtime.
8. **Sprint 5 - StackBlitzRuntime** som secondary (delningsbar preview).
9. **Sprint 6+ - Fler scaffolds, dossiers, eval-batch på egna körningar**.
10. **`apps/web`** byggs sist, tunt och konsumerar motorn.
11. **Followup-flöde** när init är `~9.0/10` stabilt.
12. **Sajtmaskin-baseline-eval (om alls)** sist, när Sajtbyggaren har 20-50 egna körningar att stå sig på.

### Dev/operator-milstolpar (parallellspår, inte canonical runtime)

Dessa är prototyp-ytor som hjälper operatören jobba **innan** Sprint 2-5 är
klara. De räknas inte som Sprint-leverabler och förbrukar inte
sprint-numreringen.

- **Builder MVP hardening** (klart, PR #3): `scripts/build_site.py`
  uppfyller phase 3 artefaktkontrakt (generated-files snapshot, repair/quality
  skeletons, `modelUsage`-stub, hård route-guard). Ersätts när Sprint 3 ger
  riktig Repair Pipeline och Quality Gate.
- **Viewser MVP** (klart, PR #4): `apps/viewser/` ger en localhost-only operator-
  prototype för chat + manuell build + preview. Den implementerar **inte**
  Dossier-edit, Project DNA, follow-up, Repair Pipeline eller Quality Gate -
  de hör till Sprint 2-3. Ersätts av riktig Engine Run-yta när Sprint 4-5
  LocalRuntime/StackBlitzRuntime är på plats.
- **Vocabulary compression** (klart, PR #5, ADR 0012): låste operator-flödet
  till åtta steg och tog bort de fyra dossier-typerna som dubblade modellen
  ovanpå Dossier-klasserna. Bara `Dossier` med klass `soft` eller `hard` kvar.
  `painter-palma` är canonical `Project Input`, inte Dossier. Se
  [ADR 0012](../governance/decisions/0012-vocabulary-compression.md) för
  vilka termer som flyttades till `globallyForbidden`.

## Baseline-kandidater (referens, inte mål)

Tre April-taggar är intressanta som **inspiration** under manual port. De portas inte automatiskt.

| Tag/Commit                                    | Datum      | Varför intressant                                                                                     |
| --------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------- |
| `ba33b28` (`baseline-before-design-priority`) | 2026-04-16 | Liten build-fix-commit; "exceptionally good generation quality" innan Design Priority-lagret tillkom. |
| `1f4e869` (`restore-milstolpe-4232ab3`)       | 2026-04    | "Simpler pipeline, richer prompts" - närmast vår målarkitektur.                                       |
| `04b3215` (`milestone-best-version`)          | 2026-04-10 | Tagg "best generation quality so far"; bevisas inte av commit ensamt.                                 |

## Februari-commits (selektivt)

| Commit    | Område                        | Använd för                                         |
| --------- | ----------------------------- | -------------------------------------------------- |
| `3e7ca17` | Builder/auth checkpoint       | Builder-livscykel-mönster (kommer i `apps/`-fasen) |
| `a5b4fb2` | Builder baseline              | Builder-livscykel-mönster                          |
| `29971fb` | Stream UX                     | Streaming-handling i UI (fas 3 codegen)            |
| `9eccc75` | Stream/builder responsiveness | Streaming-handling i UI                            |

## Inte-ta-med-listan

- `master` som-är (för bred yta, för många namnskuggor).
- Februari-snapshot (emergency backup följt av massradering).
- Tier-uppdelad quality gate. Vi har EN gate.
- Termer i [`naming-dictionary.v1.json:globallyForbidden`](../governance/policies/naming-dictionary.v1.json).
- `templates_v0/`, `archive/`, `infra/`-mappar utan klart syfte.
- Glossary/terminologi som dupliceras över `docs/`, `.cursor/rules`, kod.

## Källor till bedömningen

- [`referens/utlatanden/utlatande-1-rebuild-vs-restore.txt`](../referens/utlatanden/utlatande-1-rebuild-vs-restore.txt)
- [`referens/utlatanden/utlatande-2-llm-flode.txt`](../referens/utlatanden/utlatande-2-llm-flode.txt)
- [`referens/scaffolds-dossiers/`](../referens/scaffolds-dossiers/)
- [`referens/preview-runtime/`](../referens/preview-runtime/)
- [`referens/llm-flode/`](../referens/llm-flode/)
- Reviewerns kritik 2026-05-07 om sajtmaskin-arv och evals-ordning, vilken ledde till [ADR 0008](../governance/decisions/0008-defer-evals-until-flow-exists.md).

## Status

| Steg                                                      | Status                                                                                      |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Governance-skelett                                        | klart                                                                                       |
| Backoffice-skelett                                        | klart                                                                                       |
| Regression-tester (governance)                            | klart                                                                                       |
| GitHub Actions (CI)                                       | klart                                                                                       |
| Sprint 1 - Mock Engine Run                                | klart                                                                                       |
| Sprint 2 - Riktig fas 1 + fas 2 + andra scaffolden        | klart: Sprint 2A + Sprint 2B (planningModel + ecommerce-lite + b19 stängd)                  |
| Sprint 3 - Riktig fas 3 (codegen + repair + quality gate) | Sprint 3A klar (ADR 0015): codegen v1 + Quality Gate + no-fix Repair under `packages/generation/{codegen,quality_gate,repair}/`. Sprint 3B (real `codegenModel` + mekaniska fixes) inte startad |
| Sprint 4 - LocalRuntime                                   | inte startad                                                                                |
| Sprint 5 - StackBlitzRuntime                              | inte startad                                                                                |
| Sprint 6+ - Fler scaffolds, dossiers, evals               | inte startad                                                                                |
| `apps/web`                                                | inte startad                                                                                |
| Sajtmaskin-baseline-jämförelse                            | uppskjuten enligt [ADR 0008](../governance/decisions/0008-defer-evals-until-flow-exists.md) |
| Builder MVP hardening (parallellspår)                     | klart                                                                                       |
| Viewser MVP (parallellspår)                               | klart                                                                                       |
| Vocabulary compression (parallellspår, ADR 0012)          | klart                                                                                       |
