# GAP-viewser-wizard-assets-tab — Lägg till fjärde wizard-tab 'Bilder' — logo + mediamaterial får egen tab

- id: `GAP-viewser-wizard-assets-tab`
- type: `Gap/UI`
- owner: `christopher`
- reviewer: `jakob`
- status: `queued`
- collisionRisk: `green`
- createdAt: `2026-05-26T18:18:22Z`
- updatedAt: `2026-05-26T18:18:22Z`

## Why now

Operatorn 2026-05-26 efter pages-picker-revisionen: 'Gör så att det är fyra tabbar där den fjärde är bilderna som idag ligger i tab 3.' Tab 3 (Funktioner) blev oklar när sidor-pickern och AssetsStep delade samma yta. Att bryta ut bilder till en egen tab gör tab 3 100% sidor och ger uppladdning en tydlig hemvist. 'Mer information'-knappen flyttas samtidigt till den nya sista tabben så den syns precis innan 'Skapa sajt' — vilket var operatorens ursprungliga önskemål.

## Paths

- `apps/viewser/components/discovery-wizard/wizard-types.ts`
- `apps/viewser/components/discovery-wizard/discovery-wizard.tsx`

## Do not touch

- `apps/viewser/components/discovery-wizard/wizard-payload.ts`
- `packages/generation/**`

## Acceptance criteria

- WIZARD_STEP_ORDER har 4 steg: foundation/visual/functions/assets
- WIZARD_STEP_TITLES['assets'] = 'Bilder'
- Tab 4 (Bilder) renderar AssetsStep + 'Mer information'-knappen
- Tab 3 (Funktioner) renderar BARA FunctionsStep (sidor-pickern), inget annat
- validateWizardStep('assets', ...) returnerar null — bilder är skip-bara
- Backend-payload oförändrat
- Lint, typecheck och term-coverage rena

## Checks

- `cd apps/viewser && npm run lint`
- `cd apps/viewser && npx tsc --noEmit`
- `python scripts/check_term_coverage.py --strict`
