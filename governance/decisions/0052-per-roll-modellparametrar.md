# ADR 0052 — Per-roll modellparametrar i llm-models-policyn (reasoningEffort + maxOutputTokens)

**Status:** Accepted (2026-06-11)
**Datum:** 2026-06-11
**Implementation:** levererad på `jakob-be` 2026-06-11 — schema + policy v11,
delad läsare `packages/policies/llm_model_params.py`, trådning av de åtta
call-sites och TS-plumbing i `apps/viewser/lib/openai.ts` (verifierad mot
openai-SDK 2.36.0 i venv: `reasoning`/`max_output_tokens` stöds och
effort-enum:en matchar `none|low|medium|high|xhigh`).
**Beroenden:** ADR 0009 (llm-models-policyns ursprung), ADR 0044 (SOUL-slicen
äger chatt-personan i `apps/viewser/app/api/prompt/route.ts` — rörs inte).
Ersätter en extern agent-plan som var skriven mot ett äldre repo-läge; denna
ADR är den korrigerade versionen (rätt policyversion, rätt enum, rätt
tak-princip). Tokengräns-tabellen kommer från undersökningen 2026-06-11 som
läste varje rolls faktiska strukturerade output.

## Kontext

Alla tolv Model Roles i [`llm-models.v1.json`](../policies/llm-models.v1.json)
(v10) mappar roll -> modellsträng, inget mer. De åtta riktiga anropen i
motorn går via `client.responses.parse(...)` utan `reasoning`- eller
tak-parametrar, så modellens defaults gäller överallt. På resonerande
modeller (gpt-5-serien) är `reasoning.effort` och utdatatak den största
kvalitets-/kostnads-/latensspaken — i dag helt ostyrd.

Två fakta styr designen:

1. **Utdatataket inkluderar reasoning-tokens.** I Responses-API:t räknar
   `max_output_tokens` in både synlig output och reasoning-tokens (samma
   gäller `max_completion_tokens` i chat-API:t). Ett snålt tak stryps av
   "tänkandet" innan synlig output produceras, och call-siten degraderar
   tyst till mock. Därför: **effort först, tak generöst** — taket är en
   kostnadsförsäkring, inte ett tuningverktyg.
2. **Rätt enum är `none|low|medium|high|xhigh`** (gpt-5.5-generationens
   nivåer). Den äldre nivån `minimal` förekommer i tidigare planer och i
   vision-anropet; läsaren ska acceptera legacy-värden och mappa
   `minimal -> low` (med trace-varning) i stället för att fela.

## Beslut

### Policy och schema (additivt)

- `llm-models.schema.json` får två nya **valfria** properties per roll:
  `reasoningEffort` (enum `none|low|medium|high|xhigh`) och
  `maxOutputTokens` (positivt heltal).
- `llm-models.v1.json` bumpas **v10 -> v11** med startvärdena nedan och en
  purpose-mening om v11. Frånvarande fält = exakt dagens beteende.
- `embeddingModel` får **aldrig** chat-params (ingen reasoningEffort, inget
  maxOutputTokens) — ett governance-test ska vakta detta.

### Startvärden per roll (v11)

| Roll | reasoningEffort | maxOutputTokens | Motivering (synlig output) |
|---|---|---|---|
| briefModel | low | 6000 | Extraktion + lätt positionering; stort schema behöver marginal |
| planningModel | medium | 6000 | Äkta val (scaffold/variant/dossiers); high riskerar overthinking |
| routerModel | low | 4000 | Klassning, litet beslutsobjekt; taket bär reasoning-andelen |
| copyDirectiveModel | low | 4000 | Direktivlista med färdig kundcopy, kort |
| styleDirectiveModel | none | 2000 | Trivial mappning till hex + vibe; reasoning är slöseri |
| rerankModel | low | 2000 | Otrådad i dag — värden sätts men markeras som vilande |
| codegenModel | medium | 4000 | Se omprövningsnotisen nedan |
| repairModel | medium | 4000 | Små strukturerade patchar med grundningsregler |
| verifierModel | low | 4000 | Konservativ kritiker; hög effort ger överflaggning |
| variantModel | medium | 8000 | Operatörstooling, längre JSON, ingen latenspress |
| dossierModel | medium | 12000 | Längsta outputen (manifest + instructions) |
| embeddingModel | — | — | Chat-params förbjudna |

**Omprövningsnotis för codegenModel (skrivs in i policy-purpose):** dagens
codegen-kontrakt är medvetet smalt (rationale + max tre riskNotes, ADR 0017)
— modellen genererar inte filinnehåll, så 4000 trunkerar inget. När
kontraktet breddas till riktig fil-emission måste taket omprövas (>= 16000)
i samma ändring som kontraktet.

### Delad defensiv läsare

En ny modul `packages/policies/llm_model_params.py` blir enda sättet att läsa
fälten (samma princip som "ingen LLM utan registrerad Model Role" — ingen
kod läser params utanför policyn, inga env-overrides för params):

- `resolve_role_params(role_id)` -> fryst objekt med `model`,
  `max_output_tokens`, `reasoning_effort`. Defensiv: saknad fil/roll, trasig
  JSON, okänt enum-värde eller ogiltigt heltal ger `None`-fält plus
  trace-varning — **aldrig** ett kastat fel (ett param-fel får inte
  degradera ett bygge till mock). `minimal` accepteras och mappas till
  `low`.
- `responses_kwargs(params)` respektive `chat_completions_kwargs(params)`
  bygger API-specifika kwargs; tom dict när inget är satt (= dagens anrop).
- Sökvägen `packages/policies/` är redan vitlistad i repo-boundaries för
  alla `packages/generation/*` — modulen delas av brief/planning/router/
  codegen/repair/quality_gate utan boundary-brott och utan att duplicera
  defensiv logik på åtta ställen.

### Trådning (åtta call-sites)

Varje riktigt anrop får `**responses_kwargs(resolve_role_params("<roll>"))`
— minimal diff, inget nytt publikt API, mock-/no-key-grenarna orörda:
`brief/extract.py` (briefModel, copyDirectiveModel, styleDirectiveModel),
`planning/plan.py`, `orchestration/router/llm_fallback.py`,
`codegen/codegen.py`, `repair/blueprint_repair.py`,
`quality_gate/verifier.py`. Design-tooling-skripten (variantModel,
dossierModel) trådas i en senare slice; deras policyvärden ligger vilande
tills dess.

### TS-sidan: enbart plumbing

`apps/viewser/lib/openai.ts` får en valfri `roleId`-parameter och en defensiv
TS-läsare av samma policyfält. Utan `roleId` är beteendet exakt dagens
(chatten är medvetet ingen registrerad Model Role). Ingen konversations-roll
registreras, och det SOUL-ägda anropet i `route.ts` rörs inte (ADR 0044).

## Avgränsning och samspel

- Denna commit är **docs-only**: ingen policy-bump, inget schema och ingen
  kod ändras här. Implementeringen kan utföras av en separat agent — planen
  ovan är komplett nog att exekvera, och måste börja med `git fetch` mot
  färsk `jakob-be` (tidigare plan-versioner utgick från v9 och fel
  ADR-nummer).
- Backoffice-styrsidan (ADR 0051, parallell slice) konsumerar fälten i sin
  modellroll-flik när de finns; dess kod ska läsa via den delade läsaren och
  inte bygga ett eget param-schema.
- Tak-värdena är startvärden, inte sanning: de justeras via policy-bump när
  evals visar behov, aldrig via kod.

## Konsekvenser

- Plus: effort/kostnad styrs per roll från ett ställe; klassning slutar
  betala reasoning-skatt; tunga roller får medvetet utrymme; frånvaro av
  fält = noll regression.
- Minus: ytterligare en yta att hålla ärlig (policy <-> faktisk API-form);
  enum-/API-namn måste verifieras mot installerad SDK-version i
  implementations-slicen.
- Risk hanterad: trunkerings-fällan (reasoning-tokens i taket) är
  bortdesignad via effort-först-principen och generösa tak.
