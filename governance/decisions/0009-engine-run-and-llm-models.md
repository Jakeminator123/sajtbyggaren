# ADR 0009: Engine Run-artefaktkedja, centraliserad Repair Pipeline och Model Roles

- Status: accepterat
- Datum: 2026-05-07
- Förfinar: [ADR 0001](0001-policies-as-source-of-truth.md), [ADR 0005](0005-scaffold-dossier-model.md), [ADR 0008](0008-defer-evals-until-flow-exists.md)

## Uppdatering (2026-06-15) — Engine Run-beslutet gäller; två stale detaljer

Kärnan i denna ADR — **Engine Run** som artefaktkontrakt, centraliserad Repair
Pipeline + Quality Gate, och Model Roles som enda LLM-ingång — gäller oförändrat.
Två detaljer i texten nedan är dock föråldrade och får inte vilseleda:

- **Preview-raderna är omkörda.** Sprint-tabellens nivå 4/5 (`LocalRuntime`
  placeholder, `StackBlitzRuntime` som secondary) och raden "Långsiktig default i
  policy är fortfarande StackBlitz" speglar en preview-ordning som senare
  kullkastades av ADR 0028 → 0030 → 0033: `vercel-sandbox` är primär användarnära
  preview, `local-next` garanterad fallback, `stackblitz` **pausad**. Läs dem som
  historik, inte som dagens preview-default.
- **"`gpt-5.4` på alla roller" var en tunn v1.** Den enradiga modellmappningen
  nedan var medvetet tunn. Aktuell routing bor i `llm-models.v1.json` (per-roll-
  modeller, v13) + ADR 0052 (per-roll `reasoningEffort`/`maxOutputTokens`). Själva
  principen — "ingen LLM utan registrerad Model Role" — är just det som lät den
  routingen växa utan kodändring.

Detta rör INTE Engine Run-beslutet, artefaktkontraktet eller fas-/boundary-
reglerna. Förfinas av: ADR 0033 (preview-runtime), ADR 0052 (modellparametrar).

## Kontext

Innan implementationen av fas 1-3 påbörjades fanns två risker:

1. **Utspridd fix-kedja.** Sajtmaskin hade reparations-/autofix-logik på tre olika ställen (`validate-and-fix.ts`, `repair-loop.ts`, `partial_file_repair`) plus en separat finalize-pipeline. Det är exakt det som producerade den namnskugga och inkonsekvens vi flytt från.
2. **Saknad LLM-modellmappning.** Policies refererade till abstrakta klasser (`small-llm`, `medium-llm`, `large-llm`) men ingen kod hade en konkret modellnamn att gå på. Risk: provider-/modellkod blandas in i produktlogik.

En andra reviewer pekade på samma sak och föreslog att vi spikar **Engine Run** som artefaktkontrakt innan vi skriver runtime-kod, plus en tunn `llm-models.v1.json`.

## Beslut

Tre nya/uppdaterade kontrakt:

### 1. Engine Run

[`governance/policies/engine-run.v1.json`](../policies/engine-run.v1.json) definierar:

- **Tre faser**: `understand` (Site Brief), `plan` (Site Plan + Generation Package), `build` (Generated Files + Repair + Quality + Build Result).
- **Åtta artefakter** plus en append-only `trace.ndjson` med Engine Events.
- **Mappstruktur**: `data/runs/<runId>/` rymmer hela körningen.
- **Förbud**: ingen Repair-kod utanför `packages/generation/repair/`, ingen Quality Gate-kod utanför `packages/generation/quality-gate/`, ingen LLM-anrop utan registrerad Model Role.

Detta gör att en operatör kan följa exakt vad som händer i en körning genom att läsa en mapp - inte gräva i loggar.

### 2. LLM Models

[`governance/policies/llm-models.v1.json`](../policies/llm-models.v1.json) definierar sju Model Roles:

- `briefModel`, `planningModel`, `rerankModel`, `codegenModel`, `repairModel`, `verifierModel`, `embeddingModel`

**Tunn första version**: `gpt-5.4` på alla generation-roller, `text-embedding-3-small` för embedding. Provider: OpenAI. Att byta är policy-bump, inte kodändring.

Inga gamla tier-namn (`fast`, `pro`, `max`, `codex`, `anthropic`) får återinföras som rolnamn.

### 3. Centraliserad Repair och Quality Gate

[`repo-boundaries.v1.json`](../policies/repo-boundaries.v1.json) (v3) listar nu:

- `packages/generation/engine/` - Engine Run lifecycle och fas-orkestrator
- `packages/generation/brief/` - Fas 1 (Site Brief)
- `packages/generation/planning/` - Fas 2 (Site Plan + Generation Package)
- `packages/generation/build/` - Fas 3 driver (codegen + delegering)
- `packages/generation/repair/` - **enda** Repair Pipeline
- `packages/generation/quality-gate/` - **enda** Quality Gate

Övriga paket (`build`, etc.) får inte implementera repair- eller gate-logik själva. De importerar från de centraliserade paketen.

## Implementationsordning

Reviewerns förslag: **bygg en scaffold först**, inte alla 14.

| Sprint | Mål |
|--------|-----|
| 1 | Mock-driver: `scripts/dev_generate.py` skapar alla artefakter utan riktiga LLM-anrop. Lock på artefaktkontraktet. |
| 2 | Riktig fas 1 + fas 2 mock: briefModel + planningModel kopplade. En scaffold (`local-service-business`) med `scaffold.json`, `routes.json`, `sections.json`, `quality-contract.json`, `compatible-dossiers.json`, `selection-profile.json`, en variant (`premium-local`), två dossiers (`contact-form`, `reviews`). |
| 3 | Riktig fas 3: codegenModel + Repair Pipeline (mekaniska fixes + LLM-fix) + Quality Gate (typecheck + route-scan + policy-compliance + manual score). |
| 4 | LocalRuntime placeholder och iframe-preview. |
| 5 | StackBlitzRuntime som secondary. |
| 6+ | Fler scaffolds och dossiers. Eval-batch på egna körningar. Sajtmaskin-baseline som jämförelse om alls. |

## Konsekvenser

- Mock-driver i Sprint 1 ger oss körbar kedja utan API-kostnad. Alla artefaktnamn och fält låses tidigt.
- En ny Cursor-regel kan läggas till om reparation upptäcks utanför `packages/generation/repair/` (kommer i en framtida iteration; tills dess är `repo-boundaries`-cross-checken vakten).
- Backoffice ska få en "Engine Runs"-vy som listar `data/runs/<runId>/` och låter operatören se varje artefakt + trace.
- Den minsta körbara verticalen är: `dev_generate.py "..."` -> JSON-artefakter på disk. Det är vad Sprint 1 levererar.

## Förhållande till tidigare beslut

- **ADR 0008** (skjut upp baseline-eval) kvarstår: vi bygger motorn först, evals senare.
- **ADR 0005** (Scaffold-/Dossier-modell) kvarstår: Sprint 2 implementerar **en** scaffold enligt det kontraktet.
- **ADR 0003** (PreviewRuntime, StackBlitz först) förfinas: implementationsordningen är **LocalRuntime först** (Sprint 4), StackBlitz som secondary (Sprint 5). Långsiktig default i policy är fortfarande StackBlitz. *(historiskt — se "Uppdatering" överst; preview-defaulten är superseded av ADR 0033: vercel-sandbox primär, stackblitz pausad.)*
