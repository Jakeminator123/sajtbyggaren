# KÖR 6b — Router LLM-fallback (svåra/tvetydiga meddelanden)

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`kor-6a-router-deterministisk.md`](kor-6a-router-deterministisk.md),
[`02-orchestrator-och-intent.md`](02-orchestrator-och-intent.md) §2, §6.
**Beror på:** `kor-6a`.

---

## Mål

Lägg en LLM-fallback ovanpå den deterministiska routern för meddelanden den klassar som
`unclear` eller långa/tvetydiga. Nu (och först nu) tas frågan om model role / naming.

## Varför

Heuristiken täcker det vanliga. Tvetydiga eller långa multi-intent-meddelanden behöver
en LLM för säker klassning. Genom att lägga den **efter** `kor-6a` undviker vi att första
routerversionen blir LLM-beroende (sajtmaskins lärdom: wira intent hela vägen, inte
halvvägs).

## Scope (filer)

- Router-modulen från `kor-6a` (LLM-fallback-gren)
- `governance/policies/llm-models.v1.json` (model role för routern — **operatörsbeslut**:
  ny `routerModel` vs återanvänd befintlig roll; om ny term → naming-dictionary)
- `governance/schemas/` (oförändrat output-kontrakt från `kor-6a`)
- `tests/`

**Off-limits:** build/preview-start på `answer_only`/`plan_only`, fri filgenerering,
renderers, viewser-UI.

## Konkret arbete

1. Fallback triggas bara när heuristiken ger `unclear` eller meddelandet är långt/
   multi-intent (mönster som sajtmaskins `classifyFollowUpIntentWithLlmFallback`).
2. LLM:en returnerar **samma** strukturerade output-kontrakt som `kor-6a`
   (`generateObject`-stil, schema-validerat).
3. Mock utan `OPENAI_API_KEY`: fall tillbaka till `kor-6a`-heuristiken (ingen regression).
4. Trace-regeln från `kor-6a` gäller oförändrat.

## Testfall (DoD)

- Tvetydiga prompter som `kor-6a` markerade `unclear` klassas nu rimligt (eller ber om
  förtydligande via `requiresClarification`).
- Utan nyckel: identiskt beteende som `kor-6a` (deterministisk fallback).
- Klock-exemplen fortsatt gröna (heuristiken äger dem, LLM rör dem inte i onödan).

## Checks (scope-baserat)

`git diff --stat` · `ruff` på router-modulen · router-pytest · mock-körning utan nyckel ·
`check_term_coverage --strict` om ny model-role-term tillkom.

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 6b - lagg LLM-fallback pa routern (KOR 6a) for unclear/langa/tvetydiga
meddelanden. Samma output-kontrakt. Mock utan nyckel = KOR 6a-heuristik.

Krav:
- Fallback bara vid unclear/lang/multi-intent. Schema-validerad strukturerad output.
- Model role ar operatorsbeslut (ny routerModel vs befintlig); ny term -> naming-dictionary.
- Trace-regeln fran KOR 6a galler. Ingen build/preview pa answer_only/plan_only.

Definition of done: tvetydiga prompter klassas rimligt, mock = KOR 6a, klock-exemplen
fortsatt grona, ruff + router-pytest (+ ev. term-coverage) grona.
```
