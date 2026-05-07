# ADR 0010: Tajta LLM-kedjan, introducera Project DNA, lyfta Embedding och Fix Registry

- Status: accepterat
- Datum: 2026-05-07
- Förfinar: [ADR 0001](0001-policies-as-source-of-truth.md), [ADR 0005](0005-scaffold-dossier-model.md), [ADR 0009](0009-engine-run-and-llm-models.md)

## Kontext

Sex policies styrde redan stora delar av LLM-kedjan, men:

1. Begreppen var inte explicit grupperade i de tre faserna (`understand`/`plan`/`build`).
2. Init- och Follow-up-flöden var inte separerade i kontraktet. Risk att follow-up oavsiktligt byter `Scaffold` eller `Variant` när användaren bara vill ändra text.
3. Embeddings nämndes som mekanism i `scaffold-selection` och `dossier-selection` men hade ingen central policy. Inget gemensamt kontrakt för domäner, ägarpath eller modellroll.
4. Fix-typer (mekaniska och LLM) fanns nämnda i `engine-run.v1.json:phases.mechanical_autofix/llm_repair` men ingen registry-fil. Risk för att fix-logik landar utspritt igen, precis som i sajtmaskin.

## Beslut

### Project DNA (tunn introduktion)

Ny [`project-dna.v1.json`](../policies/project-dna.v1.json) definierar Project DNA som persistent state per projekt. Init-mode skapar DNA, follow-up läser DNA, redesign-intent triggar Project Fork. `scaffoldId` är hårt låst, `variantId` mjukt låst, dossiers/routes kan utökas vid section-/page-add. Sju FollowUp Intent-typer låser exakt vad varje intent får ändra.

Termerna `Project DNA`, `Project Fork`, `FollowUp Intent`, `Scaffold Lock`, `Variant Lock`, `Engine Run mode` registrerade i `naming-dictionary.v1` v4. Runtime-implementation kommer i kommande sprint.

### Engine Run mode

[`engine-run.v1.json`](../policies/engine-run.v1.json) v2 har nu fältet `modes` med `init` och `followup`. `input.json` skriver `mode` och optional `projectId`.

### phaseBlocks i llm-flow-concepts

[`llm-flow-concepts.v1.json`](../policies/llm-flow-concepts.v1.json) v2 har nu `phaseBlocks` som mappar de 12 phases till tre block (`understand`/`plan`/`build`). Detta gör backoffice-vyer enkla att bygga utan att duplicera kunskap.

### Embedding Policy

Ny [`embedding-policy.v1.json`](../policies/embedding-policy.v1.json) definierar fem `Embedding Domains`: `scaffolds`, `dossiers`, `reference-templates`, `section-patterns`, `style-signatures`. Lägger fast principerna `always-prefer-embedding-over-regex`, `word-matching-as-weak-signal-only`, `selection-trace-required`, `one-index-per-domain`, `embedding-text-is-curated`.

`scaffold-selection.v1` och `dossier-selection.v1` har fått fältet `prefersEmbedding: true` så det är explicit i schema-validering.

### Fix Registry

Ny [`fix-registry.v1.json`](../policies/fix-registry.v1.json) listar exakt vilka Mechanical Fixes och LLM Fixes som finns. `Repair Pipeline` läser hit. Inga fixar får implementeras utanför registry. Sandwich-mönster (mekanisk → LLM → mekanisk → validate) körs på exakt en plats: `packages/generation/repair/`.

Termerna `Mechanical Fix`, `LLM Fix` och `Fix Registry` registrerade i naming-dictionary v4.

### Shared Model Groups

[`llm-models.v1.json`](../policies/llm-models.v1.json) v2 har `sharedModelGroups` som gör delning explicit: 7 roller, 3 grupper (`smallReasoning`, `heavyCodegen`, `embedding`), en modell per grupp idag. Att skala upp är att byta modell per grupp, inte per roll.

### repo-boundaries v4

[`repo-boundaries.v1.json`](../policies/repo-boundaries.v1.json) lägger till `data/projects/` som ägarpath för Project DNA-state.

## Konsekvenser

- 14 policies validerade mot scheman (var 11).
- Cross-policy-tester som låser nya kontrakten (8 nya tester).
- Backoffice kan i kommande sprint bygga vyer som läser direkt från policies utan att duplicera kunskap.
- ProjectDNA-runtime kan implementeras stegvis utan att ändra naming eller låsregler.
- Repair Pipeline har en konkret lista att implementera fixar mot, en i taget.

## Vad detta inte är

- Ingen runtime-implementation. ProjectDNA läses inte än, fixes appliceras inte än, embeddings byggs inte än. Endast kontrakt.
- Ingen ändring av `package.json`/Node-deps. Allt detta är JSON + Python-tester.
- Ingen rörelse på `apps/` eller `packages/`-koden. Det kommer i Sprint B (backoffice) och Sprint C (riktig briefModel).
