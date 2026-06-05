# GAP-viewser-wizard-minimal-tabs — Wizard total-minimalism: 3-tabs överst + 'Mer information'-popup med scaffold-aware flikar

- id: `GAP-viewser-wizard-minimal-tabs`
- type: `Gap/UI`
- owner: `christopher`
- reviewer: `jakob`
- status: `queued`
- collisionRisk: `green`
- createdAt: `2026-05-26T16:59:15Z`
- updatedAt: `2026-05-26T16:59:15Z`

## Why now

Operatör-feedback efter 5-stegs-konsolidering: wizard fortfarande för rörig. Vill ha total minimalism — färre frågor synliga, skrap-driven bakgrundsifyllning, popup för djupare info istället för tvingande steg. Backend-payload (validateWizardStep, buildDiscoveryPayload) ändras INTE — bara UI omgrupperar samma svar.

## Paths

- `apps/viewser/components/discovery-wizard/discovery-wizard.tsx`
- `apps/viewser/components/discovery-wizard/wizard-types.ts`
- `apps/viewser/components/discovery-wizard/more-info-dialog.tsx`
- `apps/viewser/components/discovery-wizard/steps/foundation-step.tsx`
- `apps/viewser/components/discovery-wizard/steps/visual-step.tsx`
- `apps/viewser/components/discovery-wizard/steps/functions-step.tsx`
- `apps/viewser/components/discovery-wizard/steps/media-step.tsx`
- `apps/viewser/components/discovery-wizard/steps/content-orchestrator.tsx`

## Do not touch

- `scripts/`
- `packages/generation/`
- `schemas/`
- `docs/governance/`
- `tests/`
- `apps/viewser/app/api/`
- `apps/viewser/components/discovery-wizard/wizard-payload.ts`

## Acceptance criteria

- WIZARD_STEP_ORDER reducerad från 5 till 3 (foundation, visual, functions)
- Tabs visas högst upp istället för sidebar (desktop + mobile)
- Inga proaktiva tips/varningar synliga som default - bara på fel eller info-ikon
- 'Mer information'-knapp på tab 3 öppnar popup med scaffold-aware flikar
- Popup återanvänder content+media-fält och påverkar inte buildDiscoveryPayload-shape
- Logo + mediamaterial uppladdning behålls på tab 3 (functions), favicon/ogImage/backgroundVideo flyttas till popup
- GPT Vision auto-pick av hero från mediamaterial fungerar (Commit 3)
- Manuell skip från valfri tab tillåts (inga hard-requirements utöver foundation min-validering)
- Lint, typecheck, term-coverage --strict passerar

## Checks

- `npm -w @sajtbyggaren/viewser run lint`
- `npm -w @sajtbyggaren/viewser run typecheck`
- `python scripts/check_term_coverage.py --strict`
