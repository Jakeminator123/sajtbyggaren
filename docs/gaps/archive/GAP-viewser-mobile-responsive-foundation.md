# GAP-viewser-mobile-responsive-foundation — Mobil-anpassning av viewser-appen — foundation + P0-blockers

- id: `GAP-viewser-mobile-responsive-foundation`
- type: `Gap/UI`
- owner: `christopher`
- reviewer: `jakob`
- status: `queued`
- collisionRisk: `green`
- createdAt: `2026-05-26T08:36:28Z`
- updatedAt: `2026-05-26T08:36:28Z`

## Why now

Hela viewser-appen är desktop-first idag. Audit 2026-05-26 visade 5 P0-blockers som gör appen oanvändbar på 375px (iPhone SE). Operatören har bekräftat scope: hela viewser-flödet (wizard + builder), polished kvalitetsnivå. Denna GAP = foundation + P0; polish/P1 öppnas som separat GAP efter.

## Paths

- `apps/viewser/app/globals.css`
- `apps/viewser/components/builder/floating-chat.tsx`
- `apps/viewser/components/builder/builder-actions.tsx`
- `apps/viewser/components/builder/inspector/site-inspector-sheet.tsx`
- `apps/viewser/components/discovery-wizard/discovery-wizard.tsx`
- `apps/viewser/components/discovery-wizard/payload-alignment-popover.tsx`
- `apps/viewser/components/discovery-wizard/steps/visual-step.tsx`
- `apps/viewser/components/discovery-wizard/steps/content-step.tsx`
- `apps/viewser/components/ui/sheet.tsx`
- `apps/viewser/components/layout/site-header.tsx`

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

- Mobil-foundation i globals.css: safe-bottom/safe-top/safe-x + min-tap (44px).
- FloatingChat <768px = bottom-sheet (full bredd, max-h-[85dvh], pb-safe). Drag inaktiv touch. Minimerad = 56x56 FAB.
- FloatingChat composer text-base mobil — inget iOS-zoom.
- SiteInspectorSheet <768px = bottom-sheet (h-[90dvh] rounded-t-3xl). TabsList scrollable eller dropdown.
- Wizard validationError visas alltid på mobil.
- Hover-only delete på moodboard/content-bilder synlig på touch.
- PayloadAlignmentPopover max-w-[calc(100vw-2rem)] eller bottom-sheet under sm:.
- BuilderActions kolliderar inte med FloatingChat på mobil.
- site-header konsol-knapp har min-tap på mobil.
- Safe-area-padding på all fixed UI.
- sheet.tsx bottom-sheet får rounded-t-3xl + drag-handle + pb-safe.
- Inga off-limits-paths rörs.

## Checks

- `python scripts/sprintvakt_check.py`
- `python scripts/governance_validate.py`
- `python scripts/rules_sync.py --check`
- `python scripts/check_term_coverage.py --strict`
- `cd apps/viewser && npx tsc --noEmit`
- `cd apps/viewser && npm run lint`
- `python -m pytest -q tests/`
