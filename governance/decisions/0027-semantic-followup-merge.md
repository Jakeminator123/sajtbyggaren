# ADR 0027 — semantic follow-up merge i Project DNA V1

**Status:** Accepted
**Datum:** 2026-05-22
**Beroenden:** ADR 0010 (Project DNA), B71 i `docs/known-issues.md`.

## Kontext

Follow-up-flödet kan redan skapa en ny version med samma `projectId`, men
`merge_followup_project_input` har varit helt konservativ för
`company.story`, `company.tagline` och `tone`. Det skyddade B60-fyndet där rå
följdprompt läckte till kundcopy, men gjorde också att tydliga följdprompter
som "gör tonen mer premium" eller "lyft familjeföretag-storyn" inte gav någon
semantisk skillnad i v2.

`governance/policies/project-dna.v1.json` definierar den långsiktiga
lagringen som `data/projects/<projectId>/dna.json`. Den runtime-ytan finns
inte ännu och skulle kräva en bredare migrering av befintliga prompt-input
sidecars.

## Beslut

V1 implementerar semantic follow-up merge som en smal mellanstation:

1. `projectDna` lagras i befintlig meta-sidecar:
   `data/prompt-inputs/<siteId>.meta.json`.
2. Full canonical lagring i `data/projects/<projectId>/dna.json` är V2-scope.
3. Följdprompten klassificeras deterministiskt med keyword-tabell, utan LLM.
4. Följande intent-värden används i V1:
   `tone-shift`, `story-emphasize`, `tagline-update`,
   `positioning-shift`, `no-semantic-change`, `clarify`.
5. `tone-shift` får ändra `tone.primary`, `tone.secondary` och `tone.avoid`.
6. `story-emphasize` får ändra `company.story`.
7. `tagline-update` får ändra `company.tagline`.
8. `positioning-shift` skrivs bara i `projectDna.positioning`; Project Input
   har inget positioning-fält i V1.
9. `no-semantic-change` och `clarify` behåller den tidigare konservativa
   mergen för semantiska fält.

Alla semantiska textpatchar går genom befintliga publika copy-skydd:
planner-note-filter, build-imperativ-filter, UI-direktiv-filter för tagline
och längdgränser. Rå följdprompt ska fortsatt bara finnas i
`meta.followUpPrompt`, aldrig i kundcopy.

## Konsekvenser

Positiva:

- B71 kan stängas på faktisk Project Input-effekt, inte bara metadata.
- v2 får synlig artefaktdiff för tydliga tone/story/tagline-prompter.
- Additiva följdprompter fortsätter vara byte-stabila för oändrade
  semantiska fält.
- V2-flytten kan göras senare utan att blockera kärnflödet nu.

Negativa:

- `project-dna.v1.json` säger fortfarande att DNA-data lever utanför Engine
  Run-mappar. V1 avviker medvetet från slutformen och dokumenterar det här.
- Tone påverkar inte full CSS/renderad visuell känsla ännu; renderer- och
  brand-token-propagation är separat sprint.
- Keyword-tabellen ger medvetet false negatives hellre än riskerar rå
  prompt-läckage.

## Utanför scope

- Ingen SNI-runtime-konsumtion.
- Ingen Viewser-overlay-integration.
- Ingen Backoffice-editor för DNA.
- Ingen variant-promotion eller Project Fork.
- Ingen embeddings- eller LLM-baserad intentklassning.
- Ingen full `data/projects/<projectId>/dna.json`-lagring.
