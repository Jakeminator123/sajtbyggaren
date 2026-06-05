# GAP-viewser-mobile-responsive-final-polish — Mobil-anpassning fas 3 — final polish (run-history, compare swipe, device-toggle, motion)

- id: `GAP-viewser-mobile-responsive-final-polish`
- type: `Gap/UI`
- owner: `christopher`
- reviewer: `jakob`
- status: `queued`
- collisionRisk: `green`
- createdAt: `2026-05-26T09:16:41Z`
- updatedAt: `2026-05-26T09:16:41Z`

## Why now

Fas 1 + fas 2 (PR #117) löste foundation + P0 + P1-polish. Fas 3 stänger UX-gap som krävde mer än CSS: run-history fast 416px (62% av 667px-skärm), compare-modal staplar A över B på mobil (jämförelse blir meningslös), viewer-panel saknar device-toggle på desktop, motion polish på edge-pulse + bottom-sheet.

## Paths

- `apps/viewser/components/run-history.tsx`
- `apps/viewser/components/builder/inspector/compare-preview-modal.tsx`
- `apps/viewser/components/viewer-panel.tsx`
- `apps/viewser/app/globals.css`

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

- RunHistory: h-[26rem] -> max-h-[50dvh] sm:h-[26rem].
- ComparePreviewModal: mobile swipe + snap-x + A/B-indikator-pills.
- ViewerPanel device-toggle desktop (375/768/1024/full) + sessionStorage.
- FloatingChat edge-pulse: ease-in-out 3s cycle.
- Bottom-sheet scale-in via existing data-starting-style.
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
