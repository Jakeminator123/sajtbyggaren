---
id: GAP-viewser-iteration-compare
type: Gap/UI
owner: christopher
title: Iteration & Compare — site-scoped versionshistorik + diff-vy i Site Inspector
whyNow: |
  Loopen "prompt → preview → följdprompt → ny version" är i hjärtat av
  Sajtbyggarens värdeerbjudande, men idag är versionshistoriken gömd i
  ConsoleDrawer som visar runs över ALLA sajter, utan filter på aktuell
  sajt och utan möjlighet att jämföra två versioner. Operatören kan
  inte se "vad ändrades när jag skickade följdprompten 'gör hero blå'?"
  utan att manuellt jämföra artefakter i två run-katalogen — ett
  rationalitetshål mitt i kärnloopen.

  Front 3 stänger hålet genom att lägga in en site-scoped Versions-tab
  i Site Inspector (samma yta operatören redan använder för
  brief/plan/tokens/variants), där hen ser CHRONOLOGISK historik per
  sajt + kan markera två runs för diff-vy som visar exakt vad som
  ändrades (route-additions, route-removals, scaffold/variant-byte,
  tone-tags-byte, capability-diff, quality-status-före/efter).

  Inga backend-ändringar — vi läser befintliga `/api/runs` + per-run
  `/api/runs/[runId]/artifacts` och diff:ar på klient-sidan. Detta är
  100% alignment-säkert eftersom UI:t INTE skickar ny information till
  backend, bara konsumerar redan persisterad data.

paths:
  # Primary (Christopher reserved — components/**):
  - apps/viewser/components/builder/inspector/versions-tab.tsx
  - apps/viewser/components/builder/inspector/run-diff.ts
  - apps/viewser/components/builder/inspector/site-inspector-sheet.tsx
  - apps/viewser/components/builder/inspector/index.ts

doNotTouch:
  # Backend-ägt (Jakob jakob-be):
  - packages/generation/**
  - governance/policies/**
  - scripts/**
  - tests/test_*.py
  # API-routes är yellow collision-risk; vi konsumerar bara, ändrar inte:
  - apps/viewser/app/api/runs/route.ts
  - apps/viewser/app/api/runs/[runId]/artifacts/route.ts
  - apps/viewser/lib/runs.ts
  # Andra inspector-tabs (utanför scope):
  - apps/viewser/components/builder/inspector/brief-tab.tsx
  - apps/viewser/components/builder/inspector/pages-tab.tsx
  - apps/viewser/components/builder/inspector/dossiers-tab.tsx
  - apps/viewser/components/builder/inspector/tokens-tab.tsx
  - apps/viewser/components/builder/inspector/variants-tab.tsx
  - apps/viewser/components/builder/inspector/quality-tab.tsx

acceptanceCriteria:
  - Site Inspector har en ny "Versioner"-tab som listar runs filtrerade
    på aktuell siteId (klient-sidig filter på /api/runs-resultatet).
  - Varje run-rad visar: relativ tidsstämpel, version (om finns),
    build-status (dot-färg), och rationale/prompt-excerpt (från
    site-brief.json eller build-result.json codegen.rationale).
  - Aktuell run är markerad som "Du tittar på den här" (highlighted +
    badge).
  - Operatören kan markera två runs (radio-style A/B) för att triggera
    en compare-vy som visar diff av:
      * scaffoldId/variantId/starterId (före → efter, mono-format)
      * routes (added/removed lists)
      * tone-tags / requestedCapabilities (added/removed)
      * quality-status (före → efter med tone-badge)
  - Diff-vy:n laddar artefakter via befintliga
    /api/runs/[runId]/artifacts endpoints, helt klient-sidigt — INGEN
    ny backend-endpoint behövs.
  - "Jämför" är clear visual reset (knapp som rensar A/B-val).
  - Empty-states: "Inga andra versioner än" när bara 1 run, "Välj två
    versioner för att jämföra" när 0-1 är markerade.
  - run-diff.ts innehåller pure diff-funktioner (computeRunDiff(a, b))
    som är fristående testbara och deterministiska.
  - Inga ändringar i backend-API:er, inga ändringar i runs.ts, inga
    nya schemafält. Allt är UI-rendering av befintlig data.

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
createdAt: 2026-05-25T01:57:00Z
updatedAt: 2026-05-25T01:57:00Z
notes:
  - Pure UI-feature. Konsumerar befintliga API:er (/api/runs +
    /api/runs/[runId]/artifacts) read-only. Inga ändringar i lib/runs.ts,
    inga schema-ändringar, inga nya endpoints.
  - Diff-logiken lever i en pure typescript-fil (run-diff.ts) utan
    React-dependencies — kan testas isolerat och återanvändas senare
    om vi vill bygga en "show diff before publishing"-knapp i bygg-
    flödet.
  - Site-filter görs klient-sidigt på /api/runs-resultatet eftersom
    backend redan returnerar siteId per run. Att lägga till en
    `?siteId=X`-query-param skulle vara en backend-ändring och bryta
    branch-scope-ui-ux.md.
  - Followup-loop ÄR redan implementerad via FloatingChat +
    useFollowupBuild + dialogs — denna gap kompletterar den med
    historisk vy + diff. Vi ändrar INTE follow-up-flödet.
---

## Implementation outline

### A. run-diff.ts (pure logic)

Exporterar:

- `computeRunDiff(a: RunArtefactBundle, b: RunArtefactBundle): RunDiff`
- `RunDiff` shape: `{ scaffoldChange, variantChange, starterChange,
   routesAdded[], routesRemoved[], toneAdded[], toneRemoved[],
   capabilitiesAdded[], capabilitiesRemoved[], qualityBefore, qualityAfter,
   statusChange }`
- `formatDiffSummary(diff): string` — en kort prosa-sammanfattning
  som passar i ett rad-element ("Routes: +1 −0, Variant: A → B").

Implementation: pure set-diff på arrays, plain string-compare på
scaffoldId/variantId/starterId. Helt deterministisk → enkelt att
testa med fixture-data.

### B. versions-tab.tsx

Komponent som:

1. Fetch:ar `/api/runs` en gång vid mount.
2. Filtrerar på `runs[].siteId === currentSiteId`.
3. Renderar lista med run-cards (timestamp, version, status-dot,
   rationale-excerpt).
4. Radio-state: `compareA: string | null`, `compareB: string | null`.
5. När båda satta: fetcher artefakter för båda runs och anropar
   `computeRunDiff` + renderar compare-vyn.

UX:
- Aktuell run (props.runId) får "Aktiv"-badge.
- Hover på rad visar "Markera som A" / "Markera som B".
- Sticky compare-knapp högst upp efter båda valts.

### C. site-inspector-sheet.tsx integration

Lägg `<TabsTrigger value="versions">Versioner</TabsTrigger>` och
`<TabsContent value="versions"><VersionsTab {...} /></TabsContent>`
mellan Variants och Färger (eller mellan Färger och Kvalitet).

### D. index.ts re-export

Lägg `export { VersionsTab } from "./versions-tab"`.

### E. Verification

- Pure diff-logiken testas inline via TypeScript-typer (compiler
  fångar shape-drift).
- Hela tab-flödet testas manuellt: bygga 2 runs, växla siteInspector,
  öppna Versioner, välja två, se diff.
- Befintliga pytest-tester (inkl. wizard-payload + run-artefakter)
  förblir oberörda.
