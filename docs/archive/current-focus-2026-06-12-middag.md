# Arkiv: current-focus-block 2026-06-12 ~12:00 (middagspasset, ADR 0055 + #308–#311)

Flyttat hit från `docs/current-focus.md` när eftermiddagens avslutningsrunda
(#312/#313 mergade, main-sync för produktionstest) tog över som aktuellt block.

## Status nu (2026-06-12 ~12:00 — hostad preview-standardisering, ADR 0055)

**Git:** `main = jakob-be` (rent träd, local == origin). Förmiddagspasset är
landat direkt på `jakob-be` på operatörsmandat (Jakob ~11:00) och synkat till
`main`. Production deployar från `main`. **Tarball-omladdning KRÄVS efter
main-mergen** (passet rör `packages/preview-runtime/` + `governance/`) —
gjord i avslutningen, verifiera KV-URL:en vid tvivel.

**Landat i förmiddagspasset (operatörsbeslut: Vercel Sandbox + Blob är
STANDARD för användarpreviews; StackBlitz förblir pausad, ej avvecklad):**

- **Docs-sanering:** föråldrade B194-/run-historik-påståenden rättade
  (deploy-guide, prompt-JSDoc, `.env.example`, `preview-runtime.md`,
  rättelsenot i ADR 0033).
- **Preview-refresh-gate:** followups med visibleEffect `none`/`registered`
  river inte preview-sandboxen — `previewRunId` skiljs från `selectedRunId`
  i studio-sidan; FloatingChat trådar signalen via delade
  `readFollowupVisibleEffect`. Lås: `tests/test_viewser_preview_refresh_gate.py`.
- **Byggstart stoppar previewn:** `startHostedBuild` stoppar
  preview-sessionen före `Sandbox.create` (paritet med lokala build-runner;
  best-effort).
- **Pre-built hostat (ADR 0055):** bygget laddar upp `.next` (minus
  cache/trace) till blob; preview-sandboxen kör `npm install --omit=dev` +
  `next start`, ärlig fallback utan komplett `.next`.
- **Default-flippen:** tomt `VIEWSER_PREVIEW_MODE` = `vercel-sandbox`
  (registry, policy v4, next.config, dev.mjs, viewer-panel; `.env.example`-
  mallen sätter `local-next` explicit för lokal dev).
- **Reuse i prod:** sessions-snabbväg med buildId-invalidering mot
  `viewser:site:<siteId>:current` + liveness-probe; `VIEWSER_SANDBOX_REUSE=1`
  satt i Vercel (Production+Development; Preview-miljön blockerades av en
  CLI-bugg — sätt manuellt i dashboarden vid behov).

**Tillägg ~13:30 (hotfix-pass efter prod-E2E-incidentutredningen):** tre
fixar direkt på `jakob-be` + ff `main` (operatörsmandat): (1) hostad
preview-POST snabbare — blob-filerna laddas nu ner med begränsad samtidighet
(16 parallella, `downloadBlobEntries` i `generated-blob-source.ts`; vakter
och fel-semantik oförändrade, enhetstester utökade); (2) ärlig submit-gate i
FloatingChat — de tysta early-returns loggar nu `console.warn` med vilken
vakt som stoppade, upptagen-läget visar statusrads-hint och saknad siteId ger
ärligt fel i chatten (vakterna är oförändrade i styrka); (3) lyckad
sandbox-preview-start loggar EN server-side JSON-rad med fas-timings +
prebuilt/reused-flaggor i `vercel-sandbox-runner.ts`. Plus deploy-fix:
`ignoreCommand` i `apps/viewser/vercel.json` är nu fail-open när
`VERCEL_GIT_PREVIOUS_SHA` saknas i den grunda klonen (gav "fatal: bad
object" + deploy-ERROR på första hotfix-pushen).

**Nästa 3 prioriteringar (som de stod):**

1. **E2E-verifiera hela standardvägen i produktion** på `/studio`: init →
   preview (pre-built, kolla `timings`) → no-op-följdprompt (previewn ska
   INTE rivas) → edit-följdprompt (ny version → invalidering → ny sandbox)
   → re-POST (reused:true). Även B199 v2/#307-flödet från morgonpasset.
2. **B197 (Christophers, pågår):** `hosted-build-runner.ts` +
   `vercel-sandbox-runner.ts` ändrade IGEN — tidig rebase krävs
   (msg-0085).
3. **Uppföljningar:** blob-/KV-prune (mer angeläget nu — `.next` i
   `generated/`), `changeSet` hostat, Preview-miljöns reuse-flagga,
   Safari/Firefox-E2E för B125-stängning.

**Öppna blockers:** inga hårda.

Last verified state (som den stod): `f642b1a5` (2026-06-12 ~14:10 UTC+2;
squash-merge av #311 — feat(viewser) Projektinnehåll-panel, deriverad
sammansättningsbild av sajt-projektet i ConsoleDrawer — ovanpå hotfix-passets
`3150b471`. Review-dom GO, alla 6 checkar gröna på PR-head efter
ready-flippen, MERGEABLE/CLEAN, `main` ff:ad till samma SHA.
Tarball-omladdningen GJORD direkt efter mergen (#311 rörde
`scripts/check_term_coverage.py`): build-kontexten ompaketerad från
merge-commiten och uppladdad till blob `build-context/current.tar.gz`,
KV-nyckeln `viewser:build-context:url` uppdaterad. Föregående checkpoint
`9671de59` (#310-mergen + hotfix-passet ~13:30) är historik.)

PR-läget som det stod: #306, #307, #308, #309, #310 och #311 squash-mergade
till `jakob-be` och ff:ade till `main`.
