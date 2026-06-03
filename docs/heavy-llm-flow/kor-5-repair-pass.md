# KÖR 5 — Repair Pass v1 (repairModel, blueprint-only)

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`kor-4a-deterministic-critic.md`](kor-4a-deterministic-critic.md),
[`01-artefakt-kontrakt-blueprint.md`](01-artefakt-kontrakt-blueprint.md).
**Beror på:** `kor-1c`, `kor-4a` (drar nytta av `kor-4b` när den finns).

---

## Mål

En repair-agent som vid **reparerbara** critic-issues ändrar **bara blueprint-fält**
(inte fria filer) och triggar re-render. Detta är systemets **första riktiga
agent-loop**: bygg → granska → förbättra. Wira `repairModel` (rollen finns).

> **Implementationsnot (matchar koden, #185):** Grinden är **issue-typ-baserad**, inte
> ren severity. Den deterministiska critic v0 (kör-4a) sätter `generic_copy` och
> `thin_offer` till `severity=medium` (bara `placeholder_leakage`/`missing_cta` är
> `high`), så en ren "high-only"-grind skulle aldrig reparera dem och bryta DoD. De
> reparerbara typerna styrs därför av `fix-registry.v1.json:blueprintRepair
> .triggerIssueTypes` = `{generic_copy, thin_offer, missing_cta}` (sorteras high-först).
> Det finns **ingen** `trust_missing`-issue-typ i critic v0 — "ärlig trust" hanteras via
> `missing_cta` (conversion). Passen rör aldrig `critic.py` och inför inga nya
> critic-typer.

## Varför

Mer Lovable/v0-likt: systemet reparerar tydliga svagheter automatiskt. Viktigt: "inte
gör om allt" — bara reparera det critic pekade ut, och bara genom blueprint-patchar så
det förblir testbart och reproducerbart.

## Hur det knyter an till befintlig repair-pipeline

Repair-pipelinen finns redan central (`packages/generation/repair/`) med en
sandwich-loop och mekaniska fixes (`ensure-default-export`). LLM-fix/`repairModel` är
**inte** wirad ännu (`llmFixesApplied` alltid `[]`). Denna skiva lägger till **ett**
nytt repair-steg: **blueprint-repair** — och håller principen "en central repair-gate"
(undvik sajtmaskins spridda call-sites).

## Loop (bunden)

```text
critic.issues (typ in triggerIssueTypes)   <- fran KOR 4a (deterministisk) / KOR 4b (verifierModel)
  -> repairModel: patch relevant blueprint-falt (BARA befintliga falt)
       generic_copy   -> skriv om BEFINTLIGA hero-textfalt (headline/subheadline/proofLine)
       thin_offer     -> lagg 3 grundade tjanster i den befintliga offer-listan
       missing_cta    -> fyll conversion.primaryCta i den BEFINTLIGA conversion-gruppen
  -> re-render (samma deterministiska renderer; injicerad callback)
  -> kor critic igen (max N pass, default 1)
  -> spara repair-result.json (blueprintRepairs[] + blueprintPasses)
```

Kontrakt: passen skapar **aldrig** nya nycklar/sektioner/grupper — den skriver bara om
fält som redan finns (`generic_copy`), eller fyller ett schema-känt fält i en redan
existerande grupp (`missing_cta` -> `conversion.primaryCta`). Den materialiseras bara när
en `rerender`-callback injiceras (annars dormant). Saknad nyckel / otillgänglig modell ->
`no-fix-applied`, `blueprintPasses=0`, inga `blueprintRepairs`, trace `repair.blueprint_skipped`
(aldrig en syntetisk `success=false`). Render-fel kraschar aldrig fasen — det nedgraderas
till `partial-fix`/`no-fix-applied` med `rerender_error` i tracen.

## Output

Utöka `repair-result.json`:

```jsonc
{
  // ... befintliga mekaniska fixes ...
  "blueprintRepairs": [
    { "issueType": "generic_copy", "target": "home.hero",
      "field": "contentBlocks.home.hero.headline", "before": "...", "after": "...",
      "source": "repairModel", "success": true }
  ],
  "blueprintPasses": 1,
  "status": "fixed"   // not-needed | no-fix-applied | fixed | partial-fix
}
```

## Filer

- `packages/generation/repair/` (nytt blueprint-repair-steg i orchestration; bunden
  pass-räknare från `fix-registry.v1.json`)
- `packages/generation/` `repairModel`-resolver
- `governance/schemas/repair-result.schema.json`
- `governance/policies/fix-registry.v1.json` (max-pass för blueprint-repair)
- `tests/`

**Off-limits:** fri filpatch (LLM får aldrig skriva godtyckliga filer här), nya
canonical-typer, preview/adaptrar, viewser-UI. Repair får bara röra blueprint-fält som
redan finns i schemat.

## Konkret arbete

1. Lägg blueprint-repair efter critic i `execute_phase3_quality_and_repair`. Bara
   issues vars typ finns i `blueprintRepair.triggerIssueTypes` triggar (sorteras
   high-först); bunden pass-räknare; aktiveras bara när en `rerender`-callback injiceras.
2. `repairModel` får critic-issue + relevant blueprint-snitt och returnerar en
   **patch på namngivna fält** (validera mot schema + rails före apply).
3. Re-render via samma deterministiska väg; kör critic igen; logga before/after i
   `repair-result.json` + `trace.ndjson`.
4. Grunding-guard: repair får inte introducera siffror/orter/namn/cert som inte finns i
   `businessFacts` (samma anda som befintliga grounding-guards).

## Testfall (DoD)

- En blueprint med `generic_copy` (high) → hero skrivs om → re-render → issue borta
  eller nedgraderad.
- En `thin_offer` → fler grundade tjänster, inga påhittade.
- Repair rör **bara** blueprint-fält (verifiera att inga fria filer skrevs).
- Bunden pass-räknare respekteras (ingen oändlig loop).
- Utan nyckel: `no-fix-applied` (mock).

## Checks (scope-baserat)

`git diff --stat` · `ruff` på `packages/generation/repair` · repair-pytest ·
mock-körning utan nyckel · **full** `pytest tests/ -q` (repair-vägen rörs brett) ·
`governance_validate` (repair-result-schema rört).

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 5 - wira repairModel som en blueprint-only repair-pass efter Quality Critic
(KOR 4a). Vid reparerbara issues (typ i blueprintRepair.triggerIssueTypes, high-forst)
patchar den namngivna blueprint-falt -> re-render -> critic igen, bunden pass-rakning.
Hall principen "en central repair-gate".

Krav:
- LLM far ENDAST patcha befintliga blueprint-falt (validera mot schema/rails). Aldrig fria filer.
- Grounding-guard: inga nya siffror/orter/namn/cert som saknas i businessFacts.
- Logga before/after i repair-result.json + trace.ndjson. Bunden pass-raknare (fix-registry).
- Mock utan OPENAI_API_KEY -> no-fix-applied.

Definition of done: generic_copy/thin_offer repareras via blueprint-patch + re-render,
inga fria filer rorda, pass-rakning bunden, mock verifierad, full pytest + ruff grona.
```
