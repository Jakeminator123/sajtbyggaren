---
id: GAP-viewser-live-build-sync
type: Gap/UI
owner: christopher
title: Live Build Sync — optimistisk pending-version + bättre koordination mellan FloatingChat och Versions-tab
whyNow: |
  Efter Front 1–3 har Viewser nu (a) FloatingChat med follow-up-prompts,
  (b) Variants-tab med live-preview-switching, och (c) Versions-tab med
  A/B-diff per siteId. Men de tre ytorna pratar inte med varandra.

  När operatören skickar en follow-up från FloatingChat händer ingenting
  synligt i Versions-tab förrän bygget är 100% klart. Det skapar
  "är det stuck?"-känsla mellan klick och resultat — exakt motsatsen
  till hur Lovable och liknande verktyg känns levande.

  Live Build Sync täpper den glipan med pure UI-koordination utan att
  röra backend:

  * En optimistisk "Bygger version N…"-rad dyker upp i Versions-tab så
    fort `useFollowupBuild` triggas, så operatören ser direkt att en
    ny version är på väg.
  * När bygget är klart byts den optimistiska raden ut mot den riktiga
    runId-raden (med samma scrollposition, ingen flicker).
  * Versions-tab auto-scrollar till topp + highlightar den nya raden
    så operatören får visuell bekräftelse på att deras prompt landade.
  * "Iterera från denna"-knapp på varje run-rad öppnar chat-rutan
    med kontext-prefix "Utgå från version N: …" (UI-only workaround —
    full base-run-id-support kräver backend-gap, se
    GAP-backend-build-trace-endpoint.md).

  Allt sker via shared state lyfts till `page.tsx` (där `isBuilding`
  redan bor). Inga nya API-endpoints krävs; vi konsumerar befintliga
  callbacks (`onBuildStart`/`onBuildDone`/`onBuildEnd`).

paths:
  # Primary (christopher-reserved — apps/viewser/**):
  - apps/viewser/app/page.tsx
  - apps/viewser/components/builder/builder-shell.tsx
  - apps/viewser/components/builder/inspector/versions-tab.tsx
  - apps/viewser/components/builder/inspector/site-inspector-sheet.tsx
  # Ev. ny shared hook eller context:
  - apps/viewser/components/builder/use-pending-build.ts
  # Nota: ev. nya UI-symboler får vid behov en separat
  # [scope-leak] chore-commit som lägger till dem i
  # scripts/check_term_coverage.py — samma mönster som Variants-
  # och Versions-tab-commits ovanför.

doNotTouch:
  # API-shape = Jakob-ägt
  - apps/viewser/app/api/runs/route.ts
  - apps/viewser/app/api/runs/[runId]/artifacts/route.ts
  - apps/viewser/app/api/prompt/route.ts
  - apps/viewser/lib/runs.ts
  - apps/viewser/lib/build-runner.ts
  - apps/viewser/lib/prompt-runner.ts
  # FloatingChat-INNANMÄTET rörs INTE (1481 rader, högrisk).
  # Bara dess externa callbacks och nya pending-build-state runt den.
  - apps/viewser/components/builder/floating-chat.tsx
  # Wizard-domänen är klar — inte i scope:
  - apps/viewser/components/discovery-wizard/**
  # Backend
  - packages/generation/**
  - governance/policies/**
  - scripts/build_site.py
  - scripts/prompt_to_project_input.py
  - scripts/sprintvakt_check.py
  - tests/test_*.py

acceptanceCriteria:
  # Optimistic pending-version (B):
  - "När operatören skickar en follow-up (från FloatingChat eller
    någon av dialogerna) visas en optimistisk pending-rad högst upp
    i Versions-tab inom 100 ms efter klick. Raden har: status-dot
    (pulsande gul), label 'Bygger version N…', timestamp ('nu'), och
    den prompt-snippet operatören skrev (max 60 tecken)."
  - "Pending-raden är read-only — operatören kan inte klicka den för
    A/B-jämförelse eller iteration."
  - "Pending-raden byts ut mot den riktiga runId-raden inom samma
    fetch-cykel som triggar VersionsTab-refresh (när isBuilding
    true→false). Ingen visuell flicker — vi ersätter listan atomärt."
  # State-handoff (C):
  - "isBuilding/pendingBuild-state lyfts till page.tsx (eller en
    delad context) och skickas ner till builder-shell ->
    site-inspector-sheet -> versions-tab så alla tre ytor ser samma
    pending-tillstånd."
  - "Om bygget misslyckas (onBuildEnd utan onBuildDone), tas
    pending-raden bort med en kort 'Bygget misslyckades'-toast
    (eller in-row state). Ingen orphan pending-rad får ligga kvar."
  # Iterera från version N (delvis):
  - "Varje run-rad i versions-tab har en ny 'Iterera från denna'-knapp
    (ikon: git-branch eller liknande) som vid klick (a) stänger
    site-inspector, (b) öppnar chat-rutan (eller fokuserar input
    om redan öppen), och (c) prefyller composer-input med
    'Utgå från version N: '. Operatören kan sedan skriva sin
    follow-up och skicka."
  - "Knappen är synligt deaktiverad när raden är current run (eftersom
    'iterera från senaste' är default-beteendet utan prefix)."
  - "Workaround: prefixet 'Utgå från version N: ' når backend som ren
    prompt-text. Backend följer fortfarande siteId och senaste
    Project Input — full baseRunId-support kräver
    GAP-backend-build-trace-endpoint.md."
  # Generella:
  - "Inga ändringar i /api/prompt-, /api/runs- eller artifacts-API-shape."
  - "Inga ändringar i lib/runs.ts, lib/build-runner.ts eller
    lib/prompt-runner.ts."
  - "Inga ändringar i floating-chat.tsx interna logik (props/callbacks
    förblir samma; bara hur föräldern routar pending-state)."
  - "Befintlig A/B-diff-funktion + RadioButton-beteende oförändrat."
  - "Befintliga pytest-tester + viewser tsc + viewser lint förblir gröna."

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
createdAt: 2026-05-25T02:35:00Z
updatedAt: 2026-05-25T02:35:00Z
notes:
  - Pure UI-feature byggd ovanpå befintliga callbacks.
    Inga nya API-endpoints, inga backend-ändringar.
  - "Iterera från version N" är medvetet en delprestation. Full
    semantisk iteration (faktisk Project Input-snapshot från run N)
    kräver baseRunId i /api/prompt — spec:as i
    GAP-backend-build-trace-endpoint.md för Jakob.
  - Sub-agent-bug-hunt körs efter implementation och före push.
---

## Implementation outline

### A. Shared pending-build-state

Ny hook `use-pending-build.ts` eller ren state-lyft i `page.tsx`. Bär
information som blir tillgänglig för Versions-tab medan bygget pågår:

Type-shape för pending-build (preliminärt — slutgiltigt namn vid
implementation):

- `siteId: string` — vilken sajt som byggs
- `promptSnippet: string` — max 60 tecken av operatörens prompt
- `startedAt: number` — `Date.now()` när bygget startades
- `estimatedVersion: number` — föregående version + 1

`page.tsx` exponerar pending-tillståndet (null eller objektet) + setter.
`builder-shell.tsx` propagerar ner. `use-followup-build.ts` /
`floating-chat.tsx` anropar `onBuildStart(siteId, promptSnippet)`
(utvidgad signatur) — alternativt en ny separat callback
`onPendingBuild(meta)` så vi inte rör `useFollowupBuild`-API:n om
vi vill hålla scope strikt.

### B. Versions-tab pending-row

En ny presentation-komponent (preliminärt namn `pending-run-row`) som
renderas överst i listan när `pendingBuild?.siteId === siteId`.
Pulserande gul status-dot, "Bygger…"-label. Tar inte emot klick
(cursor: default, ingen radio-button).

### C. Versions-tab post-build auto-highlight

När `wasBuildingRef` flippar från true → false:
1. Refresh `/api/runs` (redan implementerat).
2. Hitta den nya runId i listan (jämför med tidigare lista).
3. Auto-scrolla till topp + applicera en `data-just-built` attribut för
   1.5s, som via CSS triggar en subtle fade-in highlight.

### D. "Iterera från denna"-knapp

Lägg till en tredje knapp på run-raden (utöver A/B-radio): en liten
ikon-knapp (`git-branch` från lucide-react) som öppnar chat-rutan
med ett prompt-prefix.

`site-inspector-sheet.tsx` förmedlar callback upp till
`builder-shell.tsx`. Builder-shell stänger inspector och triggar
en ny callback som föräldern delegerar till `floating-chat.tsx` via
en `defaultPrompt`-prop ELLER via en imperativ ref. Om
floating-chat-API:n kräver ändring för det, parkera delen — vi kan
istället visa "Iterera från version N"-knappen som
**copy-to-clipboard + öppna chat** som workaround utan att röra
`floating-chat.tsx`.

### E. Bug-hunt (sub-agent composer-2.5-fast)

Innan commit, kör sub-agent på:
- Race conditions mellan pending-row insert och VersionsTab refresh.
- Pending-row stale state om operatören byter siteId mid-build.
- Build-fail-path som lämnar pending-row orphan.
- A/B-radio + iterate-knapp keyboard-navigation och focus-management.
- React 19-purity: ingen `setState` i render, ingen sync-effect-setState.

### F. Verification

Manual:
1. Öppna en byggd sajt, öppna Site Inspector → Versioner-tab.
2. Skicka en follow-up från FloatingChat.
3. Verifiera att pending-rad dyker upp inom 100 ms.
4. Vänta tills bygget klart; verifiera atomisk swap till riktig run.
5. Verifiera highlight + scroll på den nya raden.
6. Klicka "Iterera från denna" på en äldre run; verifiera att
   FloatingChat öppnas/fokuseras med rätt prefix.
7. Manuell fail-test: stoppa Next-servern mitt i bygget; verifiera
   att pending-rad försvinner snyggt.

Quality guards: alla i `checks:` ovan ska vara gröna.
