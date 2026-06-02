# KÖR 5 — Repair Pass v1 (repairModel, blueprint-only)

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`kor-4a-deterministic-critic.md`](kor-4a-deterministic-critic.md),
[`01-artefakt-kontrakt-blueprint.md`](01-artefakt-kontrakt-blueprint.md).
**Beror på:** `kor-1c`, `kor-4a` (drar nytta av `kor-4b` när den finns).

---

## Mål

En repair-agent som vid **high-severity** critic-issues ändrar **bara blueprint-fält**
(inte fria filer) och triggar re-render. Detta är systemets **första riktiga
agent-loop**: bygg → granska → förbättra. Wira `repairModel` (rollen finns).

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
critic.issues (severity=high)   <- fran KOR 4a (deterministisk) / KOR 4b (verifierModel)
  -> repairModel: patch relevant blueprint-falt
       generic_copy   -> skriv om hero.headline/proofLine (positioning-grundat)
       thin_offer     -> lagg 2-3 grundade tjanster i services.service-list
       trust_missing  -> skapa arlig trust ur businessFacts (inga fake claims)
  -> re-render (samma deterministiska renderer)
  -> kor critic igen (max N pass, default 1)
  -> spara repair-result.json
```

## Output

Utöka `repair-result.json`:

```jsonc
{
  // ... befintliga mekaniska fixes ...
  "blueprintRepairs": [
    { "issueType": "generic_copy", "target": "home.hero",
      "field": "contentBlocks.home.hero.headline", "before": "...", "after": "...",
      "source": "repairModel" }
  ],
  "passes": 1,
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
   high-severity issues triggar; bunden pass-räknare.
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
(KOR 4a). Vid high-severity issues patchar den namngivna blueprint-falt -> re-render ->
critic igen, bunden pass-rakning. Hall principen "en central repair-gate".

Krav:
- LLM far ENDAST patcha befintliga blueprint-falt (validera mot schema/rails). Aldrig fria filer.
- Grounding-guard: inga nya siffror/orter/namn/cert som saknas i businessFacts.
- Logga before/after i repair-result.json + trace.ndjson. Bunden pass-raknare (fix-registry).
- Mock utan OPENAI_API_KEY -> no-fix-applied.

Definition of done: generic_copy/thin_offer repareras via blueprint-patch + re-render,
inga fria filer rorda, pass-rakning bunden, mock verifierad, full pytest + ruff grona.
```
