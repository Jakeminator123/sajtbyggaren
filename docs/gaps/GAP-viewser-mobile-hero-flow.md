# GAP-viewser-mobile-hero-flow

```yaml
id: GAP-viewser-mobile-hero-flow
type: Gap/UI
owner: christopher
title: Mobil hero - stacked layout med SM-mobile.mp4 som top-banner
whyNow: |
  Manuell test på iPhone 14 Pro-viewport (393x852) i Safari Responsive
  Design Mode visade tre fynd som scout-rapporten inte täckte:

  1. SM_hero.mp4 har object-position 78% (designat för desktop bredd) →
     3D-objektet hamnar bakom rubriken på mobil.
  2. Hero-rubriken har hårdkodad `<br />` + `max-w-lg` → radbryts till
     "Beskriv / din sajt / så bygger / vi den" på 393px.
  3. Hela hero känns inte som ett naturligt flöde på mobil (video, text,
     composer konkurrerar om utrymmet i samma absolut-positioned canvas).

  Operatören har levererat SM-mobile.mp4 (960x960 fyrkantig, 1.1MB,
  off-white bakgrund #f0f2ed) som är designad för mobil top-banner.

paths:
  - apps/viewser/components/viewer-panel.tsx
  - apps/viewser/public/SM-mobile.mp4
  - apps/viewser/components/discovery-wizard/wizard-types.ts

doNotTouch:
  - apps/viewser/app/api/**
  - apps/viewser/lib/**
  - apps/viewser/middleware.ts
  - apps/viewser/next.config.ts
  - apps/viewser/package.json
  - scripts/**
  - packages/generation/**

acceptanceCriteria:
  - "Mobil (<md): SM-mobile.mp4 renderas som top-banner (fyrkantig, centrerad)."
  - "Mobil hero-bakgrund matchar videons bakgrundsfärg (#f0f2ed) så video flyter in i bakgrunden."
  - "Mobil hero-text under videon, ingen överlapp med 3D-objektet."
  - "Hero-rubrik radbryts naturligt utan hårdkodad br på mobil."
  - "Desktop (md+): oförändrat (SM_hero.mp4 + 78% object-position + overlay-text)."
  - "Wizard foundation-validering: företagsnamn-min-längd borttagen på operatör-begäran."

checks:
  - python scripts/sprintvakt_check.py
  - python scripts/focus_check.py
  - python scripts/governance_validate.py
  - python scripts/rules_sync.py --check
  - python scripts/check_term_coverage.py --strict
  - cd apps/viewser && npx tsc --noEmit
  - cd apps/viewser && npm run lint

note: |
  Effort ~1h. Samma branch + PR #117 (fortfarande in-review).
```
