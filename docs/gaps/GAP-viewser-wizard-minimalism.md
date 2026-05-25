---
id: GAP-viewser-wizard-minimalism
type: Gap/UI
owner: christopher
title: Wizard minimalism — progressive disclosure av all sekundär text, metadata och fallback-fält
whyNow: |
  Wizarden har under Pass 1–5 + Front 2 vuxit i visuell rikedom: Vibe-
  preview-kort, FoundationSummary-transparens, ContextChips,
  PayloadAlignmentPopover, DirectivesPreview, hjälp-texter under varje
  fält, tips-rader, dubbel header-badge (eyebrow + pipeline-badge),
  och en "Designstil (fallback om vibe ej valts)"-sektion som visas
  även när vibe redan är valt.

  Resultatet är att VARJE steg har 2–4 rader prosa innan första fältet
  och 1–2 rader helper-text under varje fält. För en operatör som vet
  vad hen vill skapas brus; för en första-gångs-operatör är det
  fortfarande mycket att skanna. Användarens explicit feedback:
  "wizard ska vara minimalistisk och inte massa onödiga alternativ
  eller text som inte kan ligga bakom en minimering-pil".

  Lösningen är PROGRESSIVE DISCLOSURE av all sekundär information:
  HelperText flyttas bakom en info-ikon ("?") per fält, transparens-
  block (FoundationSummary, ContextChips, DirectivesPreview) wrappas
  i en collapsible MetadataPanel, dubbel-badge i header trimmas till
  en, fallback-sektioner döljs villkorligt, och step-descriptions
  kortas till en mening. Inga fält tas bort — bara renderingen av
  ledtext och metadata blir collapsible eller villkorlig.

  Alignment-säker: vi rör INTE wizard-payload.ts, wizard-types.ts,
  wizard-constants.ts, composeMasterPrompt eller deriveWizardDirectives.
  Backend ser exakt samma data. Det är bara UI-rendering som ändras.

paths:
  # Primary (christopher reserved — components/discovery-wizard/**):
  - apps/viewser/components/discovery-wizard/discovery-wizard.tsx
  - apps/viewser/components/discovery-wizard/steps/step-primitives.tsx
  - apps/viewser/components/discovery-wizard/steps/foundation-step.tsx
  - apps/viewser/components/discovery-wizard/steps/visual-step.tsx
  - apps/viewser/components/discovery-wizard/steps/functions-step.tsx
  - apps/viewser/components/discovery-wizard/steps/content-orchestrator.tsx
  - apps/viewser/components/discovery-wizard/steps/content-step.tsx
  - apps/viewser/components/discovery-wizard/steps/media-step.tsx
  - apps/viewser/components/discovery-wizard/foundation-summary.tsx

doNotTouch:
  # ALIGNMENT-KRITISKT — inga ändringar i wizard-kontrakten:
  - apps/viewser/components/discovery-wizard/wizard-payload.ts
  - apps/viewser/components/discovery-wizard/wizard-types.ts
  - apps/viewser/components/discovery-wizard/wizard-constants.ts
  # Backend-ägt (jakob jakob-be):
  - packages/generation/**
  - governance/policies/**
  - scripts/**
  - tests/test_*.py

acceptanceCriteria:
  - Wizard-header visar bara en badge per steg (eyebrow ELLER pipeline,
    inte båda) — pipeline-badge flyttas in i en discrete metadata-rad
    eller tas bort till förmån för eyebrow.
  - Step-description i header är max en mening (kort, action-orienterad).
    Längre förklaringar flyttas till en info-ikon ("?") bredvid titeln
    som expanderar en popover med fullständig text.
  - Per fält: HelperText bakom en CollapsibleHelp-primitiv (info-ikon
    next to label, click expanderar inline). Default: bara label + fält
    syns. Vissa kritiska helper-texter (t.ex. URL-scrape-instruktionen)
    behålls synliga av upptäckbarhetsskäl.
  - FoundationSummary (steg 1) wrappas i en collapsible MetadataPanel
    med titel "Vad backend kommer att göra" — default kollapsad.
  - ContextChips (steg 2) wrappas i samma MetadataPanel-mönster så
    visuellt brus reduceras.
  - "Designstil (fallback om vibe ej valts)" i visual-step renderas
    BARA när answers.vibe.vibeId === "" — om vibe är valt är sektionen
    onödig.
  - Tips-rader (t.ex. hex-färg-tipset) flyttas bakom CollapsibleHelp
    eller tas bort om de duplicerar information från andra fält.
  - Demo-knappen i wizard-footer dämpas (mindre, ikon-tung istället
    för text-tung) så den inte konkurrerar med primärknappen "Skapa
    sajt".
  - SectionCard-descriptions i content-orchestrator kortas till en
    mening. Längre förklaringar flyttas bakom CollapsibleHelp.
  - Top-helper i media-step ("Alla bilder är valfria…") flyttas in
    i en MetadataPanel ELLER tas bort eftersom assets-step internt
    visar samma info.
  - INGA ändringar i wizard-payload.ts, wizard-types.ts, wizard-
    constants.ts shape — alignment garanteras by-construction.
  - Befintliga pytest-tester för composeMasterPrompt +
    deriveWizardDirectives förblir gröna utan ändring.
  - Befintliga keyboard shortcuts, validering, focus-management och
    auto-default-beteenden bevaras oförändrade.

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
createdAt: 2026-05-25T02:11:00Z
updatedAt: 2026-05-25T02:11:00Z
notes:
  - Pure UI-feature. Inga ändringar i wizard-kontrakten — backend
    ser exakt samma data oavsett om operatören expanderar
    CollapsibleHelp eller inte.
  - Två nya primitiver (CollapsibleHelp + MetadataPanel) läggs till
    step-primitives.tsx och används konsekvent i alla 5 stegen.
  - Aktiverar inga nya wizard-fält. Alla fält som var synliga förut
    finns kvar — de kanske bara är placerade bakom en disclosure
    eller infoikon. Validering, persistens och pipeline-output
    påverkas inte.
  - Cross-cutting karaktär: rör 9 filer men varje ändring är liten
    (HelperText → CollapsibleHelp, transparens → MetadataPanel,
    villkorlig rendering, badge-trim).
---

## Implementation outline

### A. step-primitives.tsx (nya primitiver)

`CollapsibleHelp({ children })` — liten info-ikon ("Info" från
lucide-react eller "?"-glyph) placerad inline efter `FieldLabel`-
text. Click → expanderar inline en `<HelperText>`-stiliserad
paragraf under fältet. Default: dold. Använder `useState(open)`,
inga effekter, inga refs.

`MetadataPanel({ title, hint, children, defaultOpen=false })` —
collapsible wrapper för transparens-block (FoundationSummary,
ContextChips, etc.). Header: titel + chevron, ingen badge-count
(eftersom barnen är dekorativa, inte räknade fält). Click →
expanderar med smooth transition (matchar AdvancedDisclosure-
visuellt).

`MinimalSectionHeader({ children, info? })` — variant av
`SectionHeader` som tar en optional `info`-prop för inline
CollapsibleHelp. Behåller textstilen men dropper auto-margins
som kollidera med MetadataPanel-titlar.

### B. discovery-wizard.tsx (wizard chrome)

- Header: ta bort `WIZARD_STEP_PIPELINE_BADGE`-renderingen från
  badge-raden. Behåll bara eyebrow-pillet. Pipeline-info syns
  fortfarande för power-users via sidebar (där varje steg har
  sin numrering — pipeline-mappning är dokumenterad i
  rules/handoff.md).
- DialogDescription: korta till en mening (max ~10 ord). Längre
  förklaring → flytta in i info-popover eller ta bort.
- Demo-knapp: ikon + "Demo" istället för "Sparkles + Fyll demo".
  Mindre padding, opacity-reducerad så den signalerar dev-tool.

### C. foundation-step.tsx

- URL-scrape: behåll synlig (primär shortcut) men korta
  HelperText till "Auto-fyller alla fält." Längre förklaring →
  CollapsibleHelp.
- "Vad gör ni?" helper "1–2 meningar räcker…" → CollapsibleHelp
  eller placeholder-only.
- Verksamhetsfamilj: korta SectionHeader-helper till en mening.
- FoundationSummary: wrappa i `MetadataPanel` med titel "Så här
  tolkar vi dina val" och default-collapsed.
- AdvancedDisclosure "Specialisering & kontakt": behåll (är redan
  rätt mönster).

### D. visual-step.tsx

- ContextChips: wrappa i `MetadataPanel` med titel "Foundation-
  beslut som styr detta steg".
- Vibe-sektion: korta HelperText (en mening).
- Tonarter: korta HelperText.
- "Designstil (fallback om vibe ej valts)": render BARA när
  `answers.vibe.vibeId === ""`. Med vibe vald är den onödig.
- Inom AdvancedDisclosure "Designdetaljer": korta hex-tips-rad
  → CollapsibleHelp eller ta bort.

### E. functions-step.tsx

- Primär CTA: korta HelperText.
- AdvancedDisclosure-helpers: behåll (de förklarar vad som
  finns inuti).

### F. content-orchestrator.tsx

- SectionCard-descriptions: korta till en mening (eller flytta
  längre prosa till CollapsibleHelp).

### G. content-step.tsx (branch-specific)

- Korta HelperText för Produkter, Meny, Projekt, USP:er — alla
  till en mening + CollapsibleHelp för längre instruktioner.

### H. media-step.tsx

- Top-helper-block ("Alla bilder är valfria…"): flytta in i
  en MetadataPanel eller ta bort eftersom AssetsStep internt har
  samma info.
- AssetCard descriptions: korta till en mening där det är möjligt.

### I. foundation-summary.tsx

- Komponenten själv ändras INTE (förutom ev. layout-trim om det
  förbättrar visning inuti MetadataPanel). Den wrappas externt
  i foundation-step.tsx.

### J. Verification

- Manual: öppna wizarden, gå igenom alla 5 steg, verifiera att:
  * Header har max en badge per steg
  * Varje fält har max ett label + fält i default-state
  * Info-ikoner expanderar/kollapsar korrekt
  * MetadataPanel:erna är default-collapsed
  * Keyboard shortcuts fungerar oförändrade
- Quality guards: alla tester (inkl. wizard-payload + pipeline)
  förblir gröna.
