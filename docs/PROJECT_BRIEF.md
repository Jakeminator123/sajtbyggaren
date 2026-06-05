# Sajtbyggaren - Project Brief

## Vad

Sajtbyggaren bygger företagshemsidor åt småföretagare på en kvalitet som
siktar på `~9.0/10` enligt
[`page-quality-traits.v1.json`](../governance/policies/page-quality-traits.v1.json)
(worldclass-lite: stark business-tydlighet och teknisk korrekthet, även om vi
ännu inte siktar på wow-design-prisnivå).

Den korta produktkompassen för dagligt agentarbete finns i
[`docs/product-operating-context.md`](product-operating-context.md). Den låser
kärnflödet: `prompt -> företagshemsida -> preview -> följdprompt -> ny version`.

## Varför

Vi bygger om `Jakeminator123/sajtmaskin` (referensbranch `master`) eftersom det gamla repot blev för spritt, för många namnskuggor och svår att styra. Detaljerad bedömning i [`docs/migration-plan.md`](migration-plan.md) och i de externa utlåtandena som låg under `referens/utlatanden/` (borttaget i #191, finns i git-historiken).

## Hur

Tre lager, tre regler:

1. **Governance JSON är sanningskälla.** Allt annat härleds från `governance/`.
2. **`backoffice.py` är Streamlit-backoffice för operatören.** Inte i användarens runtime.
3. **`packages/` + `apps/` är runtime.** PreviewRuntime-abstraktion med StackBlitz först, EN quality gate.

## Vad detta brief INTE är

- Inte en prompt-katalog. Sådant bor i fas 1-policies eller scaffold-data.
- Inte en feature-lista. Vi bygger inkrementellt enligt [`migration-plan.md`](migration-plan.md).
- Inte ett designdokument. Visuella mål bor i `page-quality-traits.v1.json` och scaffold-varianter.

## Vad du ska läsa härnäst

- [`docs/agent-handbook.md`](agent-handbook.md) om du är agent eller medhjälpare.
- [`docs/architecture/system-overview.md`](architecture/system-overview.md) för att förstå lager och ägarskap.
- [`docs/architecture/llm-flow.md`](architecture/llm-flow.md) för fas 1-3.
- [`governance/decisions/`](../governance/decisions/) för varför arkitekturen ser ut så här.
