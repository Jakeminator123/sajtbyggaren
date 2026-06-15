# ADR 0003: PreviewRuntime-abstraktion med StackBlitz först

- Status: superseded av 0033 (StackBlitz-först-valet omkört: vercel-sandbox är nu primär preview, stackblitz pausad). Abstraktionen denna ADR införde lever vidare — 0030/0033 bygger på den.
- Datum: 2026-05-07

## Kontext

Sajtmaskin lät runtime-implementationen ($preview\_host$ via Fly.io) lysa igenom hela produkten. Termer som `VM`, `sandbox`, `preview-host`, `webcontainer`, `vercelSandbox` användes om vartannat. F2- och F3-tier för quality gate gjorde verifieringen krånglig och svår att resonera om.

Sajtbyggaren behöver kunna iterera snabbt i utveckling utan VM-kostnad, men ändå kunna köra en mer produktionslik miljö när det krävs.

## Beslut

- Det finns ett **interface** `PreviewRuntime` (skissas i `packages/preview-runtime/` när den fasen börjar) med implementationerna `StackBlitzRuntime`, `FlyRuntime`, `LocalRuntime`.
- Default är **StackBlitz**. `FlyRuntime` används bara när eval-batchen visar att StackBlitz inte räcker (t.ex. tier-3 SDK:er, Stripe, DB-integrationer).
- Det finns **EN** quality gate, inte F2 och F3. Om en check (typecheck/build/route-scan/preview-smoke) skippas måste det loggas som `degraded` i version-meta.
- Termer som `VM`, `sandbox`, `preview-host`, `webcontainer`, `vercelSandbox`, `tier1`, `tier2`, `tier3` är `globallyForbidden` i naming-dictionary och `forbiddenTerms` i preview-runtime-policy.

## Konsekvenser

- `apps/`, `packages/generation/`, `packages/builder/` får inte nämna `Fly` eller `StackBlitz` direkt. De talar bara med `PreviewRuntime`.
- Att byta runtime är ett konfigurationsval, inte en arkitekturändring.
- Sajtmaskins F2/F3-spagetti återinförs inte. Om quality gate behöver mer finkornighet måste en ny policy-version dokumentera det.
