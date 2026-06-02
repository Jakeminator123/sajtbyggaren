# KÖR 3b — visualDirection väljer treatment

> Ny behavior — men först **efter** att JSON-sanningen är stabil (`kor-3a`).

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`kor-3a-section-treatments-json.md`](kor-3a-section-treatments-json.md),
[`01-artefakt-kontrakt-blueprint.md`](01-artefakt-kontrakt-blueprint.md) §4.
**Beror på:** `kor-3a`, `kor-1c`.

---

## Mål

Låt blueprintets `visualDirection` (från `kor-1c`) välja section-treatment från den
JSON-sanning `kor-3a` etablerade, så samma scaffold + variant kan få olika känsla.

## Varför

Det är här Sajtbyggaren blir starkare än ren mall: en variant + en blueprint-driven
visual direction differentierar känslan utan risk för trasig CSS.

## Scope (filer)

- `packages/generation/build/dispatcher.py` (nytt steg: **visual-direction-pick** i
  prioritetsordningen)
- `governance/schemas/generation-package.schema.json` (`visualDirection`-enums — om inte
  redan satta i `kor-1a/1c`)
- `tests/`

**Off-limits:** fri CSS, nya treatments utan renderer-stöd, JSON-migrationen (gjordes i
`kor-3a`), renderers-innehåll, preview/adaptrar.

## Konkret arbete

1. Inför **visual-direction-pick** i `_treatment_for_section` med prioritet:
   **operator-pin > visual-direction-pick > variant-default > section-default**.
   (Detta är platsen `dispatcher.py`-kommentaren redan reserverar för LLM-pick.)
2. `visualDirection.heroStyle`/`sectionTreatments`-värden är **enums** som mappar 1:1
   mot vad renderern faktiskt stödjer. En ostödd treatment kan aldrig väljas (validering).
3. Utan `visualDirection` → exakt `kor-3a`-paritet (regressionsskydd).

## Testfall (DoD)

- Samma scaffold + variant men olika `visualDirection` → synligt olika treatments
  (t.ex. `service-list: tabular` vs `alternating-rows`).
- Utan `visualDirection` → byte-paritet mot `kor-3a`.
- LLM:en kan aldrig välja en treatment renderern inte stödjer (validering avvisar).

## Checks (scope-baserat)

`git diff --stat` · `ruff` på `packages/generation/build` · dispatcher-/paritets-pytest ·
`governance_validate` om schema-enums rörts.

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 3b - lat blueprintets visualDirection valja section-treatment fran JSON-
sanningen (KOR 3a). Prioritet: operator-pin > visual-direction-pick > variant-default >
section-default.

Krav:
- visualDirection-varden ar enums som mappar 1:1 mot renderer-stod; ostodd treatment avvisas.
- Utan visualDirection -> byte-paritet mot KOR 3a (regressionsskydd). Ingen fri CSS.

Definition of done: samma scaffold/variant + olika visualDirection ger olika treatments,
paritet utan visualDirection, ostodd treatment kan ej valjas, ruff + pytest grona.
```
