# Sajtbyggaren

Sajtbyggaren bygger företagshemsidor åt småföretagare på en kvalitet som
siktar på `~9.0/10` enligt
[`page-quality-traits.v1.json`](governance/policies/page-quality-traits.v1.json).

Projektet är en kontrollerad ombyggnad av [`Jakeminator123/sajtmaskin`](https://github.com/Jakeminator123/sajtmaskin) med strikt governance, tydliga begrepp och en LLM som är **exekutor**, inte arkitekt.

Produktkompassen för agenter och operatör finns i
[`docs/product-operating-context.md`](docs/product-operating-context.md):
Sajtbyggaren ska vinna genom bättre företagshemsidor för småföretagare, med
kärnflödet `prompt -> företagshemsida -> preview -> följdprompt -> ny version`.

## Aktuellt driftläge

Repo:t har ett fungerande internt operatorflöde för wizard/prompt till
artefakter och deterministiska builder-routes, men är inte launch-ready.
Den inbäddade StackBlitz-previewn i Viewser är fortfarande ett känt
preview-spår: live-körningar kan verifieras via Run Details och
artefakter, men iframen har återkommande visat `Unable to run Embedded
Project`. Det spåret är registrerat i B59/B125 och måste få en beslutad
fallback-väg innan extern kundyta.

Statusraderna längre ned ska därför läsas som intern MVP-/skelettstatus,
inte som att hela produktloopen är färdig för kunder.

## Princip

> Policies styr arkitekturen. Koden härleds. Allt annat är referens.

## Operator-flödet (åtta steg)

Låst i [ADR 0012](governance/decisions/0012-vocabulary-compression.md):

```text
Init Prompt
  ↓
Project Input (Deep Brief)         examples/<siteId>.project-input.json
  ↓
Starter                            data/starters/<starterId>/
  ↓
Scaffold                           packages/generation/orchestration/scaffolds/<scaffoldId>/
  ↓
Variant                            .../scaffolds/<scaffoldId>/variants/<variantId>.json
  ↓
Dossier (soft eller hard)          packages/generation/orchestration/dossiers/<class>/<dossierId>/
  ↓
Generation Package
  ↓
Build                              ../sajtbyggaren-output/.generated/<siteId>/  +  data/runs/<runId>/
```

`painter-palma` är ett `Project Input`, inte en Dossier. `pacman-game` är en
soft Dossier. `stripe-checkout` är en hard Dossier. Inga andra dossier-typer
(Site/Feature/Integration/Data/Hybrid) finns; de är globally forbidden.

## Tre lager

```text
governance/   - JSON-policies + schemas + rules + decisions (sanningskälla)
backoffice.py - Streamlit-backoffice (operatören redigerar governance)
packages/     - Runtime: generation, builder, preview-runtime, policies, shared
apps/         - web/api som konsumerar packages
```

## Snabbstart

Skapa en lokal virtualenv och installera beroenden (rekommenderat - `.venv/` är
gitignorerad och ska aldrig committas):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

På macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Kör validerings- och teskedjan:

```bash
python scripts/governance_validate.py    # validerar policies mot schemas
python scripts/rules_sync.py --check     # verifierar att .cursor/rules är speglad
python scripts/check_term_coverage.py    # hittar nya termer som saknar registrering
python -m pytest tests/                  # pytest-svit för cross-policy-konsistens

streamlit run backoffice.py              # backoffice för att se/redigera governance
```

För att låta fas 1 anropa riktiga `briefModel` istället för mock:

```powershell
$env:OPENAI_API_KEY = "sk-..."
python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build
```

Saknas nyckeln eller failar LLM-anropet skrivs `site-brief.json` med
`briefSource=mock-no-key` respektive `briefSource=mock-llm-error`.

Detaljer om kvalitetsskydden: [`docs/quality.md`](docs/quality.md).

## Dev-skript (PowerShell)

Fristående launchers under [`scripts/`](scripts/) som vart och ett bootar en yta. Inga av dem är produktkod - de wrappar bara befintliga kommandon så operatören kan starta delarna utan att memorera flaggor.

```powershell
scripts/dev-backoffice.ps1               # backoffice (Streamlit) på :8501
scripts/dev-builder.ps1                  # bygger painter-palma och startar Next.js på :3000
scripts/dev-builder.ps1 -SkipBuild       # samma men hoppar över npm-build (snabb iteration)
scripts/dev-builder.ps1 -NoServe         # bara builder, ingen dev-server
scripts/dev-builder.ps1 -Port 3100       # parallell-kör med viewser genom att flytta porten
scripts/dev-builder.ps1 -generateddir C:/temp/.generated  # override av preview-root
scripts/dev-viewser.ps1                  # viewser-prototyp på :3000
scripts/dev-viewser.ps1 -Port 3200       # parallell-kör med builder genom att flytta porten
scripts/clean-runs.ps1                   # rensar gamla data/runs/<runId>/-mappar (default behåller 5 senaste)
scripts/clean-runs.ps1 -Keep 0 -DryRun   # förhandsvisa total rensning
```

`dev-builder.ps1` simulerar operatörsflödet: läser ett Project Input, kör hela [`scripts/build_site.py`](scripts/build_site.py)-pipen och öppnar resultatet (inklusive `/spel`-routen från `interactive-game-loop`-dossiern). `dev-viewser.ps1` är den localhost-only operator-prototypen med PromptBuilder, run history och preview av senaste run; den kan starta ny sajt från fri prompt och fortsätta på befintligt sajtspår med follow-up prompt versions. `dev-builder` och `dev-viewser` försöker båda :3000 om inte `-Port` anges, så vid parallell-körning sätter du en port på en av dem.

Preview-output skrivs som standard till `../sajtbyggaren-output/.generated/<siteId>/` (utanför repo-roten) för att minska file-watcher-load i Cursor. Du kan override:a målet per körning med `--generated-dir` (`build_site.py`) eller PowerShell-flaggan `-generateddir` (`dev-builder.ps1`), eller globalt med env-varn `SAJTBYGGAREN_GENERATED_DIR`.

`clean-runs.ps1` är en bekvämlighetsrensare. Tester skriver inte längre till `data/runs/` (de använder `tmp_path`), men varje `dev-builder.ps1`-körning lägger till en katalog där eftersom runs är canonical historik enligt [`engine-run.v1.json`](governance/policies/engine-run.v1.json).

## Var vad bor

| Mapp | Roll |
|------|------|
| [`governance/`](governance/) | Policies (JSON), schemas (JSON Schema), rules (mänskliga regler), decisions (ADR). Sanningskälla. |
| [`backoffice.py`](backoffice.py) | Streamlit-backoffice för operatören. Inte i användarens runtime. |
| [`scripts/`](scripts/) | Validering, sync, term-coverage. |
| [`packages/`](packages/) | Runtime (kommer fyllas under fas 1-3). |
| [`apps/`](apps/) | Användar-UI (byggs sist). |
| [`tests/`](tests/) | Evals och schemavalidering. |
| [`data/`](data/) | Lokal persistent state (versions/, runs/). |
| [`docs/`](docs/) | Mänsklig dokumentation och arkitektur. |
| [`referens/`](referens/) | Externt input-material. Inte produktkod. Se [`referens/README.md`](referens/README.md). |
| [`.cursor/rules/`](.cursor/rules/) | Cursor-agent-regler (auto-genererade speglar från `governance/rules/`). |

## Språk

- **Kod på engelska** (identifierare, JSON-fältnamn, kommentarer, commits).
- **Operatörens ytor på svenska** (`docs/`, `governance/rules/`, agentens svar, backoffice-UI).
- **Slutanvändarens prompter på vilket språk som helst** - språket sätts i `siteBrief.language`.

Detaljer: [`governance/rules/code-in-english.md`](governance/rules/code-in-english.md), [`always-swedish.md`](governance/rules/always-swedish.md), [ADR 0007](governance/decisions/0007-language-policy.md).

## Arkitekturbeslut

Korta motiveringar i [`governance/decisions/`](governance/decisions/):

- [0001](governance/decisions/0001-policies-as-source-of-truth.md) - Policies som sanningskälla.
- [0002](governance/decisions/0002-backoffice-in-python-streamlit.md) - Backoffice som `backoffice.py` Streamlit, separat från runtime.
- [0003](governance/decisions/0003-preview-runtime-stackblitz-first.md) - PreviewRuntime-abstraktion, StackBlitz först.
- [0004](governance/decisions/0004-migration-from-sajtmaskin-baseline.md) - Migration från sajtmaskin-baseline.
- [0005](governance/decisions/0005-scaffold-dossier-model.md) - Scaffold-/Dossier-modell med embedding-driven selection.
- [0006](governance/decisions/0006-term-discipline.md) - Term-disciplin (deklaration före användning).
- [0007](governance/decisions/0007-language-policy.md) - Språkpolicy.
- [0008](governance/decisions/0008-defer-evals-until-flow-exists.md) - Skjut upp baseline-eval tills LLM-flödet finns.
- [0009](governance/decisions/0009-engine-run-and-llm-models.md) - Engine Run-artefaktkedja + Model Roles + centraliserad Repair Pipeline.
- [0010](governance/decisions/0010-tighten-llm-chain-and-backoffice.md) - Strama åt LLM-kedjan + backoffice.
- [0011](governance/decisions/0011-scaffolds-as-inherited-working-material.md) - Scaffolds som ärvt arbetsmaterial.
- [0012](governance/decisions/0012-vocabulary-compression.md) - Vocabulary compression (Dossier-klasser låsta till soft/hard).
- [0013](governance/decisions/0013-schema-locking-before-sprint-2b.md) - Schema-låsning före Sprint 2B.
- [0014](governance/decisions/0014-sprint-2b-planning-helper.md) - Sprint 2B planning helper (gemensam `produce_site_plan`, planSource pinned, ecommerce-lite scaffold).
- [0015](governance/decisions/0015-sprint-3a-codegen-quality-repair.md) - Sprint 3A: deterministisk `codegenModel v1`, riktiga Quality Gate-checks och no-fix Repair Pipeline under `packages/generation/{codegen,quality_gate,repair}/`.
- [0016](governance/decisions/0016-sprint-3b-mechanical-repair.md) - Sprint 3B: första mekaniska repair-fixen och sandwich-loop.
- [0017](governance/decisions/0017-sprint-3b-next-real-codegen-model.md) - Sprint 3B-next: minimal real `codegenModel` för `marketing-base`.
- [0018](governance/decisions/0018-b20-commerce-base-harmonisering.md) - `commerce-base` som harmoniserad starter.
- [0019](governance/decisions/0019-b20-step-2-mapping-activation.md) - Aktiverar `ecommerce-lite -> commerce-base`.
- [0020](governance/decisions/0020-commerce-base-lucide-react.md) - Lägger `lucide-react` i `commerce-base`.
- [0021](governance/decisions/0021-stackblitz-preview-payload-workarounds.md) - StackBlitz preview-payload-workarounds.
- [0022](governance/decisions/0022-site-brief-company-contact-fields.md) - Site Brief company/contact-fält.
- [0023](governance/decisions/0023-enabled-toggle-for-generation-assets.md) - Enabled-toggle för generationstillgångar.

## Engine Run

En körning är en `runId` med exakt 8 artefakter och en append-only trace. Det här är artefaktkontraktet hela motorn arbetar mot:

```text
data/runs/<runId>/
  input.json
  site-brief.json          (fas 1: Understand)
  site-plan.json           (fas 2: Plan)
  generation-package.json  (fas 2: Plan)
  generated-files/         (fas 3: Build)
  repair-result.json       (fas 3: Build)
  quality-result.json      (fas 3: Build)
  build-result.json        (fas 3: Build)
  trace.ndjson             (Engine Events, append-only)
```

Dev-drivern kör hela kedjan från prompt till artefakter.
- Fas 1 (Understand): anropar `briefModel` när `OPENAI_API_KEY` finns, annars mock.
- Fas 2 (Plan): anropar `planningModel` via den gemensamma helpern
  `packages/generation/planning/produce_site_plan` när `OPENAI_API_KEY` finns,
  annars mock fallback (`mock-no-key`/`mock-llm-error`).
- Fas 3 (Build): Sprint 3A landade deterministisk `codegenModel v1`-manifest
  (`packages/generation/codegen/`), riktiga Quality Gate-checks
  (typecheck/route-scan/build-status/policy-compliance via
  `packages/generation/quality_gate/`). Sprint 3B lade första mekaniska
  repair-fixen (`ensure-default-export`) och sandwich-loopen i
  `packages/generation/repair/`. Sprint 3B-next lade ett smalt real
  `codegenModel`-anrop för `marketing-base`; filerna produceras fortfarande
  deterministiskt och LLM:en får bara skriva rationale/risk-notes.

```bash
python scripts/dev_generate.py "Skapa hemsida för elektriker i Malmö"
python scripts/dev_generate.py "..." --phase brief    # bara fas 1
python scripts/dev_generate.py "..." --phase plan     # läs brief, kör fas 2
python scripts/dev_generate.py "..." --phase build    # läs package, kör fas 3
```

Detaljer: [`engine-run.v1.json`](governance/policies/engine-run.v1.json), [ADR 0009](governance/decisions/0009-engine-run-and-llm-models.md).

## Status

| Steg | Status |
|------|--------|
| Governance-skelett | klart |
| Backoffice-skelett | klart |
| Term-disciplin (regel + script) | klart |
| Regression-tester och CI | klart |
| Sprint 1 - Mock Engine Run | klart |
| Sprint 2 - Riktig fas 1 + fas 2 + andra scaffolden | klart: Sprint 2A + Sprint 2B (`briefModel` + `planningModel` kopplade via gemensamma helpers, `ecommerce-lite` tillagd, B19 stängd) |
| Sprint 3 - Riktig fas 3 (codegen + repair + gate) | Sprint 3A + 3B + 3B-next klara: codegen-manifest, Quality Gate, första mekaniska repair-fixen och minimal real `codegenModel` för `marketing-base`. Kvar i senare sprint: bredare file-emission, fler repair-fixar, modelUsage-aggregering och B13a-flytten |
| Sprint 4 - LocalRuntime | inte startad |
| Sprint 5 - StackBlitzRuntime | inte startad |
| Sprint 6+ - Fler scaffolds, dossiers, evals | inte startad |
| `apps/web` | inte startad |
| Sajtmaskin-baseline-jämförelse | uppskjuten ([ADR 0008](governance/decisions/0008-defer-evals-until-flow-exists.md)) |
| Builder MVP hardening (parallellspår) | internt klart; produktgap finns kvar i preview/follow-up-kö |
| Viewser MVP (parallellspår) | intern operator-MVP; embedded preview är inte launch-ready förrän B59/B125-fallback är vald |
| Vocabulary compression (parallellspår, [ADR 0012](governance/decisions/0012-vocabulary-compression.md)) | klart |

Detaljer: [`docs/migration-plan.md`](docs/migration-plan.md).

## Browser-stöd för preview-läge

Sluttkundens preview-yta i Viewser bygger på StackBlitz embedded WebContainers. Det är ett medvetet val (kompute körs i kundens egen browser, du betalar inget per aktiv kund — viktigt för skalning till hundratals samtidiga kunder utan server-side container-park), men det har en tydlig browser-begränsning som ska in här innan någon bygger vidare på preview-flödet:

| Browser | Embedded WebContainer-preview | Slutpublicerade kund-sajter |
|---------|-------------------------------|-----------------------------|
| Chrome / Edge / Brave / Vivaldi | **Stöds fullt ut** (Chrome 110+ för iframe-credentialless) | Stöds |
| Safari (iOS + macOS) | **Stöds inte officiellt** — embed laddar inte | Stöds (vanlig Next.js) |
| Firefox | **Stöds inte officiellt** — embed laddar inte | Stöds (vanlig Next.js) |

Det är specifikt **embedded**-WebContainers som är Chromium-only. På `stackblitz.com` direkt har Safari/Firefox beta-stöd, men inte när StackBlitz-projektet är embedded i en annan sajt (vilket är vad Viewser gör). Skälet: WebContainer kräver `SharedArrayBuffer`, vilket kräver cross-origin isolation, vilket för embedded iframe kräver ett `credentialless`-attribut som bara är implementerat i Chromium. Tekniska detaljer i [`docs/integrations/webcontainers-notes.md`](docs/integrations/webcontainers-notes.md).

**Konsekvens för slutkunder:** ~25-35% av svenska SMB-kunder är på Safari (inkl. iPhone) eller Firefox och kommer inte se preview-fliken funktionsdugligt utan en server-byggd fallback. Den fallback-vägen är registrerad som öppen bugg B125 i [`docs/known-issues.md`](docs/known-issues.md) och måste byggas innan produktlansering. Slutpublicerade sajter (det kunden faktiskt levererar till sina egna besökare) är vanlig Next.js och funkar i alla browsers oavsett.

**Konsekvens för operatörsflöde och utveckling:** kör Viewser-prototypen i Chrome/Edge/Brave. Allt annat (backoffice, builder-CLI, tester) är vanlig Python/Streamlit och funkar överallt.

Bakgrund + arkitekturalternativ för fallback (server-byggd preview-URL, Vercel preview deployment, lokal `next dev`-process per kund, "Öppna i StackBlitz"-fallback för icke-Chromium): läs B59 + B125 i `docs/known-issues.md`. Beslutet om vilken fallback-väg som väljs ska resultera i en ny ADR innan implementation.

## Bidra

Innan du gör ändringar:

1. Läs [`docs/agent-handbook.md`](docs/agent-handbook.md).
2. Validera att inga nya begrepp används utan att de finns i [`naming-dictionary.v1.json`](governance/policies/naming-dictionary.v1.json).
3. Kör de tre kontrollskripten innan commit.

## Licens

Ingen licens vald än.
