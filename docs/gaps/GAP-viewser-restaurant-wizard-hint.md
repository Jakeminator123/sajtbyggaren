# GAP-viewser-restaurant-wizard-hint

```yaml
id: GAP-viewser-restaurant-wizard-hint
type: Gap/UI
owner: christopher
title: Wizard Restaurang/Café-familjen pekar mot restaurant-hospitality scaffold
whyNow: |
  Path A-aktivering av restaurant-hospitality (GAP-backend-restaurant-
  activation, owner=jakob) levererar runtime-stödet i resolve.py +
  build_site.py. Men om wizardens BUSINESS_FAMILIES[restaurant].
  scaffoldHint fortfarande pekar mot "local-service-business" (default
  idag) faller wizard-flödet ändå tillbaka till LSB i resolve_discovery.

  Detta GAP är den minimala UI-ändring som kompletterar backend-Path A
  så att en operatör som väljer Restaurang i wizard-foundation-step
  faktiskt får /meny + /bokning istället för /tjanster.

  Splittat från GAP-backend-restaurant-activation eftersom Sprintvakt-
  lane-policyn blockerar Jakob från apps/viewser/components/**. Båda
  GAPs landar i samma commit-batch men ägs separat enligt policy.
paths:
  - apps/viewser/components/discovery-wizard/wizard-constants.ts
doNotTouch:
  - apps/viewser/components/discovery-wizard/steps/**
  - apps/viewser/components/discovery-wizard/wizard-payload.ts
  - apps/viewser/components/discovery-wizard/wizard-types.ts
  - packages/generation/**
  - scripts/**
acceptanceCriteria:
  - "BUSINESS_FAMILIES[restaurant].scaffoldHint = 'restaurant-hospitality' i wizard-constants.ts."
  - "BUSINESS_FAMILIES[restaurant].defaultVariantId pekar på en variant som finns på disk för restaurant-hospitality."
  - "WIZARD_CATEGORIES[restaurant].scaffoldHint = 'restaurant-hospitality' så att FALLBACK_DISCOVERY_OPTIONS i discovery-options.ts pekar mot rätt scaffold innan governance-API svarar (parallellitet med BUSINESS_FAMILIES krävs av acceptance #1)."
  - "WIZARD_CATEGORIES[restaurant].defaultVariantId = 'warm-bistro' (matcha BUSINESS_FAMILIES + discovery-taxonomy.v1.json id='restaurant'.defaultVariantId)."
  - "Inga andra familjer eller kategorier ändrar scaffoldHint i samma commit."
  - "Wizard-payload-test (om finns) verifierar att restaurant-familjen producerar payload med scaffoldHint='restaurant-hospitality'."
checks:
  - python scripts/sprintvakt_check.py
  - python scripts/governance_validate.py
  - python scripts/check_term_coverage.py --strict
  - cd apps/viewser && npx tsc --noEmit
  - cd apps/viewser && npm run lint
note: |
  Effort: 30 min. Trivial 1-2 rads ändring som är blockerande för att
  GAP-backend-restaurant-activation ska ge operatör-synlig effekt.
  Måste landa i samma commit-batch som backend-aktiveringen.

  Follow-up 2026-05-25 (Phase 2-sprinten): den ursprungliga PR:en
  uppdaterade BARA BUSINESS_FAMILIES[restaurant]; den parallella
  WIZARD_CATEGORIES[restaurant] missades och pekade fortsatt mot
  local-service-business / nordic-trust. Det betydde att FALLBACK_-
  DISCOVERY_OPTIONS (som byggs av WIZARD_CATEGORIES.map() i
  discovery-options.ts) gav fel scaffold + variant innan governance-
  API:t hann svara. Fixet är en enrads-ändring under samma GAP.
```
