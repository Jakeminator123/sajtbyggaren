# GAP-viewser-mobile-responsive-polish — Mobil-anpassning fas 2 — polish + P1 (tap-targets, iOS-zoom, dialogs)

- id: `GAP-viewser-mobile-responsive-polish`
- type: `Gap/UI`
- owner: `christopher`
- reviewer: `jakob`
- status: `queued`
- collisionRisk: `green`
- createdAt: `2026-05-26T09:01:46Z`
- updatedAt: `2026-05-26T09:01:46Z`

## Why now

Fas 1 (PR #117) levererade mobil-foundation + 5 P0-blockers. Fas 2 polerar de återstående ~10 P1-friktionerna från audit 2026-05-26: tap-targets under 44px, text-[13px]/[15px] inputs som triggar iOS Safari auto-zoom, dialoger med för täta grids på smala viewports, hero-typografi som dominerar mobil-canvas, och ConsoleDrawer-listor med fasta höjder.

## Paths

- `apps/viewser/components/prompt-builder.tsx`
- `apps/viewser/components/viewer-panel.tsx`
- `apps/viewser/components/console-drawer.tsx`
- `apps/viewser/components/discovery-wizard/steps/step-primitives.tsx`
- `apps/viewser/components/discovery-wizard/asset-dropzone.tsx`
- `apps/viewser/components/discovery-wizard/directives-preview.tsx`
- `apps/viewser/components/discovery-wizard/ai-image-generator-dialog.tsx`
- `apps/viewser/components/builder/dialogs/asset-uploader-dialog.tsx`
- `apps/viewser/components/builder/dialogs/color-picker-dialog.tsx`
- `apps/viewser/components/builder/inspector/quick-prompt-button.tsx`

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
- `apps/viewser/components/builder/floating-chat.tsx`
- `apps/viewser/components/builder/builder-actions.tsx`
- `apps/viewser/components/builder/inspector/site-inspector-sheet.tsx`
- `apps/viewser/components/discovery-wizard/discovery-wizard.tsx`
- `apps/viewser/components/discovery-wizard/payload-alignment-popover.tsx`
- `apps/viewser/components/discovery-wizard/steps/visual-step.tsx`
- `apps/viewser/components/discovery-wizard/steps/content-step.tsx`
- `apps/viewser/components/ui/sheet.tsx`
- `apps/viewser/components/layout/site-header.tsx`
- `apps/viewser/app/globals.css`

## Acceptance criteria

- PromptBuilder textarea text-base sm:text-[15px] + submit min-tap.
- InlineHelpButton min-tap mobile, sm:h-4 sm:w-4 desktop.
- ViewerPanel hero H1 text-3xl sm:text-4xl + padding px-5 sm:px-12 lg:px-20.
- AI image generator dialog: grid-cols-1 sm:grid-cols-2 + min-tap.
- Asset uploader: grid-cols-2 sm:grid-cols-3 + min-tap.
- Color picker: grid-cols-4 sm:grid-cols-6 + min-tap.
- ConsoleDrawer RunHistory max-h-[40dvh] istället för h-[26rem].
- AssetDropzone upload-knapp min-tap + drop-area pb-safe.
- DirectivesPreview Copy min-tap.
- QuickPromptButton min-tap.
- Inga off-limits-paths rörda (inklusive alla fas 1-paths).

## Checks

- `python scripts/sprintvakt_check.py`
- `python scripts/focus_check.py`
- `python scripts/governance_validate.py`
- `python scripts/rules_sync.py --check`
- `python scripts/check_term_coverage.py --strict`
- `cd apps/viewser && npx tsc --noEmit`
- `cd apps/viewser && npm run lint`
- `python -m pytest -q tests/`
