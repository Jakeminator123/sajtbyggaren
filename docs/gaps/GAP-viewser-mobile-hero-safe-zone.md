# GAP-viewser-mobile-hero-safe-zone — Scout pass 4 P1-fixar: hero safe zone, wizard asterisk, prompt-builder safe-area

- id: `GAP-viewser-mobile-hero-safe-zone`
- type: `Gap/UI`
- owner: `christopher`
- reviewer: `jakob`
- status: `completed`
- collisionRisk: `green`
- createdAt: `2026-05-26T10:52:20Z`
- updatedAt: `2026-05-26T22:30:00Z`
- completedAt: `2026-05-26T13:19:16Z`
- fixCommits: `1740472`

## Why now

Scout-bug-hunt pass 4 (composer-2.5-fast, read-only) paa christopher-ui-branchen hittade tre P1-fynd som maaste fixas innan PR #117 mergas: (1) Hero-text taecks av PromptBuilder paa iPhone SE 375x667 (video ~300px + text ~200px + composer ~150px laemnar ingen marginal). (2) Wizard Foeretagsnamn-asterisk visas men validation togs bort i 59eed4c WCAG 2.2-brott. (3) PromptBuilder saknar pb-safe knappar ligger naera iPhone home-indicator. Inga P0. P1 nummer 4 StackBlitz containerRef skippas eftersom default-mode local-next inte paaverkas.

## Paths

- `apps/viewser/components/viewer-panel.tsx`
- `apps/viewser/components/discovery-wizard/steps/foundation-step.tsx`
- `apps/viewser/components/discovery-wizard/steps/company-step.tsx`
- `apps/viewser/components/prompt-builder.tsx`

## Do not touch

- `apps/viewser/components/discovery-wizard/wizard-types.ts`
- `apps/viewser/app/globals.css`
- `packages/generation/`
- `apps/viewser/app/api/`
- `apps/viewser/lib/`

## Acceptance criteria

- Mobil 375x667: hero-text scrollas och hamnar aldrig bakom PromptBuilder
- viewer-panel mobil anvaender overflow-y-auto naer showHero=true
- Hero-text container har pb-40 paa mobil saa composer-overlap aldrig sker vid normal text
- Desktop md+ behaaller absolute-overlay-layout med overflow-hidden
- Wizard foundation-step + company-step visar Foeretagsnamn utan asterisk (optional-prop visar 'valfritt' via FieldLabel)
- PromptBuilder composer anvaender pb-safe-or-4 sm:pb-7 saa iPhone X+ home-indicator respekteras

## Completion note

Verifierat 2026-05-26 mot origin/jakob-be: fixen finns i PR #118-squashen
`1740472` och kodläget uppfyller acceptanskriterierna.

## Checks

- `sprintvakt_check`
- `focus_check`
- `viewser_typecheck`
- `viewser_lint`
- `term_coverage_strict`
- `ruff_check`
