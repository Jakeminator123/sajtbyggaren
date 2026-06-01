# GAP-viewser-wizard-pages-picker — Tab 3 till sidor-picker: stora klickbara sidkort istället för dolda funktioner

- id: `GAP-viewser-wizard-pages-picker`
- type: `Gap/UI`
- owner: `christopher`
- reviewer: `jakob`
- status: `queued`
- collisionRisk: `green`
- createdAt: `2026-05-26T18:14:54Z`
- updatedAt: `2026-05-26T18:14:54Z`

## Why now

Operatorn 2026-05-26 efter popup-revision v2: 'Detta måste bli lättare. För svårt att förstå hur man ska kryssa i olika sidor som ska skapas.' Nuvarande tab 3 visar en statisk 'VALDA FUNKTIONER'-chip-summary som ser klickbar ut men inte är det, plus två gömda disclosures där man faktiskt kryssar i FUNKTIONER (FAQ, kontaktformulär, kundvagn) istället för sidor. Operatorn vill se sidor som hemsidan ska ha och kunna toggla dem direkt. Funktioner härleds automatiskt via pageMustHave-länken som redan finns i FUNCTION_GROUPS.

## Paths

- `apps/viewser/components/discovery-wizard/steps/functions-step.tsx`

## Do not touch

- `apps/viewser/components/discovery-wizard/wizard-payload.ts`
- `apps/viewser/components/discovery-wizard/wizard-constants.ts`
- `packages/generation/**`

## Acceptance criteria

- Tab 3 visar 15 sidor som stora klickbara kort i ett 2/3-kolumns rutnät
- Hela kortet är klickbart med tydlig markerad/avmarkerad state (Check-ikon på markerade)
- togglePage(page) togglar både mustHave OCH motsvarande selectedFunctions-id om pageMustHave-länken finns
- Auto-apply familjens rekommenderade sidor + funktioner vid family-byte när inget redan är förvalt
- Primar CTA + finjustering + speciallaper finns kvar bara i Mer information-popupens Avancerat-flik
- Backend-payload (mustHave + selectedFunctions) oförändrat — wizard-payload.ts rörs inte
- Lint, typecheck och term-coverage rena

## Checks

- `cd apps/viewser && npm run lint`
- `cd apps/viewser && npx tsc --noEmit`
- `python scripts/check_term_coverage.py --strict`
