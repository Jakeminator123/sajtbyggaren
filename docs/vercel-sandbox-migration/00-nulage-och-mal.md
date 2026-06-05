# Nuläge och mål

## Nuläge (dagens arkitektur)
Operatörsappen `apps/viewser` (Next.js) kör lokalt och driver hela loopen:

1. `/api/prompt` (localhost-låst via `assertLocalhost`) tar en prompt, kör
   `scripts/prompt_to_project_input.py` (fas 1) och sedan `scripts/build_site.py`
   via `apps/viewser/lib/build-runner.ts` (fas 2). Bygget skrivs till lokal disk
   under `../sajtbyggaren-output/.generated/<siteId>/builds/<buildId>/` med en
   `current.json`-pekare.
2. `/api/preview/[siteId]` (localhost-låst) resolvar runtime via
   `currentViewserRuntime`. I vercel-sandbox-läge laddar
   `apps/viewser/lib/vercel-sandbox-runner.ts` upp den aktiva builden till en
   sandbox, kör `npm install` + `next build` + `next start`, och returnerar en
   publik vercel.run-URL. Sessionen (siteId till sandbox-id) hålls i minnet i
   `apps/viewser/lib/vercel-sandbox-sessions.ts`.
3. `ViewerPanel` iframe:ar URL:en; `FloatingChat` ligger ovanpå och skickar
   följdprompter till `/api/prompt` (läge followup).

Detta är live-bevisat lokalt (se `docs/handoff.md`). Men allt hänger på en lokal
maskin med Python, repot, och en OIDC-token i `apps/viewser/.env.vercel.local`.

## Varför det inte "bara funkar" hostat
- Localhost-lås: `/api/prompt` och `/api/preview/[siteId]` returnerar fel utanför
  localhost.
- Python-beroende: byggorkestreringen är Python och shellar ut lokalt; hostad
  serverless-Node har ingen Python (koden degraderar via `isHostedVercelRuntime`
  -> `hostedPythonRuntimeUnavailable`).
- Lokal disk: genererade sajter och `current.json` ligger på lokal disk; hostad
  serverless har ingen beständig disk, och sandboxar är efemära.
- Minnesbaserade sessioner: sandbox-registret tappas vid varje kallstart och per
  instans.
- Ingen auth eller tenant: dagens skydd är localhost; en hostad multi-användar-
  produkt behöver riktig auth och isolering per användare.

## Mål (v0- eller Lovable-likt, hostat)
En inloggad användare på en hostad URL:
1. Skriver en prompt -> en företagssajt genereras.
2. Sajten startar i en sandbox och visas i en iframe (eller en modernare
   motsvarighet) med en chatt för följdfrågor.
3. Följdprompter bygger om -> previewen uppdateras till ny version.
4. Versionshistorik, delbara länkar, och snabb uppstart (snapshots eller warm-pool).

## Gap-lista (det här ska faserna stänga)
- G1 Byggorkestrering bort från lokal Python (kör i sandbox eller egen worker).
- G2 Beständig lagring av genererade sajter och pekare (blob plus en liten databas).
- G3 Durabelt sandbox-sessionsregister (databas i stället för minne).
- G4 Auth och tenant-isolering (ersätt `assertLocalhost`).
- G5 Snabb preview-uppstart (snapshots, warm-pool, återanvändning).
- G6 Modern preview-yta (streaming-loggar, element-inspektor, delning).
- G7 Kostnads- och livscykelstyrning (idle-stop, ttl, kvoter, observability).
- G8 De två kvarvarande buggarna (A pending-robusthet, B riktig layout-codegen).
