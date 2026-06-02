# KÖR 3a — Section treatments: Python → JSON (paritet)

> Ren **behavior-preserving refaktor**. Ingen ny feature. Mål: byte-paritet.

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`00-malbild-och-lager.md`](00-malbild-och-lager.md) §4.
**Beror på:** inget hårt (kan göras när som helst; kör efter `kor-2` i sekvensen).

---

## Mål

Flytta section-treatment-sanningen från hårdkodad Python (`dispatcher.py`
`_SECTION_TREATMENTS_BY_VARIANT`) till **deklarativ JSON**, utan att ändra någon output.
Detta gör att en framtida LLM-pick (`kor-3b`) kan läsa samma JSON.

## Varför

Idag ligger variant→treatment i Python, vilket LLM:en inte kan resonera över och som
lätt driver isär från planning-prompten (`_SECTION_TREATMENTS_CATALOGUE`). En sanning i
JSON tar bort drift-risken **innan** vi lägger ny behavior ovanpå.

## Scope (filer)

- Ny deklarativ JSON: antingen fält `sectionTreatments` i varje
  `scaffolds/<id>/variants/<variantId>.json`, **eller** ny
  `scaffolds/<id>/section-treatments.json` (välj det som speglar dagens dict renast).
- `packages/generation/build/dispatcher.py` (läs JSON i stället för
  `_SECTION_TREATMENTS_BY_VARIANT`)
- `packages/generation/planning/plan.py` (`_SECTION_TREATMENTS_CATALOGUE` läser samma
  JSON i stället för Python-spegel)
- ev. `governance/schemas/` (om nytt fält i variant-schema)
- `tests/`

**Off-limits:** ny treatment-behavior, `visualDirection`-pick (det är `kor-3b`),
renderers, preview/adaptrar.

## Konkret arbete

1. Exportera dagens `_SECTION_TREATMENTS_BY_VARIANT` 1:1 till JSON.
2. `dispatcher.py` läser JSON; behåll prioritetsordningen **operator-pin > variant-
   default > section-default** exakt som idag.
3. `plan.py` läser samma JSON för prompt-katalogen (en sanning).
4. Lägg ett test som bevisar **byte-för-byte-paritet** mot dagens render-output för alla
   varianter (snapshot-jämförelse).

## Testfall (DoD)

- Render-output är **byte-identisk** mot före migrationen för alla 27 varianter.
- `dispatcher.py` och planning-prompten läser **samma** JSON.
- Inga `_SECTION_TREATMENTS_BY_VARIANT`-/`_SECTION_TREATMENTS_CATALOGUE`-dictar kvar i
  Python (eller de är tunna wrappers runt JSON-läsningen).

## Checks (scope-baserat)

`git diff --stat` · `ruff` på `packages/generation/build|planning` · paritets-/
dispatcher-pytest · `governance_validate` om variant-schema rörts.

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 3a - migrera dispatcher.py:_SECTION_TREATMENTS_BY_VARIANT till deklarativ
JSON (variant- eller section-treatments-fil). Ren behavior-preserving refaktor.

Krav:
- Byte-for-byte-paritet i render-output for alla varianter (snapshot-test).
- Behall prioritet operator-pin > variant-default > section-default.
- plan.py-katalogen laser SAMMA JSON (en sanning). Ingen ny behavior (det ar 3b).

Definition of done: paritetstest gront for alla varianter, en JSON-sanning lases av bade
dispatcher och planning, ruff + relevanta pytest grona.
```
