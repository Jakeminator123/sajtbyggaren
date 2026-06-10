# ADR 0048 — Hostad byggväg: python-pipen körs i en vercel-sandbox med blob-output

**Status:** Accepted
**Datum:** 2026-06-10 (operatörsbeslut, Jakob)
**Beroenden:** ADR 0030 (preview-provider-portability), ADR 0033 (vercel-sandbox
primär preview). Stänger G1 och artefaktdelen av G2 i
[`docs/vercel-sandbox-migration/01-arkitekturval.md`](../../docs/vercel-sandbox-migration/01-arkitekturval.md).
Referens: [`apps/viewser/lib/hosted-build-runner.ts`](../../apps/viewser/lib/hosted-build-runner.ts),
[`docs/vercel-sandbox-migration/p2-hosted-build-implementation.md`](../../docs/vercel-sandbox-migration/p2-hosted-build-implementation.md).

## Kontext

Hostad viewser kan visa UI och förhandsvisa redan byggda sajter, men bygget
kräver lokal python + lokal disk (`isHostedVercelRuntime` ->
`hostedPythonRuntimeUnavailable`, 501). Målet (migrationsplanens P2) är att en
användarsajt ska kunna byggas hostat utan operatörens maskin.

## Alternativ

- A. Kör python-byggaren oförändrad i en sandbox; skriv artefakter till blob.
- B. Slå ihop bygg och preview i samma sandbox.
- C. Porta byggaren till node.

## Beslut

Alternativ A. Den deterministiska python-pipen
(`scripts/prompt_to_project_input.py` + `scripts/build_site.py` +
`packages/generation/`) körs oförändrad i en vercel-sandbox (runtime `node24`,
som har `python3`). Minst omskrivning, och bygg-pipen förblir
leverantörsneutral: sandboxen är bara en exekveringsyta.

- Build-kontexten (scripts/, packages/, governance/, data/starters/,
  requirements.txt) laddas upp som tar.gz till blob av ett operatörs-CLI
  (`apps/viewser/scripts/upload-build-context-to-blob.mjs`); sandboxen skapas
  med `source: { type: "tarball" }` från den.
- Orkestreringen körs detached — http-requesten väntar aldrig in bygget.
  Sandbox-TTL (15 min) är kostnadstaket; ett hängt bygge läcker aldrig.
- Bygg-output publiceras fil för fil till blob under
  `generated/<siteId>/<relPath>` — exakt det layout
  `lib/generated-blob-source.ts` redan läser, så befintlig hostad
  sandbox-preview fungerar direkt på resultatet.
- Run-status och den hostade `current.json`-motsvarigheten skrivs till
  kv-store (ADR 0049); klienter pollar `GET /api/hosted-build/<runId>`.
- Vägen är bakom `VIEWSER_ENABLE_HOSTED_BUILD=1` — utan flaggan degraderar
  `/api/prompt` hostat ärligt som tidigare.

## Termer

Beslutet introducerar två canonical termer, registrerade i
naming-dictionary v34: hosted-build (den hostade byggvägen ovan) och
build-context (pipens minimala filuppsättning som tar.gz i blob,
uppladdad av operatörs-CLI:t; måste laddas om när pipen ändras).

## Konsekvenser

- Plus: ingen omskrivning av genereringspipen; lokal väg helt oförändrad;
  kostnadstak per bygge via sandbox-TTL; preview-kedjan återanvänds.
- Minus: kallstart (pip + npm install + next build) gör hostade byggen
  långsammare än lokala; följdprompter hostat kräver persisterad run-historik
  (P3) och failar ärligt tills dess; B (bygg+preview i samma sandbox) och
  snapshots (G5) är kvar som senare optimeringar.
