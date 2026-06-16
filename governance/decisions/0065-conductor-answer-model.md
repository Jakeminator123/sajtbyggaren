# ADR 0065 — answerModel: dirigentens svars-/resonemangsroll

**Status:** Accepted
**Datum:** 2026-06-16
**Beroenden:** ADR 0062 (OpenClaw som dirigent, rollkontrakt + action-bryggan +
ärlig no-op), ADR 0052 (per-roll modellparametrar), ADR 0044 (SOUL/chatt-persona),
ADR 0034 (följdprompt väg A). Relaterat: ADR 0036 (router-vokabulär).
**Berörda filer:**
[`governance/policies/llm-models.v1.json`](../policies/llm-models.v1.json),
[`packages/generation/orchestration/openclaw/report.py`](../../packages/generation/orchestration/openclaw/report.py),
[`packages/generation/orchestration/openclaw/core.py`](../../packages/generation/orchestration/openclaw/core.py),
[`apps/viewser/lib/openai.ts`](../../apps/viewser/lib/openai.ts),
[`apps/viewser/app/api/prompt/route.ts`](../../apps/viewser/app/api/prompt/route.ts).

## Kontext

Dirigenten (OpenClaw) ska kännas levande i kärnloopen
`prompt -> företagshemsida -> preview -> följdprompt -> ny version`. Idag
formuleras följdpromptsvaret i chatten av tre nyckel-gatade hjälpare i
`apps/viewser/app/api/prompt/route.ts` (`generateConversationAnswer`,
`generateAppliedConfirmation`, `generateFollowupOutcomeSummary`), som alla
anropar `chatWithOpenAi` i `apps/viewser/lib/openai.ts`. Två problem:

1. **Governance-glapp.** Dessa anrop går **inte** via en registrerad `Model
   Role`. `chatWithOpenAi` anropas utan `roleId`, och koden säger uttryckligen
   att chatten "medvetet INGEN registrerad Model Role" är. Det bryter mot
   policyns princip: ingen kod får anropa en LLM utan att en registrerad `Model
   Role` driver anropet. #363-passet flaggade exakt detta.
2. **Mekanisk känsla.** Utan nyckel (eller vid timeout) faller svaret tillbaka
   på `report.py:build_followup_report` — en deterministisk svensk rad (#363-
   golvet). Det golvet är ärligt och nödvändigt, men de terse raderna gör att
   följdsvaren kan kännas mekaniska i stället för "okej, du menar nog X — jag
   gjorde Y / kunde inte göra Y än".

Att registrera svarsmodellen som en `Model Role` stänger glappet och ger
parametrarna en spårbar, central hemvist (samma som övriga roller, ADR 0052).

## Beslut

Vi registrerar en konduktor-svars-/resonemangsroll `answerModel` i
`governance/policies/llm-models.v1.json` (version 14 -> 15, samma param-form som
övriga roller: `id`/`model`/`provider`/`reasoningEffort`/`maxOutputTokens`).
`answerModel` ingår i `smallReasoning`-gruppen.

`answerModel` formulerar dirigentens korta svenska följdpromptsvar:

- På en **applicerad** ändring: vad som uppfattades + vad som gjordes + den
  synliga effekten (ny version, ändrade sidor).
- På en **ärlig no-op** eller en **ostödd** intent (t.ex. `route_add`, eller en
  öppettider-följdprompt som inte mappades): "jag uppfattar att du vill X; det
  stöds inte än / inget syntes" — aldrig en felaktigt självsäker rad.

Svaret grundas ENBART i OpenClaw-beslutet + action-bryggans rapporterade fakta:
`editKind`/roll/target, `bridge.applied`, `appliedVisibleEffect`,
`previewShouldRefresh`, chain-`stage` och no-op-skäl. Modellen hittar aldrig på
en åtgärd eller en lyckad ändring.

Utan OPENAI_API_KEY (eller vid timeout) är fallbacken oförändrad: den
deterministiska raden från `report.py:build_followup_report` (no-key-paritet).
Med nyckel är beteendet icke-regressivt mot dagens hjälpare — samma in/ut, men
nu via den registrerade rollen.

## Hårda gränser (rails — icke förhandlingsbart)

I `answerModel`-rollens anda är detta en **förståelse-/narrationsyta**, inte en
ny befogenhet (samma princip som ADR 0062: frihet i förståelsen, kontroll i
appliceringen):

- **Text-only.** `answerModel` producerar narration + intent-resonemang som
  TEXT. Den får ingen ny rätt att agera — den deterministiska apply-kedjan
  (`router -> context -> patch -> apply -> targeted render`) validerar och
  applicerar fortfarande, och äger `appliedVisibleEffect`/`previewShouldRefresh`.
- **Ingen påhittad success.** Rollen får ALDRIG påstå en ändring som
  `bridge.applied`/`appliedVisibleEffect` inte rapporterat — ingen påhittad
  klar-signal. En icke-applicerad tur är en ärlig no-op.
- **Ingen fri fil- eller kod-emission.** Rollen skriver aldrig filer och
  genererar aldrig kod; den läser fakta och skriver en svensk rad.
- **No-key-golv ordagrant.** Saknas nyckeln står `report.py`-raden kvar exakt
  som idag.

## Parametrar

`answerModel` = `gpt-5.5` / `openai` / `reasoningEffort: low` /
`maxOutputTokens: 16000`. Låg reasoning räcker för en grundad narration av redan
kända fakta (samma klass som `copyDirectiveModel`/`rerankModel`); det generösa
utdatataket är en kostnadsförsäkring mot trunkering (ADR 0052-anda), aldrig ett
tuningverktyg. `reasoningEffort: xhigh` används aldrig (operatörsbeslut v14).

## Konsekvenser

- Plus: följdsvaren läses som en dirigent som förstår intentet och är ärlig om
  utfallet, inte som en maskinell statusrad — utan att rucka ärlighetskontraktet.
- Plus: LLM-anropet för chattsvaret går nu via en registrerad `Model Role`;
  glappet #363 flaggade är stängt för prompt-routens dirigentsvar.
- Plus: en framtida modell-/effort-justering är en policy-bump, inte en
  kodändring.
- Avgränsning: den hostade answer-only-genvägen (`lib/hosted-answer-only.ts`)
  och den generiska chatt-routen (`app/api/chat/route.ts`) anropar fortfarande
  `chatWithOpenAi` utan roll; de ligger utanför detta pass och är naturliga
  följdkandidater för samma roll.

## Vad ADR 0065 INTE beslutar

- **Ingen intent-förståelse-resolver på routern.** Att låta en modell tolka om
  intentet ovanpå `classify.py` är ett SEPARAT senare spår; detta pass är bara
  svars-/resonemangs- och narrationsmodellen.
- **Ingen ny befogenhet.** Inga nya `EditKind`, ingen ändring av apply-kedjan,
  router-decision-schemat eller rollkontrakten.
- **Ingen ny sanningskälla.** Action-bryggan förblir auktoritativ för vad som
  faktiskt hände.
