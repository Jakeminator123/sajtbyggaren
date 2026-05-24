---
id: GAP-viewser-wizard-first-impression
type: Gap/UI
owner: christopher
title: Wizard första intryck — foundation + visual step som säljer "fantastisk sajt" på 5 sekunder
whyNow: |
  Wizarden är funktionellt komplett men de FÖRSTA INTRYCKEN är texttunga:
  foundation-steget öppnar med en URL-input + 8 text-only family-kort, och
  visual-steget visar små text-vibes-kort utan rik live-preview. Operatören
  ser inte "vad blir det här för sajt?" förrän slutet av wizarden. Den
  första interaktionen avgör om operatören tror att Sajtbyggaren kan göra
  något FANTASTISKT eller bara producerar en standard-sajt.

  Front 2:s uppdrag är att göra de första två stegen till en visuell teaser
  som direkt kommunicerar kvalitet och hastighet, UTAN att lägga till en
  enda byte text för operatören att läsa. Allt sker via rik visuell
  rendering av data som REDAN finns i wizard-state.

  KRITISKT — alignment-kontrakt: backend-prompten byggs av
  composeMasterPrompt() + deriveWizardDirectives() i wizard-payload.ts
  utifrån WizardAnswers. Denna gap ändrar INTE shape-en på WizardAnswers,
  payload eller någon backend-konsumerad funktion. Den lägger bara till
  visuella renderings-komponenter som DERIVER från existerande state.
  Resultatet: zero alignment-risk, zero ny backend-kommunikation, snabbare
  upplevd hastighet.

paths:
  # Primary (Christopher reserved — components/**):
  - apps/viewser/components/discovery-wizard/steps/foundation-step.tsx
  - apps/viewser/components/discovery-wizard/steps/visual-step.tsx
  - apps/viewser/components/discovery-wizard/visual-preview-card.tsx
  - apps/viewser/components/discovery-wizard/foundation-summary.tsx
  - apps/viewser/components/discovery-wizard/payload-alignment-popover.tsx

doNotTouch:
  # ALIGNMENT-KRITISKT — dessa filer ÄR kontraktet med backend.
  # Får ej röras i denna PR (lägger till nya WizardAnswers-fält = bryter
  # backend-kompabilitet och kräver Jakob-handoff):
  - apps/viewser/components/discovery-wizard/wizard-payload.ts
  - apps/viewser/components/discovery-wizard/wizard-types.ts
  - apps/viewser/components/discovery-wizard/wizard-constants.ts
  # Andra wizard-steg (utanför scope för denna sprint):
  - apps/viewser/components/discovery-wizard/steps/functions-step.tsx
  - apps/viewser/components/discovery-wizard/steps/content-orchestrator.tsx
  - apps/viewser/components/discovery-wizard/steps/media-step.tsx
  - apps/viewser/components/discovery-wizard/steps/content-step.tsx
  - apps/viewser/components/discovery-wizard/steps/company-step.tsx
  - apps/viewser/components/discovery-wizard/steps/pages-step.tsx
  - apps/viewser/components/discovery-wizard/steps/site-type-step.tsx
  - apps/viewser/components/discovery-wizard/steps/story-step.tsx
  - apps/viewser/components/discovery-wizard/steps/assets-step.tsx
  - apps/viewser/components/discovery-wizard/steps/brand-step.tsx
  # Jakob backend (consume-only — ingen ändring krävs):
  - packages/generation/**
  - governance/policies/**
  - scripts/**
  - tests/test_*.py

acceptanceCriteria:
  - Foundation-steg: varje FamilyCard visar (a) en 2-färgs swatch-rad med
    default-vibens primary+accent, (b) en mini hero-layout-glyph, (c)
    befintlig label + description. Detta är PURE rendering av existerande
    BUSINESS_FAMILIES.defaultVariantId → findVibe() → swatches — ingen ny
    state, ingen ny backend-kommunikation.
  - Foundation-steg: när businessFamily är vald + offer ifylld, visa en
    FoundationSummary-panel som transparency-tells operatören vad
    pipeline:n kommer få: scaffold-id, default-vibe, antal förvalda
    funktioner per family, branch, default typografi-känsla. Använder
    samma data som redan skickas till backend (RECOMMENDED_FUNCTIONS_BY_FAMILY,
    BUSINESS_FAMILIES, findVibe).
  - Visual-steg: VibeCard uppgraderas från textsnutt-kort till mini-sajt-
    preview-kort med (a) hero-mock (rubrik + 2 chips + knapp), (b)
    primary/accent/background-swatches inline, (c) typografi-preview ("Aa"
    i variantens font-stack). Större kort (höjd ~140px istället för ~70px).
  - Visual-steg: ContextChips-rad högst upp som visar "[Family]" →
    "[Scaffold]" → "[Default vibe]" där varje chip är klickbar (family =
    hoppa till foundation, vibe = behåll nuvarande val). Speglar exakt
    den signal som scaffoldHint + defaultVariantId skickar till backend.
  - Visual-steg: en PayloadAlignmentPopover ("ⓘ Vad backend får")
    tillgänglig från visual-steget som visar live det JSON-block som
    deriveWizardDirectives() returnerar (operativ-transparens — operatören
    förstår exakt vad som skickas).
  - Inga nya fält i WizardAnswers. Inga ändringar i wizard-payload.ts,
    wizard-types.ts eller wizard-constants.ts shape — bara nya
    rendering-komponenter som DERIVERAR från existerande state.
  - composeMasterPrompt() + deriveWizardDirectives() returnerar BYTE-
    IDENTISK output för samma WizardAnswers före/efter denna PR
    (bevisas av befintliga pytest-tester som matchar mot fixture-output).
  - Performance: foundation-steget öppnar instant (< 100ms render) trots
    rikare kort — använder useMemo för derived data och inline-SVG för
    glyphs (ingen extra HTTP, ingen ny font-load).

checks:
  - python scripts/sprintvakt_check.py
  - python scripts/governance_validate.py
  - python scripts/rules_sync.py --check
  - python scripts/check_term_coverage.py --strict
  - python -m ruff check .
  - python -m pytest tests/ -q
  - cd apps/viewser && npx tsc --noEmit
  - cd apps/viewser && npm run lint

collisionRisk: green
reviewer: jakob
status: queued
createdAt: 2026-05-25T01:47:00Z
updatedAt: 2026-05-25T01:47:00Z
notes:
  - Green collision risk — ALLA paths är inom Christophers
    components/**-reserved och INGEN av dem rör backend-konsumerade filer.
    Bevisas av att composeMasterPrompt/deriveWizardDirectives output förblir
    byte-identisk för samma answers-objekt.
  - Alignment-strategi: istället för att lägga till nya fält som backend
    ska konsumera (vilket skulle kräva Jakob-handoff + schema-bump),
    visualiserar denna gap EXISTERANDE state rikare. Backend ser oförändrad
    payload. Operatören ser fantastisk wizard.
  - Inga nya WizardAnswers-fält. Inga ändringar i payload-builders. Inga
    ändringar i payload-shape. Allt är ren visuell uplift av befintlig
    information.
  - PayloadAlignmentPopover använder den existerande
    `deriveWizardDirectives` exporten — den anropas read-only och resultatet
    JSON-stringifieras till tooltipen. Detta är extra alignment-säkert
    eftersom popover:n visar EXAKT det som skickas vid submit.
---

## Implementation outline

### A. FamilyCard upgrade (foundation-step.tsx)

Lyft befintlig family-card-rendering till en `FamilyCard`-funktion
internt i foundation-step.tsx (eller ny visual-preview-card.tsx). Lägg
till:

- 2-färgs swatch-rad ovanför label, läser från
  `findVibe(family.defaultVariantId)` → `primarySwatch + accentSwatch`.
- Hero-layout-glyph (återanvänd den befintliga `HeroLayoutGlyph` från
  visual-step.tsx — lyft den till delad fil `visual-preview-card.tsx`).

### B. FoundationSummary-panel (ny: foundation-summary.tsx)

Visas när `businessFamily` + `offer` är ifyllda. Rendrar:

- Scaffold: `family.scaffoldHint` (samma värde som skickas i
  `directives.scaffoldHint`).
- Default vibe: `findVibe(family.defaultVariantId).label` + swatches.
- Default typografi: `findVibe(family.defaultVariantId).defaultTypographyFeel`.
- "Vi förvaljar N funktioner" — räknar
  `RECOMMENDED_FUNCTIONS_BY_FAMILY[family.id].length`.
- "Branch: `branchForFamily(family.id)`" — speglar samma värde som
  skickas i `discovery.contentBranch`.

Hela panelen är read-only, ren rendering av derived data.

### C. VibeCard upgrade (visual-step.tsx)

Befintlig `VibeCard` (linje 580 i visual-step.tsx) växer från ~70px
band-kort till ~140px micro-sajt-preview-kort:

- Hero-mock: rubrik (variantens label), 2 chips (Boka/Nyhet), en knapp.
- Primary/accent/background-swatches inline.
- Typografi-preview ("Aa" i variantens font-stack via
  `typographyPreviewFamily()`).

### D. ContextChips (visual-step.tsx)

Tunn chip-rad högst upp i visual-steget:

- `[Family-label]` → klick = hoppa till foundation (via prop callback).
- `[Scaffold-hint]` → readonly chip.
- `[Default vibe]` → readonly chip.

Renderar bara om `businessFamily` är vald. Speglar exakt den signal
som skickas via `directives.scaffoldHint`.

### E. PayloadAlignmentPopover (ny: payload-alignment-popover.tsx)

En liten "ⓘ Vad backend får" knapp i hörnet av visual-steget. Klick
öppnar popover med:

- `directives.scaffoldHint`
- `directives.variantHint`
- `directives.tone`
- `directives.brand`
- `directives.layoutHint`

Anropar `deriveWizardDirectives(initialPrompt, answers, scaffoldHint)`
read-only och JSON.stringify:ar resultatet. När wizard ändras
uppdateras popover-innehållet automatiskt (useMemo på `answers`).

### F. Verification

- Existerande pytest-suite kör mot composeMasterPrompt + deriveWizardDirectives
  → om output ändras bryts tester (alignment-guarantee).
- `npx tsc --noEmit` fångar shape-drift.
- `npm run lint` fångar hook-rule violations.
- Manuell smoke: öppna wizarden, byt mellan families, observera att
  FoundationSummary uppdateras live; öppna visual-steget, byt mellan
  vibes, observera att VibeCard har rikare preview.
