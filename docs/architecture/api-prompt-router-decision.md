---
status: active
owner: backend
truth_level: summary
last_verified_commit: f56ac30
---

# routerDecision i /api/prompt (Fas 1, skiva 1a)

Kort not om hur den deterministiska routern (KÖR-6a) syns i operatörens UI.
Hör ihop med Fas 1 i `docs/heavy-llm-flow/post-build-plan.md` (rör inte den
filen). Skiva 1b (wira hela follow-up-kedjan) är separat.

## Vad slicen gör

`/api/prompt` klassar varje inkommande prompt med den deterministiska
`classify_message` och returnerar resultatet som `routerDecision` i svaret,
bredvid dagens `runId`/`siteId`/`buildStatus`. Då kan FloatingChat ärligt visa
vad routern tyckte ("fråga", "plan", "ändring") via helpers från PR #177
(`extractRouterDecision` + `summarizeRouterDecision`).

## Dataväg

```text
/api/prompt  ->  lib/router-classify-runner.ts (classifyMessage)
             ->  spawn scripts/classify_message.py  (deterministisk classify_message)
             ->  RouterDecision.model_dump() som JSON
             ->  routerDecision i svaret (read-only metadata)
```

`scripts/classify_message.py` följer samma mönster som
`scripts/prompt_to_project_input.py`: apps/viewser importerar aldrig
`packages/` direkt utan shell:ar till ett skript i `scripts/`.

## Hårda gränser i denna slice

- **Deterministisk only.** Använder `classify_message`, aldrig
  `classify_message_with_llm_fallback`. Ingen modellroll, ingen
  `OPENAI_API_KEY`-kostnad per prompt.
- **Read-only metadata.** `routerDecision` styr inte bygget eller previewen.
  `shouldStartPreview` och hela byggvägen är oförändrade och beräknas
  deterministiskt precis som förut. Bridge-fel degraderar till `null`.
- **answer_only / plan_only startar fortfarande ingen build.** Routern sätter
  `buildRequirement` i {none, plan_only} och `shouldStartPreview=false` för de
  utfallen — den kan aldrig be om ett bygge.
- **Ingen påhittad effekt (ärlighetsgrind).** På en följdprompt där den
  befintliga copy/edit-vägen redan landade en synlig ändring
  (`appliedCopyDirectives` ifyllt eller `appliedVisibleEffect === true`)
  skickas `routerDecision=null`, så UI:t aldrig säger "inte byggt än" över en
  ändring som faktiskt applicerades. Init-builds och äkta no-op-följdprompter
  bär hela beslutet.
- Rör inte preview-runtime/`current.json`-kontraktet. Bygger inte om
  follow-up-kedjan (skiva 1b).

## Tester

- `tests/test_api_prompt_router_decision.py` — bridge-CLI:n emitterar
  schema-giltig `routerDecision` (mot `router-decision.schema.json`),
  answer_only/plan_only ber aldrig om bygge, route:n exponerar beslutet som
  read-only metadata och behåller localhost-/hosted-vakterna.
- `tests/test_api_prompt_smoke.py` — det riktiga HTTP-svaret innehåller en
  schema-giltig `routerDecision` (slow, kräver node/npm).
