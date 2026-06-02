# KÖR 7c — Artifact apply + ny version

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`kor-7b-patch-planner-dry-run.md`](kor-7b-patch-planner-dry-run.md),
[`03-preview-data-och-versioner.md`](03-preview-data-och-versioner.md) §2–3.
**Beror på:** `kor-7b`.

---

## Mål

Applicera en **validerad** patch (från `kor-7b`) genom att skapa **nästa** version —
aldrig genom att skriva över historik. Ingen build (det är `kor-7d`).

## Varför

Apply ska skapa en korrekt, versionerad ändring som bevarar identitet, så följdprompten
blir "ny version" och inte "ny sajt". Att hålla detta skilt från rebuild gör att vi kan
verifiera versionslogiken isolerat.

## Immutabilitetsregel (icke förhandlingsbar)

Patchen får **aldrig mutera gamla run-artefakter.** Engine Run-kontraktet bygger på att
varje `runId` har sin egen artefaktkedja i `data/runs/<runId>/` så operatören kan följa
exakt vad som hände i körningen. Project Input-versioner är immutabla snapshots;
skrivlogiken vägrar skriva över en befintlig version.

Apply **får**:
- skapa **nästa** Project Input-version (`<siteId>.v<N+1>`), och
- låta nästa runs härledda artefakter (`site-brief`/`site-plan`/`generation-package`)
  skrivas under en **ny** `runId` när `kor-7d` bygger.

Apply **får inte**:
- röra ett tidigare `runId`:s `site-brief.json` / `site-plan.json` /
  `generation-package.json`,
- skriva över en befintlig `vN`-snapshot.

## Scope (filer)

- `packages/generation/orchestration/` (apply-steg)
- `scripts/prompt_to_project_input.py` (återanvänd merge-/versions-logiken; skapa
  `<siteId>.v<N+1>`, bevara `projectId`/`siteId`, frys scaffold/variant)
- `tests/`

**Off-limits:** build/rebuild (`kor-7d`), `current.json`-swap (görs av build i `kor-7d`),
**mutering av gamla run-artefakter**, preview/adaptrar, viewser-UI, fri kodpatch.

## Konkret arbete

1. Applicera validerade patchar genom att **bygga nästa Project Input-version** (inte
   genom att skriva i en gammal run). Härledda artefakter för den nya versionen produceras
   när `kor-7d` kör — tidigare runs lämnas orörda.
2. Skapa `<siteId>.v<N+1>` via befintlig immutabel snapshot-logik; bevara `projectId`/
   `siteId`; frys scaffold/variant (som dagens follow-up-merge).
3. Skriv **inte** `current.json` (ingen build ännu). Logga apply i den **nya** versionens/
   runs `trace.ndjson`.

## Testfall (DoD)

- En validerad patch → ny `v<N+1>`-snapshot med ändringen; `projectId`/`siteId` bevarade;
  scaffold/variant frysta.
- **Inget tidigare `vN` eller `data/runs/<äldre runId>/`-artefakt ändras** (verifiera med
  diff före/efter).
- En `rejected`/ogiltig patch appliceras aldrig.
- `current.json` orört (ingen build i denna skiva).

## Checks (scope-baserat)

`git diff --stat` · `ruff` på berörda moduler · apply-/versions-pytest. (Full pytest om
`prompt_to_project_input.py`-merge rörs brett.)

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 7c - applicera validerad patch (KOR 7b) genom att skapa NASTA Project
Input-version (v<N+1>). INGEN build, INGEN current.json-swap.

Krav (immutabilitet):
- Mutera ALDRIG gamla run-artefakter. Tidigare runId:s site-brief/site-plan/generation-
  package och tidigare vN-snapshots lamnas helt ororda.
- Skapa bara nasta vN+1 (immutabel snapshot). Bevara projectId/siteId, frys scaffold/variant.
- Ogiltig/rejected patch appliceras aldrig. Logga apply i nya versionens trace.ndjson.

Definition of done: giltig patch ger ny v<N+1> med bevarad identitet + frusen scaffold/
variant, inga aldre artefakter andrade (diff-verifierat), current.json orort, ruff +
apply-pytest grona.
```
