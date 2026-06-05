# GAP-viewser-mobile-scout-fixes — Scout-rapporterade P0+P1 buggar i mobil fas 1+2+3

- id: `GAP-viewser-mobile-scout-fixes`
- type: `Gap/UI`
- owner: `christopher`
- reviewer: `jakob`
- status: `queued`
- collisionRisk: `green`
- createdAt: `2026-05-26T09:53:14Z`
- updatedAt: `2026-05-26T09:53:14Z`

## Why now

Scout-run pa diff ea62e45^..8724798 hittade 3 P0 (pb-safe-or-3 saknas, wizard iOS-zoom, 20px steg-chips) + ~12 P1 (hydration, flash, keyboard, footer min-tap, ModePill, pill-desync, focus, inspector, mikro-kontroller, sm-zoom). Gor PR #117 merge-redo.

## Paths

- `apps/viewser/app/globals.css`
- `apps/viewser/components/discovery-wizard/discovery-wizard.tsx`
- `apps/viewser/components/discovery-wizard/steps/step-primitives.tsx`
- `apps/viewser/components/discovery-wizard/steps/content-step.tsx`
- `apps/viewser/components/discovery-wizard/steps/foundation-step.tsx`
- `apps/viewser/components/discovery-wizard/steps/company-step.tsx`
- `apps/viewser/components/viewer-panel.tsx`
- `apps/viewser/components/prompt-builder.tsx`
- `apps/viewser/components/builder/floating-chat.tsx`
- `apps/viewser/components/builder/inspector/site-inspector-sheet.tsx`
- `apps/viewser/components/builder/inspector/compare-preview-modal.tsx`
- `apps/viewser/components/builder/dialogs/color-picker-dialog.tsx`

## Do not touch

- `apps/viewser/app/api/**`
- `apps/viewser/lib/**`
- `apps/viewser/middleware.ts`
- `apps/viewser/next.config.ts`
- `apps/viewser/package.json`
- `apps/viewser/package-lock.json`
- `scripts/**`
- `packages/generation/**`
- `governance/schemas/**`

## Acceptance criteria

- P0 #1: .pb-safe-or-3 utility finns i globals.css.
- P0 #2: Alla wizard inputs kor text-base i mobile.
- P0 #3: Mobile steg-chips >=44px hit-area.
- P1 #4-14: alla scout-flaggade buggar atgardade.
- Inga off-limits-paths.

## Checks

- `python scripts/sprintvakt_check.py`
- `python scripts/focus_check.py`
- `python scripts/governance_validate.py`
- `python scripts/rules_sync.py --check`
- `python scripts/check_term_coverage.py --strict`
- `cd apps/viewser && npx tsc --noEmit`
- `cd apps/viewser && npm run lint`
- `python -m pytest -q tests/`
