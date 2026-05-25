# GAP-viewser-side-by-side-preview

```yaml
id: GAP-viewser-side-by-side-preview
type: Gap/UI
owner: christopher
title: Sida-vid-sida-preview av två genererade versioner i Versions-tab
whyNow: |
  Iteration & Compare landar idag bara på data-nivå (scaffold/variant/routes/
  tone/capabilities). Operatören ser inte VISUELLT hur v3 skiljer sig från
  v5 utan att klicka mellan runs i ConsoleDrawer och hålla skillnaderna i
  huvudet. Två iframer sida vid sida med scroll-sync gör visuell regression
  uppenbar i en blick — kritiskt när vi börjar lova "fantastiska sajter"
  och behöver kunna jämföra olika variant/dossier-kombinationer på samma
  prompt utan att förlora referenspunkten.
paths:
  - apps/viewser/components/builder/inspector/versions-tab.tsx
  - apps/viewser/components/builder/inspector/compare-preview-modal.tsx
  - apps/viewser/components/builder/inspector/site-inspector-sheet.tsx
  - apps/viewser/components/builder/inspector/index.ts
doNotTouch:
  - apps/viewser/app/api/runs/**
  - apps/viewser/app/api/preview/**
  - apps/viewser/components/viewer-panel.tsx
  - apps/viewser/lib/runs.ts
  - packages/generation/**
  - scripts/build_site.py
acceptanceCriteria:
  - "Versions-tab har en 'Visuell jämförelse'-knapp som aktiveras när både A och B är valda och pekar på olika runIds med tillgängliga files."
  - "Klick öppnar en full-screen modal med två StackBlitz-iframer sida vid sida (50/50 grid på desktop, stackad på mobil)."
  - "Varje iframe har en pill med versionsnummer + runId och en 'Öppna i nytt fönster'-knapp."
  - "Browser-detection: Safari/Firefox visar fallback-kort med 'Öppna båda i nya fönster' istället för embeddade iframer."
  - "Cancellation: ESC eller stängningsknapp avmonterar båda iframerna och rensar StackBlitz embed-state utan att lämna stale DOM."
  - "Loading-states: båda iframerna har egen 0-100% loading-indikator; modalen blockerar inte UI medan iframerna bootar."
  - "Inga ändringar i existerande viewer-panel.tsx (vi extraherar embed-helper till delad fil om vi måste återanvända)."
  - "Inga nya backend-endpoints — återanvänd /api/runs/[runId]/files som redan returnerar alla filer för en historisk run."
checks:
  - python scripts/sprintvakt_check.py
  - python scripts/governance_validate.py
  - python scripts/check_term_coverage.py --strict
  - python -m ruff check .
  - python -m pytest tests/ -q
  - cd apps/viewser && npx tsc --noEmit
  - cd apps/viewser && npm run lint
collisionRisk: green
reviewer: jakob
status: queued
createdAt: 2026-05-25T04:50:00Z
updatedAt: 2026-05-25T04:50:00Z
notes:
  - "Två StackBlitz-instanser ~ 2× boot-tid första gången (~120s i värsta fall) men dubbla WebContainers körs OK i Chromium på modern hårdvara. Ingen serverlast tillkommer."
  - "Scroll-sync är ett stretch-mål — låt vara enkel toggle i V1, primärfeaturen är att se båda samtidigt."
  - "Path B (GAP-backend-path-b-section-renderer) ger sida-vid-sida MAX värde genom att låta operatören jämföra strukturellt olika scaffolds — den featuren är dock oberoende och låser inte denna."
```

## Bakgrund

Versions-tab har idag två jämförelse-funktioner:

1. **Data-diff** (`run-diff.ts`) — visar scaffold/variant/starter/routes/tone/capabilities/quality som strukturerad diff. Bra för "förstod motorn vad jag ville?".
2. **Iterera från denna** — sätter `baseRunId` så följdprompt utgår från en historisk version.

Men ingen av dem visar **hur sajterna ser ut** parallellt. Operatören klickar mellan runs i ConsoleDrawer och håller skillnaderna i huvudet. Det fungerar inte när vi vill jämföra subtila variant-byten (`warm-craft` vs `family-warmth`) eller olika sub-dossier-kompositioner på samma scaffold.

## Tekniska val

### Varför StackBlitz, inte lokalt-preview-pathen

`/api/preview/<siteId>` startar `next start` mot `.generated/<siteId>/` på disk — den mappen innehåller alltid **senaste** bygget för en site. För att visa v3 + v5 av samma site samtidigt krävs antingen:

- En ny `/api/preview/run/<runId>` som extraherar `data/runs/<runId>/files` till tmpdir och spawnar en port per runId. Backend-arbete, ~6h, kräver port-pool-utvidgning.
- StackBlitz-pathen, som redan returnerar files-payload per runId och kör allt klient-side. ~3h.

Vi väljer StackBlitz-pathen för V1. Om iteration visar att 2× WebContainer-boot är för långsamt kan vi senare lägga till den per-runId-preview-server som backend-feature (egen GAP).

### Browser-stöd

Samma matris som dagens ViewerPanel:

| Browser | Embedded preview | Fallback |
|---|---|---|
| Chrome / Edge / Brave / Opera | ✅ båda iframerna embeddade | n/a |
| Safari (desktop + iOS) | ❌ saknar credentialless | "Öppna båda i nya fönster" |
| Firefox | ❌ embed-stöd saknas | "Öppna båda i nya fönster" |

Två top-level-tabs på stackblitz.com fungerar i alla browsers eftersom det inte är embeddat — fallback-användaren får visserligen lämna Sajtbyggaren-fliken men ser fortfarande sajterna.

## Out-of-scope

- Scroll-sync mellan iframer (V2)
- Diff-overlay (visuell pixel-diff) — kräver headless screenshot-pipeline (eget GAP, backend)
- Per-runId preview-server (eget GAP, backend)
- Path B (`GAP-backend-path-b-section-renderer`) — separat och oberoende; låser upp jämförelse av strukturellt olika scaffolds men är inte en förutsättning här.
