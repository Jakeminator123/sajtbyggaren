# GAP-viewser-wizard-popup-tabs-v2 — Wizard popup-revision: 5 smala flikar + ta bort Specialisering

- id: `GAP-viewser-wizard-popup-tabs-v2`
- type: `Gap/UI`
- owner: `christopher`
- reviewer: `jakob`
- status: `queued`
- collisionRisk: `green`
- createdAt: `2026-05-26T18:02:59Z`
- updatedAt: `2026-05-26T18:02:59Z`

## Why now

Operatorn 2026-05-26: 'Varför specialisering? Ta bort? Gör pop-up smalare med mindre spacing på sidorna. Alternativt behåll bredden och flytta upp så att man inte behöver skrolla så mycket. Hellre fler steg/flikar och mindre att fylla i på varje än att man måste skrolla. Anpassa även för mobile.' Wizard-minimalism v1 lämnade kvar Specialiserings-disclosure och en bred popup där Innehåll-fliken blev för lång. Revisionen tar bort sub-specialisering helt (businessFamily räcker som scaffold-signal — backend faller redan tillbaka via branchForFamily) och delar popupen i fem smala flikar (Om oss / Innehåll / Kontakt / Media / Avancerat) med smalare bredd och horisontell tab-scroll på mobil.

## Paths

- `apps/viewser/components/discovery-wizard/more-info-dialog.tsx`
- `apps/viewser/components/discovery-wizard/steps/foundation-step.tsx`

## Do not touch

- `apps/viewser/components/discovery-wizard/wizard-payload.ts`
- `packages/generation/**`

## Acceptance criteria

- Specialiserings-disclosure med sub-kategori-chips finns inte längre i Foundation
- MoreInfoDialog har 5 flikar: Om oss / Innehåll / Kontakt / Media / Avancerat
- Popup-bredd <= 720px och tab-baren scrollar horisontellt på mobil
- Lint, typecheck och term-coverage rena

## Checks

- `cd apps/viewser && npm run lint`
- `cd apps/viewser && npx tsc --noEmit`
- `python scripts/check_term_coverage.py --strict`
