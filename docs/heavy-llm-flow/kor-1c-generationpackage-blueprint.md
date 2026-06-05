# KÖR 1c — planningModel fyller Generation Package-blueprintet

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`01-artefakt-kontrakt-blueprint.md`](01-artefakt-kontrakt-blueprint.md) §3–4,
[`kor-1a-blueprint-schema-skelett.md`](kor-1a-blueprint-schema-skelett.md).
**Beror på:** `kor-1a` (och drar nytta av `kor-1b`).

---

## Mål

Låt planning-vägen fylla `sectionPlan` (Site Plan) samt `contentBlocks`,
`visualDirection` och `qualityRisks` (Generation Package) — med mock-fallback. Detta är
arbetsordern renderern sedan konsumerar i `kor-2`.

## Varför

Generation Package är "the only payload that enters codegen" men idag mest refs + id:n.
Här bor det faktiska blueprint-innehållet renderern ska bygga från.

## Scope (filer)

- `packages/generation/planning/plan.py` (`PlanningChoice` += `sectionPlan`;
  `_assemble_site_plan` / `_assemble_generation_package` fyller `contentBlocks`/
  `visualDirection`/`qualityRisks`; mock-defaults)
- `packages/generation/planning/` (modell-/prompt-helpers)
- `tests/` (plan- + generation-package-tester)

**Off-limits:** schema-ändringar (`kor-1a`), renderers (`kor-2`), section-treatment-
mapping till JSON (`kor-3a`), preview/adaptrar.

## Konkret arbete

1. `PlanningChoice` får `sectionPlan`; resolvern **validerar** att varje
   `<routeId>.<sectionId>` finns i scaffoldens `sections.json` (samma rail som dossiers).
2. `_assemble_generation_package` fyller `contentBlocks.<route>.<section>` +
   `visualDirection` + `qualityRisks` (LLM när nyckel finns, annars mock-defaults).
3. `qualityRisks` härleds delvis automatiskt ur `businessFacts.unknowns` från Site Brief
   (t.ex. saknad telefon → "Do not show phone if missing").
4. Builder-vägen är ofta `pinned` (inget planning-LLM-anrop) — säkerställ att blueprint
   ändå produceras deterministiskt i den vägen (mock), så `kor-2` har data att rendera.

## Testfall (DoD)

- Fyra baseline ger fyra **tydligt olika** `contentBlocks` (hero/services skiljer sig).
- `visualDirection` skiljer sig per bransch; `sectionPlan`-nycklar finns i `sections.json`.
- `qualityRisks` speglar `unknowns` (ingen påhittad kontakt/cert).
- Ogiltig section i `sectionPlan` avvisas av resolvern.
- Utan nyckel: identiskt kontrakt via mock. Befintliga plan-tester gröna.

## Checks (scope-baserat)

`git diff --stat` · `ruff` på `packages/generation/planning/` · relevanta
plan-/package-pytest-filer · mock-körning utan nyckel. (Full pytest bara om planning-
ändringen är bred.)

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 1c - lat planning fylla sectionPlan (Site Plan) + contentBlocks/
visualDirection/qualityRisks (Generation Package). Bygg pa schemat fran KOR 1a.

Krav:
- Validera sectionPlan/contentBlocks-nycklar mot scaffoldens sections.json.
- qualityRisks harleds delvis ur businessFacts.unknowns. Inga fake-certs.
- Aven pinned builder-vag ska producera blueprint deterministiskt (mock).
- Ingen schemaandring, ingen renderer, ingen JSON-treatment-migration (KOR 3a).

Definition of done: fyra baseline ger olika contentBlocks/visualDirection, sectionPlan
validerad mot sections.json, qualityRisks speglar unknowns, mock verifierad, plan-tester +
ruff pa berord modul grona.
```
