# GAP-viewser-pipeline-status-polling

```yaml
id: GAP-viewser-pipeline-status-polling
type: Gap/UI
owner: christopher
title: FloatingChat speglar riktig pipeline-status via trace-endpoint
whyNow: |
  FloatingChat:s build-progress-steg ("Förstår promptens intentioner",
  "Renderar designer", etc.) drivs idag av en hårdkodad setTimeout-kedja
  i floating-chat.tsx (5s, 7s, 14s, 60s). Det betyder att:

    - Operatören ser "klart" innan bygget faktiskt är klart om bygget
      tar < 60s (vanligt för cache hits).
    - Operatören ser "renderar" när bygget egentligen redan landat i
      quality-gate-fasen.
    - Mock-runs och degraded fallbacks får samma fejk-loggar som riktiga
      LLM-builds.

  Trace-endpointen /api/runs/[runId]/trace + pending runs i /api/runs
  finns redan i main (commit 74a355b). Det enda som saknas är att UI
  faktiskt pollar mot den. När det är på plats slipper vi all faking och
  varje step-text kommer från scripts/build_site.py:s trace.ndjson.

  Direkt resultat: operatören ser exakt vad som händer (briefModel kör,
  planningModel kör, codegen kör, repair kör, quality gate kör), och vi
  kan ta bort de hårdkodade tidsetapperna helt.
paths:
  - apps/viewser/components/builder/floating-chat.tsx
  - apps/viewser/components/builder/use-pending-build.ts
  - apps/viewser/components/builder/use-build-trace-polling.ts
doNotTouch:
  - apps/viewser/app/api/runs/**
  - apps/viewser/lib/runs.ts
  - apps/viewser/components/builder/inspector/**
  - apps/viewser/components/discovery-wizard/**
  - packages/generation/**
  - scripts/build_site.py
acceptanceCriteria:
  - "Den hårdkodade FOLLOWUP_BUILD_STEPS-kedjan med setTimeout är borta."
  - "Efter att en build startat pollar UI mot GET /api/runs/[runId]/trace?since=<iso> så fort runId är känt (via pending row från /api/runs eller X-Run-Id-header)."
  - "Step-texten i build-meddelandet uppdateras från trace.ndjson-events (brief.generated, plan.produced, codegen.started, repair.applied, quality.evaluated, build-result.completed)."
  - "När runStatus = ok/degraded/mock visas slutresultatet med rätt variant (success/warning/info)."
  - "Polling stoppar inom 1 sekund efter att build-result landat (final event eller runStatus != pending)."
  - "Backoff: polling sker var 1.5s under första 30s, sedan var 3s — ingen evig 500ms-polling."
  - "Felhantering: 4xx från trace stoppar polling och visar tydligt error-meddelande; 5xx loggas men polling fortsätter med backoff."
  - "Befintlig pendingBuild-state i use-pending-build.ts behålls — bara faking-logiken byts."
checks:
  - python scripts/sprintvakt_check.py
  - python scripts/governance_validate.py
  - python scripts/check_term_coverage.py --strict
  - python -m ruff check .
  - python -m pytest tests/ -q
  - cd apps/viewser && npx tsc --noEmit
  - cd apps/viewser && npm run lint
note: |
  Effort: 4-6h. Direkt prioritet efter scout 2026-05-25 (composer-2.5-fast)
  som identifierade att fejk-loggar är näst-värsta UX-problemet efter
  strukturell homogenitet.
```
