# Sajtbyggaren

Sajtbyggaren bygger hemsidor och appar åt företag på en kvalitet som siktar på `~9.0/10` enligt [`page-quality-traits.v1.json`](governance/policies/page-quality-traits.v1.json).

Projektet är en kontrollerad ombyggnad av [`Jakeminator123/sajtmaskin`](https://github.com/Jakeminator123/sajtmaskin) med strikt governance, tydliga begrepp och en LLM som är **exekutor**, inte arkitekt.

## Princip

> Policies styr arkitekturen. Koden härleds. Allt annat är referens.

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

## Status

| Steg | Status |
|------|--------|
| Governance-skelett | klart |
| Backoffice-skelett | klart |
| Term-disciplin (regel + script) | klart |
| Baseline-eval mot sajtmaskin-taggar | inte startad |
| Fas 1 runtime (Site Brief) | inte startad |
| Fas 2 runtime (Orchestration) | inte startad |
| Fas 3 runtime (Codegen + Quality Gate) | inte startad |
| StackBlitzRuntime | inte startad |
| `apps/web` | inte startad |

Detaljer: [`docs/migration-plan.md`](docs/migration-plan.md).

## Bidra

Innan du gör ändringar:

1. Läs [`docs/agent-handbook.md`](docs/agent-handbook.md).
2. Validera att inga nya begrepp används utan att de finns i [`naming-dictionary.v1.json`](governance/policies/naming-dictionary.v1.json).
3. Kör de tre kontrollskripten innan commit.

## Licens

Ingen licens vald än.
