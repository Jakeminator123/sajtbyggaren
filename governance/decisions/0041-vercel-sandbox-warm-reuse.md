# ADR 0041 — Vercel Sandbox preview Tier 2: återanvänd en varm sandbox (opt-in)

**Status:** Accepted
**Datum:** 2026-06-10 (operatörsbeslut, Jakob)
**Beroenden:** ADR 0030 (Preview-Provider Portability), ADR 0033 (Vercel Sandbox
primär preview). Referens:
[`apps/viewser/lib/vercel-sandbox-runner.ts`](../../apps/viewser/lib/vercel-sandbox-runner.ts),
[`docs/spikes/vercel-sandbox-spike.md`](../../docs/spikes/vercel-sandbox-spike.md),
Tier 1 (#263, pre-built upload + `timings`), lärdomen från #156-boten
(`Sandbox.get({ resume: false })`).

## Kontext

Sajtbyggaren förhandsvisar genererade Next.js-sajter i en Vercel Sandbox
(`apps/viewser/lib/vercel-sandbox-runner.ts`). Tier 1 (#263) gav två saker: en
färdigbyggd `.next` laddas upp i stället för att byggas i sandboxen
(`VIEWSER_SANDBOX_UPLOAD_BUILT`), och varje preview-svar bär ett `timings`-objekt
(`createMs/uploadMs/installMs/buildMs/readyMs/totalMs`).

I dag skapas en **ny** sandbox per preview (`Sandbox.create`). Det betyder en
återkommande provisionerings- och install-kostnad (kall `npm install` i ett tomt
`node_modules`) även när en följdversion bara ändrat lite. För kärnflödet
`prompt -> företagshemsida -> preview -> följdprompt -> ny version` är det den
upprepade kostnaden vi vill bort.

## Beslut

Inför en **opt-in** återanvändningsväg i runnern: i stället för att alltid skapa
en ny sandbox försöker vi först återansluta till en redan varm, namngiven sandbox
för samma sajt, laddar upp den aktuella byggets filer och startar om servern.
Den dyra `Sandbox.create` + kall install hoppas då över.

### Livscykel & namngivning

- En varm sandbox har ett **deterministiskt namn per sajt**:
  `sajtbyggaren-preview-<slug(siteId)>` (utan tidsstämpel). Det icke-återanvända
  läget behåller dagens **tidsstämplade, unika** namn
  (`sajtbyggaren-preview-<slug>-<Date.now()>`), så default-beteendet är oförändrat.
- Reconnect sker via `Sandbox.get({ name, resume: false })`.
- **`resume: false` är obligatoriskt** (lärdom från #156-boten). I `@vercel/sandbox`
  v2 är `resume` **default `true`** — ett `Sandbox.get({ name })` utan flaggan
  återstartar en utgången sandbox och rapporterar `pending` i stället för det
  ärliga `stopped`/`aborted`. Tier 2:s reconnect får aldrig återuppliva en
  utgången sandbox tyst.
- En sandbox anses **utgången/oanvändbar** om `Sandbox.get` kastar (finns inte),
  eller om dess `status` inte är `running`. SDK:ns statusenum är
  `aborted | failed | pending | running | stopping | stopped | snapshotting`;
  endast `running` återanvänds. Okänd/oläsbar status behandlas konservativt som
  oanvändbar.
- **Namn-kollisionsstrategi vid fallback** (skiljer på två miss-typer så vi aldrig
  kolliderar med en just-raderad record):
  - Ren miss (`Sandbox.get` kastar not-found): fulla vägen skapar med det
    **deterministiska** namnet — inget finns, ingen kollision, och det
    bootstrappar reuse för nästa cykel.
  - **Funnen men död** (status ≠ `running`): städa best-effort
    (`stop()`/`delete()`) och skapa sedan med det **tidsstämplade** namnet just
    den här cykeln (eliminerar race:t mot en asynkron delete av det
    deterministiska namnet). Nästa cykel bootstrappar det deterministiska namnet
    igen.

### Invalidering (ny sandbox vs bara filuppladdning)

- **Bara filuppladdning + omstart:** källfiler + (pre-built) `.next` laddas upp och
  skriver över. `node_modules` ligger kvar i den varma sandboxen och laddas aldrig
  upp.
- **Säker reconcile-install:** reuse-vägen kör ändå `npm install` i den varma
  sandboxen. På oförändrad lockfile är det en nära-no-op (sekunder) eftersom
  `node_modules` redan är populerat — men det håller previewn korrekt om beroenden
  ändrats. Det dyra (provisionering + kall install i ett tomt `node_modules`) är
  borta. Att hoppa install helt (anta oförändrade beroenden) är medvetet
  **uppskjutet** bakom en framtida beroende-fingerprint.
- **Kräver ny sandbox (full fallback):** ingen varm sandbox hittas, den är inte
  `running`/utgången, eller auth/validering faller. Då körs dagens fulla väg
  (`createSandboxPreview`) oförändrad.
- v1 laddar upp **hela** den insamlade filuppsättningen (overwrite). Äkta
  delta-upload (bara faktiskt ändrade filer) är uppskjutet.

### Kill-switch

- Env: `VIEWSER_SANDBOX_REUSE`. **Opt-in, default AV.** Grind:
  `process.env.VIEWSER_SANDBOX_REUSE === "1"`.
- Detta skiljer sig medvetet från Tier 1:s `VIEWSER_SANDBOX_UPLOAD_BUILT !== "0"`
  (default PÅ): Tier 2 är default AV tills operatören mätt och bekräftat vinsten,
  så den här PR:en ger **noll regression** för dagens flöde (byte-identiskt
  beteende när flaggan är osatt eller `0`).

### Mätbarhet

- `timings`-objektet behålls; ett `reused: boolean`-fält läggs till i det
  (additivt). På återanvändning sätts `reused: true` och `createMs` utelämnas;
  på fulla vägen `reused: false`. Vinsten läses alltså som `reused: true` +
  avsaknad `createMs` + liten `installMs` i preview-svaret.

### Produktroutens livscykel-interaktion (beslut)

Produktrouten (`app/api/preview/[siteId]`) går via DI-wiringen i
`apps/viewser/lib/preview-runtime-server.ts`, som idag anropar
`stopSandboxSessionForSite(siteId)` **före** varje `createSandboxPreview` — det
skulle stoppa just den varma sandbox vi vill återanvända.

**Beslut:** i reuse-läge (`isSandboxReuseEnabled()` sant) **hoppar** DI-wiringen
det stoppet — reuse-vägen äger livscykeln (TTL + best-effort cleanup vid
död/utgången handle). Gaten ligger bakom samma default-AV-flagga, så när reuse
är av är produktrouten **byte-identisk** med idag (stoppar ev. tidigare session
som förr).

`build-runner.ts` lämnas **orört**: dess stop-before-rebuild är kvar. Ett nytt
bygge/följdprompt stoppar alltså den varma sandboxen, vilket i v1 ger en **ärlig
reuse-MISS** (`Sandbox.get` not-found) → full fallback med deterministiskt namn
(bootstrap). Att hålla sandboxen varm tvärs över ett rebuild är en senare nivå.

## Kända begränsningar

- **Overwrite-only upload:** reuse laddar upp den nya versionens filer som
  overwrite men **raderar inte** filer som fanns i en tidigare version i den varma
  sandboxen. `.next` + manifesten skrivs över, så `next start` serverar aldrig en
  borttagen route — men **stale chunks** kan ligga kvar på disk i sandboxen.
  Acceptabelt i v1 (ephemeral sandbox, TTL städar); äkta delta-/synk-upload är
  uppskjutet.
- **Källås, inte live-bevis:** testerna är källås (de bevisar källans *form* —
  `resume: false`, opt-in-grind, status-allowlist, fallback-vägar — inte live
  beteende). Live-mätning av vinsten kräver Vercel-auth och **görs av operatören**
  (samma princip som #263-testerna).

## Konsekvenser

Positiva:

- Följdversioner slipper provisionering + kall install; preview-tiden domineras
  av filuppladdning. Synligt via `reused` + `timings`.
- Opt-in/default-AV ⇒ ingen regression för dagens en-sandbox-per-preview-flöde.
- #156-lärdomen kodifierad: en utgången sandbox återupplivas aldrig tyst.

Negativa / risk:

- Omstart av `next start` i en varm sandbox (best-effort kill + restart) och
  reconcile-install verifieras live av operatören; allt ligger bakom opt-in-flaggan.
- Se även **Kända begränsningar** ovan (overwrite-only upload; källås ≠ live-bevis).

## Referenser

- [ADR 0030 — Preview-Provider Portability](0030-preview-provider-portability.md)
- [ADR 0033 — Vercel Sandbox primär preview](0033-vercel-sandbox-primary-preview.md)
- [`docs/spikes/vercel-sandbox-spike.md`](../../docs/spikes/vercel-sandbox-spike.md)
