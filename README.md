# Sajtbyggaren

Sajtbyggaren bygger hemsidor och appar åt företag på en kvalitet som siktar på `~9.0/10` enligt [`page-quality-traits.v1.json`](governance/policies/page-quality-traits.v1.json).

Projektet är en kontrollerad ombyggnad av [`Jakeminator123/sajtmaskin`](https://github.com/Jakeminator123/sajtmaskin) med strikt governance, tydliga begrepp och en LLM som är **exekutor**, inte arkitekt.

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
Build                              .generated/<siteId>/  +  data/runs/<runId>/
```

`painter-palma` är ett `Project Input`, inte en Dossier. `pacman-game` är en
soft Dossier. `stripe-checkout` är en hard Dossier. Inga andra dossier-typer
(Site/Feature/Integration/Data/Hybrid) finns; de är globally forbidden.

## Tre lager

```text
governance/   - JSON-policies + schemas + rules + decisions (sanningskälla)
backend.py    - Streamlit-backoffice (operatören redigerar governance)
packages/     - Runtime: generation, builder, preview-runtime, policies, shared
apps/         - web/api som konsumerar packages
```

## Snabbstart

```bash
pip install -r requirements.txt

python scripts/governance_validate.py    # validerar policies mot schemas
python scripts/rules_sync.py --check     # verifierar att .cursor/rules är speglad
python scripts/check_term_coverage.py    # hittar nya termer som saknar registrering
python -m pytest tests/                  # pytest-svit för cross-policy-konsistens

streamlit run backend.py                 # backoffice för att se/redigera governance
```

Detaljer om kvalitetsskydden: [`docs/quality.md`](docs/quality.md).

## Dev-skript (PowerShell)

Tre fristående launchers under [`scripts/`](scripts/) som vart och ett bootar en yta. Inga av dem är produktkod - de wrappar bara befintliga kommandon så operatören kan starta delarna utan att memorera flaggor.

```powershell
scripts/dev-backoffice.ps1               # backoffice (Streamlit) på :8501
scripts/dev-builder.ps1                  # bygger painter-palma och startar Next.js på :3000
scripts/dev-builder.ps1 -SkipBuild       # samma men hoppar över npm-build (snabb iteration)
scripts/dev-builder.ps1 -NoServe         # bara builder, ingen dev-server
scripts/dev-viewser.ps1                  # viewser-prototyp på :3000 (kan inte köras parallellt med builder-servern)
```

`dev-builder.ps1` simulerar operatörsflödet: läser ett Project Input, kör hela [`scripts/build_site.py`](scripts/build_site.py)-pipen och öppnar resultatet (inklusive `/spel`-routen från `interactive-game-loop`-dossiern). `dev-viewser.ps1` är den localhost-only operator-prototypen med chat + manuell build-knapp.

## Var vad bor

| Mapp | Roll |
|------|------|
| [`governance/`](governance/) | Policies (JSON), schemas (JSON Schema), rules (mänskliga regler), decisions (ADR). Sanningskälla. |
| [`backend.py`](backend.py) | Streamlit-backoffice för operatören. Inte i användarens runtime. |
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
- [0002](governance/decisions/0002-backoffice-in-python-streamlit.md) - Backoffice som `backend.py` Streamlit, separat från runtime.
- [0003](governance/decisions/0003-preview-runtime-stackblitz-first.md) - PreviewRuntime-abstraktion, StackBlitz först.
- [0004](governance/decisions/0004-migration-from-sajtmaskin-baseline.md) - Migration från sajtmaskin-baseline.
- [0005](governance/decisions/0005-scaffold-dossier-model.md) - Scaffold-/Dossier-modell med embedding-driven selection.
- [0006](governance/decisions/0006-term-discipline.md) - Term-disciplin (deklaration före användning).
- [0007](governance/decisions/0007-language-policy.md) - Språkpolicy.
- [0008](governance/decisions/0008-defer-evals-until-flow-exists.md) - Skjut upp baseline-eval tills LLM-flödet finns.
- [0009](governance/decisions/0009-engine-run-and-llm-models.md) - Engine Run-artefaktkedja + Model Roles + centraliserad Repair Pipeline.

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

Mock-driver kör hela kedjan utan LLM-anrop:

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
| Sprint 2 - Riktig fas 1 + fas 2 + en scaffold | inte startad |
| Sprint 3 - Riktig fas 3 (codegen + repair + gate) | inte startad |
| Sprint 4 - LocalRuntime | inte startad |
| Sprint 5 - StackBlitzRuntime | inte startad |
| Sprint 6+ - Fler scaffolds, dossiers, evals | inte startad |
| `apps/web` | inte startad |
| Sajtmaskin-baseline-jämförelse | uppskjuten ([ADR 0008](governance/decisions/0008-defer-evals-until-flow-exists.md)) |
| Builder MVP hardening (parallellspår) | klart |
| Viewser MVP (parallellspår) | klart |
| Vocabulary compression (parallellspår, [ADR 0012](governance/decisions/0012-vocabulary-compression.md)) | klart |

Detaljer: [`docs/migration-plan.md`](docs/migration-plan.md).

## Bidra

Innan du gör ändringar:

1. Läs [`docs/agent-handbook.md`](docs/agent-handbook.md).
2. Validera att inga nya begrepp används utan att de finns i [`naming-dictionary.v1.json`](governance/policies/naming-dictionary.v1.json).
3. Kör de tre kontrollskripten innan commit.

## Licens

Ingen licens vald än.
