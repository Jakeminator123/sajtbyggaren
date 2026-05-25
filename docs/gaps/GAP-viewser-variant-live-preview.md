---
id: GAP-viewser-variant-live-preview
type: Gap/UI
owner: christopher
title: Live-preview switcher för scaffold-variants utan rebuild
whyNow: |
  PR #68 lade till 4 nya restaurant-variants (warm-bistro, nordic-fine-dining,
  casual-cafe, midnight-bar) + 4 nya LSB/ecommerce-variants. Totalt 18 variants
  finns på disk men användaren ser bara EN i preview åt gången, och måste
  vänta ~30 sekunder på ny build för att se hur sajten skulle kännas i en
  annan variant. Den första uppenbara vinsten på Week 1:s variant-investering
  är att exponera dem som live-switchable presets i Site Inspector — samma
  postMessage-broadcast-mönster som TokensTab redan använder för enskilda
  färger, fast nu för hela token-bundles (primary/accent/background/
  foreground + tone). Användaren får direkt visuell feedback på "hur skulle
  min sajt kännas som casual-cafe vs midnight-bar" utan att vänta på en
  build, och kan committa med ett vanligt follow-up-prompt när hen hittat
  rätt känsla. Detta är PLAYipp/Framer/Webflow-nivåns första kvalitetssignal.

paths:
  # Primary (Christopher reserved):
  - apps/viewser/components/builder/inspector/variants-tab.tsx
  - apps/viewser/components/builder/inspector/index.ts
  - apps/viewser/components/builder/inspector/site-inspector-sheet.tsx
  # Yellow (apps/viewser/lib/** — see gaps/README.md, additive-only):
  - apps/viewser/lib/runtime-tokens.ts
  # Yellow (apps/viewser/app/api/**/route.ts — additive shape extension):
  - apps/viewser/app/api/discovery-options/route.ts

doNotTouch:
  # Jakob backend ownership (read-only consumption of variant JSON via API):
  - packages/generation/**
  - governance/policies/**
  - scripts/**
  - tests/test_*.py
  # Existing variant JSON files — READ-ONLY consumption only:
  - packages/generation/orchestration/scaffolds/*/variants/*.json
  # Out-of-scope viewser surfaces:
  - apps/viewser/components/discovery-wizard/**
  - apps/viewser/components/builder/dialogs/variant-picker-dialog.tsx
  - apps/viewser/lib/build-runner.ts
  - apps/viewser/lib/prompt-runner.ts
  - apps/viewser/lib/asset-store/**

acceptanceCriteria:
  - Ny "Variants"-tab i Site Inspector som listar alla compatible variants
    för aktuell sajts scaffold (auto-detekteras via siteId → run → scaffoldId).
  - Varje variant visas som ett kort med (a) namnet, (b) en mini-preview-thumbnail
    som renderar variantens tokens (samma TokenPreview-mönster som TokensTab),
    (c) tone-vibe-chips ("warm", "neighbourhood", etc.).
  - Hover/klick på en variant skickar postMessage-broadcast med alla
    variantens 4 färgtokens till preview-iframe (live switch utan build).
    Använder samma TOKEN_MESSAGE_TYPE-kontrakt som dagens TokensTab.
  - "Använd denna variant" knapp committar via samma follow-up-prompt-pattern
    som dagens variant-picker-dialog ("Byt sajtens design-grund...") så
    briefModel uppdaterar Project Input och nästa rebuild lockar in valet.
  - "Återställ till nuvarande variant"-knapp skickar reset-broadcast så
    preview återgår till sajtens canonical variant utan rebuild.
  - /api/discovery-options returnerar `availableVariants: { id, label,
    tokens: { primary, accent, background, foreground }, tone: { vibe[] } }[]`
    per option — purely additive, befintlig shape oförändrad.
  - `lib/runtime-tokens.ts` exporterar ny `broadcastTokenBundle(tokens)` som
    wrapper kring befintliga `broadcastTokenChange`-anropen — additivt.
  - Inga ändringar i `variant-picker-dialog.tsx` denna sprint (befintlig
    rebuild-flöde fortsätter parallellt; live-switch är komplement).
  - Mobil + tablet-responsivt (Site Inspector öppnas som Sheet/Drawer).
  - Tom-state om sajten har < 2 compatible variants ("Den här scaffolden
    har bara en variant ännu.").

checks:
  - python scripts/sprintvakt_check.py
  - python scripts/governance_validate.py
  - python scripts/rules_sync.py --check
  - python scripts/check_term_coverage.py --strict
  - python -m ruff check .
  - python -m pytest tests/ -q
  - cd apps/viewser && npx tsc --noEmit
  - cd apps/viewser && npm run lint
  # Manuell smoke (på localhost):
  - Öppna Viewser → bygg en restaurant-sajt → öppna Site Inspector
    → Variants-tab → klicka mellan 4 restaurant-variants → preview
    skiftar färgschema utan rebuild → klicka "Använd denna variant"
    → ny build triggas med rätt variantId

collisionRisk: yellow
reviewer: jakob
status: queued
createdAt: 2026-05-25T01:38:00Z
updatedAt: 2026-05-25T01:38:00Z
notes:
  - Yellow pga apps/viewser/lib/runtime-tokens.ts (additive new export only)
    + apps/viewser/app/api/discovery-options/route.ts (additive response shape).
    Båda är read-only mot Jakobs backend (packages/generation/**), ingen
    run-shape eller generator-contract påverkas.
  - postMessage-kontraktet (TOKEN_MESSAGE_TYPE) är låst i
    tests/test_build_media_rendering.py — denna gap utökar broadcast
    från enskilda tokens till bundles men ändrar inte själva message-shapen,
    så testet förblir grönt.
  - Live-switch är best-effort: same-origin local preview = funkar direkt,
    StackBlitz cross-origin = tystlåten degradation. Samma trade-off som
    TokensTab har idag, så ingen ny UX-skuld.
  - Variant-picker-dialog rörs inte. Den behåller sin nuvarande funktion
    (byt hela discovery-category via brief-prompt) och fungerar som
    nästa-steg upptill den nya tabben (kör i nästa sprint om vi vill
    konsolidera).
---

## Implementation outline

### A. API extension (additive)

`apps/viewser/app/api/discovery-options/route.ts`:
- Efter `readJson` av taxonomy + scaffoldContract, läs även variant-filer
  per scaffold: `packages/generation/orchestration/scaffolds/<scaffoldId>/variants/*.json`.
- För varje DiscoveryOption: lägg `availableVariants` med `{id, label,
  tokens: { primary, accent, background, foreground }, tone: { vibe } }`.
- Gracefully ignorera scaffolds utan variants/-dir (returnera `[]`).
- Ingen ändring av befintliga fält → ingen breaking change.

### B. Lib extension (additive)

`apps/viewser/lib/runtime-tokens.ts`:
- Lägg `broadcastTokenBundle(tokens: Record<TokenId, string>)` som kör
  `broadcastTokenChange(id, value)` för varje token.
- Lägg `broadcastTokenReset()` som kör `broadcastTokenChange(id, "reset")`
  för alla 4 tokens.
- Ingen ändring av befintliga exports.

### C. New tab

`apps/viewser/components/builder/inspector/variants-tab.tsx`:
- Tar `siteId`, `currentVariantId`, `onPrompt` som props.
- Fetchar `/api/discovery-options` (eller använder cached data om site-inspector
  redan har det).
- Hittar matchande DiscoveryOption via siteId-routing (samma logik som
  variant-picker-dialog gör idag).
- Renderar lista av variant-kort med TokenPreview-thumbnail per variant.
- Hover/klick → broadcastTokenBundle(variant.tokens).
- "Använd denna variant" → onPrompt med follow-up-prompt template.
- "Återställ" → broadcastTokenReset().

### D. Wire-up

`apps/viewser/components/builder/inspector/site-inspector-sheet.tsx`:
- Lägg `<TabsTrigger value="variants">Variants</TabsTrigger>` mellan
  brief och tokens.
- Lägg `<TabsContent value="variants"><VariantsTab ... /></TabsContent>`.

`apps/viewser/components/builder/inspector/index.ts`:
- Re-exportera `VariantsTab`.

### E. Verification

Viewser has no JS test runner (intentional per repo design — all
runtime tests are Python-side via the canonical-artefacts pipeline).
We verify the additive lib helpers with:

- `npx tsc --noEmit` — strict TypeScript catches API/return-type drift.
- `npm run lint` — ESLint catches dead-code or hook-rule violations.
- Manual UI smoke (see acceptance criteria above).
