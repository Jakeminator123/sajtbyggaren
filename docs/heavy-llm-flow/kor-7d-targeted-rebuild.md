# KÖR 7d — Targeted render + version-build

> Sista skivan. Stänger loopen: en liten ändring renderar om **bara** den påverkade
> routens filer och uppdaterar preview — utan att "släcka ner hela sajten".

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`kor-7c-artifact-apply-version.md`](kor-7c-artifact-apply-version.md),
[`03-preview-data-och-versioner.md`](03-preview-data-och-versioner.md) (hela — inkl.
status-/verifieringsrutan).
**Beror på:** `kor-7c`, `kor-2`.

> **Verifiera först (från `03`):** att `immutable_builds`/`current.json` faktiskt finns i
> koden. Saknas de → denna skiva är **blockerad** tills Windows-safe-rebuild-pipelinen
> landat. Bygg inte ett eget pointer-/build-system.

---

## Mål

Efter en apply (`kor-7c`): **rendera om bara påverkade route-filer**, uppdatera generated
snapshot, kör rimlig verifiering, uppdatera preview endast om något ändrades.

## Targeted = render/filgenerering, inte partiell Next build

Viktig nyans: i en Next.js-app kan vi **rendera/generera om bara påverkade route-filer**,
men `npm run build` är i praktiken ofta **projektbred**. Tolka inte "targeted" så
bokstavligt att du börjar bygga ett partiellt build-system.

| v1 (denna skiva) | Får fortfarande vara projektbred |
|------------------|----------------------------------|
| rendera om bara påverkade route-filer | full `npm run build` |
| uppdatera generated snapshot för dem | full `tsc` / typecheck |
| rimlig verifiering av påverkad route | Quality Gate på hela projektet |

## Scope (filer)

- `packages/generation/build/` (targeted **render**: skriv bara om påverkade route-filer;
  återanvänd immutable-build + atomär `current.json`-swap från `03`)
- `scripts/build_site.py` (avgränsad render-väg; `appliedVisibleEffect` ärligt; full
  Next build/typecheck får vara projektbred i v1)
- `tests/`

**Off-limits:** ändra `current.json`-kontraktet eller adaptrarna (bara *använd* dem),
mutering av gamla run-artefakter, fri kodpatch, viewser-UI.

## Konkret arbete

1. Härled påverkade routes ur patchen (`<route>.<section>`); **rendera om bara de
   route-filerna** in i en ny immutabel build-dir.
2. Full `npm run build` + typecheck får köras projektbrett (v1) — optimera inte bort det.
3. Återanvänd atomär pekar-swap; swap **bara** på `ok`/`degraded` (oförändrat kontrakt;
   avbruten build promotas inte).
4. `appliedVisibleEffect` sätts ärligt; preview uppdateras bara vid faktisk synlig ändring.

## Testfall (DoD)

- Klock-edit (via `kor-7c`) → bara den routens filer renderas om → ny build → preview
  uppdateras.
- Patch utan synlig effekt → `appliedVisibleEffect:false`, preview oförändrad, ingen
  falsk success.
- `projectId`/`siteId` bevarade; `current.json`-swap bara på `ok`/`degraded`; gamla runs
  orörda.
- Befintliga build-/preview-tester gröna.

## Checks (scope-baserat)

`git diff --stat` · `ruff` på `packages/generation/build` + `scripts` · targeted-render-
pytest · **full** `pytest tests/ -q` (denna skiva rör build-vägen brett) ·
`governance_validate` om build-result-schema rörs.

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 7d - targeted RENDER av bara paverkade route-filer efter apply (KOR 7c), pa
immutable-build + current.json-vagen. Full npm build/typecheck FAR vara projektbred i v1.

Forhandskoll: verifiera att immutable_builds/current.json finns i koden (se 03). Saknas
de -> skivan ar blockerad tills rebuild-pipelinen landat.

Krav:
- Rendera om bara paverkade route-filer; bygg INTE ett partiellt Next-buildsystem.
- Ateranvand current.json-swap (ror inte kontraktet), swap bara pa ok/degraded.
- Mutera aldrig gamla run-artefakter. appliedVisibleEffect arligt; no-op -> ingen falsk
  success, ingen preview-omstart. Denna skiva ror build brett -> kor full pytest.

Definition of done: klock-edit renderar om ratt route-filer + uppdaterar preview, no-op
ger appliedVisibleEffect=false utan falsk signal, identitet bevarad, gamla runs ororda,
full pytest + ruff grona.
```
