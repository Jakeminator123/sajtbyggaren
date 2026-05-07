# Referensmaterial

Den här mappen samlar **externt input** som ligger till grund för Sajtbyggarens governance och arkitektur. Allt här är referens, inte produktkod. Inget kopieras rakt av; det destilleras till policies under `governance/` och dokument under `docs/`.

## Var vad bor

| Mapp | Innehåll | Status |
|------|----------|--------|
| [`utlatanden/`](utlatanden/) | Två externa utlåtanden om "rebuild vs restore" och om LLM-flödet (fas 1-3). Bedömningarna ligger till grund för [`governance/decisions/0004`](../governance/decisions/0004-migration-from-sajtmaskin-baseline.md). | Bevaras tills migrationen från sajtmaskin är klar. |
| [`llm-flode/`](llm-flode/) | Mermaid-diagram över init- och follow-up-flödena, plus eventuella konversationer om hur shadcn passar in. Underlag för [`docs/architecture/llm-flow.md`](../docs/architecture/llm-flow.md). | Bevaras under fas 1-3-implementationen. |
| [`scaffolds-dossiers/`](scaffolds-dossiers/) | Reviewer-konversationer om Scaffold-/Dossier-modellen + ett komplett exempelpaket (zip + tar.gz). Underlag för [`scaffold-contract.v1.json`](../governance/policies/scaffold-contract.v1.json) och [`dossier-contract.v1.json`](../governance/policies/dossier-contract.v1.json). | Bevaras tills fas 2 är implementerad. |
| [`preview-runtime/`](preview-runtime/) | WebContainer-konversation som ligger till grund för [`docs/integrations/webcontainers-notes.md`](../docs/integrations/webcontainers-notes.md). | Bevaras tills `StackBlitzRuntime` är implementerad. |

## Regler för referens-materialet

- **Inget i `referens/` läses av runtime-koden eller backoffice-koden.** Allt här är input för människor och för fram-i-tiden-städning.
- **Termer som dyker upp här måste registreras i [`naming-dictionary.v1.json`](../governance/policies/naming-dictionary.v1.json) innan de används i kod** (se [`term-discipline.md`](../governance/rules/term-discipline.md)). Begrepp som finns här men inte i naming-dictionary är fortfarande inspiration, inte produktterminologi.
- **Skripten under `scripts/` ignorerar `referens/`** för att hålla diagnostik fri från brus. Cursor-sökningen exkluderar också tar.gz/zip-filer härifrån.

## När det är dags att rensa

Mappen kan trimmas i takt med att respektive funktion implementeras:

1. När fas 2 (orchestration) är klar -> arkivera/radera `scaffolds-dossiers/`.
2. När `StackBlitzRuntime` är klar -> arkivera/radera `preview-runtime/`.
3. När fas 1-3 är stabila -> arkivera/radera `llm-flode/` (eller behåll bara mermaid-källkod).
4. Arkivera/radera `utlatanden/` när migrationen är fullt avslutad.

`starter-skiss/` raderades 2026-05-07 - allt innehåll var migrerat till `governance/`.

Inget rensas innan motsvarande funktion är på plats - det här är vårt skyddsnät under bygget.
