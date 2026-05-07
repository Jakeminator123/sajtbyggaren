# ADR 0008: Skjut upp baseline-eval och stora evals tills LLM-flödet finns

- Status: accepterat
- Datum: 2026-05-07
- Ersätter delvis: [ADR 0004](0004-migration-from-sajtmaskin-baseline.md)

## Kontext

Tidigare planerade vi en baseline-eval mot tre sajtmaskin-taggar (`ba33b28`, `1f4e869`, `04b3215`) som första runtime-steg, för att välja generation-bas. Användaren och en extern reviewer landade i samma slutsats: **evals fungerade dåligt i sajtmaskin** och blir falsk trygghet om de byggs innan vi har ett eget körbart LLM-flöde.

Det vi har nu är governance, backoffice och regression-tester som skyddar konsistens. Vi har **ingen egen genereringsmotor**, ingen dev runtime och ingen preview-kedja. Att mäta sajtmaskins versioner mot vår scorecard innan vi vet hur vår egen kedja beter sig ger inget meningsfullt jämförelsetal.

## Beslut

Implementationsordningen ändras:

1. Bygg fas 1 LLM-flödet först (Site Brief som CLI).
2. Bygg fas 2 orchestration (Scaffold, Variant, Route, Dossier, BuildSpec → Generation Package).
3. Bygg fas 3 codegen + finalize med en minimal `LocalRuntime` för utveckling.
4. Lägg en liten quality gate (4 checks: typecheck, route-scan, policy-check, manuellt 7-9/10-omdöme).
5. Portera enstaka idéer manuellt från sajtmaskin enligt [`docs/migration/import-log.md`](../../docs/migration/import-log.md).
6. Bygg större eval-batchar och eventuell sajtmaskin-baseline-jämförelse sist, när vi har 20-50 riktiga körningar i Sajtbyggaren att stå sig på.

PreviewRuntime-implementationsordning blir därför:

1. `LocalRuntime` först (utvecklarens egen Node, snabb felsökning).
2. `StackBlitzRuntime` när vi behöver delningsbar preview till operatör.
3. `FlyRuntime` när hard-Dossiers (Stripe, DB, riktiga env-värden) kräver det.

`preview-runtime-policy.v1.json:default` förblir `"stackblitz"` som **systemets långsiktiga default**, men vi börjar inte där.

## Konsekvenser

- ADR 0004 är fortfarande giltigt som referens, men dess steg 3 ("Baseline-eval") flyttas till efter att fas 1-3 finns.
- `tests/evals/baseline/` byggs inte än. `tests/evals/` har just nu bara regression-tester på governance.
- `scaffold-selection.v1.json:regressionTests` och `dossier-selection.v1.json:regressionTests` är fortfarande giltiga eftersom de testar vår egen kedja, inte sajtmaskin.
- Kandidat-commits i [`docs/migration/import-log.md`](../../docs/migration/import-log.md) listas som "kandidater att titta på senare", inte som mål för automatisk porting.

## Vad detta inte är

- Det är inte ett beslut att aldrig jämföra mot sajtmaskin. När vår egen Quality Gate finns, kör vi gärna samma prompt-batch mot sajtmaskins `1f4e869` och vår egen output för att se hur vi står oss.
- Det är inte ett beslut att skippa regression-tester. Tvärtom: governance-regression-testerna finns redan, och produktionsregression läggs till efter hand i `tests/evals/`.
